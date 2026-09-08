#!/usr/bin/env python
import argparse
import os
import sys
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


def to_int(value, default=None):
    if pd.isna(value) or value == '':
        return default
    if isinstance(value, (int, float)):
        return int(value)
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else default


def norm(value, mapping, default='all'):
    return mapping.get(str(value or '').strip().lower(), mapping.get(str(value or '').strip(), default))


def read_table(source):
    path = Path(source)
    if str(source).startswith(('http://', 'https://')):
        response = requests.get(source, timeout=30, headers={'User-Agent': 'SayartiPriceUpdater/1.0'})
        response.raise_for_status()
        suffix = Path(source.split('?', 1)[0]).suffix or '.xlsx'
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            path = Path(tmp.name)
    if path.suffix.lower() in ('.xlsx', '.xls'):
        return pd.read_excel(path)
    return pd.read_csv(path)


def clean_rows(df, exchange_rate):
    rows = []
    for _, row in df.iterrows():
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
            continue
        rows.append({
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
            'source_name': str(row.get('source_name') or '').strip(),
            'source_url': str(row.get('source_url') or '').strip(),
            'is_active': str(row.get('is_active', '1')).strip().lower() not in ('0', 'false', 'no', 'لا'),
            'confidence': max(0, min(100, to_int(row.get('confidence'), 80))),
        })
    return rows


def apply_rows(rows, replace=False):
    if replace:
        MarketCarPrice.objects.all().delete()
    saved = 0
    for row in rows:
        lookup = {
            'brand': row['brand'],
            'model': row['model'],
            'year': row['year'],
            'origin': row['origin'],
            'body_type': row['body_type'],
            'condition': row['condition'],
        }
        defaults = {k: v for k, v in row.items() if k not in lookup}
        MarketCarPrice.objects.update_or_create(**lookup, defaults=defaults)
        saved += 1
    return saved


def main():
    parser = argparse.ArgumentParser(description='Update Sayarti market prices from Excel/CSV or a direct file URL.')
    parser.add_argument('source', help='Excel/CSV file path or direct URL')
    parser.add_argument('--exchange-rate', type=int, help='Manual IQD per USD rate. If omitted, SiteSettings value is used.')
    parser.add_argument('--exchange-rate-source', default='', help='Label for the exchange-rate source.')
    parser.add_argument('--replace', action='store_true', help='Delete all existing market prices before import.')
    parser.add_argument('--apply', action='store_true', help='Write changes. Without this flag the script only previews.')
    args = parser.parse_args()

    settings = SiteSettings.load()
    exchange_rate = args.exchange_rate or settings.exchange_rate_iqd_per_usd or 1500
    df = read_table(args.source)
    rows = clean_rows(df, exchange_rate)

    print(f'Exchange rate: {exchange_rate:,} IQD/USD')
    print(f'Input rows: {len(df):,}')
    print(f'Valid rows: {len(rows):,}')
    print(f'Mode: {"APPLY" if args.apply else "DRY-RUN"}')
    if rows:
        print('Sample:')
        for row in rows[:5]:
            print(f"- {row['year']} {row['name']} | {row['origin']} | {row['body_type']} | {row['price_iqd']:,} IQD | {row['price_usd'] or '-'} USD")

    if not args.apply:
        print('No changes written. Re-run with --apply to save.')
        return

    if args.exchange_rate:
        settings.exchange_rate_iqd_per_usd = args.exchange_rate
        settings.exchange_rate_source = args.exchange_rate_source or 'manual/script'
        settings.save()
    saved = apply_rows(rows, replace=args.replace)
    print(f'Saved rows: {saved:,}')


if __name__ == '__main__':
    main()
