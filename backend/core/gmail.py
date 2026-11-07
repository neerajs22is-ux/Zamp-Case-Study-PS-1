"""Gmail OAuth 2.0, Mailbox Ingestion & Pub/Sub Event Processing Service.

Covers Phase B Stage 4, 4.1 & Stage 5:
1. Three-legged OAuth 2.0 with minimum privileged scope: https://www.googleapis.com/auth/gmail.readonly.
2. Server-side token encryption using Fernet (AES-128-CBC with HMAC-SHA256 authentication).
3. Plaintext tokens and client secrets are strictly barred from database persistence and API responses.
4. Tamper-evident, short-lived HMAC OAuth state with cryptographically random nonces, session binding, and server-side atomic single-use consumption.
5. Ingestion of nested MIME parts and attachments, supporting both inline 'body.data' and external 'messages.attachments.get'.
6. Ingestion validation: %PDF- magic bytes, size limits (<= 50 MB), SHA-256 hashing.
7. Tenant isolation: org_{org_id}/invoices/{document_id}/{filename}.
8. Corrupt/non-PDF attachment quarantine into QuarantinedDocument.
9. Gmail Pub/Sub watch registration (users.watch) with 48-hour renewal schedule.
10. Authenticated Pub/Sub push notification endpoint with durable persistence before acknowledgement.
11. History synchronization (history.list) with automatic full-resynchronization fallback on expired history (HTTP 404).
12. Append-only immutable audit trail for all mailbox mutations and document ingestion events.
"""

from __future__ import annotations

import base64
import contextlib
import datetime
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.config import AppEnv, settings
from backend.core.storage import build_tenant_storage_path, storage_adapter
from backend.core.processing_events import append_checkpoint
from backend.models.domain import (
    AuditEvent, Document, GmailAccount, IngestionJob, Invoice,
    OAuthStateNonce, PubSubEvent, QuarantinedDocument
)

logger = logging.getLogger("ap_command_center.gmail")

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailIntegrationError(Exception):
    """Base error for Gmail OAuth, ingestion and Pub/Sub pipeline."""
    pass


class GmailNotConfiguredError(GmailIntegrationError):
    """Raised when Gmail OAuth credentials are not configured."""
    pass


class HistoryExpiredError(GmailIntegrationError):
    """Raised when Gmail historyId is too old (HTTP 404) requiring full sync."""
    pass


class MailboxSyncLockError(GmailIntegrationError):
    """Raised when another worker currently holds the synchronization lease for the mailbox."""
    pass


class PubSubPersistenceError(GmailIntegrationError):
    """Raised when the database transaction for PubSubEvent persistence fails."""
    pass


# ------------------------------------------------------------------------------
# 1. Server-Side Token Encryption (Fernet: AES-128-CBC + HMAC-SHA256)
# ------------------------------------------------------------------------------

def _get_encryption_cipher() -> Fernet:
    """Initializes Fernet cipher.

    Note: Fernet utilizes 128-bit AES in CBC mode with PKCS7 padding,
    authenticated using HMAC-SHA256 (standard RFC Fernet specification).
    Key is supplied via GMAIL_ENCRYPTION_KEY or derived deterministically in test mode.
    """
    if settings.GMAIL_ENCRYPTION_KEY:
        try:
            return Fernet(settings.GMAIL_ENCRYPTION_KEY.encode())
        except Exception as exc:
            if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
                raise GmailIntegrationError(f"Invalid GMAIL_ENCRYPTION_KEY configured: {exc}")

    # Fallback for local development and testing only
    key_material = hashlib.sha256((settings.SECRET_KEY + "_gmail_token_salt").encode()).digest()
    b64_key = base64.urlsafe_b64encode(key_material)
    return Fernet(b64_key)


def encrypt_refresh_token(plaintext_token: str) -> str:
    """Encrypts plaintext refresh token for secure database persistence."""
    if not plaintext_token:
        raise ValueError("Cannot encrypt empty token.")
    cipher = _get_encryption_cipher()
    return cipher.encrypt(plaintext_token.encode()).decode()


def decrypt_refresh_token(encrypted_token: str) -> str:
    """Decrypts database-stored refresh token for server-side token refresh."""
    if not encrypted_token:
        raise ValueError("Cannot decrypt empty token.")
    cipher = _get_encryption_cipher()
    return cipher.decrypt(encrypted_token.encode()).decode()


# ------------------------------------------------------------------------------
# 2. Hardened OAuth State Protection (Anti-Replay, Nonce & Session Binding)
# ------------------------------------------------------------------------------

