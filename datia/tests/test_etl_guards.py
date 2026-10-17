import os
import unittest
from types import SimpleNamespace


class TestETLGuards(unittest.TestCase):
    def setUp(self):
        # Ensure env restored after tests
        self._old_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_env)

    def test_drop_physical_requires_auth(self):
        # Import here to avoid module import side-effects until needed
        from datia.api.etl_endpoints import drop_physical_tables
        # Unauthenticated
        req = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
        res = drop_physical_tables(req, table_ids="1,2,3")
        # Endpoint returns tuple (dict, status) on error paths
        self.assertIsInstance(res, tuple)
        body, status = res
        self.assertEqual(status, 401)
        self.assertEqual(body.get("status"), "error")

        # Authenticated but not admin
        user = SimpleNamespace(is_authenticated=True, is_superuser=False, groups=SimpleNamespace(filter=lambda name: SimpleNamespace(exists=lambda: False)))
        req2 = SimpleNamespace(user=user)
        res2 = drop_physical_tables(req2, table_ids="1")
        self.assertIsInstance(res2, tuple)
        body2, status2 = res2
        self.assertEqual(status2, 403)
        self.assertEqual(body2.get("status"), "error")

    def test_disable_mssql_sync_blocks_standard(self):
        os.environ['DATIA_DISABLE_MSSQL_SYNC'] = 'true'
        from datia.api.etl_endpoints import trigger_sync
        # Minimal request mock
        req = SimpleNamespace(user=None)
        body, status = trigger_sync(
            req,
            empresa_id=None,
            table_name=None,
            filter_table=None,
            sync_type="standard",
            table_ids=None,
            sync_data="true",
            year=None,
            fast_bulk=False,
            years_count=7,
            standard_tables=None,
            force_reset=False
        )
        self.assertEqual(status, 400)
        self.assertEqual(body.get("status"), "error")
        self.assertIn("DATIA_DISABLE_MSSQL_SYNC", body.get("message", ""))

