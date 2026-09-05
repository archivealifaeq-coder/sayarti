from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.cache import cache, caches
from django.db import IntegrityError
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.utils import timezone

from cars.models import PromoCode, SiteSettings, Sponsor, SITE_SETTINGS_CACHE_KEY
from cars.views import _client_ip

# الاختبارات تعمل في عملية واحدة، لذا نستبدل التخزين "المشترك" بذاكرة محلية
# لنفس المنطق (العدّاد والحد) دون الحاجة لجدول قاعدة بيانات في قاعدة الاختبار.
_LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 't-default'},
    'shared': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 't-shared'},
}


def _make_sponsor(slug='testco', prefix='TEST'):
    sp = Sponsor.objects.create(name='شركة تجريبية', slug=slug, code_prefix=prefix, discount=10)
    sp.set_password('secret123')
    sp.save()
    return sp


class SiteSettingsCacheTests(TestCase):
    """قراءة الإعدادات من الذاكرة المؤقتة وإبطالها عند الحفظ."""

    def test_load_is_cached(self):
        cache.delete(SITE_SETTINGS_CACHE_KEY)
        SiteSettings.load()
        # القراءة الثانية يجب أن تأتي من الذاكرة المؤقتة دون أي استعلام قاعدة بيانات
        with self.assertNumQueries(0):
            second = SiteSettings.load()
        self.assertEqual(second.pk, 1)
        self.assertIsNotNone(cache.get(SITE_SETTINGS_CACHE_KEY))
        cache.delete(SITE_SETTINGS_CACHE_KEY)

    def test_save_invalidates_cache(self):
        cache.delete(SITE_SETTINGS_CACHE_KEY)
        obj = SiteSettings.load()
        self.assertIsNotNone(cache.get(SITE_SETTINGS_CACHE_KEY))
        obj.site_name = 'نسخة مختبرية'
        obj.save()
        self.assertIsNone(cache.get(SITE_SETTINGS_CACHE_KEY))


class PromoCodeConstraintTests(TestCase):
    def test_code_is_unique(self):
        sponsor = Sponsor.objects.create(name='زيت الحسام', slug='hisam', code_prefix='HISAM')
        PromoCode.objects.create(code='HISAM-1111', sponsor=sponsor)
        with self.assertRaises(IntegrityError):
            PromoCode.objects.create(code='HISAM-1111', sponsor=sponsor)


