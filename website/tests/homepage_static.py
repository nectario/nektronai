"""Static-site checks; no dependencies or services. Optional PR-base content guard."""
from pathlib import Path
from html.parser import HTMLParser
import collections, os, re, unittest

ROOT = Path(__file__).resolve().parents[1]
class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags=[]; self.words=[]; self.skip=0
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag,dict(attrs)))
        if tag in ('style','script'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('style','script'): self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.words.extend(data.split())

class HomepageChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/'index.html').read_text()
        cls.doc=Document(cls.html)
        cls.css=(ROOT/'assets/home-refinement.css').read_text()
    def test_single_title_and_unique_landmarks(self):
        self.assertEqual(sum(t=='h1' for t,a in self.doc.tags),1)
        ids=[a['id'] for t,a in self.doc.tags if 'id' in a]
        self.assertEqual(len(ids),len(set(ids)))
        for target in ('content','primary-nav','research','products','contact'): self.assertIn(target,ids)
    def test_scope_is_homepage_only(self):
        self.assertIn('body.home-page',self.css)
        for page in ROOT.glob('*.html'):
            if page.name!='index.html': self.assertNotIn('home-refinement',page.read_text())
        self.assertNotIn('@import',self.css)
    def test_research_limits_remain_visible(self):
        text=' '.join(self.doc.words)
        for statement in ('not yet integrated', 'Current products do not yet use GrowNet.', 'Research in progress', 'biologically inspired', 'Cross-language parity remains part of the plan'):
            self.assertIn(statement,text)
        self.assertNotIn('display: none',self.html)
    def test_local_navigation_targets(self):
        ids={a['id'] for t,a in self.doc.tags if 'id' in a}
        for tag,a in self.doc.tags:
            url=a.get('href','')
            if tag!='a' or not url or re.match(r'\w+:',url): continue
            file,_,anchor=url.partition('#')
            if file: self.assertTrue((ROOT/file).is_file(),url)
            elif anchor: self.assertIn(anchor,ids)
    def test_icons_are_decorative_and_logo_artwork_is_original(self):
        arrows=[a for t,a in self.doc.tags if t=='svg' and a.get('class')=='resource-arrow']
        self.assertEqual(len(arrows),3)
        self.assertTrue(all(a.get('aria-hidden')=='true' for a in arrows))
        self.assertEqual([a['src'] for t,a in self.doc.tags if t=='img'],[
            'assets/brand/wordmark-dark-320.png','assets/brand/wordmark-light-320.png',
            'assets/brand/wordmark-dark-280.png','assets/brand/wordmark-light-280.png'])
    def test_accessible_states_are_explicit(self):
        for token in (':focus-visible','prefers-reduced-motion','forced-colors','home-nav-ready'):
            self.assertIn(token,self.css)
        self.assertNotIn('translateY(',self.css)
        js=(ROOT/'assets/home-refinement.js').read_text()
        self.assertIn('button.focus()',js)
        self.assertNotIn('fetch(',js)
    def test_material_contrast(self):
        def rgb(c): return [int(c[i:i+2],16)/255 for i in (1,3,5)]
        def lum(c): return sum(v*k for v,k in zip([x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in c],(.2126,.7152,.0722)))
        def contrast(a,b):
            x,y=sorted((lum(a),lum(b)));return (y+.05)/(x+.05)
        for theme in ('dark','light'):
            selector='body.home-page {' if theme=='dark' else '.theme-light body.home-page {'
            block=self.css.split(selector,1)[1].split('}',1)[0]
            tok={k:rgb(v) for k,v in re.findall(r'(--[\w-]+):\s*(#[\da-f]{6});',block)}
            for family in ('blue','warm','slate','mint','pearl','thesis'):
                a=tok[f'--atelier-{family}-start'];b=tok[f'--atelier-{family}-end']
                for i in range(33):
                    bg=[x+(y-x)*i/32 for x,y in zip(a,b)]
                    for fg in ('--text','--muted','--muted2','--accent'):
                        self.assertGreaterEqual(contrast(tok[fg],bg),4.5,(theme,family,fg,i))
            a=tok['--atelier-button-start'];b=tok['--atelier-button-end']
            for i in range(33):
                self.assertGreaterEqual(contrast([1,1,1],[x+(y-x)*i/32 for x,y in zip(a,b)]),4.5)
    @unittest.skipUnless(os.getenv('BASELINE_HTML'), 'Optional guard for this design-only PR, not a permanent ban on copy changes')
    def test_design_pass_preserves_all_text_links_and_metadata(self):
        before=Document(Path(os.environ['BASELINE_HTML']).read_text())
        self.assertEqual(' '.join(before.words),' '.join(self.doc.words))
        def selected(doc,tag,key): return [a for t,a in doc.tags if t==tag and key in a]
        for tag,key in (('a','href'),('meta','content'),('img','src')):
            self.assertEqual(selected(before,tag,key),selected(self.doc,tag,key))

if __name__=='__main__': unittest.main(verbosity=2)
