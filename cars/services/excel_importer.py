import pandas as pd
from django.db import transaction
from cars.models import CarSpecification
from cars.services.textnorm import fold_ar, fold_engine


def _cell(row, col, default=''):
    """قراءة آمنة لأي خلية: ترجع default عند غياب العمود أو قيمة فارغة/NaN."""
    try:
        val = row.get(col, default)
    except Exception:
        return default
    if val is None:
        return default
    if isinstance(val, float) and pd.isna(val):
        return default
    if isinstance(val, str) and not val.strip():
        return default
    return val


def _year_value(row):
    """تحويل عمود السنة مع دعم الأرقام '2,000' أو 2000.0."""
    raw = row['Year']
    if isinstance(raw, str):
        raw = raw.replace(',', '').replace(' ', '').strip()
    return int(float(raw))


def validate_excel_file(file):
    """
    التحقق من صحة ملف Excel قبل البدء في الاستيراد
    """
    errors = []
    
    if file.size > 10 * 1024 * 1024:
        errors.append("الملف كبير جداً. الحد الأقصى 10 ميجابايت")
    
    if not file.name.endswith(('.xlsx', '.xls')):
        errors.append("يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls)")
    
    try:
        df = pd.read_excel(file, sheet_name=0)
    except Exception:
        errors.append("⚠️ تعذر قراءة ملف الإكسل. تأكد أن الامتداد .xlsx أو .xls وأن الملف غير تالف.")
        return errors, None
    
    required_columns = [
        'id', 'Brand_EN', 'Brand_AR', 'Model_EN', 'Model_AR',
        'Year', 'Engine', 'Oil Visc', 'Fuel', 'Octane',
        'Spark', 'Oil Capacity'
    ]
    optional_columns = [
        'Spec', 'Trim', 'Class', 'Recommendations', 'Oil Brands', 'Oil Visc (>100k)',
        'Battery', 'Battery Size', 'Battery Capacity',
        'Transmission Type', 'Transmission Oil Spec', 'Transmission Oil Brands'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"الأعمدة الناقصة: {', '.join(missing_columns)}")
    
    if 'Tire Size' not in df.columns and 'Tire PSI' not in df.columns:
        errors.append("يجب وجود عمود 'Tire Size' أو 'Tire PSI'")
    
    return errors, df


@transaction.atomic()
def import_cars_from_excel(file):
    """
    استيراد بيانات السيارات من ملف Excel مع تقرير مفصل
    """
    errors, df = validate_excel_file(file)
    
    if errors:
        return {
            'success': False,
            'errors': errors,
            'total_rows': 0,
            'created': 0,
            'updated': 0,
            'failed': 0,
            'failed_rows': []
        }
    
    total_rows = len(df)
    created_count = 0
    updated_count = 0
    failed_count = 0
    failed_rows = []
    
    for index, row in df.iterrows():
        try:
            spec_raw = _cell(row, 'Spec', 'خليجي')
            if 'خليجي' in str(spec_raw):
                spec_region_val = 'gcc'
            elif 'أمريكي' in str(spec_raw):
                spec_region_val = 'american'
            elif 'أوروبي' in str(spec_raw):
                spec_region_val = 'european'
            elif 'ياباني' in str(spec_raw):
                spec_region_val = 'japanese'
            elif 'صيني' in str(spec_raw):
                spec_region_val = 'chinese'
            else:
                spec_region_val = 'other'
            
            engine_str = str(_cell(row, 'Engine', ''))
            if 'turbo' in engine_str.lower() or 't-gdi' in engine_str.lower():
                engine_type_val = 'turbo'
            elif 'hybrid' in engine_str.lower():
                engine_type_val = 'hybrid'
            elif 'diesel' in engine_str.lower():
                engine_type_val = 'diesel'
            elif 'electric' in engine_str.lower():
                engine_type_val = 'electric'
            else:
                engine_type_val = 'regular'
            
            tire_size_val = _cell(row, 'Tire Size')
            if not tire_size_val:
                tire_size_val = _cell(row, 'Tire PSI')
            if not tire_size_val:
                tire_size_val = "غير محدد"

            battery_val = _cell(row, 'Battery Capacity')
            if not battery_val:
                battery_val = _cell(row, 'Battery')
            if not battery_val:
                battery_val = _cell(row, 'Battery Size')
            
            obj, created = CarSpecification.objects.update_or_create(
                id=int(float(row['id'])),
                defaults={
                    'brand_en': _cell(row, 'Brand_EN'),
                    'brand_ar': _cell(row, 'Brand_AR'),
                    'brand_norm': fold_ar(_cell(row, 'Brand_AR')),
                    'model_en': _cell(row, 'Model_EN'),
                    'model_ar': _cell(row, 'Model_AR'),
                    'model_norm': fold_ar(_cell(row, 'Model_AR')),
                    'year': _year_value(row),
                    'spec': _cell(row, 'Spec'),
                    'trim': _cell(row, 'Trim') or _cell(row, 'Class'),
                    'engine_type': engine_type_val,
                    'spec_region': spec_region_val,
                    'engine': _cell(row, 'Engine'),
                    'engine_norm': fold_engine(_cell(row, 'Engine')),
                    'oil_visc': _cell(row, 'Oil Visc'),
                    'oil_visc_high_km': _cell(row, 'Oil Visc (>100k)'),
                    'fuel': _cell(row, 'Fuel'),
                    'octane': _cell(row, 'Octane'),
                    'spark': _cell(row, 'Spark'),
                    'tire_size': tire_size_val,
                    'oil_capacity': _cell(row, 'Oil Capacity'),
                    'recommendations': _cell(row, 'Recommendations'),
                    'oil_brands': _cell(row, 'Oil Brands'),
                    'battery': battery_val,
                    'transmission_type': _cell(row, 'Transmission Type'),
                    'transmission_oil_spec': _cell(row, 'Transmission Oil Spec'),
                    'transmission_oil_brands': _cell(row, 'Transmission Oil Brands'),
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
                
        except Exception as e:
            failed_count += 1
            failed_rows.append({
                'row_number': index + 2,
                'error': str(e)[:200],
            })
    
    return {
        'success': True,
        'errors': [],
        'total_rows': total_rows,
        'created': created_count,
        'updated': updated_count,
        'failed': failed_count,
        'failed_rows': failed_rows
    }