"""Homepage mission/capability boundaries and an optional copy-only PR guard."""
from html.parser import HTMLParser
from pathlib import Path
import os
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.shape = []
        self.words = []
        self.skip = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.tags.append((tag, values))
        # Only these owner-approved metadata/accessibility descriptions may change.
        normalized = dict(values)
        if tag == 'meta' and (values.get('name') == 'description' or
                             values.get('property') in ('og:title', 'og:description')):
            normalized['content'] = '<approved copy>'
        if tag == 'aside' and values.get('class') == 'hero-panel home-thesis-panel':
            normalized['aria-label'] = '<approved copy>'
        if tag == 'div' and values.get('class') == 'research-loop':
            normalized['aria-label'] = '<approved copy>'
        self.shape.append(('start', tag, sorted(normalized.items())))
        if tag in ('style', 'script'):
            self.skip += 1

    def handle_endtag(self, tag):
        self.shape.append(('end', tag))
        if tag in ('style', 'script'):
            self.skip -= 1

    def handle_data(self, text):
        if not self.skip:
            self.words.extend(text.split())


def research_section(text):
    return text.split('<section id="research"', 1)[1].split('<section id="products"', 1)[0]


class VisionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text()
        cls.page = Page(cls.html)
        cls.text = ' '.join(cls.page.words)

    def test_both_ambitions_and_company_voice_are_explicit(self):
        for phrase in ('Reimagine the apps we use.', 'Rethink AI from the ground up.',
                       'Our boldest undertaking', 'Our aim is to challenge',
                       'radically different approach', 'NektronAI Product Vision',
                       'everyday life and professional work'):
            self.assertIn(phrase, self.text)
        self.assertNotIn('my boldest undertaking', self.text.lower())

    def test_products_have_independent_value_and_ai_is_more_than_chat(self):
        for phrase in ('AI into core functionality', 'beyond chatbot integration',
                       'value in their own right', 'Product revenue also helps sustain',
                       'meticulous attention to the user experience'):
            self.assertIn(phrase, self.text)
        self.assertNotRegex(self.text.lower(), r'pressure[ -]?test|stress[ -]?test|proving ground|commercial pressure|product pressure|research-product loop')

    def test_current_status_and_conditional_integration_are_not_confused(self):
        for phrase in ('Current products do not yet use GrowNet.', 'not yet integrated',
                       'continually introduce new applications, initially powered by existing AI models',
                       'As GrowNet proves its capabilities, we will begin integrating it into our products.',
                       'Research in progress', 'Architecture and claims are still evolving'):
            self.assertIn(phrase, self.text)
        self.assertNotRegex(self.text, r'(?:powered by|running on|built on) GrowNet')

    def test_all_six_products_and_existing_destinations_remain(self):
        for name in ('Nektron Write', 'Nektron Mail', 'Nektron Moments', 'DeepTrading.ai', 'InterviewHelperAI', 'TagMySpend.com'):
            self.assertIn(name, self.text)
        self.assertIn('Independent brands:', self.text)
        self.assertIn('Nektron product family', self.text)
        self.assertEqual(sum(a.get('class') == 'card product-card' for t, a in self.page.tags), 6)
        anchors = [a.get('href') for t, a in self.page.tags if t == 'a']
        for destination in ('grownet.html', '#products', '#contact', 'https://www.deeptrading.ai',
                            'https://www.interviewhelper.ai', 'https://tagmyspend.com'):
            self.assertIn(destination, anchors)
        family = self.html.split('data-added-products="nektron-family">', 1)[1].split('<div class="callout home-product-note"', 1)[0]
        self.assertEqual(re.findall(r'href="([^"]+)"', family), ['#contact', '#contact', '#contact'])

    def test_social_text_matches_the_mission_without_changing_image_or_canonical(self):
        meta = {a.get('name', a.get('property')): a.get('content') for t, a in self.page.tags if t == 'meta'}
        self.assertEqual(meta['description'], meta['og:description'])
        self.assertIn('reimagines everyday and professional apps', meta['description'])
        self.assertIn('GrowNet pursues', meta['description'])
        self.assertNotIn('pressure-test', meta['description'])
        self.assertIn('Reimagined Apps & New AI Foundations', meta['og:title'])
        self.assertEqual(meta['og:image'], meta['twitter:image'])
        self.assertIn(('link', {'rel': 'canonical', 'href': 'https://nektron.ai/'}), self.page.tags)

    @unittest.skipUnless(os.getenv('VISION_BASE_REF'), 'One-off copy scope guard requires the explicit PR base')
    def test_approved_design_links_research_and_other_production_files_are_unchanged(self):
        ref = os.environ['VISION_BASE_REF']
        self.assertRegex(ref, r'^[a-f0-9]{40}$')
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=ROOT.parent)
        old = git('show', f'{ref}:website/index.html').decode()
        self.assertEqual(Page(old).shape, self.page.shape, 'No structural, class, resource or destination changes')
        self.assertEqual(research_section(old), research_section(self.html), 'Technical research/status/Golden Rule unchanged')
        self.assertEqual(old.split('<header>', 1)[1].split('</header>', 1)[0],
                         self.html.split('<header>', 1)[1].split('</header>', 1)[0], 'Navigation and logo unchanged')
        allowed = {
            'website/index.html', 'website/tests/homepage_vision.py', 'website/tests/homepage_vision_browser.cjs',
            'website/tests/homepage_preservation.cjs', 'website/tests/sitewide_static.py',
            'website/docs/HOMEPAGE_VISION.md', '.github/workflows/website-visual-review.yml'
        }
        changed = set(git('diff', '--name-only', ref, 'HEAD', '--').decode().splitlines())
        self.assertLessEqual(changed, allowed, 'No other pages, styles, assets, scripts, downloads or infrastructure changes')


if __name__ == '__main__':
    unittest.main(verbosity=2)
