"""Operator CLI Script: Supabase & Database Backup Utility.

Usage:
  python -m backend.scripts.backup [--backup-dir DIR] [--key KEY] [--retention-days DAYS]
"""

from __future__ import annotations

import argparse
import sys
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.backup import (
    create_backup_archive, generate_backup_encryption_key, get_encryption_key, BackupError
)
from backend.core.config import settings
from backend.core.storage import storage_adapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup_cli")


def main() -> int:
    parser = argparse.ArgumentParser(description="AP Command Center Supabase Backup Utility")
    parser.add_argument("--backup-dir", default=None, help="Directory to store encrypted archives")
    parser.add_argument("--key", default=None, help="[SECURITY NOTICE: Prefer BACKUP_ENCRYPTION_KEY env var or interactive prompt to avoid process table exposure]")
    parser.add_argument("--generate-key", action="store_true", help="Generate a new random Fernet encryption key and exit")
    parser.add_argument("--no-prune", action="store_true", help="Do not prune expired backups after completion")

    args = parser.parse_args()

    if args.generate_key:
        new_key = generate_backup_encryption_key()
        print(f"GENERATED BACKUP ENCRYPTION KEY:\n{new_key}\n")
        print("IMPORTANT: Store this key securely in your password manager / key vault.")
        print("Without this key, encrypted backups cannot be decrypted or restored.")
        return 0

    db_url = (
        os.getenv("BACKUP_DATABASE_URL")
        or settings.BACKUP_DATABASE_URL
        or settings.DATABASE_URL
    )
    if not db_url:
        logger.error("Neither BACKUP_DATABASE_URL nor DATABASE_URL is configured in settings or environment.")
        return 1

    try:
        key = get_encryption_key(args.key, prompt_if_missing=True)
    except BackupError as exc:
        logger.error(str(exc))
        print("\nTo generate a new encryption key, run:\n  python -m backend.scripts.backup --generate-key\n")
        return 1

    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        logger.info("Initiating AP Command Center Supabase backup...")
        result = create_backup_archive(
            session=session,
            storage_adapter=storage_adapter,
            backup_dir=args.backup_dir,
            encryption_key=key,
            prune=not args.no_prune,
        )

        status = result["completion_status"]
        summary = result["summary"]

        print("\n" + "=" * 60)
        print(f"BACKUP COMPLETED — STATUS: {status}")
        print("=" * 60)
        print(f"Archive Path:        {result['archive_path']}")
        print(f"Archive Size:        {result['archive_size_bytes']:,} bytes")
        print(f"Total Expected:      {summary['total_expected_objects']}")
        print(f"Exported Objects:    {summary['successfully_exported_objects']}")
        print(f"Failed Exports:      {summary['failed_exports']}")
        print(f"Checksum Mismatches: {summary['checksum_mismatches']}")
        print(f"Total Bytes Stored:  {summary['total_bytes']:,} bytes")

        if result.get("pruned_backups"):
            print(f"Pruned Archives:     {len(result['pruned_backups'])}")

        print("=" * 60)

        if status != "SUCCESS":
            logger.error("Backup failed validation checks. Inspect manifest for missing/corrupted files.")
            return 1

        return 0
    except Exception as exc:
        logger.critical(f"Backup operation encountered an unhandled error: {exc}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
