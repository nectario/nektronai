import importlib.util
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[4]


def module():
    spec = importlib.util.spec_from_file_location('mail_ingest_package', ROOT/'website/scripts/prepare_mail_ingest_deployment.py')
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


class MailIngestPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preparation = module()
        # Synthetic pre-change source needs no historical Git object or live bundle.
        cls.baseline = b''.join(before for before,_ in cls.preparation.PATCHES) + cls.preparation.ASSET

    def bundle(self, directory, runtime=None, duplicate=False):
        source = Path(directory)/'live.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(source,'w') as archive:
                archive.comment=b'synthetic comment'
                for name,data in (('assets/account.css',b'synthetic-css'),('.platform/hooks/postdeploy/60_accounts.sh',b'unchanged-hook'),
                        (self.preparation.RUNTIME, runtime or self.baseline)):
                    entry=zipfile.ZipInfo(name); entry.create_system=3; entry.external_attr=(0o100755 if name.endswith('.sh') else 0o100644)<<16
                    archive.writestr(entry,data)
                if duplicate: archive.writestr(self.preparation.RUNTIME,self.baseline)
        return source

    def test_only_issuer_changes_and_modes_assets_hooks_stay_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            original=self.bundle(directory); candidate=Path(directory)/'candidate.zip'
            report=self.preparation.prepare_overlay(original,candidate,baseline=self.baseline,local_source=self.preparation.approved_source(self.baseline))
            self.assertEqual([item['path'] for item in report['changed']],[self.preparation.RUNTIME])
            with zipfile.ZipFile(original) as before,zipfile.ZipFile(candidate) as after:
                for name in ('assets/account.css','.platform/hooks/postdeploy/60_accounts.sh'):
                    self.assertEqual(before.read(name),after.read(name)); self.assertEqual(before.getinfo(name).external_attr,after.getinfo(name).external_attr)
            with self.assertRaises(RuntimeError): self.preparation.prepare_overlay(original,candidate,baseline=self.baseline,local_source=self.preparation.approved_source(self.baseline))

    def test_reviewed_live_cache_buster_is_preserved(self):
        live=self.baseline.replace(self.preparation.ASSET,b'<link rel="stylesheet" href="/assets/account.css?v=reviewed-123">')
        with tempfile.TemporaryDirectory() as directory:
            original=self.bundle(directory,live); candidate=Path(directory)/'candidate.zip'
            report=self.preparation.prepare_overlay(original,candidate,baseline=self.baseline,local_source=self.preparation.approved_source(self.baseline))
            self.assertTrue(report['preserved_live_stylesheet'])
            with zipfile.ZipFile(candidate) as archive: self.assertIn(b'account.css?v=reviewed-123',archive.read(self.preparation.RUNTIME))

    def test_unknown_live_or_local_divergence_and_duplicate_entries_stop(self):
        for live,local,duplicate in ((self.baseline+b'\n# unreviewed live change',self.preparation.approved_source(self.baseline),False),
                (self.baseline,self.preparation.approved_source(self.baseline)+b'\n# unreviewed local change',False),
                (self.baseline,self.preparation.approved_source(self.baseline),True)):
            with self.subTest(duplicate=duplicate),tempfile.TemporaryDirectory() as directory:
                original=self.bundle(directory,live,duplicate)
                with self.assertRaises(RuntimeError): self.preparation.prepare_overlay(original,Path(directory)/'candidate.zip',baseline=self.baseline,local_source=local)


if __name__=='__main__': unittest.main()
