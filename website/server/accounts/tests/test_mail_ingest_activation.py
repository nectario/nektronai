import importlib.util
import json
from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[4]


def module():
    spec=importlib.util.spec_from_file_location('ingest_flag_activation',ROOT/'website/scripts/activate_mail_ingest.py')
    result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


OLD='1'*32; NEW='2'*32


class Secret:
    def __init__(self):
        self.before=dict(NEKTRON_SITE_ORIGIN='https://nektron.ai',NEKTRON_MAIL_OAUTH_ENABLED='true',
            NEKTRON_MAIL_SIGNING_PEM='SYNTHETIC-PRIVATE-KEY',NEKTRON_DB_PASSWORD='SYNTHETIC-PASSWORD',nested=['unchanged',1])
        self.values={OLD:json.dumps(self.before)}; self.current=OLD; self.writes=[]; self.concurrent=False
    def get_secret_value(self,**request):
        return dict(VersionId=self.current,SecretString=self.values[self.current],VersionStages=['AWSCURRENT'])
    def put_secret_value(self,**request):
        assert request['VersionStages'] and 'AWSCURRENT' not in request['VersionStages']
        self.writes.append(('put',request)); self.values[request['ClientRequestToken']]=request['SecretString']
        if self.concurrent:
            self.values['3'*32]=json.dumps({**self.before,'concurrent':'edit'}); self.current='3'*32
        return dict(VersionId=request['ClientRequestToken'],VersionStages=request['VersionStages'])
    def update_secret_version_stage(self,**request):
        self.writes.append(('stage',request))
        if request['VersionStage']=='AWSCURRENT':
            assert self.current==request['RemoveFromVersionId']; self.current=request['MoveToVersionId']


class IngestActivationTests(unittest.TestCase):
    def test_rules_review_label_is_explicit_and_preserves_existing_flags(self):
        helper = module(); helper.FLAG = 'NEKTRON_MAIL_RULES_AUTHOR_ENABLED'
        secret = Secret(); secret.before['NEKTRON_MAIL_INGEST_ENABLED'] = 'true'
        secret.before['NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED'] = 'true'
        secret.values[OLD] = json.dumps(secret.before)
        result = helper.activate_flag(secret, 'synthetic-secret', attempt_id=NEW, apply=True,
                                      review_prefix='NektronMailRulesReview-')
        self.assertEqual(result['changed_fields'], ['NEKTRON_MAIL_RULES_AUTHOR_ENABLED'])
        self.assertEqual(json.loads(secret.values[NEW]), {**secret.before, 'NEKTRON_MAIL_RULES_AUTHOR_ENABLED': 'true'})
        self.assertEqual(secret.writes[0][1]['VersionStages'], ['NektronMailRulesReview-' + NEW])
        with self.assertRaisesRegex(RuntimeError, 'invalid_review_prefix'):
            helper.activate_flag(Secret(), 'synthetic-secret', attempt_id=NEW, apply=True, review_prefix='AWSCURRENT')

    def setUp(self): self.module=module()
    def test_default_is_read_only_and_reports_no_secret_fields(self):
        client=Secret(); result=self.module.activate_flag(client,'synthetic-secret-id',attempt_id=NEW)
        self.assertFalse(client.writes); self.assertFalse(result['applied'])
        text=json.dumps(result); self.assertNotIn('SYNTHETIC-PRIVATE-KEY',text); self.assertNotIn('SYNTHETIC-PASSWORD',text)
    def test_only_flag_changes_and_current_move_is_compare_and_set(self):
        client=Secret(); result=self.module.activate_flag(client,'synthetic-secret-id',attempt_id=NEW,apply=True)
        after=json.loads(client.values[NEW]); self.assertEqual(after,{**client.before,self.module.FLAG:'true'})
        self.assertEqual(result['changed_fields'],[self.module.FLAG]); self.assertEqual(client.current,NEW)
        self.assertEqual(client.writes[1][1],dict(SecretId='synthetic-secret-id',VersionStage='AWSCURRENT',MoveToVersionId=NEW,RemoveFromVersionId=OLD))
        self.assertTrue(client.writes[2][1]['VersionStage'].startswith('NektronMailIngestReview-'))
    def test_concurrent_current_change_is_never_overwritten(self):
        client=Secret(); client.concurrent=True
        with self.assertRaisesRegex(RuntimeError,'concurrent_secret_change'): self.module.activate_flag(client,'synthetic-secret-id',attempt_id=NEW,apply=True)
        self.assertEqual(client.current,'3'*32); self.assertEqual(len(client.writes),1)
    def test_already_enabled_flag_does_not_create_another_version(self):
        client=Secret(); client.values[OLD]=json.dumps({**client.before,self.module.FLAG:'true'})
        result=self.module.activate_flag(client,'synthetic-secret-id',attempt_id=NEW,apply=True)
        self.assertFalse(client.writes); self.assertEqual(result['changed_fields'],[])
    def test_duplicate_fields_and_ambiguous_flag_types_fail_closed(self):
        with self.assertRaises(RuntimeError): self.module.parse_secret('{"duplicate":1,"duplicate":2}')
        with self.assertRaises(RuntimeError): self.module.merge_flag({self.module.FLAG:True})


if __name__=='__main__': unittest.main()
