#!/usr/bin/env python
import argparse
import html
import json
import os
import re
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
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; SayartiMarketUpdater/1.0; +https://sayarti.org)',
    'Accept-Language': 'ar-IQ,ar;q=0.9,en;q=0.8',
}

BRAND_ALIASES = {
    'تويوتا': ('تويوتا', 'Toyota', 'japanese'), 'toyota': ('تويوتا', 'Toyota', 'japanese'),
    'لكزس': ('لكزس', 'Lexus', 'japanese'), 'lexus': ('لكزس', 'Lexus', 'japanese'),
    'نيسان': ('نيسان', 'Nissan', 'japanese'), 'nissan': ('نيسان', 'Nissan', 'japanese'),
    'هوندا': ('هوندا', 'Honda', 'japanese'), 'honda': ('هوندا', 'Honda', 'japanese'),
    'مازدا': ('مازدا', 'Mazda', 'japanese'), 'mazda': ('مازدا', 'Mazda', 'japanese'),
    'سوزوكي': ('سوزوكي', 'Suzuki', 'japanese'), 'suzuki': ('سوزوكي', 'Suzuki', 'japanese'),
    'هيونداي': ('هيونداي', 'Hyundai', 'korean'), 'هونداي': ('هيونداي', 'Hyundai', 'korean'), 'hyundai': ('هيونداي', 'Hyundai', 'korean'),
    'كيا': ('كيا', 'Kia', 'korean'), 'kia': ('كيا', 'Kia', 'korean'),
    'جينيسس': ('جينيسس', 'Genesis', 'korean'), 'genesis': ('جينيسس', 'Genesis', 'korean'),
    'بي واي دي': ('بي واي دي', 'BYD', 'chinese'), 'byd': ('بي واي دي', 'BYD', 'chinese'),
    'جيتور': ('جيتور', 'Jetour', 'chinese'), 'jetour': ('جيتور', 'Jetour', 'chinese'),
    'شيري': ('شيري', 'Chery', 'chinese'), 'chery': ('شيري', 'Chery', 'chinese'),
    'ام جي': ('إم جي', 'MG', 'chinese'), 'إم جي': ('إم جي', 'MG', 'chinese'), 'mg': ('إم جي', 'MG', 'chinese'),
    'شيفروليه': ('شيفروليه', 'Chevrolet', 'american'), 'شفروليه': ('شيفروليه', 'Chevrolet', 'american'), 'chevrolet': ('شيفروليه', 'Chevrolet', 'american'),
    'فورد': ('فورد', 'Ford', 'american'), 'ford': ('فورد', 'Ford', 'american'),
    'دودج': ('دودج', 'Dodge', 'american'), 'dodge': ('دودج', 'Dodge', 'american'),
    'جيب': ('جيب', 'Jeep', 'american'), 'jeep': ('جيب', 'Jeep', 'american'),
    'جي ام سي': ('جي إم سي', 'GMC', 'american'), 'gmc': ('جي إم سي', 'GMC', 'american'),
    'كاديلاك': ('كاديلاك', 'Cadillac', 'american'), 'cadillac': ('كاديلاك', 'Cadillac', 'american'),
    'مرسيدس': ('مرسيدس', 'Mercedes-Benz', 'german'), 'mercedes': ('مرسيدس', 'Mercedes-Benz', 'german'), 'mercedes benz': ('مرسيدس', 'Mercedes-Benz', 'german'),
    'بي ام دبليو': ('بي إم دبليو', 'BMW', 'german'), 'بي إم دبليو': ('بي إم دبليو', 'BMW', 'german'), 'bmw': ('بي إم دبليو', 'BMW', 'german'),
    'فولكسفاغن': ('فولكسفاغن', 'Volkswagen', 'german'), 'volkswagen': ('فولكسفاغن', 'Volkswagen', 'german'),
    'اودي': ('أودي', 'Audi', 'german'), 'أودي': ('أودي', 'Audi', 'german'), 'audi': ('أودي', 'Audi', 'german'),
    'بيجو': ('بيجو', 'Peugeot', 'european'), 'peugeot': ('بيجو', 'Peugeot', 'european'),
    'رينو': ('رينو', 'Renault', 'european'), 'renault': ('رينو', 'Renault', 'european'),
    'لاند روفر': ('لاند روفر', 'Land Rover', 'european'), 'land rover': ('لاند روفر', 'Land Rover', 'european'),
    'جاكوار': ('جاكوار', 'Jaguar', 'european'), 'jaguar': ('جاكوار', 'Jaguar', 'european'),
    'تيوته': ('تويوتا', 'Toyota', 'japanese'),
}

