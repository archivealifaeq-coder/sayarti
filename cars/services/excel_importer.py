import pandas as pd
from django.db import transaction
from cars.models import CarSpecification


def validate_excel_file(file):
    """
    التحقق من صحة ملف Excel قبل البدء في الاستيراد
    """
    errors = []
    
    # التحقق من حجم الملف (حد أقصى 10 ميجابايت)
    if file.size > 10 * 1024 * 1024:
        errors.append("الملف كبير جداً. الحد الأقصى 10 ميجابايت")
    
    # التحقق من امتداد الملف
    if not file.name.endswith(('.xlsx', '.xls')):
        errors.append("يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls)")
    
    # محاولة قراءة الملف للتحقق من سلامته
    try:
        df = pd.read_excel(file, sheet_name=0)
    except Exception as e:
        errors.append(f"لا يمكن قراءة الملف: {str(e)}")
        return errors, None
    
    # التحقق من وجود الأعمدة المطلوبة
    required_columns = [
        'id', 'Brand_EN', 'Brand_AR', 'Model_EN', 'Model_AR',
        'Year', 'Engine', 'Oil Visc', 'Fuel', 'Octane',
        'Spark', 'Oil Capacity'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        errors.append(f"الأعمدة الناقصة: {', '.join(missing_columns)}")
    
    # التحقق من وجود Tire Size أو Tire PSI
    if 'Tire Size' not in df.columns and 'Tire PSI' not in df.columns:
        errors.append("يجب وجود عمود 'Tire Size' أو 'Tire PSI'")
    
    return errors, df


@transaction.atomic()
def import_cars_from_excel(file):
    """
    استيراد بيانات السيارات من ملف Excel مع تقرير مفصل
    """
    # التحقق من الملف
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
            # معالجة Spec
            spec_raw = row.get('Spec', 'خليجي')
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
            
            # معالجة نوع المحرك
            engine_str = str(row.get('Engine', ''))
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
            
            # معالجة حجم الإطار (دعم كلا الاسمين)
            if 'Tire Size' in row and pd.notna(row['Tire Size']):
                tire_size_val = str(row['Tire Size'])
            elif 'Tire PSI' in row and pd.notna(row['Tire PSI']):
                tire_size_val = str(row['Tire PSI'])
            else:
                tire_size_val = "غير محدد"
            
            # إنشاء أو تحديث السجل
            obj, created = CarSpecification.objects.update_or_create(
                id=row['id'],
                defaults={
                    'brand_en': row['Brand_EN'],
                    'brand_ar': row['Brand_AR'],
                    'model_en': row['Model_EN'],
                    'model_ar': row['Model_AR'],
                    'year': row['Year'],
                    'spec': row.get('Spec', ''),
                    'engine_type': engine_type_val,
                    'spec_region': spec_region_val,
                    'engine': row['Engine'],
                    'oil_visc': row['Oil Visc'],
                    'oil_visc_high_km': row.get('Oil Visc (>100k)', ''),
                    'fuel': row['Fuel'],
                    'octane': row['Octane'],
                    'spark': row['Spark'],
                    'tire_size': tire_size_val,
                    'oil_capacity': row['Oil Capacity'],
                    'recommendations': row.get('Recommendations', ''),
                    'oil_brands': row.get('Oil Brands', ''),
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
                
        except Exception as e:
            failed_count += 1
            failed_rows.append({
                'row_number': index + 2,  # +2 لأن Excel يبدأ من 1 والرأس في الصف 1
                'error': str(e),
                'data': row.to_dict()
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