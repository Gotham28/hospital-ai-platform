"""Isolated evidence: no dotenv, hosted DB, real recipients or network sends.

Run: python run_meta_whatsapp_test.py
Synthetic template fixtures are not approved production copy.
"""
import os
# Guard the actual application engine before importing settings/dependencies.
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['JWT_SECRET'] = 'synthetic-test-jwt-secret'

import hashlib
import hmac
import importlib.util
import json
import logging
import tempfile
import threading
import unittest
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Dotenv source constructors read files before __call__; suppress that read itself.
with patch('pydantic_settings.DotEnvSettingsSource._read_env_files', return_value={}):
    from app.core.config import Settings
    from app.db.base import Base
    from app.models.hospital import Hospital
    from app.models.whatsapp_log import WhatsAppLog
    from app.services import meta_whatsapp as service
    from app.api.deps import get_db
    from app.api.v1.endpoints import whatsapp, whatsapp_webhook
    from app.db.session import engine as application_engine
assert str(application_engine.url) == 'sqlite://', 'Application engine must stay synthetic'



class MetaWelcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + str(Path(self.temp.name) / 'test.db'), connect_args={'check_same_thread': False, 'timeout': 10})
        Base.metadata.create_all(self.engine, tables=[Hospital.__table__, WhatsAppLog.__table__])
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.db.add_all([Hospital(id=1, name='Synthetic Hospital One', slug='synthetic-one', is_active=True), Hospital(id=2, name='Synthetic Hospital Two', slug='synthetic-two', is_active=True)])
        self.db.commit()
        self.config = Settings(
            _env_file=None, META_WHATSAPP_ENABLED=True,
            META_WHATSAPP_ACCESS_TOKEN='synthetic-token', META_WHATSAPP_PHONE_NUMBER_ID='123456',
            META_WHATSAPP_GRAPH_VERSION='v99.0', META_WHATSAPP_APP_SECRET='synthetic-app-secret',
            META_WHATSAPP_VERIFY_TOKEN='synthetic-verify', META_WHATSAPP_TEMPLATE_EN='synthetic_welcome_en',
            META_WHATSAPP_TEMPLATE_ML='synthetic_welcome_ml',
            META_WHATSAPP_TEMPLATE_BODY_EN='SYNTHETIC TEST {{1}} URL {{2}}',
            META_WHATSAPP_TEMPLATE_BODY_ML='പരീക്ഷണം {{1}} ലിങ്ക് {{2}}',
            PUBLIC_PATIENT_BASE_URL='https://example.test',
            META_WHATSAPP_ENABLED_HOSPITAL_SLUGS='synthetic-one,synthetic-two',
            WHATSAPP_RECIPIENT_HASH_SECRET='synthetic-hash-secret-' + 'x'*32,
        )
        self.old_config = {}
        from app.core.config import settings
        self.global_settings = settings
        for key in Settings.model_fields:
            if key.startswith(('META_WHATSAPP_', 'PUBLIC_PATIENT_', 'WHATSAPP_RECIPIENT_')):
                self.old_config[key] = getattr(settings, key)
                setattr(settings, key, getattr(self.config, key))
        app = FastAPI()
        app.include_router(whatsapp.router, prefix='/api/v1/hospitals/{hospital_id}/whatsapp')
        app.include_router(whatsapp_webhook.router, prefix='/api/v1/whatsapp')
        def db_override():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = db_override
        self.client = TestClient(app)
        self.sender = patch.object(service, '_post_meta', return_value=httpx.Response(200, json={'messages':[{'id':'wamid.synthetic'}]})).start()
        self.headers = self.auth(1)

    def tearDown(self):
        patch.stopall()
        self.client.close()
        for key, value in self.old_config.items():
            setattr(self.global_settings, key, value)
        self.db.close()
        self.engine.dispose()
        self.temp.cleanup()

    def auth(self, tenant):
        token = jwt.encode({'sub':'synthetic-staff', 'hospital_id':tenant, 'role':'staff'}, 'synthetic-test-jwt-secret', algorithm='HS256')
        return {'Authorization':'Bearer '+token}

    def send(self, **kwargs):
        args=dict(db=self.db, hospital_id=1, phone='9876543210', language='en', consent_confirmed=True, request_id=uuid4(), actor='synthetic-staff', config=self.config)
        args.update(kwargs)
        return service.send_welcome(**args)

    def callback(self, status='delivered', message_id='wamid.synthetic', **kwargs):
        value={'metadata':{'phone_number_id':self.config.META_WHATSAPP_PHONE_NUMBER_ID}, 'statuses':[{'id':message_id,'status':status,'timestamp':str(int(datetime.now(timezone.utc).timestamp()))}]}
        value.update(kwargs)
        return {'object':'whatsapp_business_account','entry':[{'changes':[{'field':'messages','value':value}]}]}

    def post_callback(self, payload, signature=True):
        raw=json.dumps(payload).encode()
        digest='sha256='+hmac.new(self.config.META_WHATSAPP_APP_SECRET.encode(),raw,hashlib.sha256).hexdigest()
        return self.client.post('/api/v1/whatsapp/webhook',content=raw,headers={'X-Hub-Signature-256':digest if signature else 'sha256=wrong'})


    def test_import_bootstrap_engine_and_runtime_manifests(self):
        self.assertEqual(str(application_engine.url), 'sqlite://')
        root_manifest=Path('../requirements.txt').read_bytes()
        encoding='utf-16' if root_manifest.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
        self.assertIn('phonenumbers>=9,<10',root_manifest.decode(encoding))
        self.assertIn('phonenumbers>=9,<10',Path('requirements.txt').read_text())
        self.assertEqual(service.phonenumbers.format_number(service.phonenumbers.parse('9876543210','IN'),service.phonenumbers.PhoneNumberFormat.E164), '+919876543210')

    def test_replay_ignores_mutable_send_setup(self):
        key=uuid4(); first=self.send(request_id=key)
        hospital=self.db.get(Hospital,1); hospital.name='Changed Synthetic Name'; self.db.commit()
        self.config.PUBLIC_PATIENT_BASE_URL='https://changed.example.test'
        self.config.META_WHATSAPP_TEMPLATE_EN='changed_en'
        self.config.META_WHATSAPP_TEMPLATE_BODY_EN='Changed {{1}} {{2}}'
        self.assertEqual(first,self.send(request_id=key))
        self.config.META_WHATSAPP_ENABLED=False
        self.config.META_WHATSAPP_ACCESS_TOKEN=''
        self.assertEqual(first,self.send(request_id=key))
        with self.assertRaises(service.WelcomeError) as conflict: self.send(request_id=key,language='ml')
        self.assertEqual(conflict.exception.code,'request_conflict')
        response=self.client.post('/api/v1/hospitals/1/whatsapp/send-welcome',headers=self.auth(2),json={'phone':'9876543210','language':'en','consent_confirmed':True,'request_id':str(key)})
        self.assertEqual(response.status_code,403)
        self.sender.assert_called_once()

    def test_actual_insert_collision_recovers_one_saved_request(self):
        from sqlalchemy.orm import Session, Query
        from sqlalchemy.exc import IntegrityError
        barrier=threading.Barrier(2); local=threading.local(); collisions=[]; results=[]; errors=[]
        real_first=Query.first; real_commit=Session.commit
        def simultaneous_miss(query):
            result=real_first(query)
            if query.column_descriptions[0].get('entity') is WhatsAppLog and not getattr(local,'saw_request',False):
                local.saw_request=True
                self.assertIsNone(result)
                barrier.wait(timeout=5)
            return result
        def record_commit(session):
            try: return real_commit(session)
            except IntegrityError:
                collisions.append(True)
                raise
        key=uuid4()
        def worker():
            with self.Session() as db:
                try: results.append(self.send(db=db,request_id=key))
                except Exception as error: errors.append(error)
        with patch.object(Query,'first',simultaneous_miss), patch.object(Session,'commit',record_commit):
            threads=[threading.Thread(target=worker) for _ in range(2)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertFalse(errors)
        self.assertEqual(collisions,[True])
        self.sender.assert_called_once()
        self.assertEqual(len(results),2)
        self.assertEqual(results[0]['message_id'],results[1]['message_id'])
        self.assertEqual(self.db.query(WhatsAppLog).count(),1)

    def test_equal_second_provider_events_do_not_use_submission_microseconds(self):
        for index,order in enumerate([['sent','failed'],['failed','sent']]):
            self.sender.return_value=httpx.Response(200,json={'messages':[{'id':f'wamid.equal.{index}'}]})
            result=self.send(); row=self.db.get(WhatsAppLog,result['message_id'])
            second=int(datetime.now(timezone.utc).timestamp())
            row.status_updated_at=datetime.fromtimestamp(second,timezone.utc).replace(microsecond=900000); self.db.commit()
            for status in order:
                payload=self.callback(status,message_id=row.provider_message_id)
                payload['entry'][0]['changes'][0]['value']['statuses'][0]['timestamp']=str(second)
                service.apply_statuses(self.db,payload,self.config)
            self.assertEqual(row.status,'failed')
            self.assertEqual(row.provider_event_at.replace(tzinfo=timezone.utc),datetime.fromtimestamp(second,timezone.utc))
            for status in ['delivered','read','failed','sent']:
                payload=self.callback(status,message_id=row.provider_message_id)
                payload['entry'][0]['changes'][0]['value']['statuses'][0]['timestamp']=str(second)
                service.apply_statuses(self.db,payload,self.config)
            self.assertEqual(row.status,'read')

    def test_phone_normalization(self):
        self.assertEqual(service.normalize_phone('9876543210'), '+919876543210')
        self.assertEqual(service.normalize_phone('+91 98765 43210'), '+919876543210')
        self.assertEqual(service.normalize_phone('+1 202-555-0123'), '+12025550123')
        for value in ['123', 'name', '+91 1111111111', '9876543210 ext 12']:
            with self.subTest(value=value), self.assertRaises(service.WelcomeError): service.normalize_phone(value)

    def test_both_template_payloads(self):
        for language, code in [('en','en_US'),('ml','ml')]:
            self.sender.return_value=httpx.Response(200,json={'messages':[{'id':'wamid.'+language}]})
            result=self.send(language=language)
            self.assertEqual(result['status'],'accepted')
            url,payload,_=self.sender.call_args.args
            self.assertEqual(url,'https://graph.facebook.com/v99.0/123456/messages')
            self.assertEqual(payload['to'],'919876543210')
            self.assertEqual(payload['template']['language']['code'],code)
            parameters=payload['template']['components'][0]['parameters']
            self.assertEqual([p['text'] for p in parameters],['Synthetic Hospital One','https://example.test/p/synthetic-one'])
            self.assertNotIn('body',payload)

    def test_missing_permission_has_no_side_effect(self):
        with self.assertRaises(service.WelcomeError): self.send(consent_confirmed=False)
        self.sender.assert_not_called()
        self.assertEqual(self.db.query(WhatsAppLog).count(),0)

    def test_incomplete_config_fails_closed(self):
        for key,value in [('META_WHATSAPP_ENABLED',False),('META_WHATSAPP_ACCESS_TOKEN',''),('PUBLIC_PATIENT_BASE_URL','http://example.test'),('PUBLIC_PATIENT_BASE_URL','https://example.test/path'),('META_WHATSAPP_ENABLED_HOSPITAL_SLUGS',''),('META_WHATSAPP_TEMPLATE_BODY_ML',''),('WHATSAPP_RECIPIENT_HASH_SECRET','short')]:
            with self.subTest(key=key,value=value):
                old=getattr(self.config,key); setattr(self.config,key,value)
                try:
                    with self.assertRaises(service.WelcomeError): self.send()
                finally: setattr(self.config,key,old)
        self.sender.assert_not_called()

    def test_preview_is_only_configured_copy_and_correct_link(self):
        info=service.welcome_config(self.db,1,self.config)
        self.assertEqual(info['templates']['en']['preview'],'SYNTHETIC TEST Synthetic Hospital One URL https://example.test/p/synthetic-one')
        self.assertNotIn('synthetic-token',json.dumps(info))

    def test_replay_and_conflict(self):
        key=uuid4(); first=self.send(request_id=key)
        self.assertEqual(first,self.send(request_id=key))
        for kwargs in [{'phone':'+12025550123'},{'language':'ml'}]:
            with self.assertRaises(service.WelcomeError) as error: self.send(request_id=key,**kwargs)
            self.assertEqual(error.exception.code,'request_conflict')
        self.assertEqual(self.sender.call_count,1)

    def test_concurrent_same_key_never_sends_twice(self):
        entered=threading.Event(); release=threading.Event(); results=[]; errors=[]
        def slow(*args):
            entered.set(); release.wait(5)
            return httpx.Response(200,json={'messages':[{'id':'wamid.concurrent'}]})
        self.sender.side_effect=slow
        key=uuid4()
        def worker():
            with self.Session() as db:
                try: results.append(self.send(db=db,request_id=key))
                except Exception as error: errors.append(error)
        thread=threading.Thread(target=worker); thread.start()
        self.assertTrue(entered.wait(5))
        worker(); release.set(); thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(self.sender.call_count,1)
        self.assertEqual({row['message_id'] for row in results}, {results[0]['message_id']})

    def test_privacy_and_sanitized_rejection(self):
        self.sender.return_value=httpx.Response(400,json={'error':{'code':131026,'message':'RAW 9876543210 synthetic-token'}})
        stream=StringIO(); handler=logging.StreamHandler(stream); logging.getLogger().addHandler(handler)
        try: result=self.send()
        finally: logging.getLogger().removeHandler(handler)
        row=self.db.query(WhatsAppLog).one()
        persisted=' '.join(str(value) for key,value in row.__dict__.items() if not key.startswith('_'))
        self.assertEqual(result['error_code'],'meta_131026')
        self.assertEqual(row.status,'failed')
        self.assertIsNotNone(row.consent_confirmed_at)
        for forbidden in ['9876543210','synthetic-token','synthetic-staff','RAW','SYNTHETIC TEST']:
            self.assertNotIn(forbidden,persisted+stream.getvalue()+json.dumps(result))

    def test_unknown_timeout_and_replay(self):
        self.sender.side_effect=httpx.ReadTimeout('raw 9876543210')
        key=uuid4(); first=self.send(request_id=key)
        self.assertEqual(first['status'],'unknown')
        self.assertEqual(self.send(request_id=key)['status'],'unknown')
        self.assertEqual(self.sender.call_count,1)

    def test_bad_success_and_server_errors_are_unknown(self):
        for response in [httpx.Response(200,json={}),httpx.Response(200,text='not-json'),httpx.Response(503,json={'error':{'message':'raw'}})]:
            self.sender.return_value=response
            self.assertEqual(self.send()['status'],'unknown')

    def test_initial_persistence_failure_prevents_send(self):
        from sqlalchemy.exc import OperationalError
        with patch.object(self.db,'commit',side_effect=OperationalError('sql',{},Exception('raw'))):
            with self.assertRaises(service.WelcomeError) as error: self.send()
        self.assertEqual(error.exception.code,'storage_unavailable')
        self.sender.assert_not_called()

    def test_post_send_persistence_failure_is_ambiguous(self):
        from sqlalchemy.exc import OperationalError
        original=self.db.commit; count=0
        def commit():
            nonlocal count
            count+=1
            if count==2: raise OperationalError('sql',{},Exception('raw'))
            return original()
        key=uuid4()
        with patch.object(self.db,'commit',side_effect=commit):
            with self.assertRaises(service.WelcomeError) as error: self.send(request_id=key)
        self.assertEqual(error.exception.code,'submission_unknown')
        self.send(request_id=key)
        self.assertEqual(self.sender.call_count,1)

    def test_auth_tenant_scope_and_non_echoing_validation(self):
        path='/api/v1/hospitals/1/whatsapp/send-welcome'
        body={'phone':'9876543210','language':'en','consent_confirmed':True,'request_id':str(uuid4())}
        self.assertEqual(self.client.post(path,json=body).status_code,401)
        self.assertEqual(self.client.post(path,json=body,headers=self.auth(2)).status_code,403)
        self.assertEqual(self.client.get('/api/v1/hospitals/1/whatsapp/welcome-config',headers=self.auth(None)).status_code,403)
        response=self.client.post(path,json={**body,'request_id':'RAW-9876543210'},headers=self.headers)
        self.assertEqual(response.status_code,422)
        self.assertNotIn('9876543210',response.text)
        self.sender.assert_not_called()
        response=self.client.post(path,json=body,headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'accepted')
        log_id=response.json()['message_id']
        foreign=self.client.get(f'/api/v1/hospitals/2/whatsapp/messages/{log_id}',headers=self.auth(2))
        self.assertEqual(foreign.status_code,404)

    def test_webhook_challenge_and_signature(self):
        path='/api/v1/whatsapp/webhook'
        response=self.client.get(path,params={'hub.mode':'subscribe','hub.verify_token':'synthetic-verify','hub.challenge':'synthetic-challenge'})
        self.assertEqual(response.text,'synthetic-challenge')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get(path,params={'hub.mode':'subscribe','hub.verify_token':'wrong','hub.challenge':'x'}).status_code,403)
        self.send()
        self.assertEqual(self.post_callback(self.callback(),signature=False).status_code,403)
        self.assertEqual(self.post_callback(self.callback()).status_code,200)
        self.db.expire_all()
        self.assertEqual(self.db.query(WhatsAppLog).one().status,'delivered')

    def test_sender_mismatch_cannot_update(self):
        self.send()
        self.assertEqual(self.post_callback(self.callback(metadata={'phone_number_id':'other'})).status_code,403)
        self.db.expire_all(); self.assertEqual(self.db.query(WhatsAppLog).one().status,'accepted')

    def test_duplicate_out_of_order_and_failure_events(self):
        self.send()
        for status in ['delivered','delivered','sent','failed','read','delivered','failed']:
            service.apply_statuses(self.db,self.callback(status),self.config)
        self.db.expire_all(); self.assertEqual(self.db.query(WhatsAppLog).one().status,'read')

    def test_failure_then_delivery_evidence(self):
        self.send()
        for status in ['failed','sent','delivered']:
            service.apply_statuses(self.db,self.callback(status),self.config)
        self.db.expire_all(); self.assertEqual(self.db.query(WhatsAppLog).one().status,'delivered')

    def test_early_callback_is_retryable_not_lost(self):
        self.db.add(WhatsAppLog(hospital_id=1,masked_phone='***0000',provider='meta',status='pending',created_at=datetime.now(timezone.utc)))
        self.db.commit()
        with self.assertRaises(service.WelcomeError) as error: service.apply_statuses(self.db,self.callback(),self.config)
        self.assertEqual(error.exception.status,503)
        row=self.db.query(WhatsAppLog).one(); row.provider_message_id='wamid.synthetic'; row.status='accepted'; self.db.commit()
        service.apply_statuses(self.db,self.callback(),self.config)
        self.assertEqual(row.status,'delivered')

    def test_unrelated_inbound_and_unknown_ids_not_persisted(self):
        data=self.callback(statuses=[],messages=[{'from':'9876543210','text':{'body':'RAW PATIENT TEXT'}}])
        self.assertEqual(self.post_callback(data).status_code,200)
        self.assertEqual(self.post_callback(self.callback(message_id='wamid.other')).status_code,200)
        self.assertEqual(self.db.query(WhatsAppLog).count(),0)

    def test_historical_twilio_rows_remain_usable(self):
        row=WhatsAppLog(hospital_id=1,masked_phone='***0000',status='sent',twilio_sid='SM-synthetic')
        self.db.add(row); self.db.commit()
        self.assertIsNone(row.provider); self.assertEqual(row.twilio_sid,'SM-synthetic')
        self.assertEqual(self.client.get(f'/api/v1/hospitals/1/whatsapp/messages/{row.id}',headers=self.headers).status_code,404)

    def test_malformed_signed_callback_and_size_limit(self):
        path='/api/v1/whatsapp/webhook'
        raw=b'not-json'
        digest='sha256='+hmac.new(self.config.META_WHATSAPP_APP_SECRET.encode(),raw,hashlib.sha256).hexdigest()
        response=self.client.post(path,content=raw,headers={'X-Hub-Signature-256':digest})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post(path,content=b'x'*1_048_577).status_code,413)

    def test_callback_access_log_omits_verify_token(self):
        # Extract only the actual filter class; avoid importing the full app/startup jobs.
        import ast
        tree=ast.parse(Path('app/main.py').read_text(encoding='utf-8'))
        node=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='_WhatsAppAccessFilter')
        namespace={'logging':logging}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<access-filter-test>','exec'),namespace)
        filt=namespace['_WhatsAppAccessFilter']()
        sensitive=logging.LogRecord('uvicorn.access',logging.INFO,'',0,'%s - %s %s %s %s',('client','GET','/api/v1/whatsapp/webhook?hub.verify_token=synthetic-secret','HTTP/1.1',200),None)
        ordinary=logging.LogRecord('uvicorn.access',logging.INFO,'',0,'%s - %s %s %s %s',('client','GET','/api/v1/hospitals/1','HTTP/1.1',200),None)
        self.assertFalse(filt.filter(sensitive)); self.assertTrue(filt.filter(ordinary))

    def test_repeated_sent_advances_clock_before_older_failure(self):
        self.send()
        for status,second in [('sent',100),('sent',200),('failed',150)]:
            payload=self.callback(status)
            payload['entry'][0]['changes'][0]['value']['statuses'][0]['timestamp']=str(second)
            service.apply_statuses(self.db,payload,self.config)
        row=self.db.query(WhatsAppLog).one()
        self.assertEqual(row.status,'sent')
        self.assertEqual(int(row.provider_event_at.replace(tzinfo=timezone.utc).timestamp()),200)
        updated=row.status_updated_at
        duplicate=self.callback('sent')
        duplicate['entry'][0]['changes'][0]['value']['statuses'][0]['timestamp']='200'
        service.apply_statuses(self.db,duplicate,self.config)
        self.assertEqual(row.status_updated_at,updated)

    def test_stale_failure_does_not_undo_newer_sent_callback(self):
        self.send()
        sent=self.callback('sent')
        sent['entry'][0]['changes'][0]['value']['statuses'][0]['timestamp']=str(int(datetime.now(timezone.utc).timestamp())+30)
        service.apply_statuses(self.db,sent,self.config)
        failed=self.callback('failed')
        service.apply_statuses(self.db,failed,self.config)
        self.assertEqual(self.db.query(WhatsAppLog).one().status,'sent')

    def test_migration_is_additive_offline_and_has_correct_parent(self):
        path=Path('alembic/versions/7a8b9c0d1e2f_meta_whatsapp_welcome.py')
        spec=importlib.util.spec_from_file_location('migration',path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertEqual(module.down_revision,'0c682ef81de1')
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        buffer=StringIO()
        context=MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':buffer})
        with Operations.context(context): module.upgrade()
        sql=buffer.getvalue()
        self.assertIn('ADD COLUMN provider',sql)
        self.assertIn('UNIQUE (hospital_id, request_id)',sql)
        self.assertNotIn('DROP ',sql)
        self.assertNotIn('UPDATE ',sql)
        self.assertNotIn('twilio_sid',sql)
        print('\nOFFLINE PostgreSQL migration SQL (no database connection):\n'+sql)


if __name__ == '__main__':
    unittest.main(verbosity=2)