class ClientIpTests(TestCase):
    """العنوان الحقيقي يؤخذ من آخر X-Forwarded-For (nginx يضيفه آخراً)."""

    def test_takes_last_xff_not_first(self):
        req = SimpleNamespace(META={'HTTP_X_FORWARDED_FOR': '1.2.3.4, 203.0.113.9'})
        self.assertEqual(_client_ip(req), '203.0.113.9')

    def test_falls_back_to_remote_addr(self):
        req = SimpleNamespace(META={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(_client_ip(req), '127.0.0.1')


@override_settings(CACHES=_LOCMEM_CACHES)
class PromoGenerationTests(TestCase):
    def setUp(self):
        self.sp = _make_sponsor()
        caches['shared'].delete('codegen:203.0.113.5')
        self.client = Client(REMOTE_ADDR='203.0.113.5')

    def test_generate_success(self):
        r = self.client.post('/api/promo-code/generate/', {'sponsor': self.sp.slug})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(PromoCode.objects.filter(code=data['code'], sponsor=self.sp).exists())

    def test_generate_unknown_sponsor_returns_404(self):
        r = self.client.post('/api/promo-code/generate/', {'sponsor': 'nope'})
        self.assertEqual(r.status_code, 404)

    def test_generate_rejects_same_code_twice(self):
        r1 = self.client.post('/api/promo-code/generate/', {'sponsor': self.sp.slug})
        r2 = self.client.post('/api/promo-code/generate/', {'sponsor': self.sp.slug})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertNotEqual(r1.json()['code'], r2.json()['code'])

    def test_rate_limit_per_ip(self):
        caches['shared'].set('codegen:203.0.113.5', 60, 3600)
        r = self.client.post('/api/promo-code/generate/', {'sponsor': self.sp.slug})
        self.assertEqual(r.status_code, 429)
        self.assertFalse(r.json()['success'])

    def test_rate_counter_increments_after_success(self):
        self.client.post('/api/promo-code/generate/', {'sponsor': self.sp.slug})
        self.assertEqual(caches['shared'].get('codegen:203.0.113.5', 0), 1)


@override_settings(CACHES=_LOCMEM_CACHES)
class ServicesLoginTests(TestCase):
    def setUp(self):
        self.sp = _make_sponsor()
        self.ip = '203.0.113.7'
        caches['shared'].delete(f'sfail:{self.ip}')

    def test_lockout_after_five_failures(self):
        c = Client(REMOTE_ADDR=self.ip)
        for _ in range(5):
            c.post('/services/', {'identifier': 'wrong', 'password': 'x'})
        r = c.post('/services/', {'identifier': 'wrong', 'password': 'x'})
        self.assertContains(r, 'محاولات كثيرة')

    def test_unsuccessful_attempt_counts_up(self):
        Client(REMOTE_ADDR=self.ip).post('/services/', {'identifier': 'x', 'password': 'x'})
        self.assertEqual(caches['shared'].get(f'sfail:{self.ip}', 0), 1)

    def test_success_clears_counter(self):
        caches['shared'].set(f'sfail:{self.ip}', 4, 300)
        c = Client(REMOTE_ADDR=self.ip)
        r = c.post('/services/', {'identifier': self.sp.slug, 'password': 'secret123'})
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(caches['shared'].get(f'sfail:{self.ip}'))


class MixCalculatorTests(TestCase):
    def test_valid_calculation_message(self):
        r = self.client.post('/mix/', {
            'octane_target': '95', 'octane1': '91', 'octane2': '98', 'tank_capacity': '50',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'تم حساب الخلطة بنجاح')

    def test_invalid_tank_shows_error(self):
        r = self.client.post('/mix/', {
            'octane_target': '95', 'octane1': '91', 'octane2': '98', 'tank_capacity': '0',
        })
        self.assertContains(r, 'سعة الخزان')

    def test_non_numeric_values_show_error(self):
        r = self.client.post('/mix/', {
            'octane_target': 'abc', 'octane1': '91', 'octane2': '98', 'tank_capacity': '50',
        })
        self.assertContains(r, 'أرقام صحيحة')


class ReportViewTests(TestCase):
    """تقرير الأكواد: يحمّل لحد أقصى ويقبل معاملات تالفة دون 500."""

    def setUp(self):
        self.staff = User.objects.create_superuser('boss', 'boss@example.com', 'pw')
        self.client.force_login(self.staff)
        self.sp = _make_sponsor()
        PromoCode.objects.create(code='TEST-A1', sponsor=self.sp, status='used',
                                 used_at=timezone.now())
        PromoCode.objects.create(code='TEST-B2', sponsor=self.sp, status='active',
                                 created_at=timezone.now())

    def test_report_page(self):
        r = self.client.get('/admin/report/codes/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'TEST-A1')

    def test_download_all(self):
        r = self.client.get('/admin/report/codes/?period=all&download=1')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Disposition'].split(';')[0], 'attachment')
        content = r.content.decode('utf-8')
        self.assertIn('عدد الأكواد: 2', content)
        self.assertIn('المستخدمة: 1', content)

    def test_malformed_parameters_stay_200(self):
        bad_params = [
            {'period': 'month', 'month': 'abc', 'download': '1'},
            {'period': 'day', 'day': 'zzz', 'download': '1'},
            {'period': 'year', 'year': 'xx', 'download': '1'},
            {'period': 'nope', 'download': '1'},
        ]
        for params in bad_params:
            r = self.client.get('/admin/report/codes/', params)
            self.assertEqual(r.status_code, 200, msg=params)


class PageSmokeTests(TestCase):
    def test_public_pages(self):
        for path in ['/', '/mix/', '/search/', '/budget/', '/services/', '/sitemap.xml']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_admin_pages(self):
        self.client.force_login(User.objects.create_superuser('boss2', 'b2@example.com', 'pw'))
        for path in ['/admin/', '/admin/cars/promocode/', '/admin/report/codes/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)