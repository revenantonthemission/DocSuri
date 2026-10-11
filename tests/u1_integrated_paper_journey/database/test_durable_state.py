from __future__ import annotations

import json
import subprocess
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

pytestmark = pytest.mark.u1_database


@pytest.fixture
def job(connect,identities):
    job_id=uuid4()
    with connect('assistance') as conn:
        conn.execute("INSERT INTO assistance.admission(operation_id,account_id,intent_hash,intent,disposition) VALUES(%s,%s,%s,'{}','accepted')",(job_id,identities['a'],'b'*64))
        conn.execute("INSERT INTO assistance.job(id,account_id,authority_revision,version_id,source_hash,input_hash,payload,glossary_revision,glossary_snapshot,reservation_id) VALUES(%s,%s,%s,%s,%s,%s,'{}',%s,'[]',%s)",
                     (job_id,identities['a'],identities['revision'],identities['version'],'a'*64,'b'*64,'empty:'+str(identities['a'])+':local-v1',uuid4()))
    return job_id


def claim(conn,job,worker):
    with conn.cursor(row_factory=dict_row) as cursor:
        return cursor.execute('SELECT * FROM assistance.acquire_claim(%s,%s)',(job,worker)).fetchone()


def test_selected_database_and_persistent_storage(connect,realm):
    with connect('operations') as conn:
        assert conn.execute('SHOW server_version').fetchone()[0].split()[0]=='16.15'
        for setting in ('fsync','synchronous_commit','full_page_writes','data_checksums'):
            assert conn.execute('SHOW '+setting).fetchone()[0]=='on'
        assert conn.execute('SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()[0] is False
    profile=realm[0]
    manifest=json.loads((profile.root/'environment.json').read_text())
    result=subprocess.run(['docker','inspect','--format','{{json .Mounts}}',manifest['container']],capture_output=True,text=True,check=True,timeout=5)
    mounts=json.loads(result.stdout)
    assert any(m['Type']=='volume' and m['Name']==manifest['volume'] and m['Destination']=='/var/lib/postgresql/data' for m in mounts)


@pytest.mark.parametrize('revision',[None,uuid4()])
def test_execution_authority_requires_exact_nonnull_revision(connect,identities,revision):
    with connect('assistance') as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT accounts.guard_execution(%s,%s)',(identities['a'],revision))
    with connect('assistance') as conn:
        conn.execute('SELECT accounts.guard_execution(%s,%s)',(identities['a'],identities['revision']))


@pytest.mark.parametrize('field,value',[('paper_id','other'),('source_hash','c'*64),('private_path','different'),('content',Jsonb({'changed':True}))])
def test_source_binding_cannot_be_rebound(connect,identities,field,value):
    with connect('corpus') as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(psycopg.sql.SQL('UPDATE corpus.version SET {}=%s WHERE id=%s').format(psycopg.sql.Identifier(field)),(value,identities['version']))


def test_saved_reference_must_match_exact_paper(connect,identities):
    with connect('library') as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('INSERT INTO library.saved_paper(account_id,paper_id,version_id) VALUES(%s,%s,%s)',(identities['a'],'unrelated-paper',identities['version']))


def test_acceptance_time_payload_and_glossary_are_immutable(connect,identities,job):
    conn=connect('assistance')
    before=conn.execute('SELECT accepted_at FROM assistance.job WHERE id=%s',(job,)).fetchone()[0]
    conn.commit()
    for statement in ("accepted_at=clock_timestamp()", "payload='{}'::jsonb || '{\"changed\":true}'::jsonb", "glossary_revision='other'"):
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute('UPDATE assistance.job SET '+statement+' WHERE id=%s',(job,))
        conn.rollback()
    receipt=claim(conn,job,uuid4()); conn.commit()
    assert receipt['accepted_at']==before
    assert conn.execute('SELECT count(*) FROM assistance.event WHERE job_id=%s',(job,)).fetchone()[0]==2


def test_empty_glossary_read_is_stable_and_does_not_create(connect,identities):
    with connect('assistance') as conn:
        first=conn.execute('SELECT * FROM assistance.read_glossary(%s)',(identities['a'],)).fetchone()
        second=conn.execute('SELECT * FROM assistance.read_glossary(%s)',(identities['a'],)).fetchone()
        assert first==second and first[0].startswith('empty:') and first[1]==[]
        assert conn.execute('SELECT count(*) FROM assistance.glossary WHERE account_id=%s',(identities['a'],)).fetchone()[0]==0


@pytest.mark.parametrize('missing',['worker','lease','fence'])
def test_null_claim_inputs_cannot_authorize(connect,job,missing):
    conn=connect('assistance'); c=claim(conn,job,uuid4()); conn.commit()
    values={'worker':c['worker_id'],'lease':c['lease_id'],'fence':c['fence']}; values[missing]=None
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute('SELECT * FROM assistance.guard_claim(%s,%s,%s,%s)',(job,values['worker'],values['lease'],values['fence']))


def test_incomplete_running_claim_is_rejected_at_storage_boundary(connect,job):
    with connect('assistance') as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE assistance.job SET state='running' WHERE id=%s",(job,))


def test_replacement_fences_old_worker_and_renewal_is_separate(connect,job):
    conn=connect('assistance'); worker=uuid4(); original=claim(conn,job,worker); conn.commit()
    with conn.cursor(row_factory=dict_row) as cursor:
        renewed=cursor.execute('SELECT * FROM assistance.renew_claim(%s,%s,%s,%s,%s)',
                               (job,worker,original['lease_id'],original['fence'],original['lease_revision'])).fetchone()
    conn.commit()
    assert renewed['revision']==original['revision'] and renewed['sequence']==original['sequence']
    assert renewed['lease_revision']!=original['lease_revision']
    # Deliberate clock-state fault on this owned job; normal work uses DB time.
    conn.execute("UPDATE assistance.job SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",(job,)); conn.commit()
    replacement=claim(conn,job,uuid4()); conn.commit()
    assert replacement['fence']==original['fence']+1
    for function in ('guard_claim','renew_claim'):
        args=(job,worker,original['lease_id'],original['fence'])
        if function=='renew_claim': args+= (renewed['lease_revision'],)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT * FROM assistance.'+function+'('+','.join(['%s']*len(args))+')',args)
        conn.rollback()
    conn.execute('SELECT * FROM assistance.guard_claim(%s,%s,%s,%s)',(job,replacement['worker_id'],replacement['lease_id'],replacement['fence']))


def test_history_clear_suppresses_delayed_fact_and_preserves_receipt(connect,identities):
    conn=connect('library'); account=identities['a']; session=identities['session']
    generation,revision=conn.execute('SELECT generation,revision FROM library.history_boundary WHERE account_id=%s',(account,)).fetchone()
    completed=conn.execute('SELECT clock_timestamp()').fetchone()[0]; key=uuid4()
    cleared=conn.execute('SELECT library.clear_history(%s,%s,%s,%s)',(account,session,key,revision)).fetchone()[0]
    conn.commit()
    assert conn.execute('SELECT library.accept_history_fact(%s,%s,%s,%s,%s,%s)',(account,session,uuid4(),generation,completed,Jsonb({'q':'old'}))).fetchone()[0] is False
    current_time=conn.execute('SELECT clock_timestamp()').fetchone()[0]
    assert conn.execute('SELECT library.accept_history_fact(%s,%s,%s,%s,%s,%s)',(account,session,uuid4(),cleared['generation'],current_time,Jsonb({'q':'new'}))).fetchone()[0] is True
    conn.commit()
    assert conn.execute('SELECT library.clear_history(%s,%s,%s,%s)',(account,session,key,revision)).fetchone()[0]==cleared
