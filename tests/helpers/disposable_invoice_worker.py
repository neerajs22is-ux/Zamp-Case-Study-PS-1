"""Crash-test child only: isolate credentials before importing application code."""
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.inspect_offline import configure_offline_environment
configure_offline_environment()
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from backend.core import pipeline

url, token, marker, content_file = sys.argv[1:]
parsed = make_url(url)
if parsed.host != '127.0.0.1' or parsed.username != 'ap_app_user' or not parsed.database.startswith('ap_inspection_') or not parsed.database.endswith('_test'):
    raise RuntimeError('Crash worker requires the disposable application-role database')
pipeline.SessionLocal = sessionmaker(bind=create_engine(url,connect_args={'options':'-c statement_timeout=8000 -c lock_timeout=3000'}),autoflush=False)
pipeline.JOB_LEASE_SECONDS = 2
content = Path(content_file).read_bytes()
pipeline.storage_adapter = SimpleNamespace(get_file=lambda _: content)
def blocked_provider(**_):
    Path(marker).write_text('provider entered; completion unknown')
    threading.Event().wait(30)
    raise RuntimeError('Crash test was not terminated')
pipeline.execute_document_pipeline('job',token,extractor=SimpleNamespace(extract_hybrid=blocked_provider),org_id='a')
