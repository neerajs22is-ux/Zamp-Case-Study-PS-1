"""Real Supabase identity/storage + migrated PostgreSQL acceptance subset.

Requires a private ownership journal for a newly created disposable project.
No .env is loaded, no existing project is used, and inference is deliberately
disabled until an isolated extraction credential can be provisioned.
"""
import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--owned-state',type=Path,required=True)
parser.add_argument('--full',action='store_true')
parser.add_argument('--attempt',type=int,default=1)
parser.add_argument('--evidence-dir',type=Path,default=ROOT/'docs/inspection-evidence/provider-environment')
args = parser.parse_args()
state_path = args.owned_state.resolve()
state = json.loads(state_path.read_text())
assert state.get('resource_status')=='created', 'Requires a current newly-created disposable project; deleted journals cannot be reused'
assert state_path.parent.parent == ROOT/'scratch'
assert (state_path.parent/'.owned-by-ps1-acceptance').read_text() == state['run_id']
assert state['run_id'].startswith('ps1-acceptance-')
assert state['project_id'] not in state['existing_project_ids']
setup = json.loads((args.evidence_dir/'setup.json').read_text())
assert setup['status']=='created' and setup['project_id']==state['project_id'] and setup['run_id']==state['run_id']
assert len(state['test_identities'])==2
assert state['own_database_host']=='db.'+state['project_id']+'.supabase.co'

from pydantic_settings.sources import DotEnvSettingsSource
DotEnvSettingsSource.__call__ = lambda self: {}
for name in list(os.environ):
    if any(word in name for word in ['DATABASE_URL','POSTGRES_URL','SUPABASE','MANTLE','PALMYRA','GMAIL','AWS_','BACKUP_']):
        os.environ.pop(name,None)
database_name=state['application_database']
assert database_name.startswith('ps1_acceptance_')
admin_url=f"postgresql+psycopg://postgres:{state['db_password']}@{state['own_database_host']}:5432/{database_name}?sslmode=require"
app_password = state.setdefault('app_role_password',secrets.token_urlsafe(32))
app_url=f"postgresql+psycopg://ap_app_user:{app_password}@{state['own_database_host']}:5432/{database_name}?sslmode=require"
state_path.write_text(json.dumps(state))
os.environ.update(APP_ENV='staging',DEBUG='false',SECRET_KEY=secrets.token_urlsafe(48),DATABASE_URL=app_url,MIGRATION_DATABASE_URL=admin_url,
    SUPABASE_URL=state['supabase_url'],SUPABASE_ISSUER=state['supabase_url']+'/auth/v1',
    SUPABASE_SERVICE_ROLE_KEY=state['service_role_key'],SUPABASE_STORAGE_BUCKET=state['bucket'],
    STORAGE_BUCKET_NAME=state['bucket'],STORAGE_PROVIDER='supabase',ENABLE_BACKGROUND_PIPELINE='false',
    ENABLE_DEV_SESSION='false',LOCAL_AUTH_BYPASS='false')
if args.full:
    assert state.get('mantle_project_id') and state.get('mantle_key')
    os.environ.update(MANTLE_API_KEY=state['mantle_key'],MANTLE_PROJECT_ID=state['mantle_project_id'],MANTLE_MODEL_ID=state['model_id'])
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
import httpx
import psycopg
from psycopg import sql
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine,select,text,func
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient
from backend.models.domain import (Organisation,User,RoleAssignment,IdentityMembership,Vendor,VendorGSTIN,
    WorkOrderSnapshot,WorkOrderLineSnapshot,GoodsReceiptSnapshot,GoodsReceiptLineSnapshot,
    QualityControlSnapshot,IngestionJob,Document,Invoice,AuditEvent,MatchRun,MatchGateCheck,ExtractedField,ExtractionRun)
from backend.core.database import set_tenant_context

