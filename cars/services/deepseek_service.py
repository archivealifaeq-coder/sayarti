import json
import logging
import hashlib
import re
import requests
from django.conf import settings
from django.core.cache import cache, caches
from django.db.models import Q
from ..models import SiteSettings, MarketCarPrice

logger = logging.getLogger('cars')

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'qwen/qwen3.8-27b'
TIMEOUT = 35

DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
DEEPSEEK_MODEL = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
if DEEPSEEK_MODEL == 'deepseek-v4-flash':
    DEEPSEEK_MODEL = 'deepseek-chat'
GEMINI_MODEL = getattr(settings, 'GEMINI_MODEL', 'gemini-3.6-flash')
GEMINI_API_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'

MARKET_BUDGET_RESULTS = 4
MIN_YEAR = 1990
MAX_YEAR = 2026
BUDGET_MARGIN_PERCENT = 0.02
PREMIUM_AI_PER_IP_HOURLY_LIMIT = 5

def _get_key(settings_field, env_field):
    try:
        val = getattr(SiteSettings.load(), settings_field)
        if val:
            return val
    except Exception:
        pass
    return getattr(settings, env_field, '')


def _clean_json(content):
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[1]
    if content.endswith('```'):
        content = content.rsplit('```', 1)[0]
    content = content.strip()
    return content


