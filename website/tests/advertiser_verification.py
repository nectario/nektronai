"""Business facts and crawl permissions; no network or private records."""
import hashlib
import json
import os
import re
import unittest
from html import unescape
from pathlib import Path
from urllib.robotparser import RobotFileParser

ROOT = Path(os.environ.get('ADVERTISER_SITE', Path(__file__).resolve().parents[1]))

def read(name):
    return (ROOT / name).read_text(encoding='utf-8')

class AdvertiserChecks(unittest.TestCase):
    def test_venture_order(self):
        for page in ('index.html','about.html'):
            text=read(page)
            # In About, inspect the portfolio rather than the founder's biography.
            if page=='about.html':text=text.split('The current portfolio includes',1)[1]
            self.assertLess(text.index('DeepTrading.ai'),text.index('TagMySpend.com'))
            self.assertLess(text.index('TagMySpend.com'),text.index('InterviewHelperAI'))

    def test_visible_company_information(self):
        for page in ('support.html','privacy.html','terms.html'):
            text=unescape(re.sub('<[^>]+>', ' ', read(page)))
            for value in ('Nektron, Inc.','99 Prospect Ave.','Bayonne, NJ 07002','United States','info@nektron.ai'):
                self.assertIn(value,text,page)
        self.assertIn('Founder &amp; CEO: Nektarios Kalogridis',read('support.html'))
        about=unescape(re.sub('<[^>]+>', '', read('about.html')))
        self.assertIn('NektronAI is a product and technology brand operated by Nektron, Inc., a New Jersey corporation.',about)
        for page in ('privacy.html','terms.html'):
            self.assertIn('NektronAI is operated by Nektron, Inc., a New Jersey corporation.',read(page))

    def test_structured_organization(self):
        for page in ('index.html','about.html'):
            scripts=re.findall(r'<script type="application/ld\+json">(.*?)</script>',read(page),re.S)
            org=[json.loads(s) for s in scripts if json.loads(s).get('@type')=='Organization']
            self.assertEqual(len(org),1)
            data=org[0]
            self.assertEqual(data['name'],'NektronAI')
            self.assertEqual(data['legalName'],'Nektron, Inc.')
            self.assertEqual(data['founder']['name'],'Nektarios Kalogridis')
            self.assertEqual(data['email'],'info@nektron.ai')
            self.assertEqual(data['address'],{'@type':'PostalAddress','streetAddress':'99 Prospect Ave.','addressLocality':'Bayonne','addressRegion':'NJ','postalCode':'07002','addressCountry':'US'})
            self.assertNotIn('taxID',data)
            self.assertNotIn('vatID',data)
            self.assertNotIn('telephone',data)

    def test_ads_crawl_allowed_without_opening_other_crawlers(self):
        robots=RobotFileParser();robots.parse(read('robots.txt').splitlines())
        for path in ('/','/index.html#contact','/contact.html','/index.html#products','/about.html','/support.html','/privacy.html','/terms.html','/assets/styles.css'):
            self.assertTrue(robots.can_fetch('OAI-AdsBot',path),path)
        self.assertFalse(robots.can_fetch('OAI-AdsBot','/api/account/session'))
        self.assertFalse(robots.can_fetch('OAI-AdsBot','/server/accounts/app.py'))
        self.assertFalse(robots.can_fetch('GPTBot','/'))
        self.assertFalse(robots.can_fetch('OtherCrawler','/'))

    @unittest.skipUnless(os.getenv('ADVERTISER_BASELINE'),'Production baseline comparison is optional')
    def test_exact_design_and_unrelated_file_preservation(self):
        baseline=Path(os.environ['ADVERTISER_BASELINE'])
        allowed={'index.html','about.html','support.html','privacy.html','terms.html','robots.txt','.platform/hooks/postdeploy/50_configure_https.sh'}
        changed=set()
        for old in baseline.rglob('*'):
            if old.is_file():
                relative=old.relative_to(baseline)
                self.assertTrue((ROOT/relative).is_file(),str(relative))
                if hashlib.sha256(old.read_bytes()).digest()!=hashlib.sha256((ROOT/relative).read_bytes()).digest():changed.add(relative.as_posix())
        self.assertLessEqual(changed,allowed)
        old_home=(baseline/'index.html').read_text(encoding='utf-8')
        # The owner subsequently requested this one ordering change.
        old_home=old_home.replace('<code>DeepTrading.ai</code>, <code>InterviewHelperAI</code>, <code>TagMySpend.com</code>',
                                  '<code>DeepTrading.ai</code>, <code>TagMySpend.com</code>, <code>InterviewHelperAI</code>')
        self.assertEqual(re.search(r'<body\b.*',read('index.html'),re.S).group(),re.search(r'<body\b.*',old_home,re.S).group())
        for page in ('index.html','about.html','support.html','privacy.html','terms.html'):
            old=(baseline/page).read_text(encoding='utf-8');new=read(page)
            self.assertEqual(re.findall(r'(?:class|style)="[^"]*"',new),re.findall(r'(?:class|style)="[^"]*"',old),page)
            self.assertEqual(re.search(r'<footer\b.*',new,re.S).group(),re.search(r'<footer\b.*',old,re.S).group(),page)

if __name__=='__main__':unittest.main(verbosity=2)
