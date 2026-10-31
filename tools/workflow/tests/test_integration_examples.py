import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExampleTests(unittest.TestCase):
    def test_case_adapter_runs_callback_on_independent_copy(self):
        adapter = load('workflow_adapter', ROOT/'cases/108-frozen-release-and-ui-resources/after/adapter.py')
        with tempfile.TemporaryDirectory() as folder:
            live = Path(folder)/'source'
            live.mkdir()
            (live/'Configuration.xml').write_text('<root/>', encoding='utf-8')
            seen = []
            def lint(snapshot):
                self.assertNotEqual(snapshot, live)
                self.assertEqual((snapshot/'Configuration.xml').read_text(), '<root/>')
                seen.append(snapshot)
                return 0
            self.assertEqual(adapter.validate_snapshot(Path(folder), live, lint), 0)
            self.assertEqual(len(seen), 1)

    def test_link_checker_accepts_existing_bsl_under_tools(self):
        checker = load('workflow_link_checker', ROOT/'tools/check_links.py')
        self.assertIsNone(checker.resolve('tools/workflow/reference/manager.bsl', str(ROOT)))
        self.assertIsNotNone(checker.resolve('tools/workflow/reference/absent.bsl', str(ROOT)))
