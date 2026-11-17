import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog', ROOT/'scripts/generate-ui-catalog.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def test_generated_catalog_is_current(self):
        self.assertEqual(catalog.generate(), catalog.OUTPUT.read_text(encoding='ascii'))

    def test_reject_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads('{"same": 1, "same": 2}', object_pairs_hook=catalog.unique)

    def test_escape_boundary_before_digits(self):
        emitted = catalog.literal('中文89，1–128，CP866，96-DPI')
        self.assertNotRegex(emitted, r'\\[0-7]{3}[0-9]')
        self.assertTrue(emitted.isascii())

    def test_reject_format_specifiers(self):
        with self.assertRaises(ValueError): catalog.parameters('{app!r}')
        with self.assertRaises(ValueError): catalog.parameters('{0}')

    def test_reject_different_template_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            for lang, value in [('en', '{profile}'), ('zh-CN', '{shell}')]:
                (Path(directory)/f'{lang}.json').write_text(json.dumps(dict(
                    schema=1, locale=lang, messages={'profile.active': value})), encoding='utf-8')
            with self.assertRaises(ValueError): catalog.generate(Path(directory))

    def test_reject_different_keys_and_allow_empty_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            for lang, messages in [('en', {'profile.active':'{profile}'}), ('zh-CN', {})]:
                (Path(directory)/f'{lang}.json').write_text(json.dumps(dict(
                    schema=1, locale=lang, messages=messages)), encoding='utf-8')
            with self.assertRaises(ValueError): catalog.generate(Path(directory))
            (Path(directory)/'zh-CN.json').write_text(json.dumps(dict(
                schema=1,locale='zh-CN',messages={'profile.active':''})), encoding='utf-8')
            self.assertIn('profile.active', catalog.generate(Path(directory)))


if __name__ == '__main__': unittest.main()