MODEL_BRAND_HINTS = {
    'توسان': ('هيونداي', 'Hyundai', 'korean'), 'tucson': ('هيونداي', 'Hyundai', 'korean'),
    'النترا': ('هيونداي', 'Hyundai', 'korean'), 'elantra': ('هيونداي', 'Hyundai', 'korean'),
    'سوناتا': ('هيونداي', 'Hyundai', 'korean'), 'sonata': ('هيونداي', 'Hyundai', 'korean'),
    'سبورتاج': ('كيا', 'Kia', 'korean'), 'sportage': ('كيا', 'Kia', 'korean'),
    'كراون': ('تويوتا', 'Toyota', 'japanese'), 'crown': ('تويوتا', 'Toyota', 'japanese'),
    'راف فور': ('تويوتا', 'Toyota', 'japanese'), 'rav4': ('تويوتا', 'Toyota', 'japanese'),
    'كامري': ('تويوتا', 'Toyota', 'japanese'), 'camry': ('تويوتا', 'Toyota', 'japanese'),
    'كورولا': ('تويوتا', 'Toyota', 'japanese'), 'corolla': ('تويوتا', 'Toyota', 'japanese'),
    'اكورد': ('هوندا', 'Honda', 'japanese'), 'accord': ('هوندا', 'Honda', 'japanese'),
    'ماليبو': ('شيفروليه', 'Chevrolet', 'american'), 'malibu': ('شيفروليه', 'Chevrolet', 'american'),
    'تاهو': ('شيفروليه', 'Chevrolet', 'american'), 'tahoe': ('شيفروليه', 'Chevrolet', 'american'),
    'اكاديا': ('جي إم سي', 'GMC', 'american'), 'acadia': ('جي إم سي', 'GMC', 'american'),
    'جالنجر': ('دودج', 'Dodge', 'american'), 'challenger': ('دودج', 'Dodge', 'american'),
    'جارجر': ('دودج', 'Dodge', 'american'), 'تشارجر': ('دودج', 'Dodge', 'american'), 'charger': ('دودج', 'Dodge', 'american'),
    'جيتا': ('فولكسفاغن', 'Volkswagen', 'german'), 'jetta': ('فولكسفاغن', 'Volkswagen', 'german'),
    'defender': ('لاند روفر', 'Land Rover', 'european'), 'ديفندر': ('لاند روفر', 'Land Rover', 'european'),
}

BODY_HINTS = {
    'suv': ('راف', 'راف4', 'rav4', 'توسان', 'tucson', 'سبورتاج', 'sportage', 'اكاديا', 'acadia', 'باليسيد', 'palisade', 'لاندكروزر', 'land cruiser', 'برادو', 'prado', 'تاهو', 'tahoe', 'يوكن', 'yukon', 'شيروكي', 'cherokee', 'ديفندر', 'defender', 'lx', '5008'),
    'pickup': ('هايلكس', 'hilux', 'رام', 'ram ', 'سلفرادو', 'silverado', 'f-150', 'رابتور', 'raptor'),
    'hatchback': ('يارس', 'yaris', 'بيكانتو', 'picanto', 'i10', 'swift'),
    'van': ('باص', 'فان', 'van', 'هايس', 'hiace'),
    'coupe': ('كوبيه', 'coupe', 'جالنجر', 'challenger', 'كمارو', 'camaro', 'موستنج', 'mustang'),
    'sedan': ('كورولا', 'corolla', 'كامري', 'camry', 'النترا', 'elantra', 'سوناتا', 'sonata', 'ماليبو', 'malibu', 'اكورد', 'accord', 'تشارجر', 'charger', 'جارجر', 'جيتا', 'jetta', 'k5'),
}


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
    response = requests.get(url, timeout=35, headers=REQUEST_HEADERS)
    response.raise_for_status()
    suffix = Path(url.split('?', 1)[0]).suffix.lower() or '.csv'
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(response.content)
        return Path(tmp.name)


