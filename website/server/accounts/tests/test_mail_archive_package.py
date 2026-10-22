"""Ensure dedicated Linux service users can import new recovery modules."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


def preparation_module():
    source = Path(__file__).resolve().parents[3] / 'scripts/prepare_mail_archive_keys_deployment.py'
    spec = importlib.util.spec_from_file_location('archive_deployment_package', source)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


class ArchivePackageTests(unittest.TestCase):
    def test_new_runtime_entries_are_regular_world_readable_linux_source_files(self):
        module = preparation_module()
        for path in module.NEW_RUNTIME:
            entry = module.runtime_entry(path)
            self.assertEqual(entry.create_system, 3)
            self.assertEqual(entry.external_attr >> 16, 0o100644)
            self.assertEqual(entry.compress_type, zipfile.ZIP_DEFLATED)

    def test_permission_repair_preserves_every_content_and_unrelated_mode(self):
        module = preparation_module()
        with tempfile.TemporaryDirectory() as directory:
            old, fixed = Path(directory) / 'old.zip', Path(directory) / 'fixed.zip'
            with zipfile.ZipFile(old, 'w') as bundle:
                for name in ('assets/account.css', '.platform/hooks/postdeploy/60_accounts.sh', *sorted(module.NEW_RUNTIME)):
                    entry = zipfile.ZipInfo(name)
                    entry.external_attr = (0o100755 if name.endswith('.sh') else 0o600) << 16
                    bundle.writestr(entry, b'synthetic unchanged content')
            module.repair_runtime_permissions(old, fixed)
            with zipfile.ZipFile(old) as before, zipfile.ZipFile(fixed) as after:
                for name in before.namelist():
                    self.assertEqual(before.read(name), after.read(name))
                    if name in module.NEW_RUNTIME:
                        self.assertEqual(after.getinfo(name).external_attr >> 16, 0o100644)
                    else:
                        self.assertEqual(before.getinfo(name).external_attr, after.getinfo(name).external_attr)
            with self.assertRaises(RuntimeError):
                module.repair_runtime_permissions(old, fixed)


if __name__ == '__main__':
    unittest.main()
