"""Offline orchestration checks: never import a Windows fixture or launch a GUI."""
import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('interaction_acceptance', ROOT/'scripts/interaction_acceptance.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base/'source'
        for name in ('tests', 'tools', 'scripts'):
            (self.source/name).mkdir(parents=True)
        (self.source/'tests/fixture.py').write_text('raise RuntimeError("must never run")')
        (self.source/'tools/nemoterm_debug.py').write_text('# snapshot')
        (self.source/'scripts/interaction_manual.py').write_text('# manual snapshot')
        self.exe = self.base/'candidate.exe'
        self.exe.write_bytes(b'not executable; preparation must only hash and copy')
        self.args = argparse.Namespace(stage=self.base/'stage', exe=self.exe,
            sha256=runner.digest(self.exe), codex=None, opencode=None)

    def prepare(self):
        with patch.object(runner, 'ROOT', self.source), patch.object(runner.subprocess, 'check_output',
                side_effect=['a'*40+'\n', '']), patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('No launch')):
            with contextlib.redirect_stdout(io.StringIO()):runner.prepare(self.args)

    def test_default_only_lists_plan(self):
        with patch.object(runner, 'prepare', side_effect=AssertionError()), patch.object(runner, 'run', side_effect=AssertionError()):
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(runner.main([]), 0)
            self.assertIn('input-byte', text.getvalue())

    def test_catalog_has_unique_real_fixtures(self):
        cases = runner.catalog()
        self.assertEqual(len(cases), 26)
        self.assertEqual(len({c['id'] for c in cases}), 26)
        for case in cases:self.assertTrue((ROOT/'tests'/case['script']).is_file())

    def test_unknown_selection_rejected(self):
        with self.assertRaises(ValueError):runner.selected(runner.catalog(), ['typo'])

    def test_group_and_case_union_deduplicated(self):
        self.assertEqual([c['id'] for c in runner.selected(runner.catalog(), ['input'], ['input-byte'])], ['input-byte', 'input-wide'])

    def test_prepare_does_not_execute_candidate(self):
        self.prepare()
        self.assertEqual(runner.verify_stage(self.args.stage)['executable_sha256'], self.args.sha256)
        self.assertEqual(runner.load(self.args.stage/'results.json'), [])
        self.assertTrue(all(c['status']=='not_run' for c in runner.load(self.args.stage/'manual-results.json')['checks']))

    def test_bad_image_hash_leaves_no_stage(self):
        self.args.sha256='0'*64
        with self.assertRaises(ValueError):runner.prepare(self.args)
        self.assertFalse(self.args.stage.exists())

    def test_existing_stage_preserved(self):
        self.prepare()
        with self.assertRaises(ValueError):runner.prepare(self.args)
        runner.verify_stage(self.args.stage)

    def test_changed_snapshot_rejected(self):
        self.prepare()
        (self.args.stage/'snapshot/tests/fixture.py').write_text('# changed')
        with self.assertRaises(ValueError):runner.verify_stage(self.args.stage)

    def test_changed_manual_helper_rejected(self):
        self.prepare()
        (self.args.stage/'interaction_manual.py').write_text('# changed')
        with self.assertRaises(ValueError):runner.verify_stage(self.args.stage)

    def test_execution_rejects_local_and_self_hosted_desktops(self):
        for environment in ({}, {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'self-hosted'}):
            with patch.dict(runner.os.environ, environment, clear=True):
                with self.assertRaises(ValueError):runner.run(argparse.Namespace())

    def test_remote_runner_retains_ci_identity(self):
        with patch.dict(runner.os.environ, {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted'}):
            runner.require_remote_runner()
            self.assertEqual(runner.os.environ['GITHUB_ACTIONS'], 'true')

    def test_stop_only_writes_marker(self):
        self.prepare()
        with contextlib.redirect_stdout(io.StringIO()):runner.main(['stop','--stage',str(self.args.stage)])
        self.assertTrue((self.args.stage/'STOP').exists())
        self.assertEqual(runner.load(self.args.stage/'results.json'), [])


if __name__=='__main__':unittest.main()
