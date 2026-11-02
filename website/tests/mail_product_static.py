"""Public Mail page: assets, access boundaries, download and accessible markup."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    VOID_TAGS = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self, html):
        super().__init__(); self.tags=[]; self.regions={}; self.stack=[]; self.feed(html)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs); self.tags.append((tag,attrs))
        region=attrs.get('id')
        if region:self.regions[region]=[]
        if tag not in self.VOID_TAGS:self.stack.append((tag,region))
    def handle_endtag(self,tag):
        for index in range(len(self.stack)-1,-1,-1):
            if self.stack[index][0]==tag:
                del self.stack[index:]; break
    def handle_data(self,data):
        for _,region in self.stack:
            if region:self.regions[region].append(data)
    def text(self,region):return ' '.join(' '.join(self.regions[region]).split())

class MailProductChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/'nektron-mail.html').read_text(encoding='utf-8')
        cls.page=Page(cls.html); cls.tags=cls.page.tags
        cls.js=(ROOT/'assets/nektron-mail.js').read_text(encoding='utf-8')
    def test_ids_and_controls_are_connected(self):
        ids=[a['id'] for _,a in self.tags if 'id' in a]
        self.assertEqual(len(ids),len(set(ids)))
        for _,a in self.tags:
            for ref in (a.get('aria-controls','')+' '+a.get('aria-labelledby','')).split(): self.assertIn(ref,ids)
            if a.get('href','').startswith('#'):self.assertIn(a['href'][1:],ids)
        self.assertEqual(sum(a.get('role')=='tab' for _,a in self.tags),6)
        self.assertEqual(sum(a.get('aria-selected')=='true' for _,a in self.tags),1)
        for key in ('ArrowRight','ArrowLeft','Home','End'):self.assertIn(key,self.js)
    def test_all_referenced_local_assets_and_gallery_images_exist(self):
        for tag,a in self.tags:
            for key in ('src','href'):
                path=a.get(key,'').split('?')[0].split('#')[0]
                if path and not re.match(r'\w+:',path) and not path.startswith('/'):
                    self.assertTrue((ROOT/path).is_file(),path)
            if tag=='img':self.assertIn('alt',a)
        for name in ('overview-light','overview-dark','compose','search','rules','downloads'):
            self.assertTrue((ROOT/f'assets/mail/{name}.webp').is_file())
            self.assertIn(name+'.webp',self.js)
    def test_download_is_the_verified_versioned_release(self):
        link=next(a for _,a in self.tags if a.get('id')=='installer-download')
        self.assertEqual(link['href'],'https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.131.exe')
        self.assertIn('83B81A57E539A2F003F9D472878322028CD81C17DB80B66F3D15C83167D85318',self.html)
        self.assertIn('61,035,888 bytes',self.html)
        self.assertIn('Nektron, Inc.',self.html)
    def test_preview_and_connected_feature_limits_are_visible(self):
        for phrase in ('Windows preview','Gmail sign-in is currently available to invited testers','limited-access','not available for Gmail',
                       'Public subscription purchasing is not available yet','attachment-content search are not active',
                       'Microsoft 365','WebView2 Runtime','does not restore missing mail files'):
            self.assertIn(phrase,self.html)
        self.assertNotRegex(self.html,r'\$\d|guaranteed 120|never lose|zero-knowledge')
    def test_first_screen_keeps_product_name_and_explains_mailbox_eligibility(self):
        self.assertEqual(self.page.text('mail-title'),'Nektron Mail')
        eligibility=self.page.text('preview-compatibility')
        for phrase in ('Gmail','IMAP','Exchange Server (EWS)','POP3','Amazon WorkMail','Windows x64','invited testers','Ask about Gmail access'):
            self.assertIn(phrase,eligibility)
        self.assertLess(self.html.index('id="preview-compatibility"'),self.html.index('class="mail-hero-screen"'))
        self.assertIn('One Windows email app.',self.html)
        positions=[eligibility.index(provider) for provider in ('Gmail','IMAP','Exchange Server (EWS)','POP3','Amazon WorkMail')]
        self.assertEqual(positions,sorted(positions))
        self.assertIn('class="mail-gmail">Gmail</strong>',self.html)
        self.assertNotIn('Gmail preview access',self.html)
        self.assertNotIn('Gmail preview access',self.js)
        self.assertEqual(self.html.count('Gmail, IMAP, Exchange Server (EWS), POP3 and Amazon WorkMail.'),2)
    def test_custom_provider_support_keeps_protocol_and_pilot_limits_clear(self):
        for phrase in ('Exchange Server uses HTTPS EWS','configure SMTP for sending',
                       'Microsoft 365 / Outlook.com sign-in is not available',
                       'POP3 downloads from your provider’s Inbox and leaves copies on the server',
                       'POP3 read state stays on this PC','calendars, contacts, MAPI and ActiveSync are not included'):
            self.assertIn(phrase,self.html)
        business=self.page.text('business-archive')
        self.assertIn('Amazon WorkMail mailboxes connected through IMAP',business)
        self.assertIn('custom IMAP, Exchange Server and POP3 connections are also outside this pilot',business)
        self.assertNotIn('other Exchange servers, custom IMAP and POP3 are not available',self.html)
    def test_search_and_all_mailboxes_are_scoped_without_combined_inbox_claim(self):
        self.assertIn('selected mailbox',self.page.text('features'))
        self.assertIn('From, To, Cc, Bcc, Correspondent, Subject, Body, Filename',self.page.text('features'))
        self.assertIn('Sort results by date or folder',self.html)
        self.assertIn('double-click a result or press Enter',self.html)
        self.assertIn('continues through the available local records automatically',self.html)
        self.assertIn('Cc, Bcc',self.js)
        self.assertIn('rather than a combined inbox',self.html)
        self.assertIn('up to 100 mailbox profiles',self.html)
        self.assertNotRegex(self.html.lower(),r'unlimited accounts|search all your accounts at once|unified inbox')
    def test_ai_authoring_is_reviewed_eligible_and_explicit_about_data(self):
        ai=self.page.text('ai-rules')
        for phrase in ('plain English','Describe','Review','Apply','eligible NektronAI accounts',
                       'prompt, rule draft and folder names','provider credentials',
                       'while Nektron Mail is open','You choose when a rule takes effect'):
            self.assertIn(phrase,ai)
        self.assertIn('does not automatically attach message bodies, attachments',ai)
    def test_local_archive_and_business_service_are_distinct(self):
        local=self.page.text('local-archive'); business=self.page.text('business-archive')
        for phrase in ('durable local archive','offline reading','separate backup','coverage'):
            self.assertIn(phrase,local)
        for phrase in ('FOR SMALL BUSINESSES','long-term storage','customer conversations',
                       'attachment metadata','object storage','authorization for each supported mailbox',
                       'authorized Amazon WorkMail','Gmail database archiving is not currently available',
                       'not a customer-configured database connection or built-in AI email search'):
            self.assertIn(phrase.lower(),business.lower())
        self.assertIn('does not restore missing mail files',self.page.text('archive-recovery'))
        order=[self.html.index('id="'+region+'"') for region in ('features','ai-rules','local-archive','business-archive','download')]
        self.assertEqual(order,sorted(order))
        self.assertNotRegex(business.lower(),r'guaranteed permanence|compliance certified|immutable retention|automatic backups')
    def test_five_benefits_and_planned_replies_do_not_overstate_current_ai(self):
        benefits=self.page.text('features')
        for phrase in ('YOUR MAILBOXES','INTEGRATED AI','ROBUST SEARCH','INTUITIVE DESIGN','CENTRAL ARCHIVING'):
            self.assertIn(phrase,benefits)
        planned=self.page.text('ai-roadmap')
        self.assertIn('NOT AVAILABLE IN THIS PREVIEW',planned)
        self.assertIn('does not automatically write or send replies',planned)
        self.assertNotIn('Automatic replies',benefits)
        self.assertIn('INDIVIDUALS',self.page.text('business-archive'))
    def test_contact_ctas_use_existing_mailto_workflow_with_specific_subjects(self):
        contacts=[a for tag,a in self.tags if tag=='a' and a.get('href','').startswith('mailto:')]
        self.assertGreaterEqual(len(contacts),3)
        subjects=[]
        for link in contacts:
            target=urlsplit(link['href'])
            self.assertEqual(target.path,'info@nektron.ai')
            subject=parse_qs(target.query).get('subject',[''])[0]
            self.assertTrue(subject.startswith('Nektron Mail'))
            subjects.append(subject)
        for purpose in ('business archiving','Gmail access','AI rule assistance'):
            self.assertTrue(any(purpose in subject for subject in subjects),purpose)
    def test_discovery_entrypoints_exist(self):
        self.assertIn('href="nektron-mail.html"',(ROOT/'index.html').read_text(encoding='utf-8'))
        self.assertIn('href="nektron-mail.html#download"',(ROOT/'downloads.html').read_text(encoding='utf-8'))
        self.assertIn('https://nektron.ai/nektron-mail.html',(ROOT/'sitemap.xml').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
