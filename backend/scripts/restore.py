"""Operator CLI Script: Supabase & Database Restore Utility.

Usage:
  python -m backend.scripts.restore --archive ARCHIVE_PATH --key KEY --target-db-url TARGET_URL --confirm-restore
"""

from __future__ import annotations

import argparse
import os
import sys
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.backup import (
    restore_backup_archive, get_encryption_key, BackupError
)
from backend.core.storage import storage_adapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restore_cli")


def main() -> int:
    parser = argparse.ArgumentParser(description="AP Command Center Supabase Restoration Utility")
    parser.add_argument("--archive", required=True, help="Path to the encrypted backup archive (.tar.gz.enc)")
    parser.add_argument("--key", default=None, help="[SECURITY NOTICE: Prefer BACKUP_ENCRYPTION_KEY env var or interactive prompt to avoid process table exposure]")
    parser.add_argument("--target-db-url", default=None, help="Explicit target PostgreSQL connection string; alternatively set RESTORE_TARGET_DATABASE_URL")
    parser.add_argument("--confirm-restore", action="store_true", help="Explicit confirmation required to execute destructive restoration")
    parser.add_argument("--skip-storage", action="store_true", help="Restore database only, skip storage objects")
    parser.add_argument("--confirm-target-bucket", default=None, help="Exact configured destination bucket name; required when restoring storage")

    args = parser.parse_args()

    target_url = (
        args.target_db_url
        or os.getenv("RESTORE_TARGET_DATABASE_URL")
    )
    if not target_url:
        logger.error("Explicit restore target required: --target-db-url or RESTORE_TARGET_DATABASE_URL.")
        return 1

    if not args.skip_storage and (not args.confirm_target_bucket or args.confirm_target_bucket != getattr(storage_adapter, 'bucket', None)):
        logger.error("An exact --confirm-target-bucket matching the configured destination is required, or use --skip-storage.")
        return 1

    if not args.confirm_restore:
        print("\n" + "!" * 70)
        print("ERROR: DESTRUCTIVE RESTORATION GUARD")
        print("!" * 70)
        print("Restoration will modify database tables and overwrite existing records.")
        print("To proceed, you must pass the --confirm-restore flag.")
        print("Example:")
        print(f"  python -m backend.scripts.restore --archive {args.archive} --target-db-url <URL> --confirm-restore\n")
        return 1

    try:
        resolved_key = get_encryption_key(args.key, prompt_if_missing=True)
    except BackupError as exc:
        logger.error(str(exc))
        return 1

    logger.info(f"Connecting to target database: {target_url.split('@')[-1] if '@' in target_url else 'configured target'}")
    target_engine = create_engine(target_url)
    session_factory = sessionmaker(bind=target_engine)
    target_session = session_factory()

    try:
        logger.info(f"Decrypting and validating backup archive: {args.archive}")
        result = restore_backup_archive(
            archive_path=args.archive,
            encryption_key=resolved_key,
            target_session=target_session,
            target_storage=None if args.skip_storage else storage_adapter,
            confirm_restore=args.confirm_restore,
        )

        print("\n" + "=" * 60)
        print(f"RESTORATION COMPLETED — STATUS: {result['status']}")
        print("=" * 60)
        print(f"Backup ID:          {result['backup_id']}")
        print(f"Restored At:        {result['restoration_timestamp']}")
        print(f"Database Result:    {result['database']}")
        print(f"Storage Result:     {result['storage']}")
        print(f"Verification:       {result['verification']}")
        print("=" * 60)
        print("\nSUPABASE AUTH OPERATOR NOTICE:")
        print("Database and storage restoration does not recreate Supabase Auth identities.")
        print("Use the provider's verified identity recovery procedure; do not infer email confirmation from workspace records.")
        print("=" * 60 + "\n")

        return 0
    except BackupError as exc:
        logger.error(f"Restoration failed: {exc}")
        return 1
    except Exception as exc:
        logger.critical("Restoration failed (%s)", type(exc).__name__)
        return 1
    finally:
        target_session.close()
        target_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
