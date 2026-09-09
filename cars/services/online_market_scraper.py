import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

import requests
from django.db import transaction

from cars.models import MarketCarPriceCandidate, SiteSettings


logger = logging.getLogger('cars')

OPENSOOQ_SEARCH_URL = 'https://iq.opensooq.com/ar/search'
USER_AGENT = 'Mozilla/5.0 (compatible; SayartiPriceReview/1.0; +https://sayarti.org)'
MIN_YEAR = 1990
MAX_YEAR = datetime.now().year + 1
MIN_PRICE_IQD = 3_000_000
MAX_PRICE_IQD = 300_000_000

BRANDS = {
    'toyota': {'ar': 'تويوتا', 'en': 'Toyota', 'origin': 'japanese'},
    'hyundai': {'ar': 'هيونداي', 'en': 'Hyundai', 'origin': 'korean'},
    'kia': {'ar': 'كيا', 'en': 'Kia', 'origin': 'korean'},
    'nissan': {'ar': 'نيسان', 'en': 'Nissan', 'origin': 'japanese'},
    'chevrolet': {'ar': 'شيفروليه', 'en': 'Chevrolet', 'origin': 'american'},
    'mg': {'ar': 'MG', 'en': 'MG', 'origin': 'chinese'},
    'chery': {'ar': 'شيري', 'en': 'Chery', 'origin': 'chinese'},
    'geely': {'ar': 'جيلي', 'en': 'Geely', 'origin': 'chinese'},
    'saipa': {'ar': 'سايبا', 'en': 'Saipa', 'origin': 'iranian'},
    'samand': {'ar': 'سمند', 'en': 'Samand', 'origin': 'iranian'},
}

BODY_KEYWORDS = {
    'suv': ('suv', 'جيب', 'دفع رباعي', 'كروس', 'كروس اوفر', 'لاندكروزر', 'برادو', 'توسان', 'سبورتاج', 'راف فور'),
    'pickup': ('بيكب', 'بكب', 'بيك اب', 'هايلوكس', 'دبل قمارة'),
    'hatchback': ('هاتشباك', 'سبارك', 'بيكانتو', 'i10'),
    'van': ('فان', 'باص', 'h1', 'ستاركس'),
    'coupe': ('كوبيه', 'coupe'),
}


@dataclass
class ScrapeSummary:
    fetched: int = 0
    saved: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


def _to_int(value):
    if value is None:
        return None
    digits = re.sub(r'[^\d]', '', str(value))
    return int(digits) if digits else None


def extract_year(text):
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', str(text or ''))
    if not years:
        return None
    year = int(years[0])
    if MIN_YEAR <= year <= MAX_YEAR:
        return year
    return None


def extract_price_iqd(text):
    raw = str(text or '').strip().lower()
    if not raw or any(word in raw for word in ('مجاني', 'بدون سعر', 'قابل للتفاوض')):
        return None
    values = []
    for match in re.findall(r'[\d,]+', raw):
        value = _to_int(match)
        if value and not (MIN_YEAR <= value <= MAX_YEAR):
            values.append(value)
    if not values:
        return None
    value = max(values)
    if '$' in raw or 'دولار' in raw or 'usd' in raw:
        rate = SiteSettings.load().exchange_rate_iqd_per_usd or 1500
        value = int(value * rate)
    if MIN_PRICE_IQD <= value <= MAX_PRICE_IQD:
        return value
    return None


def detect_body_type(title):
    folded = str(title or '').lower()
    for body_type, keywords in BODY_KEYWORDS.items():
        if any(keyword in folded for keyword in keywords):
            return body_type
    return 'sedan'


def extract_model(title, brand_ar):
    cleaned = re.sub(r'\b(19\d{2}|20\d{2})\b', ' ', str(title or ''))
    cleaned = re.sub(r'[^\w\s\u0600-\u06ff]', ' ', cleaned)
    parts = [p for p in cleaned.split() if p and p != brand_ar]
    if not parts:
        return 'غير محدد'
    return parts[0][:100]


def stable_external_id(source_url):
    if not source_url:
        return None
    digest = hashlib.sha1(source_url.encode('utf-8')).hexdigest()[:14]
    return int(digest, 16)


