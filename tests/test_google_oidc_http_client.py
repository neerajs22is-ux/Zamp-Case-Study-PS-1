"""Signed disposable OIDC fixtures; JWKS HTTP is intercepted locally."""
import datetime as dt
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwk, jwt

from backend.core.auth import require_maintenance_auth
from backend.core.config import AppEnv, settings
from backend.core.gmail import validate_pubsub_oidc_token, GmailIntegrationError


def test_google_oidc_jwks_uses_declared_http_client_and_fails_closed(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public_pem = private.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    key = jwk.construct(public_pem, algorithm='RS256').to_dict()
    key['kid'] = 'disposable'
    audience = 'https://demo.example.test/hook'
    email = 'service@example.test'
    claims = {'iss': 'https://accounts.google.com', 'aud': audience, 'email': email,
              'exp': int(dt.datetime.now(dt.timezone.utc).timestamp()) + 300}
    signed = jwt.encode(claims, private_pem, algorithm='RS256', headers={'kid': 'disposable'})
    monkeypatch.setattr(settings, 'APP_ENV', AppEnv.STAGING)
    monkeypatch.setattr(settings, 'CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL', email)
    monkeypatch.setattr(settings, 'CLOUD_SCHEDULER_VERIFICATION_AUDIENCE', audience)
    def response(status):
        return httpx.Response(status, json={'keys': [key]}, request=httpx.Request('GET', 'https://www.googleapis.com/oauth2/v3/certs'))
    monkeypatch.setattr(httpx, 'get', lambda *a, **kw: response(200))
    assert validate_pubsub_oidc_token('Bearer ' + signed, audience, email)['email'] == email
    request = SimpleNamespace(url=audience, headers={})
    credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials=signed)
    assert require_maintenance_auth(request, credentials, None).actor_type == 'CLOUD_SCHEDULER'
    monkeypatch.setattr(httpx, 'get', lambda *a, **kw: response(503))
    with pytest.raises(GmailIntegrationError):
        validate_pubsub_oidc_token('Bearer ' + signed, audience, email)
    with pytest.raises(HTTPException) as denied:
        require_maintenance_auth(request, credentials, None)
    assert denied.value.status_code == 401
