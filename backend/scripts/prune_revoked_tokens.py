"""Explicit operator cleanup of expired revocations; never loads an implicit target.

Run only against the intended database with a narrowly authorized maintenance
identity. Tokens remain in the table for at least 24 hours beyond expiry.
"""
import argparse
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def prune(session):
    if session.get_bind().dialect.name != 'postgresql':
        raise RuntimeError('PostgreSQL maintenance connection required')
    result = session.execute(text("""
        DELETE FROM revoked_access_tokens
        WHERE expires_at < (clock_timestamp() AT TIME ZONE 'UTC') - INTERVAL '24 hours'
    """))
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-expired-prune', action='store_true')
    args = parser.parse_args()
    url = os.environ.get('REVOCATION_MAINTENANCE_DATABASE_URL')
    if not args.confirm_expired_prune or not url:
        parser.error('Explicit confirmation and REVOCATION_MAINTENANCE_DATABASE_URL are required')
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            count = prune(session)
            session.commit()
        print(f'Expired revocation rows removed: {count}')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
