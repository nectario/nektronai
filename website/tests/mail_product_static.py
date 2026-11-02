"""Public Mail page: assets, access boundaries, download and accessible markup."""
from pathlib import Path
from html.parser import HTMLParser
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.tags=[]; self.feed(html)
    def handle_starttag(self,tag,attrs): self.tags.append((tag,dict(attrs)))

class MailProductChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/'nektron-mail.html').read_text(encoding='utf-8')
        cls.tags=Page(cls.html).tags
        cls.js=(ROOT/'assets/nektron-mail.js').read_text(encoding='utf-8')
    def test_ids_and_controls_are_connected(self):
        ids=[a['id'] for _,a in self.tags if 'id' in a]
        self.assertEqual(len(ids),len(set(ids)))
        for _,a in self.tags:
            for ref in (a.get('aria-controls','')+' '+a.get('aria-labelledby','')).split(): self.assertIn(ref,ids)
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
        self.assertEqual(link['href'],'https://d2j3ldvioomkd6.cloudfront.net/assets/downloads/NektronMail.Setup.0.1.126.exe')
        self.assertIn('359ED42CACDBD714979D18669998DDE4BE9E32D5C6F42FDDFB51188CFFE3F8F2',self.html)
        self.assertIn('Nektron, Inc.',self.html)
    def test_preview_and_connected_feature_limits_are_visible(self):
        for phrase in ('Windows preview','approved Google test users','limited-access','not available for Gmail',
                       'Public subscription purchasing is not available yet','attachment-content search are not active',
                       'Microsoft 365','WebView2 Runtime','does not restore missing mail files'):
            self.assertIn(phrase,self.html)
        self.assertNotRegex(self.html,r'\$\d|guaranteed 120|never lose|zero-knowledge')
    def test_discovery_entrypoints_exist(self):
        self.assertIn('href="nektron-mail.html"',(ROOT/'index.html').read_text(encoding='utf-8'))
        self.assertIn('href="nektron-mail.html#download"',(ROOT/'downloads.html').read_text(encoding='utf-8'))
        self.assertIn('https://nektron.ai/nektron-mail.html',(ROOT/'sitemap.xml').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
