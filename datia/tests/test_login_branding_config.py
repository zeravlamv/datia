import time
from django.test import TestCase, Client
from django.contrib.auth.models import User
from datia.models.master import GlobalConfig

class LoginBrandingConfigTests(TestCase):
    def setUp(self):
        self.client = Client()
        GlobalConfig.load()

    def test_global_config_get_ok_and_perf(self):
        t0 = time.perf_counter()
        res = self.client.get('/api/config/global')
        elapsed = time.perf_counter() - t0
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, dict)
        self.assertLess(elapsed, 1.0)

    def test_update_global_config_requires_staff(self):
        user = User.objects.create_user(username='u', password='p')
        self.client.login(username='u', password='p')
        payload = {"settings": {"app_name": "DemoApp", "selected_logo": "/static/logo.png"}}
        res = self.client.post('/api/config/global', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get('status'), 403)
        self.assertEqual(data.get('error'), 'Unauthorized')

    def test_update_global_config_ok_sets_keys(self):
        admin = User.objects.create_superuser(username='admin', email='a@b.c', password='x')
        self.client.login(username='admin', password='x')
        payload = {"settings": {"app_name": "MiApp", "selected_logo": "/static/custom.png"}}
        res = self.client.post('/api/config/global', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = self.client.get('/api/config/global').json()
        self.assertEqual(data.get('app_name'), 'MiApp')
        self.assertEqual(data.get('selected_logo'), '/static/custom.png')
