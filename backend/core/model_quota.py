"""Durable conservative reservations, not a provider billing guarantee."""
import math
from sqlalchemy import text
from backend.core.config import settings
from backend.core.processing_events import lease_now


class ModelQuotaExceeded(Exception):
    pass


def reserve_model_attempt(db, org_id):
    """Reserve both buckets atomically in caller's transaction, before extraction.

    Never refund: a worker can die after a provider accepted its request.
    SQLite is for functional tests; PostgreSQL serializes conflicting upserts.
    """
    now = lease_now(db)
    amount = math.ceil(settings.MANTLE_MAX_DOCUMENT_COST_USD * 1_000_000)
    limit = math.floor(settings.MODEL_RESERVATION_BUDGET_USD_PER_TENANT_MONTH * 1_000_000)
    if amount <= 0 or amount > limit:
        raise ModelQuotaExceeded("Model reservation exceeds the configured monthly limit.")
    statement = text("""
        INSERT INTO model_quota_buckets (org_id, period, bucket, used)
        SELECT :org, :period, :bucket, :amount WHERE :amount <= :limit
        ON CONFLICT (org_id, period, bucket) DO UPDATE
        SET used = model_quota_buckets.used + :amount
        WHERE model_quota_buckets.used + :amount <= :limit
        RETURNING used
    """)
    for period, bucket, increment, maximum in (
        ('minute', now.strftime('%Y%m%d%H%M'), 1, settings.MODEL_MAX_ATTEMPTS_PER_TENANT_MINUTE),
        ('month', now.strftime('%Y%m'), amount, limit),
    ):
        row = db.execute(statement, {'org': org_id, 'period': period, 'bucket': bucket,
                                    'amount': increment, 'limit': maximum}).first()
        if row is None:
            raise ModelQuotaExceeded(f"Model {period} reservation limit reached; retry after the period resets.")