def _normalize_for_cache(value):
    if isinstance(value, str):
        return re.sub(r'\s+', ' ', value.strip().lower())
    if isinstance(value, dict):
        return {k: _normalize_for_cache(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_cache(v) for v in value]
    return value


def _cache_key(prefix, payload):
    raw = json.dumps(_normalize_for_cache(payload), ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f'ai:{prefix}:{digest}'


def _cache_get(key):
    try:
        return caches['shared'].get(key)
    except Exception:
        return cache.get(key)


def _cache_set(key, value, timeout):
    try:
        caches['shared'].set(key, value, timeout)
    except Exception:
        cache.set(key, value, timeout)


def _premium_ai_allowed(client_ip):
    if not client_ip:
        return True
    key = f'ai:premium_hour:{client_ip}'
    used = _cache_get(key) or 0
    if used >= PREMIUM_AI_PER_IP_HOURLY_LIMIT:
        return False
    _cache_set(key, used + 1, 3600)
    return True


def _provider_chain(client_ip=None):
    if _premium_ai_allowed(client_ip):
        return [
            ('DeepSeek', _call_deepseek),
            ('Gemini', _call_gemini),
            ('Groq', _call_groq),
        ]
    return [('Groq', _call_groq)]


def _json_list(content, key='cars'):
    data = json.loads(content)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get(key), list):
        return data[key]
    return []


def _format_iqd(lo, hi):
    if not lo and not hi:
        return ''
    if lo == hi or not hi:
        return f'{lo:,} د.ع'
    return f'{lo:,} - {hi:,} د.ع'


def _format_usd(lo, hi):
    if not lo and not hi:
        return ''
    if lo == hi or not hi:
        return f'{lo:,}'
    return f'{lo:,} - {hi:,}'


def _budget_margin(budget):
    return max(1, int(int(budget) * BUDGET_MARGIN_PERCENT))


def find_market_cars_by_budget(budget, currency='iqd', origin='all', condition='used', body_type='all'):
    qs = MarketCarPrice.objects.filter(condition=condition, is_active=True)
    if origin != 'all':
        qs = qs.filter(Q(origin=origin) | Q(origin='all'))
    if body_type != 'all':
        qs = qs.filter(Q(body_type=body_type) | Q(body_type='all'))

    margin = _budget_margin(budget)
    min_budget = budget - margin
    max_budget = budget + margin
    if currency == 'usd':
        qs = qs.exclude(price_usd__isnull=True).filter(price_usd__gte=min_budget, price_usd__lte=max_budget)
    else:
        qs = qs.filter(price_iqd__gte=min_budget, price_iqd__lte=max_budget)
    candidates = []
    for car in qs[:1000]:
        price = car.price_usd if currency == 'usd' else car.price_iqd
        if not price:
            continue
        distance = abs(price - budget)
        candidates.append((-car.year, distance, -car.confidence, car))

    candidates.sort(key=lambda item: item[:3])
    cars = []
    for _year, _distance, _confidence, car in candidates[:MARKET_BUDGET_RESULTS]:
        cars.append({
            'name': car.name,
            'year': car.year,
            'price_min': car.price_iqd,
            'price_max': car.price_iqd,
            'price_iq': _format_iqd(car.price_iqd, car.price_iqd),
            'price_usd': _format_usd(car.price_usd, car.price_usd),
            'engine': car.engine or 'غير محدد',
            'fuel_economy': car.fuel_economy or 'جيد',
            'maintenance': car.maintenance or 'متوسطة',
            'pros': car.pros or 'خيار قريب من ميزانيتك حسب جدول أسعار السوق المحلي.',
            'over_budget': (car.price_usd if currency == 'usd' else car.price_iqd) > budget,
            'confidence': car.confidence,
            'origin': car.get_origin_display(),
            'body_type': car.get_body_type_display(),
            'source_name': car.source_name,
        })

    if not cars:
        return {'success': False}
    return {'success': True, 'cars': cars, 'provider': 'قاعدة أسعار السوق', 'from_market': True}


def _call_groq(prompt, max_tokens=900, temperature=0.25):
    api_key = _get_key('groq_api_key', 'GROQ_API_KEY')
    if not api_key:
        raise RuntimeError('GROQ_API_KEY not configured')

    resp = requests.post(
        GROQ_API_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': GROQ_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature,
            'max_tokens': max_tokens,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return _clean_json(data['choices'][0]['message']['content'])


def _call_deepseek(prompt, max_tokens=900, temperature=0.25):
    api_key = _get_key('deepseek_api_key', 'DEEPSEEK_API_KEY')
    if not api_key:
        raise RuntimeError('DEEPSEEK_API_KEY not configured')

    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': DEEPSEEK_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature,
            'max_tokens': max_tokens,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return _clean_json(data['choices'][0]['message']['content'])


def _call_gemini(prompt, max_tokens=900, temperature=0.25):
    api_key = _get_key('gemini_api_key', 'GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not configured')

    url = f'{GEMINI_API_URL}?key={api_key}'
    resp = requests.post(
        url,
        headers={'Content-Type': 'application/json'},
        json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': temperature, 'maxOutputTokens': max_tokens},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data['candidates'][0]['content']['parts'][0]['text']
    return _clean_json(text)


def _to_int(value):
    """يحوّل قيمة (رقم أو نص أرقام) إلى int، ويعيد None إن تعذّر."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r'[^\d]', '', value)
        return int(digits) if digits else None
    return None


def find_cars_by_budget(budget, currency='iqd', origin='all', condition='used', body_type='all', client_ip=None):
    market_result = find_market_cars_by_budget(budget, currency, origin, condition, body_type)
    if market_result.get('success'):
        return market_result

    return {
        'success': False,
        'provider': 'قاعدة أسعار السوق',
        'error': 'عزيزي السائق المحترم انا المهندس علي النعيمي ارحب بك .. و اعتذر جدا لعدم تلبية طلبك فانا احدث قاعدة البيانات باستمرار ان شاء الله ستجد طلبك خلال ايام .. ارجو المعذرة',
    }


SEARCH_PROMPT = """أنت مستشار سيارات محترف ومتخصص في سوق السيارات العراقي.
مهمتك: أعطني نتيجتين فقط حقيقيتين وموثوقتين، وليس تخميناً.
يجب أن تكون المعلومات مستخلصة من المواقع الرسمية للشركات المصنعة فقط (Toyota, Hyundai, Kia, Nissan, MG, Chery, Geely, ...) والمواقع الرسمية المعتمدة.

قاعدة ذهبية عن الدقة:
- لا تختلق أو تخمّن أرقاماً. إن لم تتأكد من معلومة (مثل نوع شمعات الاحتراق أو لزوجة الزيت)، اترك الحقل فارغاً سلسلة نصية فارغة "" بدل إعطاء قيمة خاطئة.
- أعطِ تفاصيل حقيقية ومدققة 100% فقط، ولو على حساب إكمال كل الحقول.
- لزوجة الزيت الحقيقية مثال: "5W-30"، وشمعات الاحتراق/البلكات مثال: "NGK Iridium".
- إن كانت السيارة هايبرد، اذكر البطارية الصغيرة 12V إن أمكن، واذكر أن بطارية الهايبرد عالية الجهد تحتاج فحصاً متخصصاً ولا تُستبدل مثل البطارية الصغيرة.
- أعطِ ملاحظات عملية تخدم السائق: نوع البلكات، البطارية الصغيرة، مقاس الإطار، زيت الناقل، ونصيحة صيانة مختصرة.
اكتب النتيجة بالتنسيق التالي (JSON فقط، بدون أي نص قبل أو بعد أو تعليقات):
[
  {{
    "name": "اسم السيارة والموديل الكامل",
    "year": 2020,
    "engine": "السعة بالمحرك",
    "fuel": "الوقود",
    "oil_visc": "لزوجة الزيت أو فارغة",
    "oil_capacity": "سعة الزيت أو فارغة",
    "spark": "شمعات الاحتراق أو فارغة",
    "spark_notes": "ملاحظة قصيرة عن البلكات/فترة الفحص أو فارغة",
    "octane": 91,
    "battery": "البطارية الصغيرة 12V أو حجم/سعة البطارية أو فارغة",
    "hybrid_battery": "تفاصيل بطارية الهايبرد عالية الجهد أو فارغة إن لم تكن هايبرد",
    "battery_notes": "ملاحظة مهمة عن البطارية أو فارغة",
    "tire_size": "حجم الإطار أو فارغة",
    "transmission": "ناقل الحركة (أوتوماتيك/عادي/CVT) أو فارغة",
    "transmission_oil_spec": "مواصفة زيت ناقل الحركة أو فارغة",
    "driver_tip": "نصيحة عملية مختصرة للسائق",
    "specs": "تفاصيل عامة مختصرة ومدققة عن السيارة"
  }}
]

ملاحظة: أبرز النتيجة المطابقة أو الأقرب للسيارة المطلوبة أولاً في القائمة. اجعل التفاصيل واقعية ومدققة من المصادر الرسمية فقط.

بيانات بحث المستخدم الذي لم نجده في قاعدة البيانات:
{search_info}"""


def _build_search_prompt(brand, model, year, engine):
    parts = []
    if brand:
        parts.append(f'الماركة: {brand}')
    if model:
        parts.append(f'الموديل: {model}')
    if year:
        parts.append(f'السنة: {year}')
    if engine:
        parts.append(f'سعة المحرك: {engine}')
    return SEARCH_PROMPT.format(search_info='\n'.join(parts) if parts else 'غير محدد')


def suggest_cars_ai(brand='', model='', year='', engine=''):
    key = _cache_key('suggest', {'brand': brand, 'model': model, 'year': year, 'engine': engine})
    cached = _cache_get(key)
    if cached:
        return cached

    prompt = _build_search_prompt(brand, model, year, engine)

    providers = [
        ('DeepSeek', _call_deepseek),
        ('Gemini', _call_gemini),
        ('Groq', _call_groq),
    ]

    for name, call in providers:
        try:
            content = call(prompt, max_tokens=1000, temperature=0.2)
            cars = json.loads(content)
            if isinstance(cars, list) and cars:
                result = {'success': True, 'cars': cars, 'provider': name}
                _cache_set(key, result, 60 * 60 * 24 * 7)
                return result
        except requests.exceptions.Timeout:
            logger.warning(f'{name} API timeout (search suggest)')
        except requests.exceptions.RequestException as e:
            logger.error('%s API error (search suggest): %s', name, e.__class__.__name__)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f'{name} parse error (search suggest): {e}')
        except RuntimeError:
            logger.warning(f'{name} not configured')

    return {'success': False}


QUICK_PARSE_PROMPT = """أنت مساعد ذكي متخصص في فك رموز طلبات البحث عن السيارات.
مهمتك: استخرج من وصف المستخدم المعلومات التالية وأعد JSON فقط (بدون أي نص أو تعليق قبل أو بعد):
{{
  "brand": "الماركة",
  "model": "الموديل",
  "year": "سنة الصنع (أرقام فقط أو سلسلة فارغة)",
  "engine": "سعة المحرك مثل 1.6 أو 2.0 (أو سلسلة فارغة)",
  "fuel": "نوع الوقود: بنزين/هايبرد/ديزل/كهرباء (أو سلسلة فارغة)",
  "engine_type": "نوع المحرك مثل V6/Turbo (أو سلسلة فارغة)",
  "spec_region": "مواصفات المنطقة مثل خليجي/أمريكي/صيني (أو سلسلة فارغة)"
}}

قواعد دقيقة:
- إن لم تُذكر معلومة اجعلها سلسلة فارغة "" بالضبط ولا تخمّن أبداً.
- الماركة والموديل بالعربية مع مراعاة الصيغ الشائعة (تويوتا، كورولا، هايلكس، كامري...).
- أعد JSON فقط بدون أسطر إضافية أو تعليقات.

وصف المستخدم: «{query}»"""


def parse_free_query(query):
    """يفكّ جملة البحث الحر إلى حقول منظمة (ماركة، موديل، سنة، محرك...)

    المزوّد الأساسي: DeepSeek، والاحتياطيات: Gemini ثم Groq. تُجرب حتى ينجح أحدها.
    """
    key = _cache_key('parse', {'query': query})
    cached = _cache_get(key)
    if cached:
        return cached

    prompt = QUICK_PARSE_PROMPT.format(query=query)
    providers = [
        ('DeepSeek', _call_deepseek),
        ('Gemini', _call_gemini),
        ('Groq', _call_groq),
    ]
    for name, call in providers:
        try:
            content = call(prompt, max_tokens=220, temperature=0.0)
            data = json.loads(content)
            if isinstance(data, dict):
                _cache_set(key, data, 60 * 60 * 24 * 30)
                return data
        except requests.exceptions.Timeout:
            logger.warning(f'{name} timeout (parse_free_query)')
        except requests.exceptions.RequestException as e:
            logger.error('%s error (parse_free_query): %s', name, e.__class__.__name__)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f'{name} parse error (parse_free_query): {e}')
        except RuntimeError:
            logger.warning(f'{name} not configured (parse_free_query)')
    return {}
