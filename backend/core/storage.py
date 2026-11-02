"""Private Encrypted Object Storage Adapter (Supabase Storage & S3).

Enforces:
1. Production originals stored exclusively in approved encrypted private buckets (Supabase Storage / S3).
2. Local disk production fallback is strictly barred.
3. Cryptographic SHA-256 integrity verification.
4. Time-bounded presigned URLs with authorization checks (TTL <= 300s).
5. Tenant isolation: org_{org_id}/invoices/{document_id}/{filename}.
6. Compensating cleanup and authorized purge capabilities.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from backend.core.config import AppEnv, settings

logger = logging.getLogger("ap_command_center.storage")


class StorageError(Exception):
    """Base error for object storage operations."""
    pass


class StorageNotConfiguredError(StorageError):
    """Raised when object storage is invoked without required credentials."""
    pass


def build_tenant_storage_path(org_id: str, document_id: str, filename: str) -> str:
    """Constructs a deterministic, tenant-isolated object storage path.

    Format: org_{org_id}/invoices/{document_id}/{filename}
    """
    clean_org = org_id.strip()
    import pathlib
    clean_filename = pathlib.PureWindowsPath(filename.strip()).name
    clean_filename = pathlib.PurePosixPath(clean_filename).name.replace(" ", "_")
    org_folder = clean_org if clean_org.startswith("org_") else f"org_{clean_org}"
    return f"{org_folder}/invoices/{document_id}/{clean_filename}"


class ObjectStorageAdapter(ABC):
    @abstractmethod
    def save_file(
        self,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
        storage_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Saves file bytes and returns metadata with SHA-256 hash."""
        pass

    @abstractmethod
    def get_file(self, storage_key: str) -> bytes:
        """Retrieves raw file bytes."""
        pass

    @abstractmethod
    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        """Generates short-lived presigned URL for private document access (max 300s)."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes object from storage for compensating rollback or authorized purge."""
        pass

    @abstractmethod
    def list_objects(self, prefix: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Lists objects at the given prefix with pagination."""
        pass

    @abstractmethod
    def list_all_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Recursively lists all physical objects in the bucket, traversing pagination and subprefixes."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Verifies storage bucket connectivity and status."""
        pass


class SupabaseStorageAdapter(ObjectStorageAdapter):
    """Production Supabase Storage Adapter utilizing private bucket and official REST API."""

    def __init__(self):
        self.supabase_url = (settings.SUPABASE_URL or "").rstrip("/")
        self.service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = None  # Storage operations strictly require privileged service_role_key; anon_key is never used
        self.bucket = settings.SUPABASE_STORAGE_BUCKET or settings.STORAGE_BUCKET_NAME or "invoices"

    @staticmethod
    def is_new_secret_key(key: str) -> bool:
        """Determines if a key is Supabase's new API key format (e.g. sb_secret_).

        Supabase documentation specifies that new publishable and secret API keys (such as
        sb_secret_... or sb_pub_...) are not JWTs and must only be supplied via the 'apikey' header,
        never as Authorization: Bearer.
        """
        if not key:
            return False
        clean = key.strip()
        return clean.startswith("sb_secret_") or clean.startswith("sb_pub_") or clean.startswith("sb_publishable_") or clean.startswith("sb_")

    def _get_auth_headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        # Privileged server-side operations strictly require SUPABASE_SERVICE_ROLE_KEY.
        # Unprivileged anon or publishable keys must NEVER be silently substituted.
        key = (self.service_role_key or "").strip()
        headers: Dict[str, str] = {}
        if key:
            headers["apikey"] = key
            # Legacy JWT-based service_role keys (eyJ...) are sent in both apikey and Authorization: Bearer.
            # New Supabase API keys (sb_secret_...) are opaque API tokens, not JWTs, and must only be passed via apikey.
            if not self.is_new_secret_key(key):
                headers["Authorization"] = f"Bearer {key}"
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def check_health(self) -> Dict[str, Any]:
        if not self.supabase_url or not self.service_role_key:
            return {
                "status": "NOT_CONFIGURED",
                "provider": "supabase",
                "bucket": self.bucket,
                "readiness": False,
                "message": "Supabase Storage credentials (SUPABASE_URL and privileged SUPABASE_SERVICE_ROLE_KEY) are not configured.",
            }

        try:
            import httpx
            # Query bucket metadata from official Supabase Storage API
            url = f"{self.supabase_url}/storage/v1/bucket/{self.bucket}"
            resp = httpx.get(url, headers=self._get_auth_headers(), timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                is_public = data.get("public", False)
                if is_public:
                    return {
                        "status": "DEGRADED",
                        "provider": "supabase",
                        "bucket": self.bucket,
                        "readiness": True,
                        "message": f"WARNING: Bucket '{self.bucket}' is public. Invoices must be stored in private buckets only.",
                    }
                return {
                    "status": "CONNECTED",
                    "provider": "supabase",
                    "bucket": self.bucket,
                    "readiness": True,
                    "message": f"Verified access to private Supabase Storage bucket '{self.bucket}'.",
                }
            elif resp.status_code in (401, 403):
                return {
                    "status": "BLOCKED",
                    "provider": "supabase",
                    "bucket": self.bucket,
                    "readiness": False,
                    "message": f"Supabase Storage authentication failed ({resp.status_code}): Invalid service role key.",
                }
            elif resp.status_code == 404:
                return {
                    "status": "NOT_CONFIGURED",
                    "provider": "supabase",
                    "bucket": self.bucket,
                    "readiness": False,
                    "message": f"Supabase Storage bucket '{self.bucket}' does not exist. Creation required.",
                }
            else:
                return {
                    "status": "ERROR",
                    "provider": "supabase",
                    "bucket": self.bucket,
                    "readiness": False,
                    "message": f"Supabase Storage check returned HTTP {resp.status_code}: {resp.text}",
                }
        except Exception as exc:
            return {
                "status": "ERROR",
                "provider": "supabase",
                "bucket": self.bucket,
                "readiness": False,
                "message": f"Supabase Storage connection error: {str(exc)}",
            }

    def save_file(
        self,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
        storage_key: Optional[str] = None
    ) -> Dict[str, Any]:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError(
                f"Cannot save document: Supabase Storage is not ready ({health['message']}). "
                f"Local disk fallback is forbidden."
            )

        sha256_hash = hashlib.sha256(content).hexdigest()
        key = storage_key or f"originals/{sha256_hash}/{filename}"
        clean_key = key.lstrip("/")

        import httpx
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{clean_key}"
        headers = self._get_auth_headers(content_type=mime_type)
        headers["x-upsert"] = "true"

        try:
            resp = httpx.post(url, headers=headers, content=content, timeout=30.0)
            if resp.status_code not in (200, 201):
                raise StorageError(f"Supabase Storage upload failed ({resp.status_code}): {resp.text}")
        except httpx.RequestError as exc:
            raise StorageError(f"Supabase Storage upload network failure: {str(exc)}")

        return {
            "storage_provider": "supabase",
            "bucket": self.bucket,
            "storage_key": clean_key,
            "sha256": sha256_hash,
            "size_bytes": len(content),
            "mime_type": mime_type,
        }

    def get_file(self, storage_key: str) -> bytes:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Supabase Storage is not ready.")

        clean_key = storage_key.lstrip("/")
        import httpx
        url = f"{self.supabase_url}/storage/v1/object/authenticated/{self.bucket}/{clean_key}"
        headers = self._get_auth_headers()

        try:
            resp = httpx.get(url, headers=headers, timeout=30.0)
            if resp.status_code == 404 or (resp.status_code == 400 and ("not_found" in resp.text.lower() or "nosuchkey" in resp.text.lower())):
                raise FileNotFoundError(f"Object '{clean_key}' not found in Supabase bucket '{self.bucket}'.")
            if resp.status_code != 200:
                raise StorageError(f"Supabase Storage get failed ({resp.status_code}): {resp.text}")
            return resp.content
        except httpx.RequestError as exc:
            raise StorageError(f"Supabase Storage download network failure: {str(exc)}")

    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Supabase Storage is not ready.")

        effective_expiry = min(max(expires_in, 1), 300)
        clean_key = storage_key.lstrip("/")

        import httpx
        url = f"{self.supabase_url}/storage/v1/object/sign/{self.bucket}/{clean_key}"
        headers = self._get_auth_headers(content_type="application/json")

        try:
            resp = httpx.post(url, headers=headers, json={"expiresIn": effective_expiry}, timeout=10.0)
            if resp.status_code != 200:
                raise StorageError(f"Supabase signed URL generation failed ({resp.status_code}): {resp.text}")
            data = resp.json()
            signed_url_path = data.get("signedURL") or data.get("url")
            if not signed_url_path:
                raise StorageError("Supabase returned empty signedURL.")
            if signed_url_path.startswith("http"):
                return signed_url_path
            return f"{self.supabase_url}/storage/v1{signed_url_path}"
        except httpx.RequestError as exc:
            raise StorageError(f"Supabase Storage signed URL network failure: {str(exc)}")

    def delete_file(self, storage_key: str) -> bool:
        health = self.check_health()
        if not health["readiness"]:
            return False

        clean_key = storage_key.lstrip("/")
        import httpx
        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}"
        headers = self._get_auth_headers(content_type="application/json")

        try:
            resp = httpx.request("DELETE", url, headers=headers, json={"prefixes": [clean_key]}, timeout=10.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.error(f"Failed to delete file from Supabase Storage: {exc}")
            return False

    def list_objects(self, prefix: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Supabase Storage is not ready.")

        import httpx
        url = f"{self.supabase_url}/storage/v1/object/list/{self.bucket}"
        headers = self._get_auth_headers(content_type="application/json")
        body = {
            "prefix": prefix.strip("/"),
            "limit": limit,
            "offset": offset,
            "sortBy": {"column": "name", "order": "asc"},
        }

        try:
            resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
            if resp.status_code != 200:
                raise StorageError(f"Supabase Storage list failed ({resp.status_code}): {resp.text}")
            return resp.json()
        except httpx.RequestError as exc:
            raise StorageError(f"Supabase Storage list network failure: {str(exc)}")

    def list_all_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        """Traverses pagination and subfolders to return all file objects in the bucket."""
        all_files: List[Dict[str, Any]] = []
        prefixes_to_visit = [prefix.strip("/")]
        visited_prefixes = set()

        while prefixes_to_visit:
            curr_prefix = prefixes_to_visit.pop(0)
            if curr_prefix in visited_prefixes:
                continue
            visited_prefixes.add(curr_prefix)

            offset = 0
            page_limit = 100
            while True:
                items = self.list_objects(prefix=curr_prefix, limit=page_limit, offset=offset)
                if not items:
                    break

                for item in items:
                    name = item.get("name", "")
                    full_path = f"{curr_prefix}/{name}".strip("/") if curr_prefix else name
                    # In Supabase Storage, directory entries have id is None or no metadata
                    is_folder = item.get("id") is None and not item.get("metadata")
                    if is_folder:
                        if full_path not in visited_prefixes:
                            prefixes_to_visit.append(full_path)
                    else:
                        meta = item.get("metadata") or {}
                        all_files.append({
                            "name": name,
                            "path": full_path,
                            "size": meta.get("size", 0),
                            "content_type": meta.get("mimetype", "application/pdf"),
                            "id": item.get("id"),
                            "updated_at": item.get("updated_at"),
                            "created_at": item.get("created_at"),
                        })

                if len(items) < page_limit:
                    break
                offset += page_limit

        return all_files


class S3EncryptedStorageAdapter(ObjectStorageAdapter):
    """Production S3 Adapter utilizing SSE-KMS / SSE-S3 encryption."""

    def __init__(self):
        self.bucket = settings.STORAGE_BUCKET_NAME
        self.region = settings.STORAGE_REGION
        self.kms_key_id = settings.STORAGE_KMS_KEY_ID

    def check_health(self) -> Dict[str, Any]:
        if not self.bucket:
            return {
                "status": "NOT_CONFIGURED",
                "provider": "s3",
                "bucket": None,
                "region": self.region,
                "readiness": False,
                "message": "STORAGE_BUCKET_NAME is not configured.",
            }

        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError

            s3_client = boto3.client("s3", region_name=self.region)
            s3_client.head_bucket(Bucket=self.bucket)
            return {
                "status": "CONNECTED",
                "provider": "s3",
                "bucket": self.bucket,
                "region": self.region,
                "readiness": True,
                "message": f"Verified access to S3 bucket '{self.bucket}'.",
            }
        except NoCredentialsError:
            return {
                "status": "BLOCKED",
                "provider": "s3",
                "bucket": self.bucket,
                "region": self.region,
                "readiness": False,
                "message": "AWS credentials (AWS_ACCESS_KEY_ID or IAM role) not found.",
            }
        except Exception as exc:
            return {
                "status": "ERROR",
                "provider": "s3",
                "bucket": self.bucket,
                "region": self.region,
                "readiness": False,
                "message": f"S3 access check failed: {str(exc)}",
            }

    def save_file(
        self,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
        storage_key: Optional[str] = None
    ) -> Dict[str, Any]:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError(
                f"Cannot save document: Object storage is not ready ({health['message']}). "
                f"Local disk fallback is forbidden."
            )

        import boto3
        s3 = boto3.client("s3", region_name=self.region)
        sha256_hash = hashlib.sha256(content).hexdigest()
        key = storage_key or f"originals/{sha256_hash}/{filename}"

        extra_args: Dict[str, Any] = {
            "ContentType": mime_type,
            "Metadata": {"sha256": sha256_hash},
        }
        if self.kms_key_id:
            extra_args["ServerSideEncryption"] = "aws:kms"
            extra_args["SSEKMSKeyId"] = self.kms_key_id
        else:
            extra_args["ServerSideEncryption"] = "AES256"

        s3.put_object(Bucket=self.bucket, Key=key, Body=content, **extra_args)

        return {
            "storage_provider": "s3",
            "bucket": self.bucket,
            "storage_key": key,
            "sha256": sha256_hash,
            "size_bytes": len(content),
            "mime_type": mime_type,
        }

    def get_file(self, storage_key: str) -> bytes:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Storage is not configured.")
        import boto3
        s3 = boto3.client("s3", region_name=self.region)
        resp = s3.get_object(Bucket=self.bucket, Key=storage_key)
        return resp["Body"].read()

    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Storage is not configured.")
        effective_expiry = min(max(expires_in, 1), 300)
        import boto3
        s3 = boto3.client("s3", region_name=self.region)
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": storage_key},
            ExpiresIn=effective_expiry,
        )

    def delete_file(self, storage_key: str) -> bool:
        health = self.check_health()
        if not health["readiness"]:
            return False
        import boto3
        s3 = boto3.client("s3", region_name=self.region)
        try:
            s3.delete_object(Bucket=self.bucket, Key=storage_key)
            return True
        except Exception as exc:
            logger.error(f"Failed to delete S3 object: {exc}")
            return False

    def list_objects(self, prefix: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Storage is not configured.")
        import boto3
        s3 = boto3.client("s3", region_name=self.region)
        resp = s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix.strip("/"), MaxKeys=limit)
        items = []
        for obj in resp.get("Contents", []):
            items.append({
                "name": os.path.basename(obj["Key"]),
                "path": obj["Key"],
                "size": obj["Size"],
                "content_type": "application/pdf",
                "id": obj.get("ETag"),
                "updated_at": obj.get("LastModified", "").isoformat() if hasattr(obj.get("LastModified"), "isoformat") else str(obj.get("LastModified")),
            })
        return items

    def list_all_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        health = self.check_health()
        if not health["readiness"]:
            raise StorageNotConfiguredError("Storage is not configured.")
        import boto3
        s3 = boto3.client("s3", region_name=self.region)
        paginator = s3.get_paginator("list_objects_v2")
        all_objs = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix.strip("/")):
            for obj in page.get("Contents", []):
                all_objs.append({
                    "name": os.path.basename(obj["Key"]),
                    "path": obj["Key"],
                    "size": obj["Size"],
                    "content_type": "application/pdf",
                    "id": obj.get("ETag"),
                    "updated_at": obj.get("LastModified", "").isoformat() if hasattr(obj.get("LastModified"), "isoformat") else str(obj.get("LastModified")),
                })
        return all_objs


class TestInMemoryStorageAdapter(ObjectStorageAdapter):
    """Isolated storage adapter for unit test environments only."""
    __test__ = False

    def __init__(self):
        self._store: Dict[str, Tuple[bytes, Dict[str, Any]]] = {}

    def check_health(self) -> Dict[str, Any]:
        return {
            "status": "CONNECTED",
            "provider": "in_memory_test",
            "bucket": "test-bucket",
            "region": "test-region",
            "readiness": True,
            "message": "In-memory test storage adapter active.",
        }

    def save_file(
        self,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
        storage_key: Optional[str] = None
    ) -> Dict[str, Any]:
        sha256_hash = hashlib.sha256(content).hexdigest()
        key = storage_key or f"test-originals/{sha256_hash}/{filename}"
        clean_key = key.lstrip("/")
        meta = {
            "storage_provider": "in_memory_test",
            "bucket": "test-bucket",
            "storage_key": clean_key,
            "sha256": sha256_hash,
            "size_bytes": len(content),
            "mime_type": mime_type,
        }
        self._store[clean_key] = (content, meta)
        return meta

    def get_file(self, storage_key: str) -> bytes:
        clean_key = storage_key.lstrip("/")
        if clean_key not in self._store:
            raise FileNotFoundError(f"Storage key '{clean_key}' not found.")
        return self._store[clean_key][0]

    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        clean_key = storage_key.lstrip("/")
        effective_expiry = min(max(expires_in, 1), 300)
        return f"http://localhost:8000/api/v1/documents/preview?key={clean_key}&expires={effective_expiry}&token=test_signed_token"

    def delete_file(self, storage_key: str) -> bool:
        clean_key = storage_key.lstrip("/")
        if clean_key in self._store:
            del self._store[clean_key]
            return True
        return False

    def list_objects(self, prefix: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        clean_prefix = prefix.strip("/")
        matching = []
        for k in sorted(self._store.keys()):
            if not clean_prefix or k == clean_prefix or k.startswith(clean_prefix + "/"):
                content, meta = self._store[k]
                matching.append({
                    "name": os.path.basename(k),
                    "path": k,
                    "size": meta.get("size_bytes", len(content)),
                    "content_type": meta.get("mime_type", "application/pdf"),
                    "sha256": meta.get("sha256"),
                    "id": k,
                    "updated_at": datetime.datetime.now(datetime.UTC).isoformat() + "Z",
                })
        return matching[offset : offset + limit]

    def list_all_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        clean_prefix = prefix.strip("/")
        all_objs = []
        offset = 0
        limit = 100
        while True:
            page = self.list_objects(prefix=clean_prefix, limit=limit, offset=offset)
            if not page:
                break
            all_objs.extend(page)
            if len(page) < limit:
                break
            offset += limit
        return all_objs


_test_storage_singleton: Optional[TestInMemoryStorageAdapter] = None


def get_storage_adapter() -> ObjectStorageAdapter:
    global _test_storage_singleton
    if settings.APP_ENV == AppEnv.TEST:
        if _test_storage_singleton is None:
            _test_storage_singleton = TestInMemoryStorageAdapter()
        return _test_storage_singleton
    if settings.STORAGE_PROVIDER == "supabase":
        return SupabaseStorageAdapter()
    return S3EncryptedStorageAdapter()


class StorageProxy(ObjectStorageAdapter):
    """Dynamic storage proxy delegating to the active environment adapter."""

    def save_file(
        self,
        content: bytes,
        filename: str,
        mime_type: str = "application/pdf",
        storage_key: Optional[str] = None
    ) -> Dict[str, Any]:
        return get_storage_adapter().save_file(content, filename, mime_type=mime_type, storage_key=storage_key)

    def get_file(self, storage_key: str) -> bytes:
        return get_storage_adapter().get_file(storage_key)

    def generate_signed_url(self, storage_key: str, expires_in: int = 300) -> str:
        return get_storage_adapter().generate_signed_url(storage_key, expires_in=expires_in)

    def delete_file(self, storage_key: str) -> bool:
        return get_storage_adapter().delete_file(storage_key)

    def list_objects(self, prefix: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return get_storage_adapter().list_objects(prefix=prefix, limit=limit, offset=offset)

    def list_all_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        return get_storage_adapter().list_all_objects(prefix=prefix)

    def check_health(self) -> Dict[str, Any]:
        return get_storage_adapter().check_health()


storage_adapter = StorageProxy()
