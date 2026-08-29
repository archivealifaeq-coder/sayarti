# -*- coding: utf-8 -*-
import json
from datetime import date, timedelta

from django.core.cache import cache

try:
    from google.oauth2 import service_account as _sa
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
    _GA_LIB_AVAILABLE = True
except Exception:  # noqa: BLE001 - library optional
    BetaAnalyticsDataClient = None
    _GA_LIB_AVAILABLE = False


CACHE_KEY = 'ga_visitor_stats'
CACHE_TTL = 600  # 10 minutes


def _run_report(client, property_id, days):
    end = date.today()
    start = end - timedelta(days=days)
    request = RunReportRequest(
        property='properties/{}'.format(property_id),
        date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        metrics=[Metric(name='activeUsers')],
    )
    response = client.run_report(request)
    if response.rows:
        return int(response.rows[0].metric_values[0].value)
    return 0


def get_visitor_stats(property_id=None, service_account_json=None, use_cache=True):
    """Return visitor counts for today/week/month/all time or an error status.

    Returns a dict with keys: status ('ok'|'setup'|'error'), today, week,
    month, total, and optional message.
    """
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached

    if not _GA_LIB_AVAILABLE:
        result = {'status': 'setup', 'today': 0, 'week': 0, 'month': 0, 'total': 0,
                  'message': 'الحزمة google-analytics-data غير مثبتة على الخادم'}
        if use_cache:
            cache.set(CACHE_KEY, result, CACHE_TTL)
        return result

    if property_id is None or service_account_json is None:
        from .models import SiteSettings
        settings = SiteSettings.load()
        property_id = property_id or settings.ga4_property_id
        service_account_json = service_account_json or settings.ga_service_account_json

    if not property_id or not service_account_json:
        return {'status': 'setup', 'today': 0, 'week': 0, 'month': 0, 'total': 0,
                'message': 'أدخل معرف الخاصية ومفتاح الخدمة في إعدادات الموقع'}

    try:
        info = json.loads(service_account_json)
        credentials = _sa.Credentials.from_service_account_info(info)
        client = BetaAnalyticsDataClient(credentials=credentials)
        today = _run_report(client, property_id, 0)
        week = _run_report(client, property_id, 7)
        month = _run_report(client, property_id, 30)
        total = _run_report(client, property_id, 2000)  # من 2020 حتى اليوم
        result = {'status': 'ok', 'today': today, 'week': week,
                  'month': month, 'total': total}
    except Exception as exc:  # noqa: BLE001
        result = {'status': 'error', 'today': 0, 'week': 0, 'month': 0, 'total': 0,
                  'message': 'تعذر جلب الإحصائيات: {}'.format(exc)}

    if use_cache:
        cache.set(CACHE_KEY, result, CACHE_TTL)
    return result