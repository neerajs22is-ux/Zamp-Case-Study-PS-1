"""Own a loopback-only disposable PostgreSQL cluster, run tests, then remove it.

Usage: python scripts/inspect_postgres.py --bin-dir PATH [pytest args]
No configured database URL or workspace .env is used. Requires portable native
PostgreSQL binaries, never starts the application server or a Windows service.
"""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
parser = argparse.ArgumentParser()
parser.add_argument('--bin-dir', type=Path, required=True)
args, pytest_args = parser.parse_known_args()
binary = args.bin_dir.resolve()
for name in ('initdb.exe', 'pg_ctl.exe'):
    if not (binary / name).is_file():
        parser.error(f'Missing PostgreSQL binary: {name}')

# Reuse credential/network isolation without running the offline test entry point.
from inspect_offline import configure_offline_environment
configure_offline_environment()
work = (ROOT / 'scratch' / f'postgres-tests-{uuid.uuid4().hex}').resolve()
work.mkdir()
(work / '.owned-by-inspection').write_text('disposable PostgreSQL only')
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
def pg(name, *arguments):
    # Windows postgres children can inherit pg_ctl pipe handles. A regular log
    # file avoids waiting forever for a child-held stdout pipe after pg_ctl exits.
    with (work / 'launcher.log').open('ab') as log:
        return subprocess.run([str(binary / name), *map(str, arguments)], check=True,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=flags, timeout=60)
started = False
try:
    pg('initdb.exe', '-D', work / 'data', '-U', 'postgres', '-A', 'trust', '--encoding=UTF8', '--locale=C')
    pg('pg_ctl.exe', '-D', work / 'data', '-l', work / 'server.log',
       '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
    started = True
    print(f'Disposable PostgreSQL on loopback port {port}; no application server', flush=True)
    import pytest
    # Always supply explicit test paths, even when the caller passes options.
    # Bare pytest would also collect unrelated scratch scripts in this repo.
    result = pytest.main(['tests/postgres', 'tests/phase_b/test_identity_memberships_postgres.py',
        'tests/phase_b/test_workspace_postgres.py', 'tests/phase_b/test_stage1_tenant_isolation.py', '-q', '-rs', *pytest_args,
        '--disposable-postgres-port', str(port), '--disposable-postgres-root', str(work)])
finally:
    if started or (work / 'data' / 'postmaster.pid').exists():
        pg('pg_ctl.exe', '-D', work / 'data', '-m', 'fast', '-w', 'stop')
    # Delete only the unique directory this invocation created, after shutdown.
    if work.parent != (ROOT / 'scratch').resolve() or not (work / '.owned-by-inspection').is_file():
        raise RuntimeError('Refusing cleanup outside owned disposable directory')
    shutil.rmtree(work)
    print('Stopped and removed owned disposable PostgreSQL cluster', flush=True)
raise SystemExit(result)
