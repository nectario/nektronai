"""Contact endpoint abuse cases. Mail delivery is mocked throughout."""
import unittest
from unittest.mock import Mock, patch
from test_accounts import MemoryStore, SETTINGS, ORIGIN
from app import create_app
from mail import Mailer

DATA={'name':'Test Visitor','email':'visitor@example.com','topic':'general','message':'Please tell me more about your products.','website':''}

class RateStore(MemoryStore):
    def __init__(self): super().__init__(); self.now=100000; self.counts={}
    def allow_request(self,key,limit=20,seconds=600):
        bucket=(key,self.now//seconds);self.counts[bucket]=self.counts.get(bucket,0)+1
        return self.counts[bucket]<=limit

class ContactTests(unittest.TestCase):
    def setUp(self):
        self.store=RateStore();self.mail=Mock();self.app=create_app(SETTINGS,self.store,self.mail)
        self.app.testing=True;self.client=self.app.test_client()
    def csrf(self,ip='198.51.100.1'):
        return self.client.get('/api/account/csrf',base_url=ORIGIN,environ_overrides={'REMOTE_ADDR':ip}).json['csrfToken']
    def post(self,data=None,ip='198.51.100.1',headers=None,**kwargs):
        return self.client.post('/api/account/contact',base_url=ORIGIN,json=DATA if data is None else data,
            headers=headers if headers is not None else {'Origin':ORIGIN,'X-CSRF-Token':self.csrf(ip)},
            environ_overrides={'REMOTE_ADDR':ip},**kwargs)
    def test_public_submission_does_not_require_login_or_create_user(self):
        self.assertEqual(self.post().json,{'sent':True})
        self.mail.send_contact.assert_called_once_with(DATA['name'],DATA['email'],'General inquiry',DATA['message'])
        self.assertFalse(self.store.users)
    def test_csrf_origin_and_json_are_required(self):
        self.assertEqual(self.post(headers={}).status_code,403)
        self.assertEqual(self.post(headers={'Origin':'https://evil.example','X-CSRF-Token':self.csrf()}).status_code,403)
        r=self.client.post('/api/account/contact',base_url=ORIGIN,data='name=Test',headers={'Origin':ORIGIN,'X-CSRF-Token':self.csrf()},content_type='application/x-www-form-urlencoded')
        self.assertEqual(r.status_code,415);self.mail.send_contact.assert_not_called()
    def test_header_injection_and_unknown_fields_are_rejected(self):
        for field,value in [('name','Test\r\nBcc: evil@example.com'),('email','visitor@example.com\r\nBcc: evil@example.com'),
                            ('email','a@example.com,b@example.com'),('topic','general\nInjected'),('to','evil@example.com'),('attachments',[])]:
            with self.subTest(field=field):self.assertEqual(self.post({**DATA,field:value}).status_code,400)
        self.mail.send_contact.assert_not_called()
    def test_malformed_and_large_requests_are_rejected(self):
        for field,value in [('name',{}),('topic','unknown'),('message',''),('message','x'*2001),('message','bad\x00content'),('name','\ud800')]:
            self.assertEqual(self.post({**DATA,field:value}).status_code,400)
        self.assertEqual(self.post({**DATA,'message':'x'*6000}).status_code,413)
        self.mail.send_contact.assert_not_called()
    def test_honeypot_never_sends_email(self):
        self.assertEqual(self.post({**DATA,'website':'spam.example'}).status_code,200)
        self.mail.send_contact.assert_not_called()
    def test_international_domain_is_safe_for_ses_reply_to(self):
        self.assertEqual(self.post({**DATA,'email':'visitor@b\u00fccher.de'}).status_code,200)
        self.assertEqual(self.mail.send_contact.call_args.args[1],'visitor@xn--bcher-kva.de')
    def test_duplicate_submit_is_rate_limited(self):
        self.assertEqual(self.post().status_code,200)
        self.assertEqual(self.post().status_code,429)
        self.mail.send_contact.assert_called_once()
    def test_ip_and_email_hourly_limits(self):
        for i in range(3):
            self.assertEqual(self.post().status_code,200);self.store.now+=61
        self.assertEqual(self.post().status_code,429)
        self.assertEqual(self.post(ip='198.51.100.2').status_code,429)
        self.assertEqual(self.mail.send_contact.call_count,3)
    def test_site_wide_limit_bounds_distributed_abuse(self):
        for i in range(30):
            self.assertEqual(self.post({**DATA,'email':f'test{i}@example.com'},ip=f'198.51.100.{i+1}').status_code,200)
        self.assertEqual(self.post({**DATA,'email':'extra@example.com'},ip='198.51.100.100').status_code,429)
        self.assertEqual(self.mail.send_contact.call_count,30)
    def test_failures_never_report_success_or_expose_details(self):
        self.mail.send_contact.side_effect=RuntimeError('sensitive internal detail')
        result=self.post();self.assertEqual(result.status_code,503);self.assertNotIn('sensitive',result.text)
        self.mail.send_contact.reset_mock()
        csrf=self.csrf()
        with patch.object(self.store,'allow_request',side_effect=RuntimeError('offline')):
            self.assertEqual(self.post(headers={'Origin':ORIGIN,'X-CSRF-Token':csrf}).status_code,503)
        self.mail.send_contact.assert_not_called()
    def test_untrusted_content_is_plain_text_and_destination_is_fixed(self):
        message='<script>alert(1)</script>\nDROP TABLE User;\nhttps://example.com'
        with patch('mail.boto3.client') as client:
            mailer=Mailer({});mailer.send_contact('Test',DATA['email'],'General inquiry',message)
            request=client.return_value.send_email.call_args.kwargs
            self.assertEqual(request['Destination'],{'ToAddresses':['info@nektron.ai']})
            self.assertEqual(request['ReplyToAddresses'],[DATA['email']])
            self.assertEqual(set(request['Content']['Simple']['Body']),{'Text'})
            self.assertIn(message,request['Content']['Simple']['Body']['Text']['Data'])
            self.assertEqual(request['Content']['Simple']['Subject']['Data'],'NektronAI contact: General inquiry')

if __name__=='__main__':unittest.main()
