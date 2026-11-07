"""Provision only new labeled acceptance resources; never loads application .env.

Journal is private under ignored scratch. Existing project IDs are excluded.
Run cleanup even after a failed acceptance run; no paid plan change is performed.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import secrets
import subprocess
import time

import httpx
import psycopg
from psycopg import sql

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--owned-root',type=Path,required=True)
p.add_argument('--cleanup',action='store_true')
p.add_argument('--resume',action='store_true',help='Resume this same owned setup journal after an inspected setup failure')
p.add_argument('--evidence-dir',type=Path,default=ROOT/'docs/inspection-evidence/provider-full-20261106')
args=p.parse_args()
owned=args.owned_root.resolve()
assert owned.parent==ROOT/'scratch'
name=(owned/'.owned-by-ps1-acceptance').read_text()
assert name==owned.name and name.startswith('ps1-acceptance-')
state_file=owned/'private-state.json'
evidence=args.evidence_dir.resolve()
assert evidence.parent==ROOT/'docs/inspection-evidence'
evidence.mkdir(exist_ok=True)
assert args.cleanup or args.resume or not (evidence/'setup.json').exists(), 'Use a fresh evidence directory; historical setup evidence must not be overwritten'
state=json.loads(state_file.read_text()) if state_file.exists() else {'run_id':name,'resource_status':'creating','aws_profile':'rag4i-dev'}
flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
def save():state_file.write_text(json.dumps(state))
def aws(*args):
    r=subprocess.run(['aws',*args,'--profile',state['aws_profile'],'--output','json','--no-cli-pager'],capture_output=True,text=True,timeout=45,creationflags=flags)
    if r.returncode: raise RuntimeError('AWS operation failed: '+args[0]+' '+args[1]+'; response withheld')
    return json.loads(r.stdout) if r.stdout.strip() else {}
def supa(*args):
    r=subprocess.run(['cmd','/c','supabase',*args,'--output','json'],capture_output=True,text=True,timeout=90,creationflags=flags)
    if r.returncode: raise RuntimeError('Supabase operation failed: '+args[0]+' '+args[1]+'; response withheld')
    if args[:2]==('projects','delete'):return {'command_completed':True}
    return json.loads(r.stdout) if r.stdout.strip() else {}
def bearer():return {'Authorization':'Bearer '+state['mantle_key']}
base='https://bedrock-mantle.ap-south-1.api.aws/v1'
policy_name='PS1DisposableOnly'
def put_policy(doc):aws('iam','put-user-policy','--user-name',name,'--policy-name',policy_name,'--policy-document',json.dumps(doc))
def policy(statements):return {'Version':'2012-10-17','Statement':statements}
def token_statement():return {'Effect':'Allow','Action':'bedrock-mantle:CallWithBearerToken','Resource':'*','Condition':{'StringEquals':{'aws:RequestedRegion':'ap-south-1'},'DateLessThan':{'aws:CurrentTime':state['permission_expires_at']}}}
if args.cleanup:
    report={'run_id':name,'mantle_project_id':state.get('mantle_project_id'),'mantle_project_archived':bool(state.get('mantle_archived')),'iam_user_and_key_deleted':bool(state.get('iam_user_deleted') and state.get('credential_deleted'))}
    if state.get('mantle_project_id') and not state.get('mantle_archived'):
        assert state['mantle_project_id']!='default'
        put_policy(policy([token_statement(),{'Effect':'Allow','Action':['bedrock-mantle:ArchiveProject','bedrock-mantle:GetProject','bedrock-mantle:ListTagsForResource'],'Resource':state['mantle_project_arn']}]))
        for attempt in range(6):
            r=httpx.post(base+'/organization/projects/'+state['mantle_project_id']+'/archive',headers={**bearer(),'Content-Type':'application/json'},timeout=25)
            if r.status_code==200:break
            time.sleep(3)
        assert r.status_code==200,'Owned Mantle project archive failed'
        state['mantle_archived']=True;save()
        report['mantle_project_archived']=True
        report['mantle_archive_response_status']=r.json().get('status')
        report['mantle_project_id']=state['mantle_project_id']
    if state.get('credential_id') and not state.get('credential_deleted'):
        aws('iam','delete-service-specific-credential','--user-name',name,'--service-specific-credential-id',state['credential_id'])
        state['credential_deleted']=True;save()
    if state.get('iam_user_created') and not state.get('iam_user_deleted'):
        user=aws('iam','get-user','--user-name',name)['User']
        assert user['Arn']==state['iam_user_arn'] and any(t['Key']=='PS1Run' and t['Value']==name for t in user.get('Tags',[]))
        aws('iam','delete-user-policy','--user-name',name,'--policy-name',policy_name)
        aws('iam','delete-user','--user-name',name)
        state['iam_user_deleted']=True;save();report['iam_user_and_key_deleted']=True
    if state.get('project_id') and not state.get('supabase_deleted'):
        projects=supa('projects','list')
        found=[x for x in projects if x['id']==state['project_id']]
        assert state['project_id'] not in state['existing_project_ids']
        if found:
            assert len(found)==1 and found[0]['name']==name
            supa('projects','delete',state['project_id'],'--yes')
        remaining=supa('projects','list')
        assert not any(x['id']==state['project_id'] for x in remaining)
        assert all(any(x['id']==old for x in remaining) for old in state['existing_project_ids'])
        state['supabase_deleted']=True;save();report['supabase_project_deleted']=True;report['existing_project_ids_preserved']=True
    report['resource_status']='cleaned'
    (evidence/'cleanup.json').write_text(json.dumps(report,indent=2)+'\n')
    state_file.write_text(json.dumps({'run_id':name,'resource_status':'deleted','mantle_project_archived':state.get('mantle_archived'),'secrets_removed':True}))
    print(json.dumps(report));raise SystemExit(0)

assert not state_file.exists() or (args.resume and state['resource_status']=='creating'),'New ownership journal or explicit owned setup resume required'
identity=aws('sts','get-caller-identity')
state.update(account=identity['Account'])
state.setdefault('db_password',secrets.token_urlsafe(32))
state.setdefault('permission_expires_at',(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ'))
save()
if not state.get('iam_user_created'):
    user=aws('iam','create-user','--user-name',name,'--tags',json.dumps([{'Key':'PS1Run','Value':name},{'Key':'Environment','Value':'DisposableTest'}]))['User']
    state.update(iam_user_arn=user['Arn'],iam_user_created=True);save()
project_scope='arn:aws:bedrock-mantle:ap-south-1:'+state['account']+':project/*'
put_policy(policy([token_statement(),{'Effect':'Allow','Action':['bedrock-mantle:CreateProject','bedrock-mantle:TagResource'],'Resource':project_scope,'Condition':{'StringEquals':{'aws:RequestTag/PS1Run':name,'aws:RequestedRegion':'ap-south-1'}}},
    {'Effect':'Allow','Action':['bedrock-mantle:ListProjects','bedrock-mantle:GetProject','bedrock-mantle:ListTagsForResource'],'Resource':project_scope,'Condition':{'StringEquals':{'aws:RequestedRegion':'ap-south-1'}}}]))
if not state.get('mantle_key'):
    credential=aws('iam','reset-service-specific-credential','--user-name',name,'--service-specific-credential-id',state['credential_id'])['ServiceSpecificCredential'] if state.get('credential_id') else aws('iam','create-service-specific-credential','--user-name',name,'--service-name','bedrock.amazonaws.com','--credential-age-days','1')['ServiceSpecificCredential']
    state['credential_id']=credential['ServiceSpecificCredentialId'];save()
    state['mantle_key']=credential.get('ServiceApiKeyValue') or credential.get('ServiceCredentialSecret') or credential.get('ServicePassword')
    assert state['mantle_key'],'No service credential value returned'
    save()
for attempt in range(8):
    r=httpx.get(base+'/organization/projects',headers=bearer(),timeout=25)
    if r.status_code==200:break
    time.sleep(3)
assert r.status_code==200,'Cannot reconcile newly owned Mantle project metadata'
existing_owned=[x for x in r.json()['data'] if x.get('name')==name]
assert len(existing_owned)<=1,'Multiple newly-owned projects require explicit reconciliation'
if existing_owned:
    project=existing_owned[0]
else:
    r=httpx.post(base+'/organization/projects',headers=bearer(),json={'name':name,'tags':{'PS1Run':name,'Environment':'DisposableTest'}},timeout=25)
    assert r.status_code==200,f'Mantle project creation HTTP {r.status_code}'
    project=r.json()
assert project['name']==name and project['id']!='default'
state.update(mantle_project_id=project['id'],mantle_project_arn=project['arn']);save()
# The creation endpoint accepted but ignored data_retention_mode. Use the
# project update API and read it back before granting any inference access.
put_policy(policy([token_statement(),{'Effect':'Allow','Action':['bedrock-mantle:UpdateProject','bedrock-mantle:GetProject','bedrock-mantle:ListTagsForResource'],'Resource':project['arn'],'Condition':{'StringEquals':{'aws:RequestedRegion':'ap-south-1'}}}]))
for attempt in range(8):
    retention=httpx.post(base+'/organization/projects/'+project['id'],headers=bearer(),json={'data_retention':{'mode':'none'}},timeout=25)
    if retention.status_code==200:break
    if retention.status_code!=403:break
    time.sleep(3)
assert retention.status_code==200,'Project-only retention update failed'
retention=httpx.get(base+'/organization/projects/'+project['id'],headers=bearer(),timeout=25)
assert retention.status_code==200 and retention.json().get('data_retention')=={'mode':'none'},'Project retention not verified'
state['verified_data_retention']={'mode':'none'};save()
model='qwen.qwen3-235b-a22b-2507-v1:0'
restricted=policy([token_statement(),{'Effect':'Allow','Action':['bedrock-mantle:GetModel','bedrock-mantle:ListModels'],'Resource':project['arn'],'Condition':{'StringEquals':{'aws:RequestedRegion':'ap-south-1'}}},
    {'Effect':'Allow','Action':'bedrock-mantle:CreateInference','Resource':project['arn'],'Condition':{'StringEquals':{'bedrock-mantle:Model':model,'aws:RequestedRegion':'ap-south-1'},'DateLessThan':{'aws:CurrentTime':state['permission_expires_at']}}}])
put_policy(restricted)
(evidence/'extraction-policy.json').write_text(json.dumps(restricted,indent=2)+'\n')
state['model_id']=model
projects=supa('projects','list');state['existing_project_ids']=[x['id'] for x in projects];save()
assert projects and len(set(x['organization_id'] for x in projects))==1
new=supa('projects','create',name,'--org-id',projects[0]['organization_id'],'--region','ap-south-1','--db-password',state['db_password'],'--yes')
state['project_id']=new['id'];assert state['project_id'] not in state['existing_project_ids'];save()
state['supabase_url']='https://'+state['project_id']+'.supabase.co'
keys=supa('projects','api-keys','--project-ref',state['project_id'])
for key in keys:
    if key['name'] in ('anon','service_role'):state[key['name']+'_key']=key['api_key']
state['own_database_host']='db.'+state['project_id']+'.supabase.co'
state['own_database_user']='postgres';state['bucket']='ps1-'+name.rsplit('-',1)[-1];state['application_database']='ps1_acceptance_'+name.rsplit('-',1)[-1];save()
admin_headers={'apikey':state['service_role_key'],'Authorization':'Bearer '+state['service_role_key']}
for attempt in range(12):
    try:
        r=httpx.get(state['supabase_url']+'/auth/v1/settings',headers={'apikey':state['anon_key']},timeout=15)
        if r.status_code==200:break
    except httpx.RequestError:pass
    time.sleep(5)
assert r.status_code==200,'New project not ready'
r=httpx.post(state['supabase_url']+'/storage/v1/bucket',headers=admin_headers,json={'id':state['bucket'],'name':state['bucket'],'public':False,'file_size_limit':1048576,'allowed_mime_types':['application/pdf']},timeout=25)
assert r.status_code==200
state['test_identities']=[];save()
for tenant in ('a','b'):
    email='ps1-'+tenant+'-'+name.rsplit('-',1)[-1]+'@example.test';password=secrets.token_urlsafe(32)
    r=httpx.post(state['supabase_url']+'/auth/v1/admin/users',headers=admin_headers,json={'email':email,'password':password,'email_confirm':True,'app_metadata':{'purpose':name}},timeout=25);assert r.status_code==200
    uid=r.json()['id']
    r=httpx.post(state['supabase_url']+'/auth/v1/token?grant_type=password',headers={'apikey':state['anon_key']},json={'email':email,'password':password},timeout=25);assert r.status_code==200
    state['test_identities'].append({'tenant':tenant,'id':uid,'email':email,'password':password,'access_token':r.json()['access_token']});save()
with psycopg.connect(host=state['own_database_host'],dbname='postgres',user='postgres',password=state['db_password'],sslmode='require',connect_timeout=15,autocommit=True) as db:
    db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(state['application_database'])))
state['resource_status']='created';save()
report={'run_id':name,'status':'created','project_id':state['project_id'],'mantle_project_id':state['mantle_project_id'],'dedicated_iam_user':name,'identity_verified':True,'permission_expires_at':state['permission_expires_at'],'api_key_expiry_days':1}
(evidence/'setup.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
