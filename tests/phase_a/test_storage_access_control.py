"""Tests for Private Encrypted Object Storage Access Control."""

import pytest
from backend.core.storage import S3EncryptedStorageAdapter, StorageNotConfiguredError


def test_production_storage_rejects_unconfigured_credentials(monkeypatch):
    """Production S3 adapter must raise StorageNotConfiguredError when bucket/credentials are missing."""
    monkeypatch.setattr("backend.core.config.settings.STORAGE_BUCKET_NAME", None)
    adapter = S3EncryptedStorageAdapter()
    health = adapter.check_health()
    assert health["readiness"] is False
    assert health["status"] == "NOT_CONFIGURED"

    with pytest.raises(StorageNotConfiguredError, match="Object storage is not ready"):
        adapter.save_file(b"%PDF-test", "test.pdf", "application/pdf")

    with pytest.raises(StorageNotConfiguredError, match="Storage is not configured"):
        adapter.get_file("originals/hash/test.pdf")

    with pytest.raises(StorageNotConfiguredError, match="Storage is not configured"):
        adapter.generate_signed_url("originals/hash/test.pdf")


def test_storage_adapter_no_local_disk_production_fallback(monkeypatch):
    """Production adapter must not fall back to local disk paths."""
    monkeypatch.setattr("backend.core.config.settings.STORAGE_BUCKET_NAME", "unauthorized-bucket")
    adapter = S3EncryptedStorageAdapter()
    assert not hasattr(adapter, "_local_fallback_dir")
    assert not hasattr(adapter, "local_disk_path")


def test_in_memory_test_adapter_signed_urls():
    """Test adapter generates time-bounded signed URLs."""
    from backend.core.storage import TestInMemoryStorageAdapter
    test_adapter = TestInMemoryStorageAdapter()
    meta = test_adapter.save_file(b"%PDF-test", "test.pdf", "application/pdf")
    signed_url = test_adapter.generate_signed_url(meta["storage_key"], expires_in=900)
    assert "token=test_signed_token" in signed_url
    assert meta["storage_key"] in signed_url