def fetch_html(url):
    response = requests.get(url, timeout=35, headers=REQUEST_HEADERS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_year(text):
    match = re.search(r'\b(19[9]\d|20\d{2})\b', str(text or ''))
    return int(match.group(1)) if match else None


def normalized_text(value):
    return re.sub(r'\s+', ' ', str(value or '').replace('ـ', '').strip()).lower()


def infer_brand(title):
    lowered = normalized_text(title)
    for alias in sorted(BRAND_ALIASES, key=len, reverse=True):
        if alias in lowered:
            return BRAND_ALIASES[alias]
    for alias in sorted(MODEL_BRAND_HINTS, key=len, reverse=True):
        if alias in lowered:
            return MODEL_BRAND_HINTS[alias]
    parts = str(title or '').split()
    brand = parts[0] if parts else ''
    return brand, '', 'all'


def infer_model(title, brand):
    clean_title = re.sub(r'\b(19[9]\d|20\d{2})\b', ' ', str(title or ''))
    clean_title = re.sub(r'[^\w\u0600-\u06FF\-]+', ' ', clean_title).strip()
    words = clean_title.split()
    if not words:
        return ''
    brand_words = set(str(brand or '').replace('إ', 'ا').replace('أ', 'ا').split())
    filtered = [w for w in words if w.replace('إ', 'ا').replace('أ', 'ا') not in brand_words]
    return filtered[0] if filtered else words[-1]


def infer_body_type(title):
    lowered = normalized_text(title)
    for body_type, hints in BODY_HINTS.items():
        if any(hint in lowered for hint in hints):
            return body_type
    return 'all'


def price_fields(price, currency, exchange_rate):
    amount = to_int(price)
    if not amount or amount <= 0:
        return None, None
    currency = str(currency or '').upper()
    if currency == 'USD' and amount < 500000:
        return int(amount * exchange_rate), amount
    if currency == 'IQD' or amount >= 500000:
        return amount, int(amount / exchange_rate)
    return int(amount * exchange_rate), amount


def source_row(title, year, price, currency, url, source_name, exchange_rate, condition='used'):
    brand, brand_en, origin = infer_brand(title)
    model = infer_model(title, brand)
    price_iqd, price_usd = price_fields(price, currency, exchange_rate)
    if not (brand and model and year and price_iqd):
        return None
    if price_iqd < 3000000 or price_iqd > 300000000:
        return None
    return {
        'name': str(title or f'{brand} {model} {year}').strip()[:180],
        'brand_ar': brand,
        'brand_en': brand_en,
        'model_ar': model,
        'year': year,
        'origin': origin,
        'body_type': infer_body_type(title),
        'condition': condition,
        'price_iqd': price_iqd,
        'price_usd': price_usd,
        'source_name': source_name,
        'source_url': url,
        'confidence': 72,
        'pros': f'سعر مستخرج من عرض منشور في {source_name}.',
    }


def read_opensooq_rows(source, exchange_rate):
    page = fetch_html(source)
    rows = []
    scripts = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, flags=re.S | re.I)
    for script in scripts:
        try:
            data = json.loads(html.unescape(script.strip()))
        except json.JSONDecodeError:
            continue
        graphs = data.get('@graph') if isinstance(data, dict) else []
        for graph in graphs or []:
            item_list = graph.get('itemListElement') if isinstance(graph, dict) else None
            if not item_list:
                continue
            for entry in item_list:
                if not isinstance(entry, dict):
                    continue
                item = entry.get('item') or {}
                if not isinstance(item, dict):
                    continue
                if item.get('@type') != 'Vehicle':
                    continue
                offer = item.get('offers') or {}
                condition = 'new' if 'NewCondition' in str(item.get('itemCondition') or '') else 'used'
                row = source_row(
                    item.get('name'),
                    extract_year(item.get('name') or item.get('description')),
                    offer.get('price'),
                    offer.get('priceCurrency'),
                    item.get('url') or source,
                    'السوق المفتوح',
                    exchange_rate,
                    condition,
                )
                if row:
                    rows.append(row)
    return rows


