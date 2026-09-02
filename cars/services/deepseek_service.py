import json
import logging
import requests
from django.conf import settings
from ..models import SiteSettings

logger = logging.getLogger('cars')

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'qwen/qwen3.8-27b'
TIMEOUT = 35

GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

BUDGET_PROMPT = """أنت مستشار سيارات محترف ومتخصص في سوق السيارات العراقي.
تحدث باللغة العربية الفصحى الواضحة واللطيفة (تجنب اللهجة العامية).

الميزانية: {budget} {currency_name}
نوع السيارة: {car_type}
الحالة: {condition}

أعطني 6-8 سيارات مناسبة بالسوق العراقي بالتنسيق التالي (JSON فقط، بدون نص إضافي):
[
  {{
    "name": "اسم السيارة والموديل",
    "year": 2018,
    "price_iq": "20-25 مليون",
    "price_usd": "13,000-16,000",
    "engine": "1.6L",
    "fuel_economy": "ممتاز/جيد/مقبول",
    "maintenance": "رخيصة/متوسطة/غالية",
    "pros": "مميزات مختصرة بلغة عربية فصحى"
  }}
]

قواعد:
1. الأسعار بالدينار العراقي والدولار، واقعية ومطابقة للأسعار الفعلية في السوق العراقي
2. فقط سيارات متوفرة فعلياً بالعراق
3. اذكر ماركات متوفرة: تويوتا، هيونداي، كيا، نيسان، مازدا، شيري، MG، جيلي، وغيرها
4. لا تتجاوز الميزانية
5. أضف في "pros" فصحى لطيفة ومهذبة
6. JSON فقط بدون أي نص قبل أو بعد"""


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


def _build_prompt(budget, currency, car_type, condition):
    currency_names = {
        'iqd': 'دينار عراقي',
        'usd': 'دولار أمريكي',
    }
    car_type_names = {
        'all': 'أي نوع',
        'japanese': 'ياباني (تويوتا، نيسان، مازدا)',
        'korean': 'كوري (هيونداي، كيا)',
        'chinese': 'صيني (شيري، MG، جيلي)',
        'american': 'أمريكي (شفروليت، فورد)',
        'european': 'أوروبي (فولكس، أوبل)',
    }
    condition_names = {
        'used': 'مستعمل',
        'new': 'جديد',
    }
    return BUDGET_PROMPT.format(
        budget=f'{budget:,}',
        currency_name=currency_names.get(currency, 'دينار عراقي'),
        car_type=car_type_names.get(car_type, 'أي نوع'),
        condition=condition_names.get(condition, 'مستعمل'),
    )


def _call_groq(prompt):
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
            'temperature': 0.7,
            'max_tokens': 2500,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return _clean_json(data['choices'][0]['message']['content'])


def _call_gemini(prompt):
    api_key = _get_key('gemini_api_key', 'GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not configured')

    url = f'{GEMINI_API_URL}?key={api_key}'
    resp = requests.post(
        url,
        headers={'Content-Type': 'application/json'},
        json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 2500},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data['candidates'][0]['content']['parts'][0]['text']
    return _clean_json(text)


def find_cars_by_budget(budget, currency='iqd', car_type='all', condition='used'):
    prompt = _build_prompt(budget, currency, car_type, condition)

    providers = [
        ('Groq', _call_groq),
        ('Gemini', _call_gemini),
    ]

    errors = []
    for name, call in providers:
        try:
            content = call(prompt)
            cars = json.loads(content)
            if isinstance(cars, list) and cars:
                return {'success': True, 'cars': cars, 'provider': name}
            errors.append(f'{name}: نتيجة فارغة')
        except requests.exceptions.Timeout:
            errors.append(f'{name}: انتهت المهلة')
            logger.warning(f'{name} API timeout')
        except requests.exceptions.RequestException as e:
            errors.append(f'{name}: خطأ اتصال ({e})')
            logger.error(f'{name} API error: {e}')
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            errors.append(f'{name}: تعذر تحليل النتيجة')
            logger.error(f'{name} parse error: {e}')
        except RuntimeError as e:
            logger.warning(str(e))

    return {'success': False, 'error': 'تعذر الحصول على نتيجة. حاول مرة أخرى.'}
