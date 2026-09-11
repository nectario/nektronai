"""Sitewide presentation guards. No network, third-party packages or private data."""
from pathlib import Path
from html.parser import HTMLParser
import os, re, unittest
ROOT = Path(__file__).resolve().parents[1]
PAGES = ('index.html', 'about.html', 'docs.html', 'downloads.html', 'changelog.html',
         'grownet.html', 'grownet-formal-spec.html', 'privacy.html', 'terms.html', 'support.html')

class Snapshot(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.words=[]; self.links=[]; self.images=[]; self.meta=[]; self.ids=[]
        self.skip=0; self.extra=0
        self.feed(content)
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='div' and (self.extra or a.get('data-added-products')=='nektron-family'):
            self.extra += 1
        if self.extra:return
        if tag in ('script','style'):self.skip+=1
        if tag=='a':self.links.append(a)
        if tag=='img':self.images.append(a)
        if tag=='meta':self.meta.append(a)
        if 'id' in a:self.ids.append(a['id'])
    def handle_endtag(self,tag):
        if self.extra:
            if tag=='div':self.extra-=1
            return
        if tag in ('script','style'):self.skip-=1
    def handle_data(self,data):
        if not self.skip and not self.extra:self.words.extend(data.split())

class SitewideChecks(unittest.TestCase):
    def test_added_products_are_bounded_and_do_not_invent_availability(self):
        html=(ROOT/'index.html').read_text()
        self.assertEqual(html.count('data-added-products="nektron-family"'),1)
        block=html.split('data-added-products="nektron-family">',1)[1].split('<div class="callout home-product-note"',1)[0]
        for name in ('Nektron Write','Nektron Mail'):self.assertIn('<h3>'+name+'</h3>',block)
        self.assertEqual(re.findall(r'href="([^"]+)"',block),['#contact','#contact'])
        self.assertNotRegex(block.lower(),r'coming soon|download|available now|macos|windows|subscription')
        for name in ('DeepTrading.ai','InterviewHelperAI','TagMySpend.com'):self.assertIn(name,html)
        self.assertLess(html.index('class="grid cols-3 home-product-grid"'),html.index('data-added-products='))
        self.assertIn('class="grid cols-3 product-family-grid"',html)
    def test_all_original_copy_links_images_metadata_and_ids(self):
        baseline=os.getenv('BASELINE_SITE')
        if not baseline:self.skipTest('Supply the PR base directory for the design-only content guard')
        for name in PAGES:
            with self.subTest(page=name):
                old=(Path(baseline)/name).read_bytes();new=(ROOT/name).read_bytes()
                if name!='index.html':self.assertEqual(old,new,'Secondary HTML must be byte-for-byte unchanged')
                a,b=Snapshot(old.decode()),Snapshot(new.decode())
                for field in ('words','links','images','meta','ids'):self.assertEqual(getattr(a,field),getattr(b,field),field)
        original=(Path(baseline)/'assets/site.js').read_text()
        self.assertTrue((ROOT/'assets/site.js').read_text().endswith(original),'Existing theme/download logic is unchanged')
        for name in ('styles.css','home-refinement.css','home-refinement.js'):
            self.assertEqual((ROOT/'assets'/name).read_bytes(),(Path(baseline)/'assets'/name).read_bytes(),
                             'The approved homepage design must not be revised: '+name)
    def test_route_scope_is_explicit_and_failure_keeps_original_page(self):
        js=(ROOT/'assets/site.js').read_text().split('// NektronAI — tiny client script',1)[0]
        for name in PAGES:self.assertIn('/'+name,js)
        self.assertIn('routes.has(pagePath)',js)
        self.assertIn("addEventListener('load', enable",js)
        self.assertNotRegex(js,r'innerHTML|textContent|fetch\(|localStorage\.setItem|remove\(')
        self.assertIn('button.focus()',js)
        guard='if (pagePath === "/" || pagePath === "/index.html") return;'
        self.assertIn(guard,js)
        self.assertLess(js.index(guard),js.index('function enable()'))
    def test_homepage_additions_do_not_load_the_secondary_redesign(self):
        html=(ROOT/'index.html').read_text()
        self.assertIn('<body class="home-page">',html)
        self.assertIn('href="assets/homepage-additions.css"',html)
        self.assertNotIn('href="assets/atelier.css"',html)
        css=(ROOT/'assets/homepage-additions.css').read_text()
        self.assertNotRegex(css,r'--(?:text|muted|accent|atelier-[\w-]+)\s*:')
        self.assertNotRegex(css,r'font-size|font-family|box-shadow|\.button|\.header-inner|\.home-thesis-panel')
        self.assertIn('body.home-page::before',css)
        self.assertIn('body.home-page .product-family-grid',css)
        # The owner has now approved the separate product/research narrative.
        # Keep the capability boundary; homepage_vision.py guards the new copy.
        self.assertIn('Current products do not yet use GrowNet.',html)
    def test_gradients_backgrounds_and_accessible_states(self):
        css=(ROOT/'assets/atelier.css').read_text()
        for term in ('prefers-reduced-motion','forced-colors','@media print',':focus-visible','atelier-nav-ready','overflow-y: auto'):
            self.assertIn(term,css)
        self.assertNotIn('translateY(',css)
        self.assertNotIn('background-attachment: fixed',css)
        for theme in ('light','dark'):
            f=ROOT/f'assets/backgrounds/atelier-flow-{theme}.webp'
            self.assertTrue(f.is_file())
            self.assertLess(f.stat().st_size,50000,'Keep the decorative asset lightweight')
            self.assertEqual(f.read_bytes()[:4],b'RIFF')
            self.assertEqual(f.read_bytes()[8:12],b'WEBP')
    def test_gradient_text_contrast_in_both_themes(self):
        def rgb(s):return [int(s[i:i+2],16)/255 for i in (1,3,5)]
        def lum(a):return sum(k*(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4) for k,c in zip((.2126,.7152,.0722),a))
        def ratio(a,b):x,y=sorted((lum(a),lum(b)));return (y+.05)/(x+.05)
        css=(ROOT/'assets/atelier.css').read_text()
        for theme,selector in [('dark','body.atelier-site {'),('light','.theme-light body.atelier-site {')]:
            block=css.split(selector,1)[1].split('}',1)[0]
            t={k:rgb(v) for k,v in re.findall(r'(--[\w-]+):\s*(#[\da-f]{6});',block)}
            for material in ('blue','warm','slate','mint','pearl','thesis'):
                for n in range(33):
                    bg=[a+(b-a)*n/32 for a,b in zip(t[f'--atelier-{material}-start'],t[f'--atelier-{material}-end'])]
                    for fg in ('--text','--muted','--muted2','--accent'):
                        self.assertGreaterEqual(ratio(t[fg],bg),4.5,(theme,material,fg,n))
            for n in range(33):
                bg=[a+(b-a)*n/32 for a,b in zip(t['--atelier-button-start'],t['--atelier-button-end'])]
                self.assertGreaterEqual(ratio([1,1,1],bg),4.5)

if __name__=='__main__':unittest.main(verbosity=2)
