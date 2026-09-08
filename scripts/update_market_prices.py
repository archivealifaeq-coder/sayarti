#!/usr/bin/env python
import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import requests


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from cars.models import MarketCarPrice, SiteSettings  # noqa: E402


ORIGINS = {
    'all': 'all', 'عام': 'all', 'الكل': 'all',
    'japanese': 'japanese', 'ياباني': 'japanese',
    'korean': 'korean', 'كوري': 'korean',
    'chinese': 'chinese', 'صيني': 'chinese',
    'american': 'american', 'امريكي': 'american', 'أمريكي': 'american',
    'german': 'german', 'الماني': 'german', 'ألماني': 'german',
    'european': 'european', 'اوربي': 'european', 'أوروبي': 'european',
    'iranian': 'iranian', 'ايراني': 'iranian', 'إيراني': 'iranian',
}

BODY_TYPES = {
    'all': 'all', 'عام': 'all', 'الكل': 'all',
    'sedan': 'sedan', 'سيدان': 'sedan',
    'suv': 'suv', 'عائلي': 'suv', 'عائلية': 'suv', 'اس يو في': 'suv',
    'pickup': 'pickup', 'بيكب': 'pickup', 'بكب': 'pickup',
    'hatchback': 'hatchback', 'هاتشباك': 'hatchback',
    'van': 'van', 'فان': 'van',
    'coupe': 'coupe', 'كوبيه': 'coupe',
}

CONDITIONS = {'used': 'used', 'مستعمل': 'used', 'new': 'new', 'جديد': 'new'}
REQUIRED_COLUMNS = {'name', 'brand_ar', 'model_ar', 'year', 'origin', 'body_type', 'condition'}


def to_int(value, default=None):
    if pd.isna(value) or value == '':
        return default
    if isinstance(value, (int, float)):
        return int(value)
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else default


def norm(value, mapping, default='all'):
    raw = str(value or '').strip()
    return mapping.get(raw.lower(), mapping.get(raw, default))


def download_to_temp(url):
    response = requests.get(url, timeout=35, headers={'User-Agent': 'SayartiMarketUpdater/1.0'})
    response.raise_for_status()
    suffix = Path(url.split('?', 1)[0]).suffix.lower() or '.csv'
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(response.content)
        return Path(tmp.name)


def read_rows(source):
    path = download_to_temp(source) if source.startswith(('http://', 'https://')) else Path(source)
    suffix = path.suffix.lower()
    if suffix in ('.xlsx', '.xls'):
        return pd.read_excel(path).to_dict('records')
    if suffix == '.json':
        data = json.loads(path.read_text(encoding='utf-8'))
        return data['cars'] if isinstance(data, dict) and isinstance(data.get('cars'), list) else data
    return pd.read_csv(path).to_dict('records')


def clean_row(row, exchange_rate, source_name):
    brand = str(row.get('brand_ar') or row.get('brand') or '').strip()
    model = str(row.get('model_ar') or row.get('model') or '').strip()
    year = to_int(row.get('year'))
    price_iqd = to_int(row.get('price_iqd') or row.get('price'))
    price_usd = to_int(row.get('price_usd'))
    if not price_iqd and price_usd:
        price_iqd = int(price_usd * exchange_rate)
    if not price_usd and price_iqd:
        price_usd = int(price_iqd / exchange_rate)
    if not (brand and model and year and price_iqd):
        return None
    return {
        'name': str(row.get('name') or f'{brand} {model} {year}').strip(),
        'brand': brand,
        'brand_en': str(row.get('brand_en') or '').strip(),
        'model': model,
        'model_en': str(row.get('model_en') or '').strip(),
        'year': year,
        'origin': norm(row.get('origin') or row.get('car_type'), ORIGINS),
        'body_type': norm(row.get('body_type'), BODY_TYPES),
        'condition': norm(row.get('condition'), CONDITIONS, 'used'),
        'price_iqd': price_iqd,
        'price_usd': price_usd,
        'engine': str(row.get('engine') or '').strip(),
        'fuel_economy': str(row.get('fuel_economy') or 'جيد').strip(),
        'maintenance': str(row.get('maintenance') or 'متوسطة').strip(),
        'pros': str(row.get('pros') or '').strip()[:240],
        'source_name': str(row.get('source_name') or source_name).strip(),
        'source_url': str(row.get('source_url') or '').strip(),
        'is_active': str(row.get('is_active', '1')).strip().lower() not in ('0', 'false', 'no', 'لا'),
        'confidence': max(0, min(100, to_int(row.get('confidence'), 80))),
    }


def group_key(row):
    return (row['brand'], row['model'], row['year'], row['origin'], row['body_type'], row['condition'])


