"""Run inspection tests without .env credentials, network connections, or servers.

Usage: python scripts/inspect_offline.py [pytest arguments]
Only in-process ASGI clients are used. Live database tests must be run separately
against an explicitly provisioned disposable database.
"""
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

def configure_offline_environment():
    # Never load workspace credentials, including in Settings() calls inside tests.
    from pydantic_settings.sources import DotEnvSettingsSource
    DotEnvSettingsSource.__call__ = lambda self: {}
    for key in list(os.environ):
        if any(part in key for part in ("DATABASE_URL", "POSTGRES_URL", "SUPABASE", "MANTLE", "PALMYRA", "GMAIL", "AWS_", "BACKUP_", "LIVE_")):
            os.environ.pop(key, None)
    os.environ.update(APP_ENV="test", DATABASE_URL="sqlite:///:memory:",
                      ENABLE_BACKGROUND_PIPELINE="false", ENABLE_DEV_SESSION="false")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    def deny_connection(sock, address, *args, **kwargs):
        # Windows asyncio constructs its wakeup socketpair using loopback TCP.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address, *args, **kwargs)
        raise RuntimeError("Inspection runner blocks all outbound socket connections")

    socket.socket.connect = deny_connection
    def guard_connect_ex(sock, address, *args, **kwargs):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect_ex(sock, address, *args, **kwargs)
        raise RuntimeError("Inspection runner blocks all outbound socket connections")
    socket.socket.connect_ex = guard_connect_ex


if __name__ == '__main__':
    configure_offline_environment()
    import pytest
    raise SystemExit(pytest.main(sys.argv[1:] or ["tests", "-q"]))