result={'run_id':state['run_id'],'project_id':state['project_id'],'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
    'mode':'REAL_IDENTITY_STORAGE_DATABASE_ONLY_INFERENCE_BLOCKED','cases':[],'checks':[],
    'model_inference_calls':0,'model_usage':None,'model_cost_usd':None,'financial_actions_submitted':0}
phase='migration'
evidence = args.evidence_dir/(f'acceptance-attempt-{args.attempt}.json' if args.full else 'authenticated-subset.json')
result['provider_requests']=[]
result['actual_extractions']=[]
if args.full: result['mode']='REAL_AUTHENTICATED_PROVIDER_PIPELINE'
current_case=None
original_http_client=httpx.Client
class ObservedHTTPClient(original_http_client):
    def __init__(self,*a,**kw):
        hooks={key:list(value) for key,value in kw.pop('event_hooks',{}).items()}
        hooks.setdefault('request',[]).append(lambda request: request.extensions.update(ps1_started=time.perf_counter()))
        def observe(response):
            if response.request.url.host!='bedrock-mantle.ap-south-1.api.aws' or response.request.url.path!='/v1/chat/completions': return
            response.read()
            body=response.json()
            result['provider_requests'].append(dict(case=current_case,http_status=response.status_code,latency_ms=round((time.perf_counter()-response.request.extensions['ps1_started'])*1000,2),usage=body.get('usage'),returned_model=body.get('model'),requested_model=state['model_id'],project_id=state['mantle_project_id'],error_code=(body.get('error') or {}).get('code')))
            result['model_inference_calls']=len(result['provider_requests']);save()
        hooks.setdefault('response',[]).append(observe)
        super().__init__(*a,event_hooks=hooks,**kw)
if args.full:
    httpx.Client=ObservedHTTPClient
    from engine.hybrid_extractor import HybridAPExtractor
    original_extract=HybridAPExtractor.extract_hybrid
    def observed_extract(self,*a,**kw):
        value=original_extract(self,*a,**kw)
        result['actual_extractions'].append(dict(case=current_case,document_id=value.document_id,document_type=value.document_type,is_payable_invoice=value.is_payable_invoice,grounding_tripwire_passed=value.grounding_tripwire_passed,unverified_fields=value.unverified_fields,tax_valid=value.tax_arithmetic.is_valid,invoice_number=value.invoice_number,supplier_name=value.supplier_name,supplier_gstin=value.supplier_gstin,po_reference=value.po_reference,grand_total=value.grand_total,taxable_value=value.taxable_value,total_tax_amount=value.total_tax_amount,line_items=value.line_items,evidence={key:val.model_dump() for key,val in value.evidence.items()}));save()
        return value
    HybridAPExtractor.extract_hybrid=observed_extract