def aggregate_rows(rows, min_samples):
    grouped = defaultdict(list)
    for row in rows:
        grouped[group_key(row)].append(row)

    accepted = []
    low_samples = []
    for key, items in grouped.items():
        if len(items) < min_samples:
            low_samples.append((key, items))
            continue
        prices_iqd = [i['price_iqd'] for i in items if i['price_iqd']]
        prices_usd = [i['price_usd'] for i in items if i['price_usd']]
        base = max(items, key=lambda i: (i['confidence'], len(i.get('source_url') or ''))).copy()
        base['price_iqd'] = int(statistics.median(prices_iqd))
        base['price_usd'] = int(statistics.median(prices_usd)) if prices_usd else None
        base['confidence'] = min(100, int(sum(i['confidence'] for i in items) / len(items)) + min(10, len(items) * 2))
        base['pros'] = base['pros'] or f'سعر محسوب من {len(items)} مصدر/عرض بعد مراجعة أولية.'
        accepted.append(base)
    return accepted, low_samples


def is_large_change(existing, row, max_change_percent):
    if not existing or not existing.price_iqd:
        return False
    change = abs(row['price_iqd'] - existing.price_iqd) / existing.price_iqd
    return change > max_change_percent


def apply_rows(rows, max_change_percent, allow_large_change):
    saved = skipped_large = 0
    for row in rows:
        lookup = {
            'brand': row['brand'],
            'model': row['model'],
            'year': row['year'],
            'origin': row['origin'],
            'body_type': row['body_type'],
            'condition': row['condition'],
        }
        existing = MarketCarPrice.objects.filter(**lookup).first()
        if is_large_change(existing, row, max_change_percent) and not allow_large_change:
            skipped_large += 1
            continue
        defaults = {k: v for k, v in row.items() if k not in lookup}
        MarketCarPrice.objects.update_or_create(**lookup, defaults=defaults)
        saved += 1
    return saved, skipped_large


def main():
    parser = argparse.ArgumentParser(description='Update Sayarti market prices from approved structured sources.')
    parser.add_argument('--source', action='append', required=True, help='Approved CSV/Excel/JSON source URL or file. Repeatable.')
    parser.add_argument('--source-name', default='مصدر معتمد', help='Default source label if rows do not include source_name.')
    parser.add_argument('--exchange-rate', type=int, help='Manual IQD per USD rate. If omitted, SiteSettings value is used and not changed.')
    parser.add_argument('--exchange-rate-source', default='', help='Saved only when --exchange-rate and --apply are used.')
    parser.add_argument('--min-samples', type=int, default=1, help='Minimum offers per car key before accepting an update.')
    parser.add_argument('--max-change-percent', type=float, default=8.0, help='Reject existing-price changes above this percent unless allowed.')
    parser.add_argument('--allow-large-change', action='store_true', help='Allow updates even if price changed strongly.')
    parser.add_argument('--replace', action='store_true', help='Delete existing prices before saving accepted rows.')
    parser.add_argument('--apply', action='store_true', help='Write changes. Without this flag the script only previews.')
    args = parser.parse_args()

    settings = SiteSettings.load()
    exchange_rate = args.exchange_rate or settings.exchange_rate_iqd_per_usd or 1500
    cleaned = []
    raw_count = 0
    for source in args.source:
        rows = read_rows(source)
        raw_count += len(rows)
        for row in rows:
            clean = clean_row(row, exchange_rate, args.source_name)
            if clean:
                cleaned.append(clean)

    accepted, low_samples = aggregate_rows(cleaned, args.min_samples)
    max_change_percent = args.max_change_percent / 100

    print(f'Exchange rate: {exchange_rate:,} IQD/USD')
    print(f'Sources: {len(args.source):,}')
    print(f'Input rows: {raw_count:,}')
    print(f'Valid rows: {len(cleaned):,}')
    print(f'Accepted groups: {len(accepted):,}')
    print(f'Low-sample groups: {len(low_samples):,}')
    print(f'Max accepted change: {args.max_change_percent:.1f}%')
    print(f'Mode: {"APPLY" if args.apply else "DRY-RUN"}')
    for row in accepted[:10]:
        print(f"- {row['year']} {row['name']} | {row['origin']} | {row['body_type']} | {row['price_iqd']:,} IQD | {row['price_usd'] or '-'} USD | confidence {row['confidence']}%")

    if not args.apply:
        print('No changes written. Re-run with --apply to save accepted updates.')
        return

    if args.replace:
        MarketCarPrice.objects.all().delete()
    if args.exchange_rate:
        settings.exchange_rate_iqd_per_usd = args.exchange_rate
        settings.exchange_rate_source = args.exchange_rate_source or 'manual/script'
        settings.save()
    saved, skipped_large = apply_rows(accepted, max_change_percent, args.allow_large_change)
    print(f'Saved rows: {saved:,}')
    print(f'Skipped large changes: {skipped_large:,}')


if __name__ == '__main__':
    main()
