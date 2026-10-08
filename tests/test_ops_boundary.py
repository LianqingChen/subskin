"""Guard the website/host-operations split without touching application databases."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("site_maintenance", ROOT / "web/backend/services/site_maintenance.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class OpsBoundaryTests(unittest.TestCase):
    def test_storage_metadata_is_bounded_to_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'website.sqlite'
            database.write_bytes(b'example')
            result = module.storage_status(str(database))
            self.assertEqual(result, {'available': True, 'database_bytes': 7, 'wal_bytes': 0})
            self.assertNotIn(directory, str(result))
    def test_retired_routes_are_not_registered_or_exported(self):
        for name in ['web/backend/app/main.py', 'web/backend/api/__init__.py']:
            source = (ROOT / name).read_text()
            self.assertNotIn('admin_terminal', source)
        tree = ast.parse((ROOT/'web/backend/api/admin_general.py').read_text())
        paths = [node.args[0].value for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('get','post') and node.args and isinstance(node.args[0],ast.Constant)]
        self.assertFalse(any(str(path).startswith('/system/') for path in paths))
        self.assertIn('/embed-batch',paths);self.assertIn('/site/status',paths);self.assertIn('/content/briefings',paths)
    def test_terminal_frontend_dependencies_are_removed(self):
        import json
        dependencies=json.loads((ROOT/'web/admin/package.json').read_text())['dependencies']
        self.assertFalse(any(name.startswith('@xterm/') for name in dependencies))
        self.assertFalse((ROOT/'web/admin/src/views/Terminal.vue').exists())

if __name__=='__main__': unittest.main()