def parse_opensooq_html(html, brand_key, optional_fields=None):
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError('beautifulsoup4 غير مثبت. نفذ: pip install -r requirements.txt') from exc

    optional_fields = set(optional_fields or [])
    brand = BRANDS[brand_key]
    soup = BeautifulSoup(html or '', 'html.parser')
    cards = soup.select('a[href*="/ar/"]')
    candidates = []
    seen_links = set()

    for link in cards:
        href = link.get('href') or ''
        source_url = urljoin('https://iq.opensooq.com', href)
        if source_url in seen_links:
            continue
        seen_links.add(source_url)

        card_text = ' '.join(link.stripped_strings)
        if brand['ar'] not in card_text and brand['en'].lower() not in card_text.lower():
            continue
        year = extract_year(card_text)
        price_iqd = extract_price_iqd(card_text)
        if not year or not price_iqd:
            continue

        model = extract_model(card_text, brand['ar'])
        item = {
            'id1': stable_external_id(source_url),
            'raw_title': card_text[:240],
            'name': f'{brand["ar"]} {model} {year}',
            'brand': brand['ar'],
            'brand_en': brand['en'],
            'model': model,
            'model_en': '',
            'year': year,
            'origin': brand['origin'],
            'body_type': detect_body_type(card_text) if 'body_type' in optional_fields else 'all',
            'condition': 'used',
            'price_iqd': price_iqd,
            'price_usd': int(price_iqd / (SiteSettings.load().exchange_rate_iqd_per_usd or 1500)) if 'price_usd' in optional_fields else None,
            'engine': '',
            'fuel_economy': '',
            'maintenance': '',
            'pros': f'مقترح من إعلان: {card_text[:180]}' if 'pros' in optional_fields else '',
            'source_name': 'السوق المفتوح العراق',
            'source_url': source_url,
            'confidence': 60,
            'notes': 'مقترح من سكربت التحديث الأونلاين، يحتاج مراجعة قبل الاعتماد.',
        }
        candidates.append(item)

    return candidates


def fetch_opensooq_brand(brand_key, max_pages=2, timeout=25, optional_fields=None):
    if brand_key not in BRANDS:
        raise ValueError('Unknown brand key')
    all_candidates = []
    with requests.Session() as session:
        session.headers.update({'User-Agent': USER_AGENT, 'Accept-Language': 'ar,en;q=0.8'})
        for page in range(1, max_pages + 1):
            response = session.get(
                OPENSOOQ_SEARCH_URL,
                params={'q': BRANDS[brand_key]['ar'], 'page': page, 'sort': 'date_desc'},
                timeout=timeout,
            )
            response.raise_for_status()
            all_candidates.extend(parse_opensooq_html(response.text, brand_key, optional_fields=optional_fields))
    return all_candidates


@transaction.atomic
def save_candidates(candidates):
    summary = ScrapeSummary(fetched=len(candidates))
    for item in candidates:
        source_url = item.get('source_url')
        if not source_url:
            summary.skipped += 1
            continue
        lookup = {'source_url': source_url}
        defaults = dict(item)
        defaults.pop('source_url', None)
        _, created = MarketCarPriceCandidate.objects.update_or_create(**lookup, defaults=defaults)
        if created:
            summary.saved += 1
        else:
            summary.updated += 1
    return summary


def run_online_update(source='opensooq', brands=None, max_pages=2, save=True, optional_fields=None):
    if source != 'opensooq':
        raise ValueError('المصدر الوحيد المدعوم حالياً هو السوق المفتوح العراق')
    summary = ScrapeSummary()
    collected = []
    for brand_key in brands or []:
        try:
            brand_candidates = fetch_opensooq_brand(brand_key, max_pages=max_pages, optional_fields=optional_fields)
            collected.extend(brand_candidates)
        except Exception as exc:
            logger.warning('Online market scrape failed for %s: %s', brand_key, exc.__class__.__name__)
            summary.failed += 1
    if save:
        saved_summary = save_candidates(collected)
        summary.fetched += saved_summary.fetched
        summary.saved += saved_summary.saved
        summary.updated += saved_summary.updated
        summary.skipped += saved_summary.skipped
    else:
        summary.fetched = len(collected)
    return summary