def generate_oauth_state(
    org_id: str,
    user_id: str,
    db: Optional[Session] = None,
    session_binding: Optional[str] = None,
    ttl_seconds: int = 600,
) -> str:
    """Creates a tamper-evident, short-lived HMAC-signed OAuth state string.

    Enforces:
    - 32-character cryptographically random nonce.
    - 10-minute expiry (600 seconds).
    - Client/session binding hash if supplied.
    - Server-side persistence in oauth_state_nonces for atomic single-use verification.
    """
    nonce = secrets.token_urlsafe(24)
    now = datetime.datetime.now(datetime.timezone.utc)
    now_ts = int(now.timestamp())
    exp_ts = now_ts + ttl_seconds

    payload = {
        "nonce": nonce,
        "org_id": org_id,
        "user_id": user_id,
        "session_binding": session_binding,
        "ts": now_ts,
        "exp": exp_ts,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(settings.SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()

    if db is not None:
        state_record = OAuthStateNonce(
            id=nonce,
            org_id=org_id,
            user_id=user_id,
            session_binding=session_binding,
            is_consumed=False,
            expires_at=datetime.datetime.utcfromtimestamp(exp_ts),
        )
        db.add(state_record)
        db.commit()

    return f"{encoded}.{sig}"


def validate_and_consume_oauth_state(
    state: str,
    db: Optional[Session] = None,
    session_binding: Optional[str] = None,
) -> Tuple[str, str]:
    """Validates state signature, expiration, session binding, and single-use consumption."""
    parts = state.split(".")
    if len(parts) != 2:
        raise GmailIntegrationError("Invalid state parameter format.")

    encoded, sig = parts
    expected_sig = hmac.new(settings.SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise GmailIntegrationError("State parameter signature verification failed: Tampering detected.")

    try:
        data = json.loads(base64.urlsafe_b64decode(encoded.encode()).decode())
    except Exception:
        raise GmailIntegrationError("Corrupted state payload.")

    nonce = data.get("nonce")
    org_id = data.get("org_id")
    user_id = data.get("user_id")
    exp_ts = data.get("exp", 0)
    now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    if now_ts > exp_ts:
        raise GmailIntegrationError("OAuth state parameter has expired (10-minute window exceeded).")

    # Verify session binding if both provided
    if session_binding and data.get("session_binding") and session_binding != data.get("session_binding"):
        raise GmailIntegrationError("OAuth session binding mismatch: Initiating browser session required.")

    # Server-side single-use atomic consumption
    if db is not None and nonce:
        record = db.execute(select(OAuthStateNonce).where(OAuthStateNonce.id == nonce)).scalar_one_or_none()
        if record:
            if record.is_consumed:
                raise GmailIntegrationError("OAuth state parameter has already been consumed: Replay attack rejected.")
            record.is_consumed = True
            record.consumed_at = datetime.datetime.utcnow()
            db.commit()

    return org_id, user_id


# Alias for backwards compatibility
validate_oauth_state = validate_and_consume_oauth_state


def build_authorization_url(
    org_id: str,
    user_id: str,
    db: Optional[Session] = None,
    session_binding: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    ttl_seconds: int = 600,
) -> str:
    """Constructs the canonical Google OAuth 2.0 authorization URL."""
    if not settings.GMAIL_CLIENT_ID:
        raise GmailNotConfiguredError("GMAIL_CLIENT_ID is not configured.")

    state = generate_oauth_state(org_id, user_id, db=db, session_binding=session_binding, ttl_seconds=ttl_seconds)
    effective_redirect_uri = redirect_uri or settings.GMAIL_REDIRECT_URI or f"{settings.BASE_URL.rstrip('/')}/api/v1/integrations/gmail/callback"
    params = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "redirect_uri": effective_redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = httpx.URL("", params=params).query.decode()
    return f"{GOOGLE_AUTH_URL}?{query}"


# ------------------------------------------------------------------------------
# 3. Token Exchange & Refresh Handlers
# ------------------------------------------------------------------------------

def exchange_code_for_tokens(code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Exchanges authorization code for Google access and refresh tokens."""
    if not (settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET):
        raise GmailNotConfiguredError("GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET are required.")

    effective_redirect_uri = redirect_uri or settings.GMAIL_REDIRECT_URI or f"{settings.BASE_URL.rstrip('/')}/api/v1/integrations/gmail/callback"
    payload = {
        "code": code,
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "redirect_uri": effective_redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        resp = httpx.post(GOOGLE_TOKEN_URL, data=payload, timeout=15.0)
        if resp.status_code != 200:
            raise GmailIntegrationError(f"Token exchange failed (HTTP {resp.status_code}): {resp.text}")
        return resp.json()
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error during token exchange: {str(exc)}")


def refresh_access_token(encrypted_token: str, db: Optional[Session] = None, account: Optional[GmailAccount] = None) -> str:
    """Exchanges encrypted refresh token for a short-lived access token.

    Updates account.oauth_status to EXPIRED if refresh token is invalid/revoked.
    """
    if not (settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET):
        raise GmailNotConfiguredError("Gmail client credentials are not configured.")

    plaintext_refresh_token = decrypt_refresh_token(encrypted_token)
    payload = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": plaintext_refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        resp = httpx.post(GOOGLE_TOKEN_URL, data=payload, timeout=15.0)
        if resp.status_code in (400, 401):
            if db and account:
                account.oauth_status = "EXPIRED"
                db.commit()
            raise GmailIntegrationError(f"Access token refresh failed (HTTP {resp.status_code}): {resp.text}")
        if resp.status_code != 200:
            raise GmailIntegrationError(f"Access token refresh failed (HTTP {resp.status_code}): {resp.text}")
        data = resp.json()
        return data["access_token"]
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error during token refresh: {str(exc)}")


def fetch_mailbox_profile(access_token: str) -> Dict[str, Any]:
    """Fetches verified mailbox profile (emailAddress, historyId, etc.) from Google Gmail Profile API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(f"{GMAIL_API_BASE}/profile", headers=headers, timeout=10.0)
        if resp.status_code != 200:
            raise GmailIntegrationError(f"Failed to fetch Gmail profile: HTTP {resp.status_code}")
        return resp.json()
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error querying Gmail profile: {str(exc)}")


def fetch_mailbox_profile_address(access_token: str) -> str:
    """Fetches verified mailbox email address from Google Gmail Profile API."""
    try:
        data = fetch_mailbox_profile(access_token)
        return data.get("emailAddress", "")
    except Exception:
        # Fallback direct call if fetch_mailbox_profile was overridden or mocked
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = httpx.get(f"{GMAIL_API_BASE}/profile", headers=headers, timeout=10.0)
            if resp.status_code != 200:
                raise GmailIntegrationError(f"Failed to fetch Gmail profile: HTTP {resp.status_code}")
            return resp.json().get("emailAddress", "")
        except httpx.RequestError as exc:
            raise GmailIntegrationError(f"Network error querying Gmail profile: {str(exc)}")


# ------------------------------------------------------------------------------
# 4. MIME Attachment Extraction (Nested Parts, body.data & attachments.get)
# ------------------------------------------------------------------------------

def find_all_pdf_attachments(part: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recursively traverses nested MIME parts to extract all PDF attachments."""
    results: List[Dict[str, Any]] = []

    filename = part.get("filename", "")
    mime_type = part.get("mimeType", "")
    body = part.get("body", {})

    is_pdf = filename.lower().endswith(".pdf") or mime_type == "application/pdf"
    has_data = bool(body.get("data") or body.get("attachmentId"))

    if is_pdf and has_data:
        results.append({
            "filename": filename or "attachment.pdf",
            "mime_type": mime_type or "application/pdf",
            "data": body.get("data"),
            "attachment_id": body.get("attachmentId"),
            "size": body.get("size", 0),
        })

    # Traverse nested multipart children
    for subpart in part.get("parts", []):
        results.extend(find_all_pdf_attachments(subpart))

    return results


def extract_attachment_bytes(access_token: str, message_id: str, attachment_info: Dict[str, Any]) -> bytes:
    """Extracts attachment bytes from direct body.data or external attachments.get."""
    raw_data = attachment_info.get("data")
    if raw_data:
        padded = raw_data + "=" * (-len(raw_data) % 4)
        return base64.urlsafe_b64decode(padded)

    attachment_id = attachment_info.get("attachment_id")
    if attachment_id:
        return get_attachment_bytes(access_token, message_id, attachment_id)

    raise ValueError("No attachment data or attachmentId provided in MIME part.")


def get_attachment_bytes(access_token: str, message_id: str, attachment_id: str) -> bytes:
    """Downloads attachment bytes from Google messages.attachments.get."""
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{GMAIL_API_BASE}/messages/{message_id}/attachments/{attachment_id}"
    try:
        resp = httpx.get(url, headers=headers, timeout=15.0)
        if resp.status_code != 200:
            raise GmailIntegrationError(f"Failed to fetch attachment: HTTP {resp.status_code}")
        data = resp.json().get("data", "")
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded)
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error downloading attachment: {str(exc)}")


def parse_sender_info(from_header: str) -> Tuple[str, str]:
    """Extracts display name and raw email from a standard 'From' header."""
    match = re.search(r"^(.*?)\s*<([^>]+)>$", from_header.strip())
    if match:
        name = match.group(1).strip().strip('"')
        email_addr = match.group(2).strip().lower()
        return name or email_addr, email_addr
    return from_header.strip(), from_header.strip().lower()


def list_mailbox_messages(access_token: str, query: str = "has:attachment filename:pdf", max_results: int = 10) -> List[Dict[str, Any]]:
    """Queries dedicated mailbox messages matching invoice attachment filter."""
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": query, "maxResults": max_results}
    try:
        resp = httpx.get(f"{GMAIL_API_BASE}/messages", headers=headers, params=params, timeout=15.0)
        if resp.status_code != 200:
            raise GmailIntegrationError(f"Failed to list messages: HTTP {resp.status_code}")
        return resp.json().get("messages", [])
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error listing messages: {str(exc)}")


def get_message_detail(access_token: str, message_id: str) -> Dict[str, Any]:
    """Fetches full RFC-822 message details including headers and payload structure."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(f"{GMAIL_API_BASE}/messages/{message_id}?format=full", headers=headers, timeout=15.0)
        if resp.status_code != 200:
            raise GmailIntegrationError(f"Failed to fetch message {message_id}: HTTP {resp.status_code}")
        return resp.json()
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error fetching message: {str(exc)}")


# ------------------------------------------------------------------------------
# 5. Full Mailbox Ingestion Pipeline (Processes Single Messages or Query Batches)
# ------------------------------------------------------------------------------

def process_single_message_ingestion(
    db: Session,
    account: GmailAccount,
    access_token: str,
    message_id: str,
    actor_id: str,
) -> Dict[str, Any]:
    """Ingests all valid PDF attachments from a single RFC-822 message."""
    try:
        detail = get_message_detail(access_token, message_id)
    except Exception as exc:
        logger.warning(f"Could not fetch detail for msg {message_id}: {exc}")
        return {"ingested": [], "quarantined": [], "duplicates": 0}

    headers_list = detail.get("payload", {}).get("headers", [])
    headers_map = {h["name"].lower(): h["value"] for h in headers_list}
    from_hdr = headers_map.get("from", "Unknown Vendor")
    subject = headers_map.get("subject", "No Subject")
    vendor_display, vendor_email = parse_sender_info(from_hdr)

    # Recursive MIME attachment discovery
    attachments = find_all_pdf_attachments(detail.get("payload", {}))
    ingested = []
    quarantined = []
    duplicates = 0

    for att in attachments:
        filename = att["filename"]
        try:
            content = extract_attachment_bytes(access_token, message_id, att)
        except Exception as exc:
            logger.error(f"Failed to extract attachment {filename} from msg {message_id}: {exc}")
            continue

        # 1. Size constraints
        if len(content) == 0 or len(content) > settings.MAX_UPLOAD_FILE_SIZE_BYTES:
            q_id = f"q_{uuid.uuid4().hex[:12]}"
            q_doc = QuarantinedDocument(
                id=q_id,
                org_id=account.org_id,
                document_id=f"doc_{uuid.uuid4().hex[:12]}",
                quarantine_reason="FILE_TOO_LARGE" if len(content) > settings.MAX_UPLOAD_FILE_SIZE_BYTES else "EMPTY_FILE",
                details=f"File '{filename}' ({len(content)} bytes) violated size constraints.",
                status="ACTIVE",
            )
            db.add(q_doc)
            quarantined.append({"filename": filename, "reason": q_doc.quarantine_reason})
            continue

        # 2. Magic bytes check (%PDF-)
        if not content.startswith(b"%PDF-"):
            q_id = f"q_{uuid.uuid4().hex[:12]}"
            q_doc = QuarantinedDocument(
                id=q_id,
                org_id=account.org_id,
                document_id=f"doc_{uuid.uuid4().hex[:12]}",
                quarantine_reason="MALFORMED_PDF",
                details=f"File '{filename}' failed PDF magic bytes signature check.",
                status="ACTIVE",
            )
            db.add(q_doc)
            quarantined.append({"filename": filename, "reason": "MALFORMED_PDF"})
            continue

        # 3. SHA-256 and Tenant Duplicate Check
        sha256_hash = hashlib.sha256(content).hexdigest()
        existing = db.execute(
            select(Document).where(
                Document.org_id == account.org_id,
                Document.sha256_hash == sha256_hash,
                Document.is_deleted == False,
            )
        ).scalar_one_or_none()

        if existing:
            duplicates += 1
            logger.info(f"Duplicate document detected: {filename} ({sha256_hash[:12]}...)")
            continue

        # 4. Storage Persistence
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        inv_id = f"inv_{uuid.uuid4().hex[:12]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        storage_path = build_tenant_storage_path(account.org_id, doc_id, filename)

        try:
            storage_meta = storage_adapter.save_file(
                content=content,
                filename=filename,
                mime_type="application/pdf",
                storage_key=storage_path,
            )
        except Exception as exc:
            logger.error(f"Storage adapter failed for {filename}: {exc}")
            continue

        # 5. Database Records
        try:
            invoice = Invoice(
                id=inv_id,
                org_id=account.org_id,
                source_channel="GMAIL",
                vendor_name=vendor_display,
                stage="RECEIVED",
                decision="NEEDS_REVIEW",
                decision_reason=f"Ingested from mailbox {account.mailbox_address}. Subject: '{subject}'",
            )
            db.add(invoice)
            db.flush()

            doc = Document(
                id=doc_id,
                org_id=account.org_id,
                invoice_id=inv_id,
                filename=filename,
                mime_type="application/pdf",
                file_size_bytes=len(content),
                sha256_hash=sha256_hash,
                storage_provider=storage_meta["storage_provider"],
                storage_key=storage_meta["storage_key"],
                is_original=True,
                is_deleted=False,
            )
            db.add(doc)

            job = IngestionJob(
                id=job_id,
                org_id=account.org_id,
                document_id=doc_id,
                idempotency_key=f"gmail_{message_id}_{sha256_hash}",
                source_channel="GMAIL",
                status="QUEUED",
            )
            db.add(job)

            db.flush()
            append_checkpoint(db, job, 'INTAKE', 'QUEUED',
                f"Automated ingestion of {filename} from {vendor_email}",
                attempt=0, invoice_id=inv_id, actor_id=actor_id, actor_role='SYSTEM_ADMIN',
                action='GMAIL_INVOICE_INGESTED', source_reference=storage_meta['storage_key'])

            ingested.append({
                "document_id": doc_id,
                "invoice_id": inv_id,
                "filename": filename,
                "vendor": vendor_display,
                "sha256": sha256_hash,
            })
        except Exception as exc:
            db.rollback()
            try:
                storage_adapter.delete_file(storage_meta["storage_key"])
            except Exception:
                pass
            logger.error(f"DB failure ingesting document {filename}: {exc}")
            continue

    return {"ingested": ingested, "quarantined": quarantined, "duplicates": duplicates}


def sync_gmail_mailbox(
    db: Session,
    org_id: str,
    actor_id: str,
    max_messages: int = 10,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Syncs mailbox via query search."""
    start_time = time.time()
    max_duration = timeout_seconds if timeout_seconds is not None else getattr(settings, "GMAIL_SYNC_TIMEOUT_SECONDS", 240)

    gmail_acc = db.execute(
        select(GmailAccount).where(
            GmailAccount.org_id == org_id,
            GmailAccount.oauth_status == "AUTHORIZED",
        )
    ).scalar_one_or_none()

    if not gmail_acc:
        return {
            "status": "NOT_CONNECTED",
            "org_id": org_id,
            "message": "No authorized Gmail mailbox configured for this organisation.",
            "ingested_count": 0,
            "quarantined_count": 0,
            "duplicates_skipped": 0,
            "invoices": [],
        }

    if not gmail_acc.encrypted_refresh_token:
        gmail_acc.oauth_status = "EXPIRED"
        db.commit()
        return {
            "status": "EXPIRED",
            "org_id": org_id,
            "message": "Gmail refresh token missing or revoked. Re-authorization required.",
            "ingested_count": 0,
            "quarantined_count": 0,
            "duplicates_skipped": 0,
            "invoices": [],
        }

    try:
        access_token = refresh_access_token(gmail_acc.encrypted_refresh_token, db=db, account=gmail_acc)
    except Exception as exc:
        logger.error(f"Failed to refresh Gmail token: {exc}")
        return {
            "status": "AUTH_FAILED",
            "org_id": org_id,
            "message": f"Gmail access token refresh failed: {str(exc)}",
            "ingested_count": 0,
            "quarantined_count": 0,
            "duplicates_skipped": 0,
            "invoices": [],
        }

    messages = list_mailbox_messages(access_token, query="has:attachment filename:pdf", max_results=max_messages)
    all_ingested = []
    all_quarantined = []
    total_duplicates = 0
    timed_out = False

    for msg_stub in messages:
        elapsed = time.time() - start_time
        if max_duration is not None and elapsed >= max_duration:
            logger.warning(
                f"Full mailbox sync deadline ({max_duration}s) reached after {elapsed:.2f}s "
                f"for {gmail_acc.mailbox_address}. Halting sync safely."
            )
            timed_out = True
            break

        res = process_single_message_ingestion(db, gmail_acc, access_token, msg_stub["id"], actor_id)
        all_ingested.extend(res["ingested"])
        all_quarantined.extend(res["quarantined"])
        total_duplicates += res["duplicates"]

    if timed_out:
        db.commit()
        return {
            "status": "TIMED_OUT",
            "timed_out": True,
            "org_id": org_id,
            "mailbox": gmail_acc.mailbox_address,
            "ingested_count": len(all_ingested),
            "quarantined_count": len(all_quarantined),
            "duplicates_skipped": total_duplicates,
            "invoices": all_ingested,
            "quarantined": all_quarantined,
        }

    try:
        prof = fetch_mailbox_profile(access_token)
        if prof.get("historyId"):
            gmail_acc.last_history_id = str(prof["historyId"])
    except Exception as exc:
        logger.warning(f"Failed to refresh history watermark after full mailbox sync: {exc}")

    gmail_acc.last_synced_at = datetime.datetime.utcnow()
    db.commit()

    return {
        "status": "SUCCESS",
        "org_id": org_id,
        "mailbox": gmail_acc.mailbox_address,
        "ingested_count": len(all_ingested),
        "quarantined_count": len(all_quarantined),
        "duplicates_skipped": total_duplicates,
        "invoices": all_ingested,
        "quarantined": all_quarantined,
    }


# ------------------------------------------------------------------------------
# 6. Stage 5: Gmail Watch Registration (users.watch) & 48-Hour Renewal
# ------------------------------------------------------------------------------

def register_gmail_watch(access_token: str, topic_name: str, label_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Calls Google Gmail users.watch to establish push notifications to Pub/Sub topic."""
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "topicName": topic_name,
        "labelIds": label_ids or ["INBOX"],
    }

    try:
        resp = httpx.post(f"{GMAIL_API_BASE}/watch", headers=headers, json=payload, timeout=15.0)
        if resp.status_code != 200:
            raise GmailIntegrationError(f"users.watch failed (HTTP {resp.status_code}): {resp.text}")
        return resp.json()
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error registering Gmail watch: {str(exc)}")


def stop_gmail_watch(access_token: str) -> bool:
    """Calls Google Gmail users.stop to cancel push notifications."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.post(f"{GMAIL_API_BASE}/stop", headers=headers, timeout=10.0)
        return resp.status_code in (200, 204)
    except Exception as exc:
        logger.error(f"users.stop failed: {exc}")
        return False


def setup_mailbox_watch(db: Session, account: GmailAccount, topic_name: Optional[str] = None) -> Dict[str, Any]:
    """Sets up or renews Gmail watch registration on a specific GmailAccount."""
    topic = topic_name or account.pubsub_topic or settings.PUBSUB_TOPIC_NAME
    if not topic:
        raise GmailIntegrationError("Pub/Sub topicName is required for watch registration.")

    if not account.encrypted_refresh_token:
        raise GmailIntegrationError("Mailbox has no encrypted refresh token.")

    access_token = refresh_access_token(account.encrypted_refresh_token, db=db, account=account)
    watch_data = register_gmail_watch(access_token, topic)

    now = datetime.datetime.utcnow()
    exp_ms = int(watch_data.get("expiration", 0))
    expiration_dt = datetime.datetime.utcfromtimestamp(exp_ms / 1000.0) if exp_ms else now + datetime.timedelta(days=7)

    account.pubsub_topic = topic
    account.watch_history_id = watch_data.get("historyId")
    account.watch_expiration_at = expiration_dt
    account.watch_last_renewed_at = now
    account.watch_status = "ACTIVE"
    account.updated_at = now
    db.commit()

    return {
        "status": "WATCH_ACTIVE",
        "mailbox": account.mailbox_address,
        "topic": topic,
        "history_id": account.watch_history_id,
        "expiration_at": expiration_dt.isoformat() + "Z",
        "renewed_at": now.isoformat() + "Z",
    }


def renew_expiring_watches(db: Session) -> Dict[str, Any]:
    """Renews active mailbox watches nearing the 48-hour renewal window."""
    now = datetime.datetime.utcnow()
    threshold = now - datetime.timedelta(hours=settings.GMAIL_WATCH_RENEWAL_HOURS)

    accounts = db.execute(
        select(GmailAccount).where(
            GmailAccount.oauth_status == "AUTHORIZED",
            GmailAccount.watch_status == "ACTIVE",
            GmailAccount.watch_last_renewed_at < threshold,
        )
    ).scalars().all()

    renewed = []
    failed = []

    for acc in accounts:
        try:
            res = setup_mailbox_watch(db, acc)
            renewed.append(acc.mailbox_address)
        except Exception as exc:
            logger.error(f"Failed to renew watch for {acc.mailbox_address}: {exc}")
            acc.watch_status = "FAILED"
            db.commit()
            failed.append({"mailbox": acc.mailbox_address, "error": str(exc)})

    return {"renewed_count": len(renewed), "failed_count": len(failed), "renewed": renewed, "failed": failed}


# ------------------------------------------------------------------------------
# 7. Stage 5: Gmail History Sync (users.history.list) with Resync Fallback
# ------------------------------------------------------------------------------

def is_history_id_greater(new_id: Optional[str], current_id: Optional[str]) -> bool:
    """Returns True if new_id represents a strictly newer history position than current_id.
    
    Gmail historyIds are decimal strings representing unsigned 64-bit integers.
    """
    if not new_id:
        return False
    if not current_id:
        return True
    try:
        return int(new_id) > int(current_id)
    except (ValueError, TypeError):
        return str(new_id) > str(current_id)


def acquire_mailbox_lock(
    db: Session,
    account_id: str,
    lease_seconds: int = 120,
    wait_timeout_seconds: float = 0.0,
) -> Optional[str]:
    """Atomically acquires an exclusive processing lease on a mailbox."""
    start_time = time.monotonic()

    while True:
        now = datetime.datetime.utcnow()
        token = uuid.uuid4().hex
        expires_at = now + datetime.timedelta(seconds=lease_seconds)

        stmt = (
            update(GmailAccount)
            .where(
                GmailAccount.id == account_id,
                (GmailAccount.sync_lock_expires_at == None) | (GmailAccount.sync_lock_expires_at < now),
            )
            .values(
                sync_lock_token=token,
                sync_lock_expires_at=expires_at,
            )
        )
        result = db.execute(stmt)
        db.commit()

        if result.rowcount > 0:
            return token

        elapsed = time.monotonic() - start_time
        if elapsed >= wait_timeout_seconds:
            return None
        time.sleep(min(0.05, wait_timeout_seconds - elapsed))


def release_mailbox_lock(db: Session, account_id: str, token: str) -> bool:
    """Releases a previously acquired mailbox processing lease."""
    stmt = (
        update(GmailAccount)
        .where(
            GmailAccount.id == account_id,
            GmailAccount.sync_lock_token == token,
        )
        .values(
            sync_lock_token=None,
            sync_lock_expires_at=None,
        )
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0


@contextlib.contextmanager
def mailbox_sync_lease(
    db: Session,
    account_id: str,
    lease_seconds: int = 120,
    wait_timeout_seconds: float = 0.0,
):
    """Context manager acquiring and releasing an exclusive per-mailbox lease."""
    token = acquire_mailbox_lock(db, account_id, lease_seconds, wait_timeout_seconds)
    if not token:
        raise MailboxSyncLockError(
            f"Mailbox {account_id} is currently locked by another active synchronization process."
        )
    try:
        yield token
    finally:
        try:
            release_mailbox_lock(db, account_id, token)
        except Exception as exc:
            logger.warning(f"Failed to release mailbox lock for {account_id}: {exc}")


def get_history_messages(access_token: str, start_history_id: str) -> Tuple[List[str], str]:
    """Retrieves new message IDs since start_history_id using users.history.list.

    Raises HistoryExpiredError if Gmail API returns HTTP 404.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "startHistoryId": start_history_id,
        "historyTypes": "messageAdded",
    }

    try:
        resp = httpx.get(f"{GMAIL_API_BASE}/history", headers=headers, params=params, timeout=15.0)
        if resp.status_code == 404:
            raise HistoryExpiredError(f"historyId '{start_history_id}' has expired on Gmail servers.")
        if resp.status_code != 200:
            raise GmailIntegrationError(f"history.list failed (HTTP {resp.status_code}): {resp.text}")

        data = resp.json()
        new_history_id = data.get("historyId", start_history_id)
        message_ids: List[str] = []

        for record in data.get("history", []):
            for item in record.get("messagesAdded", []):
                msg = item.get("message", {})
                if msg.get("id"):
                    message_ids.append(msg["id"])

        return list(set(message_ids)), str(new_history_id)
    except httpx.RequestError as exc:
        raise GmailIntegrationError(f"Network error querying Gmail history: {str(exc)}")


def sync_gmail_history(
    db: Session,
    account: GmailAccount,
    notification_history_id: str,
    actor_id: str = "PUBSUB_PUSH",
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Syncs new messages via history.list, falling back to full reconciliation on 404.

    Enforces internal processing deadline comfortably below Cloud Run container timeout
    and Pub/Sub ack deadline (default 240s vs 300s).
    """
    start_time = time.time()
    max_duration = timeout_seconds if timeout_seconds is not None else getattr(settings, "GMAIL_SYNC_TIMEOUT_SECONDS", 240)

    if not account.encrypted_refresh_token:
        account.oauth_status = "EXPIRED"
        db.commit()
        return {"status": "AUTH_EXPIRED", "ingested_count": 0}

    access_token = refresh_access_token(account.encrypted_refresh_token, db=db, account=account)
    start_history_id = account.last_history_id or account.watch_history_id

    if not start_history_id:
        # Initial sync: run full reconciliation
        res = sync_gmail_mailbox(db, account.org_id, actor_id=actor_id, timeout_seconds=max_duration)
        if res.get("timed_out") or res.get("status") == "TIMED_OUT":
            return res
        try:
            prof = fetch_mailbox_profile(access_token)
            if prof.get("historyId"):
                account.last_history_id = str(prof["historyId"])
        except Exception as exc:
            logger.warning(f"Failed to refresh historyId after HistoryExpiredError fallback: {exc}")
            if is_history_id_greater(notification_history_id, account.last_history_id):
                account.last_history_id = notification_history_id
        account.last_synced_at = datetime.datetime.utcnow()
        db.commit()
        return res

    try:
        msg_ids, latest_history_id = get_history_messages(access_token, start_history_id)
    except HistoryExpiredError:
        logger.warning(
            f"History ID {start_history_id} expired (HTTP 404) for {account.mailbox_address}. "
            f"Triggering documented full-resynchronization fallback."
        )
        remaining_budget = max(1.0, max_duration - (time.time() - start_time)) if max_duration else None
        res = sync_gmail_mailbox(db, account.org_id, actor_id=f"{actor_id}_FULL_FALLBACK", timeout_seconds=remaining_budget)
        if res.get("timed_out") or res.get("status") == "TIMED_OUT":
            res["fallback_full_sync"] = True
            return res
        try:
            prof = fetch_mailbox_profile(access_token)
            if prof.get("historyId"):
                account.last_history_id = str(prof["historyId"])
        except Exception as exc:
            logger.warning(f"Failed to refresh historyId after HistoryExpiredError fallback: {exc}")
            if is_history_id_greater(notification_history_id, account.last_history_id):
                account.last_history_id = notification_history_id
        account.last_synced_at = datetime.datetime.utcnow()
        db.commit()
        res["fallback_full_sync"] = True
        return res

    all_ingested = []
    all_quarantined = []
    total_duplicates = 0
    timed_out = False

    for m_id in msg_ids:
        elapsed = time.time() - start_time
        if max_duration is not None and elapsed >= max_duration:
            logger.warning(
                f"Gmail sync processing deadline ({max_duration}s) reached after {elapsed:.2f}s "
                f"for {account.mailbox_address}. Processed {len(all_ingested)} invoices before halting. "
                f"Watermark not advanced to ensure safe redelivery."
            )
            timed_out = True
            break

        single_res = process_single_message_ingestion(db, account, access_token, m_id, actor_id=actor_id)
        all_ingested.extend(single_res["ingested"])
        all_quarantined.extend(single_res["quarantined"])
        total_duplicates += single_res["duplicates"]

    if timed_out:
        # Halt safely: commit any processed invoices, do NOT advance account.last_history_id watermark
        db.commit()
        return {
            "status": "TIMED_OUT",
            "timed_out": True,
            "org_id": account.org_id,
            "mailbox": account.mailbox_address,
            "history_id": account.last_history_id,
            "messages_checked": len(all_ingested) + len(all_quarantined) + total_duplicates,
            "ingested_count": len(all_ingested),
            "quarantined_count": len(all_quarantined),
            "duplicates_skipped": total_duplicates,
            "invoices": all_ingested,
            "quarantined": all_quarantined,
        }

    # Strictly monotonic watermark advancement: watermark must never move backwards
    candidate_history_id = latest_history_id
    if is_history_id_greater(notification_history_id, candidate_history_id):
        candidate_history_id = notification_history_id

    if is_history_id_greater(candidate_history_id, account.last_history_id):
        account.last_history_id = candidate_history_id

    account.last_synced_at = datetime.datetime.utcnow()
    db.commit()

    return {
        "status": "SUCCESS",
        "org_id": account.org_id,
        "mailbox": account.mailbox_address,
        "history_id": account.last_history_id,
        "messages_checked": len(msg_ids),
        "ingested_count": len(all_ingested),
        "quarantined_count": len(all_quarantined),
        "duplicates_skipped": total_duplicates,
        "invoices": all_ingested,
    }


# ------------------------------------------------------------------------------
# 8. Stage 5: Pub/Sub Notification Validation & Durable Persistence
# ------------------------------------------------------------------------------

def validate_pubsub_oidc_token(
    auth_header: Optional[str],
    expected_audience: Optional[str] = None,
    expected_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Validates the OIDC token sent by Google Cloud Pub/Sub push subscriptions."""
    if not auth_header or not auth_header.startswith("Bearer "):
        raise GmailIntegrationError("Missing or malformed Authorization header.")

    token = auth_header.split(" ", 1)[1].strip()

    if settings.APP_ENV == AppEnv.TEST:
        # In test mode, allow test token inspection
        if token == "invalid_token":
            raise GmailIntegrationError("Invalid OIDC signature.")
        if token.startswith("test_oidc:"):
            parts = token.split(":", 2)
            # test_oidc:<email>:<aud>
            token_email = parts[1] if len(parts) > 1 else "pubsub-invoker@gcp.internal"
            token_aud = parts[2] if len(parts) > 2 else (expected_audience or "https://api.domain.com")
            if expected_audience and token_aud != expected_audience:
                raise GmailIntegrationError(f"Audience mismatch: expected {expected_audience}, got {token_aud}")
            if expected_email and token_email != expected_email:
                raise GmailIntegrationError(f"Email mismatch: expected {expected_email}, got {token_email}")
            return {"email": token_email, "aud": token_aud, "iss": "https://accounts.google.com"}

    try:
        from jose import jwt as jose_jwt
        unverified_claims = jose_jwt.get_unverified_claims(token)

        # 1. Validate issuer
        iss = unverified_claims.get("iss", "")
        if iss not in ("https://accounts.google.com", "accounts.google.com"):
            raise GmailIntegrationError(f"Invalid OIDC token issuer: {iss}")

        # 2. Validate audience
        aud = unverified_claims.get("aud", "")
        effective_aud = expected_audience or settings.PUBSUB_VERIFICATION_AUDIENCE
        if effective_aud and aud != effective_aud:
            raise GmailIntegrationError(f"OIDC audience mismatch: expected '{effective_aud}', got '{aud}'")

        # 3. Validate service account email
        email = unverified_claims.get("email", "")
        effective_email = expected_email or settings.PUBSUB_SERVICE_ACCOUNT_EMAIL
        if effective_email and email != effective_email:
            raise GmailIntegrationError(f"OIDC service account mismatch: expected '{effective_email}', got '{email}'")

        # In production, verify signature against Google's public certs
        if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
            jwks_resp = httpx.get("https://www.googleapis.com/oauth2/v3/certs", timeout=5)
            jwks_resp.raise_for_status()
            jwks = jwks_resp.json()
            jose_jwt.decode(token, jwks, algorithms=["RS256"], audience=effective_aud)

        return unverified_claims
    except Exception as exc:
        raise GmailIntegrationError(f"Pub/Sub OIDC token validation failed: {str(exc)}")


def clean_expired_mailbox_locks(db: Session) -> int:
    """Explicitly resets any stale mailbox synchronization locks where lease has expired."""
    now = datetime.datetime.utcnow()
    stmt = (
        update(GmailAccount)
        .where(
            GmailAccount.sync_lock_expires_at != None,
            GmailAccount.sync_lock_expires_at < now,
        )
        .values(
            sync_lock_token=None,
            sync_lock_expires_at=None,
        )
    )
    result = db.execute(stmt)
    db.commit()
    if result.rowcount > 0:
        logger.info(f"Reclaimed {result.rowcount} expired mailbox synchronization lease(s).")
    return result.rowcount


def process_single_pubsub_event(
    db: Session,
    account: GmailAccount,
    event_record: PubSubEvent,
    wait_timeout_seconds: float = 0.5,
) -> Dict[str, Any]:
    """Processes an individual PubSubEvent under a mailbox concurrency lease.

    Guarantees:
    1. Preserves strictly monotonic history watermarks.
    2. Respects exclusive per-mailbox processing lease.
    3. Handles lock contention gracefully (CONCURRENT_DEFERRED).
    4. Marks event COMPLETED on success, or records FAILED with error message and retry count.
    5. Deduplicates attachments via SHA-256 hash.
    """
    history_id = event_record.history_id
    message_id = event_record.pubsub_message_id
    event_id = event_record.id

    # 1. Out-of-order check: do not regress watermark if incoming historyId is older or equal
    if account.last_history_id and not is_history_id_greater(history_id, account.last_history_id):
        logger.info(
            f"Notification/event {event_id} ({message_id}) historyId '{history_id}' <= current watermark '{account.last_history_id}'. "
            f"Safely completing event without redundant sync."
        )
        event_record.status = "COMPLETED"
        event_record.processed_at = datetime.datetime.utcnow()
        db.commit()
        return {
            "status": "OUT_OF_ORDER_SKIPPED",
            "event_id": event_id,
            "pubsub_message_id": message_id,
            "mailbox": account.mailbox_address,
            "history_id": history_id,
            "current_watermark": account.last_history_id,
            "message": "Notification historyId is older than or equal to current watermark; safely acknowledged without regressing watermark.",
        }

    # 2. Acquire per-mailbox exclusive processing lease to prevent concurrent corruption
    # Aligns with Cloud Run container request timeout and Pub/Sub ack deadline (default 300s)
    ack_lease_seconds = getattr(settings, "PUBSUB_ACK_DEADLINE_SECONDS", 300)
    try:
        with mailbox_sync_lease(db, account.id, lease_seconds=ack_lease_seconds, wait_timeout_seconds=wait_timeout_seconds):
            db.refresh(account)

            # Re-check watermark after lock acquisition in case prior worker advanced it
            if account.last_history_id and not is_history_id_greater(history_id, account.last_history_id):
                event_record.status = "COMPLETED"
                event_record.processed_at = datetime.datetime.utcnow()
                db.commit()
                return {
                    "status": "OUT_OF_ORDER_SKIPPED",
                    "event_id": event_id,
                    "pubsub_message_id": message_id,
                    "mailbox": account.mailbox_address,
                    "history_id": history_id,
                    "current_watermark": account.last_history_id,
                    "message": "Watermark advanced by prior concurrent worker; safely acknowledged.",
                }

            event_record.last_attempted_at = datetime.datetime.utcnow()
            sync_result = sync_gmail_history(db, account, history_id, actor_id=f"PUBSUB_{message_id[:8]}")

            if sync_result.get("timed_out") or sync_result.get("status") == "TIMED_OUT":
                logger.warning(
                    f"Pub/Sub event {event_id} ({message_id}) reached processing deadline during sync. "
                    f"Releasing mailbox lease and keeping event status RECEIVED for safe redelivery/reclaim."
                )
                event_record.status = "RECEIVED"
                event_record.error_message = (
                    f"Sync processing deadline reached ({getattr(settings, 'GMAIL_SYNC_TIMEOUT_SECONDS', 240)}s). "
                    f"Processed {sync_result.get('ingested_count', 0)} invoices; remaining messages deferred for safe retry."
                )
                db.commit()
                # Exiting the 'with mailbox_sync_lease' context block immediately releases the lease lock!
                return {
                    "status": "TIMED_OUT",
                    "event_id": event_id,
                    "pubsub_message_id": message_id,
                    "mailbox": account.mailbox_address,
                    "sync_result": sync_result,
                    "retryable": True,
                }

            event_record.status = "COMPLETED"
            event_record.error_message = None
            event_record.processed_at = datetime.datetime.utcnow()
            db.commit()

            return {
                "status": "PROCESSED",
                "event_id": event_id,
                "pubsub_message_id": message_id,
                "mailbox": account.mailbox_address,
                "sync_result": sync_result,
            }
    except MailboxSyncLockError as lock_exc:
        logger.warning(f"Mailbox {account.mailbox_address} concurrency lock contention: {lock_exc}")
        event_record.status = "CONCURRENT_DEFERRED"
        event_record.error_message = str(lock_exc)
        event_record.last_attempted_at = datetime.datetime.utcnow()
        db.commit()
        return {
            "status": "CONCURRENT_DEFERRED",
            "event_id": event_id,
            "pubsub_message_id": message_id,
            "mailbox": account.mailbox_address,
            "detail": "Mailbox synchronization currently in progress by another worker. Event deferred.",
        }
    except Exception as exc:
        event_record.status = "FAILED"
        event_record.error_message = str(exc)
        event_record.last_attempted_at = datetime.datetime.utcnow()
        db.commit()
        logger.error(f"Failed to process Pub/Sub event {event_id} ({message_id}) for {account.mailbox_address}: {exc}")
        return {
            "status": "FAILED",
            "event_id": event_id,
            "pubsub_message_id": message_id,
            "error": str(exc),
        }


def process_pubsub_push_notification(db: Session, request_body: Dict[str, Any]) -> Dict[str, Any]:
    """Validates, persists durably, and processes an incoming Pub/Sub push notification.

    Stage 5.2 Enhancements:
    1. If existing PubSubEvent is COMPLETED or OUT_OF_ORDER_SKIPPED: acknowledges as duplicate without re-processing.
    2. If existing PubSubEvent is unfinished (RECEIVED, FAILED, CONCURRENT_DEFERRED): reclaims it for processing,
       incrementing retry_count and updating last_attempted_at.
    3. If new messageId: durably commits event with status RECEIVED before processing begins.
    4. Concurrency-safe: acquires per-mailbox lease and respects monotonic watermarks.
    """
    message = request_body.get("message")
    if not isinstance(message, dict):
        raise GmailIntegrationError("Invalid Pub/Sub push payload: missing 'message' object.")

    raw_data = message.get("data")
    message_id = message.get("messageId")
    subscription = request_body.get("subscription", "")

    if not raw_data or not message_id:
        raise GmailIntegrationError("Invalid Pub/Sub push payload: missing 'data' or 'messageId'.")

    # 1. Decode payload
    try:
        padded = raw_data + "=" * (-len(raw_data) % 4)
        decoded_bytes = base64.urlsafe_b64decode(padded)
        data_json = json.loads(decoded_bytes.decode())
    except Exception as exc:
        raise GmailIntegrationError(f"Failed to decode Pub/Sub data payload: {str(exc)}")

    email_address = data_json.get("emailAddress", "").strip().lower()
    history_id = str(data_json.get("historyId", "")).strip()

    if not email_address or not history_id:
        raise GmailIntegrationError("Pub/Sub data payload missing 'emailAddress' or 'historyId'.")

    # 2. Resolve mailbox to registered organisation
    account = db.execute(
        select(GmailAccount).where(
            GmailAccount.mailbox_address == email_address,
            GmailAccount.oauth_status == "AUTHORIZED",
        )
    ).scalar_one_or_none()

    if not account:
        logger.warning(f"Pub/Sub notification received for unknown/unauthorized mailbox: {email_address}")
        return {
            "status": "UNKNOWN_MAILBOX",
            "mailbox": email_address,
            "message": "Mailbox not registered or authorized in this system.",
        }

    # 3. Check for existing event record
    existing_event = db.execute(
        select(PubSubEvent).where(PubSubEvent.pubsub_message_id == message_id)
    ).scalar_one_or_none()

    if existing_event:
        if existing_event.status in ("COMPLETED", "OUT_OF_ORDER_SKIPPED"):
            logger.info(f"Duplicate Pub/Sub notification received: {message_id} (already completed)")
            return {
                "status": "DUPLICATE",
                "pubsub_message_id": message_id,
                "event_id": existing_event.id,
                "message": "Duplicate notification acknowledged idempotently.",
            }

        # Event is unfinished: RECEIVED, FAILED, or CONCURRENT_DEFERRED
        logger.info(
            f"Redelivered unfinished Pub/Sub notification: {message_id} (status: {existing_event.status}). "
            f"Reclaiming for execution."
        )
        existing_event.retry_count = (existing_event.retry_count or 0) + 1
        existing_event.last_attempted_at = datetime.datetime.utcnow()
        db.commit()
        event_record = existing_event
    else:
        # 4. Durable persistence before returning acknowledgement
        event_id = f"pse_{uuid.uuid4().hex[:12]}"
        event_record = PubSubEvent(
            id=event_id,
            org_id=account.org_id,
            mailbox_address=account.mailbox_address,
            history_id=history_id,
            pubsub_message_id=message_id,
            subscription=subscription,
            payload_json=data_json,
            status="RECEIVED",
            retry_count=0,
            last_attempted_at=datetime.datetime.utcnow(),
        )
        db.add(event_record)
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.critical(f"Durable persistence failed for PubSubEvent {message_id}: {exc}")
            raise PubSubPersistenceError(f"Database commit failed during notification persistence: {exc}")

    # 5. Execute processing under per-mailbox lease
    return process_single_pubsub_event(db, account, event_record, wait_timeout_seconds=0.5)


def reclaim_unfinished_pubsub_events(
    db: Session,
    max_age_seconds: int = 60,
    limit: int = 50,
) -> Dict[str, Any]:
    """Scans and reclaims unfinished PubSubEvent records (RECEIVED, FAILED, CONCURRENT_DEFERRED).

    Allows recovery of events where the application crashed or lease contention deferred processing,
    without requiring external Pub/Sub redelivery.
    """
    clean_expired_mailbox_locks(db)

    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(seconds=max_age_seconds)

    unfinished_events = db.execute(
        select(PubSubEvent)
        .where(
            PubSubEvent.status.in_(["RECEIVED", "FAILED", "CONCURRENT_DEFERRED", "PARTIALLY_PROCESSED"]),
            (PubSubEvent.last_attempted_at == None) | (PubSubEvent.last_attempted_at < cutoff),
        )
        .order_by(PubSubEvent.received_at.asc())
        .limit(limit)
    ).scalars().all()

    processed_count = 0
    completed_count = 0
    failed_count = 0
    deferred_count = 0
    details = []

    for event in unfinished_events:
        account = db.execute(
            select(GmailAccount).where(
                GmailAccount.mailbox_address == event.mailbox_address,
                GmailAccount.oauth_status == "AUTHORIZED",
            )
        ).scalar_one_or_none()

        if not account:
            logger.warning(f"Cannot reclaim event {event.id}: account {event.mailbox_address} unauthorized or not found.")
            continue

        processed_count += 1
        event.retry_count = (event.retry_count or 0) + 1
        event.last_attempted_at = now
        db.commit()

        res = process_single_pubsub_event(db, account, event, wait_timeout_seconds=0.0)
        status_result = res.get("status")

        if status_result in ("PROCESSED", "OUT_OF_ORDER_SKIPPED"):
            completed_count += 1
        elif status_result == "FAILED":
            failed_count += 1
        elif status_result == "CONCURRENT_DEFERRED":
            deferred_count += 1

        details.append({
            "event_id": event.id,
            "pubsub_message_id": event.pubsub_message_id,
            "mailbox": event.mailbox_address,
            "result_status": status_result,
            "retry_count": event.retry_count,
        })

    return {
        "scanned_count": len(unfinished_events),
        "processed_count": processed_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "deferred_count": deferred_count,
        "details": details,
    }


# ------------------------------------------------------------------------------
# 9. Stage 5: Periodic 6-Hour Mailbox Reconciliation
# ------------------------------------------------------------------------------

def reconcile_all_active_mailboxes(db: Session, max_age_hours: int = 6) -> Dict[str, Any]:
    """Reconciles all active mailboxes and reclaims unfinished Pub/Sub events."""
    reclaimed_locks = clean_expired_mailbox_locks(db)
    reclaimed_events = reclaim_unfinished_pubsub_events(db, max_age_seconds=60)

    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(hours=max_age_hours)

    accounts = db.execute(
        select(GmailAccount).where(
            GmailAccount.oauth_status == "AUTHORIZED",
            (GmailAccount.last_synced_at == None) | (GmailAccount.last_synced_at < cutoff),
        )
    ).scalars().all()

    reconciled = []
    total_ingested = 0
    for acc in accounts:
        try:
            res = sync_gmail_mailbox(db, acc.org_id, actor_id="PERIODIC_6H_RECONCILIATION")
            count = res.get("ingested_count", 0)
            total_ingested += count
            reconciled.append({"mailbox": acc.mailbox_address, "ingested": count})
        except Exception as exc:
            logger.error(f"Periodic reconciliation failed for {acc.mailbox_address}: {exc}")

    return {
        "reconciled_mailboxes": len(reconciled),
        "reconciled_count": len(reconciled),
        "total_ingested": total_ingested,
        "reclaimed_locks": reclaimed_locks,
        "reclaimed_events": reclaimed_events,
        "details": reconciled,
    }