def save(): evidence.write_text(json.dumps(result,indent=2)+'\n')
try:
    config=Config(str(ROOT/'alembic.ini')); config.set_main_option('sqlalchemy.url',admin_url)
    command.upgrade(config,'head')
    with psycopg.connect(host=state['own_database_host'],dbname='postgres',user='postgres',password=state['db_password'],sslmode='require',connect_timeout=10) as connection:
        attributes=connection.execute("SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname='ap_app_user'").fetchone()
        assert attributes==(False,False,False,False), 'Runtime role must already be restricted by actual migrations'
        connection.execute(sql.SQL('ALTER ROLE ap_app_user PASSWORD {}').format(sql.Literal(app_password)))
    admin=create_engine(admin_url,poolclass=NullPool,connect_args={'connect_timeout':10})
    manifest=json.loads((ROOT/'output/pdf/ps1-acceptance-20261106/manifest.json').read_text())
    orgs={item['tenant']:state['run_id']+'-'+item['tenant'] for item in state['test_identities']}
    phase='synthetic source setup'
    if not state.get('sources_seeded'):
        with Session(admin) as db:
            for item in state['test_identities']:
                org=orgs[item['tenant']]
                db.add(Organisation(id=org,name=state['run_id']+' synthetic tenant '+item['tenant']));db.flush()
                db.add(User(id=item['id'],org_id=org,email=item['email'],full_name='Disposable acceptance user '+item['tenant']));db.flush()
                db.add(RoleAssignment(id='role-'+item['tenant'],org_id=org,user_id=item['id'],role_name='AP_ASSOCIATE'))
                db.add(IdentityMembership(id='membership-'+item['tenant'],org_id=org,user_id=item['id'],subject=item['id'],issuer=state['supabase_url']+'/auth/v1'))
            org=orgs['a']
            db.add(Vendor(id='accept-vendor',org_id=org,erp_vendor_code='ACCEPT-VENDOR',legal_name='PS1 Synthetic Services'));db.flush()
            db.add(VendorGSTIN(id='accept-gstin',org_id=org,vendor_id='accept-vendor',gstin='29ABCDE1234F1Z5',state_code='29',status='ACTIVE'))
            for i,po in enumerate(manifest['procurement']):
                pid='accept-po-'+str(i); grn='accept-grn-'+str(i)
                db.add(WorkOrderSnapshot(id=pid,org_id=org,po_number=po['po_number'],vendor_code=po['vendor_code'],currency='INR',status='OPEN',total_authorized_amount=1000,remaining_balance=1000));db.flush()
                db.add(WorkOrderLineSnapshot(id='accept-pol-'+str(i),org_id=org,po_id=pid,line_number=1,item_code='SERVICE',description=po['lines'][0]['description'],authorized_quantity=10,contracted_unit_rate=100,authorized_line_total=1000))
                db.add(GoodsReceiptSnapshot(id=grn,org_id=org,grn_number=po['grn_number'],po_number=po['po_number'],received_date=dt.datetime(2026,11,6)));db.flush()
                db.add(GoodsReceiptLineSnapshot(id='accept-grnl-'+str(i),org_id=org,grn_id=grn,po_line_number=1,accepted_quantity=10,rejected_quantity=0))
                if po['qc_status']:
                    db.add(QualityControlSnapshot(id='accept-qc-'+str(i),org_id=org,grn_number=po['grn_number'],qc_certificate_number='ACCEPT-QC-'+str(i),overall_status='ACCEPTED'))
            db.commit()
        state['sources_seeded']=True;state_path.write_text(json.dumps(state))
    from backend.main import app
    from backend.core.database import SessionLocal
    from backend.core.storage import get_storage_adapter, SupabaseStorageAdapter
    assert type(get_storage_adapter()) is SupabaseStorageAdapter, 'Provider acceptance cannot use test/mock storage'
    result['storage_adapter']='SupabaseStorageAdapter'
    result['application_environment']='staging'
    phase='real identity authentication and runtime role'
    with SessionLocal() as db:
        role=db.execute(text('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
        assert tuple(role)==('ap_app_user',False,False)
        result['runtime_role']={'name':role[0],'superuser':role[1],'bypassrls':role[2]}
    identities={x['tenant']:x for x in state['test_identities']}
    headers={key:{'Authorization':'Bearer '+item['access_token']} for key,item in identities.items()}
    with TestClient(app) as client, httpx.Client(timeout=25,follow_redirects=False) as remote:
        for tenant in ('a','b'):
            response=client.get('/api/v1/auth/me',headers=headers[tenant]);assert response.status_code==200
            profile=response.json();assert profile['id']==identities[tenant]['id'] and profile['org_id']==orgs[tenant]
            result['checks'].append({'operation':'real signed provider JWT + membership tenant '+tenant,'status':'PASS'})
        accepted={}
        phase='authenticated private uploads'
        for case in manifest['cases']:
            start=time.perf_counter(); path=ROOT/'output/pdf/ps1-acceptance-20261106'/case['pdf']; content=path.read_bytes()
            with SessionLocal() as db:
                set_tenant_context(db,orgs['a']);before_jobs=db.scalar(select(func.count()).select_from(IngestionJob))
            cached=state.get('accepted_docs',{}).get(case['case'])
            if cached:
                data=cached['data'];row=dict(cached['row']);row['reused_owned_upload_from_previous_attempt']=True
                response=None
            else:
                response=client.post('/api/v1/connections/upload',headers=headers['a'],files={'file':(path.name,content,'application/pdf')})
                row={'case':case['case'],'upload_http_status':response.status_code,'upload_ms':round((time.perf_counter()-start)*1000,2)}
                if case['case']!='identical_duplicate' and response.status_code==200:
                    state.setdefault('accepted_docs',{})[case['case']]={'data':response.json(),'row':dict(row)};state_path.write_text(json.dumps(state))
            if case['case']=='identical_duplicate':
                assert response.status_code==409
                assert response.json()['invoice_id']==accepted['happy']['invoice_id']
                with SessionLocal() as db:
                    set_tenant_context(db,orgs['a'])
                    assert db.scalar(select(func.count()).select_from(IngestionJob))==before_jobs
                row.update(observed='DUPLICATE_DETECTED',expected_matched=True,new_job_count=0,additional_model_calls=0)
            else:
                if response is not None:
                    assert response.status_code==200;data=response.json()
                accepted[case['case']]=data
                run=client.get('/api/v1/invoices/'+data['invoice_id']+'/processing',headers=headers['a']);assert run.status_code==200
                job=run.json()['jobs'][0];assert job['status'] in ('QUEUED','COMPLETED','FAILED')
                assert (job['events'][0]['stage'],job['events'][0]['status'])==('INTAKE','QUEUED')
                expected=hashlib.sha256(content).hexdigest()
                assert data['sha256']==expected
                start=time.perf_counter()
                download=client.get('/api/v1/documents/'+data['document_id']+'/download',headers=headers['a'])
                assert download.status_code==200 and hashlib.sha256(download.content).hexdigest()==expected
                preview=client.get('/api/v1/documents/'+data['document_id']+'/preview',headers=headers['a'])
                assert preview.status_code==200 and hashlib.sha256(preview.content).hexdigest()==expected
                signed=client.get('/api/v1/documents/'+data['document_id']+'/signed-url',headers=headers['a']);assert signed.status_code==200
                signed_bytes=remote.get(signed.json()['signed_url']);assert signed_bytes.status_code==200
                assert hashlib.sha256(signed_bytes.content).hexdigest()==expected
                unsigned=remote.get(state['supabase_url']+'/storage/v1/object/public/'+state['bucket']+'/'+data['storage_key'])
                assert unsigned.status_code != 200
                row.update(invoice_id=data['invoice_id'],document_id=data['document_id'],sha256=expected,
                    integrity_verified=True,private_unsigned_http_status=unsigned.status_code,
                    readback_checks_ms=round((time.perf_counter()-start)*1000,2),persisted_events=job['events'],
                    observed='QUEUED_INTAKE_ONLY',expected_matched=None,
                    blocker='Isolated extraction credential cannot be provisioned with expired AWS sessions.')
            result['cases'].append(row);save()
        phase='cross-tenant denial'
        doc=accepted['happy']['document_id']; inv=accepted['happy']['invoice_id']
        for endpoint in [f'/api/v1/invoices/{inv}',f'/api/v1/invoices/{inv}/processing',f'/api/v1/documents/{doc}',f'/api/v1/documents/{doc}/download',f'/api/v1/documents/{doc}/preview',f'/api/v1/documents/{doc}/signed-url']:
            denied=client.get(endpoint,headers=headers['b']);assert denied.status_code in (403,404)
            result['checks'].append({'endpoint':endpoint,'cross_tenant_http_status':denied.status_code,'status':'PASS'})
        denied=client.get(f'/api/v1/invoices/{inv}/processing');assert denied.status_code==401
        result['checks'].append({'operation':'anonymous run access denial','http_status':denied.status_code,'status':'PASS'})
        denied=client.get('/api/v1/auth/me',headers={**headers['a'],'X-Tenant-ID':orgs['b']});assert denied.status_code==403
        result['checks'].append({'operation':'forged workspace header denial','http_status':denied.status_code,'status':'PASS'})
        with SessionLocal() as db:
            set_tenant_context(db,orgs['b'])
            assert db.scalars(select(Document)).all()==[] and db.scalars(select(Invoice)).all()==[]
            result['checks'].append({'operation':'non-bypass PostgreSQL tenant B cannot read tenant A invoice/documents','status':'PASS'})
        with SessionLocal() as db:
            set_tenant_context(db,orgs['a'])
            assert db.scalar(select(func.count()).select_from(IngestionJob))==4
            if not args.full: assert db.scalar(select(func.count()).select_from(AuditEvent))==4
        if args.full:
            phase='live authenticated processing'
            from concurrent.futures import ThreadPoolExecutor
            from decimal import Decimal
            for case in manifest['cases']:
                if case['case']=='identical_duplicate': continue
                current_case=case['case'];data=accepted[current_case]
                row=next(x for x in result['cases'] if x['case']==current_case)
                row.pop('blocker',None)
                run_path='/api/v1/invoices/'+data['invoice_id']+'/processing'
                run=client.get(run_path,headers=headers['a']).json();job=run['jobs'][0]
                polls=[];started=time.perf_counter()
                if job['status']!='COMPLETED':
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future=executor.submit(client.post,'/api/v1/documents/process-next',headers=headers['a'])
                        while not future.done():
                            live=client.get(run_path,headers=headers['a']);assert live.status_code==200
                            snapshot=live.json()['jobs'][0]
                            polls.append(dict(status=snapshot['status'],event_count=len(snapshot['events']),last_stage=snapshot['events'][-1]['stage'],last_status=snapshot['events'][-1]['status']))
                            time.sleep(.3)
                        dispatch=future.result();assert dispatch.status_code==200
                run=client.get(run_path,headers=headers['a']).json();job=run['jobs'][0]
                row['processing_wall_ms']=round((time.perf_counter()-started)*1000,2);row['poll_observations']=polls;row['persisted_events']=job['events'];row['job_status']=job['status']
                if job['status']!='COMPLETED':
                    row.update(observed=job['status'],expected_matched=False)
                    result.update(status='PROCESSING_FAILED',failed_case=current_case);save()
                    raise RuntimeError('Real processing failed; preserve evidence and inspect before retry')
                with SessionLocal() as db:
                    set_tenant_context(db,orgs['a']);inv=db.get(Invoice,data['invoice_id'])
                    match=db.scalar(select(MatchRun).where(MatchRun.invoice_id==inv.id).order_by(MatchRun.evaluated_at.desc()))
                    gates=db.scalars(select(MatchGateCheck).where(MatchGateCheck.match_run_id==match.id).order_by(MatchGateCheck.gate_number)).all()
                    row.update(observed=inv.decision,stage=inv.stage,gates=[dict(number=g.gate_number,status=g.status,notes=g.evidence_notes) for g in gates],expected_matched=inv.decision==case['expected']['decision'] and inv.stage==case['expected']['stage'])
                    assert Decimal(str(inv.total_amount))==Decimal(str(case['ground_truth']['grand_total']))
                assert [e['sequence'] for e in job['events']]==list(range(1,len(job['events'])+1))
                outcome=job['events'][-1];assert outcome['status']=='RECORDED' and outcome['outcome']['decision']==row['observed']
                row['recorded_outcome_verified']=True;save()
            result['status']='PASS' if all(x['expected_matched'] for x in result['cases']) else 'EXPECTATION_FAILURE'
        else:
            result['status']='PARTIAL_IDENTITY_STORAGE_INTAKE_PASS_EXTRACTION_BLOCKED'
        result['source_records_seeded']=True
        result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat();save()
    admin.dispose()
except Exception as exc:
    result.update(status='FAILED',failed_phase=phase,failure_type=type(exc).__name__)
    save()
    raise