def dict_value(obj, *keys):
    if not isinstance(obj, dict):
        return ''
    for key in keys:
        value = obj.get(key)
        if value not in (None, ''):
            return value
    return ''


def localized_value(obj, base):
    return dict_value(obj, base, f'{base}Ar', f'{base}AR', f'{base}Arabic', f'{base}Name', f'{base}NameAr', f'{base}NameAR', f'{base}NameArabic')


def read_iqcars_rows(source, exchange_rate):
    page = fetch_html(source)
    match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', page, flags=re.S | re.I)
    if not match:
        return []
    try:
        data = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return []
    payload = data.get('props', {}).get('pageProps', {}).get('data', {}).get('data', {})
    cars = list(payload.get('Cars') or [])
    for featured in payload.get('FeaturedCars') or []:
        car = featured.get('Car') if isinstance(featured, dict) else None
        if car:
            cars.append(car)
    rows = []
    seen = set()
    for car in cars:
        car_id = dict_value(car, 'ID', 'Id', 'id')
        if car_id and car_id in seen:
            continue
        seen.add(car_id)
        brand_obj = car.get('Brand') or {}
        model_obj = car.get('Model') or {}
        sfx_obj = car.get('ModelSFX') or {}
        year_obj = car.get('Year') or {}
        brand = localized_value(brand_obj, 'Brand') or localized_value(brand_obj, 'BrandName')
        model = localized_value(model_obj, 'Model') or localized_value(model_obj, 'ModelName')
        sfx = localized_value(sfx_obj, 'SFX') or localized_value(sfx_obj, 'SFXName')
        year = to_int(localized_value(year_obj, 'Year') or dict_value(car, 'YearName', 'Year'))
        title = ' '.join(str(part).strip() for part in (brand, model, sfx, year) if part)
        url = f'https://www.iqcars.net/ar/car/{car_id}' if car_id else source
        price = dict_value(car, 'PriceIQD', 'Price', 'PricePublishing', 'LastPrice')
        currency = 'IQD' if dict_value(car, 'PriceIQD') else 'USD'
        row = source_row(title, year, price, currency, url, 'IQCars', exchange_rate, 'used')
        if row:
            rows.append(row)
    return rows


def read_rows(source, exchange_rate=None):
    if source.startswith(('http://', 'https://')):
        lowered = source.lower()
        if 'opensooq.com' in lowered:
            return read_opensooq_rows(source, exchange_rate or 1500)
        if 'iqcars.net' in lowered:
            return read_iqcars_rows(source, exchange_rate or 1500)
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
        'id1': to_int(row.get('id1')),
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
        lookup = {'id1': row['id1']} if row.get('id1') else {
            'brand': row['brand'], 'model': row['model'], 'year': row['year'],
            'origin': row['origin'], 'body_type': row['body_type'], 'condition': row['condition'],
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
    failed_sources = []
    seen_id1 = set()
    for source in args.source:
        try:
            rows = read_rows(source, exchange_rate)
        except requests.RequestException as exc:
            failed_sources.append((source, str(exc)))
            continue
        raw_count += len(rows)
        for row in rows:
            clean = clean_row(row, exchange_rate, args.source_name)
            if clean:
                if clean.get('id1'):
                    if clean['id1'] in seen_id1:
                        continue
                    seen_id1.add(clean['id1'])
                cleaned.append(clean)

    accepted, low_samples = aggregate_rows(cleaned, args.min_samples)
    max_change_percent = args.max_change_percent / 100

    print(f'Exchange rate: {exchange_rate:,} IQD/USD')
    print(f'Sources: {len(args.source):,}')
    print(f'Input rows: {raw_count:,}')
    print(f'Valid rows: {len(cleaned):,}')
    print(f'Accepted groups: {len(accepted):,}')
    print(f'Low-sample groups: {len(low_samples):,}')
    print(f'Failed sources: {len(failed_sources):,}')
    print(f'Max accepted change: {args.max_change_percent:.1f}%')
    print(f'Mode: {"APPLY" if args.apply else "DRY-RUN"}')
    for source, error in failed_sources[:5]:
        print(f'! Failed source: {source} | {error}')
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
