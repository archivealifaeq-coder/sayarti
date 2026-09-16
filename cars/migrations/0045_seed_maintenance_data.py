from django.db import migrations


def seed_maintenance(apps, schema_editor):
    OBDCode = apps.get_model('cars', 'OBDCode')
    CarSymptom = apps.get_model('cars', 'CarSymptom')
    SymptomCause = apps.get_model('cars', 'SymptomCause')
    MaintenanceTask = apps.get_model('cars', 'MaintenanceTask')

    obd_rows = [
        {
            'code': 'P0300', 'title': 'اختلال احتراق عشوائي', 'slug': 'p0300-random-misfire', 'system': 'engine', 'severity': 'high', 'safety_status': 'check_soon',
            'plain_explanation': 'الكود يعني أن المحرك لا يحرق الوقود بشكل منتظم في سلندر أو أكثر.',
            'local_explanation': 'يعني السيارة بيها تقطيع أو رجة لأن الحرق مو مضبوط. بالعراق غالباً السبب بواجي، كويل، بخاخات، أو بنزين رديء.',
            'common_causes': 'بواجي ضعيفة\nكويلات متعبة\nبخاخات متسخة\nتهريب هواء\nضغط وقود ضعيف',
            'local_causes': 'بنزين نوعية ضعيفة\nغبار يوسخ فلتر الهواء\nقطع تجارية غير أصلية',
            'symptoms': 'رجة عالسلو\nتقطيع عند الدعسة\nصرفية بنزين\nلمبة Check Engine',
            'self_check_steps': 'افحص آخر تبديل بواجي\nراقب هل اللمبة تومض\nجرّب بنزين من محطة موثوقة\nافحص فلتر الهواء',
            'mechanic_advice': 'إذا اللمبة تومض أو الرجة قوية، افحصها سريعاً حتى لا يتضرر الكتلايزر.',
            'dont_do': 'لا تضغط على السيارة إذا الرجة قوية. لا تبدل قطع عشوائياً بدون فحص كمبيوتر.',
            'estimated_cost_note': 'الكلفة تختلف حسب السبب: تنظيف بخاخات أقل من تبديل كويلات أو بواجي أصلية.',
        },
        {
            'code': 'P0420', 'title': 'كفاءة دبة التلوث منخفضة', 'slug': 'p0420-catalyst-efficiency', 'system': 'emissions', 'severity': 'medium', 'safety_status': 'check_soon',
            'plain_explanation': 'كمبيوتر السيارة يرى أن عمل دبة التلوث أو حساسات الأوكسجين غير طبيعي.',
            'local_explanation': 'غالباً المشكلة من حساس أوكسجين، تهريب اكزوز، أو دبة تلوث متعبة بسبب وقود رديء أو تقطيع قديم.',
            'common_causes': 'حساس أوكسجين\nدبة تلوث ضعيفة\nتهريب في الاكزوز\nMisfire سابق',
            'local_causes': 'بنزين رديء\nإلغاء أو تفريغ دبة التلوث\nاستخدام قطع غير أصلية',
            'symptoms': 'لمبة Check Engine\nصرفية أعلى\nضعف عزم أحياناً',
            'self_check_steps': 'افحص وجود تهريب اكزوز\nافحص بيانات حساسات O2\nتأكد لا توجد أكواد تقطيع أخرى',
            'mechanic_advice': 'لا تبدل دبة التلوث مباشرة قبل فحص الحساسات والتهريبات.',
        },
        {
            'code': 'P0171', 'title': 'الخليط فقير - هواء أكثر من الوقود', 'slug': 'p0171-system-too-lean', 'system': 'fuel', 'severity': 'medium', 'safety_status': 'check_soon',
            'plain_explanation': 'المحرك يستلم هواء أكثر أو وقود أقل من المطلوب.',
            'local_explanation': 'ممكن تهريب هواء، فلتر أو بخاخات، أو حساس MAF متوسخ من الغبار.',
            'common_causes': 'تهريب هواء\nحساس MAF متسخ\nضغط وقود ضعيف\nبخاخات متسخة',
            'local_causes': 'غبار كثيف\nفلتر هواء تجاري\nتنظيف غير صحيح للحساسات',
            'symptoms': 'ضعف عزم\nرجة\nصرفية\nتأخير تشغيل',
            'self_check_steps': 'افحص ليّات الهواء\nنظف حساس MAF بمنظف مخصص\nافحص فلتر الهواء',
        },
    ]
    for row in obd_rows:
        OBDCode.objects.update_or_create(code=row['code'], defaults=row)

    symptom_rows = [
        {
            'name': 'رجة عالسلو', 'slug': 'idle-shaking', 'category': 'engine', 'severity': 'medium', 'safety_status': 'check_soon',
            'description': 'اهتزاز واضح والسيارة واقفة أو على N/P، وقد يزيد مع تشغيل المكيف.',
            'driver_questions': 'هل الرجة تزيد مع المكيف؟\nهل لمبة Check Engine شغالة؟\nمتى آخر تبديل بواجي؟\nهل الرجة تختفي عند الدعسة؟',
            'self_check_steps': 'افحص فلتر الهواء\nتأكد من نظافة الثروتل\nافحص البواجي والكويلات\nاقرأ أكواد OBD إن وجدت',
            'urgent_warning': 'إذا الرجة قوية جداً أو اللمبة تومض، لا تضغط على السيارة قبل الفحص.',
            'causes': [
                ('بواجي ضعيفة', 'البواجي القديمة تسبب حرق غير منتظم خصوصاً على السلو.', 'افحص عمر البواجي وشكل رأس الشمعة.', 'استبدال بواجي أصلية بالمواصفة الصحيحة.', 'P0300'),
                ('كويل متعب', 'الكويل الضعيف يسبب تقطيع متقطع أو رجة.', 'فحص كمبيوتر أو تبديل مكان الكويل للتأكد.', 'تبديل الكويل المتضرر فقط بعد التشخيص.', 'P0300,P0301'),
                ('ثروتل أو بخاخات متسخة', 'الاتساخ يخلط نسبة الهواء والوقود خصوصاً مع الزحام والغبار.', 'فحص وتنظيف ثروتل وبخاخات بطريقة صحيحة.', 'تنظيف احترافي دون رش عشوائي على الحساسات.', ''),
            ],
        },
        {
            'name': 'تقطيع عند الدعسة', 'slug': 'hesitation-on-acceleration', 'category': 'engine', 'severity': 'high', 'safety_status': 'check_soon',
            'description': 'السيارة تتأخر أو تقطع عند الضغط على البنزين، خصوصاً في الطلعة أو التجاوز.',
            'driver_questions': 'هل يحدث وهي باردة أم حارة؟\nهل يظهر عند دعسة قوية فقط؟\nهل الوقود من محطة جديدة؟',
            'self_check_steps': 'افحص فلتر الهواء\nجرّب قراءة أكواد OBD\nراقب صوت طرمبة البنزين\nافحص البواجي والكويلات',
            'urgent_warning': 'إذا التقطيع يسبب فقدان عزم أثناء التجاوز، افحصها قبل السفر.',
            'causes': [
                ('ضغط وقود ضعيف', 'الوقود لا يصل بكمية كافية عند الدعسة.', 'فحص ضغط الوقود والفلتر والطرمبة.', 'تبديل الفلتر أو الطرمبة حسب نتيجة الفحص.', ''),
                ('حساس MAF متسخ', 'قراءة الهواء غير دقيقة فتختل الخلطة.', 'تنظيف الحساس بمنظف مخصص فقط.', 'تنظيف أو تبديل الحساس إذا تكرر العطل.', 'P0171'),
                ('كويل أو بواجي', 'الحرق يضعف تحت الحمل.', 'فحص Misfire بجهاز OBD.', 'تبديل القطعة المتضررة بالمواصفة الصحيحة.', 'P0300'),
            ],
        },
        {
            'name': 'حرارة المحرك', 'slug': 'engine-overheating', 'category': 'cooling', 'severity': 'critical', 'safety_status': 'stop_now',
            'description': 'ارتفاع مؤشر الحرارة أو ظهور تحذير حرارة في الطبلون.',
            'driver_questions': 'هل المروحة تعمل؟\nهل ماء الرديتر ناقص؟\nهل توجد تهريبات؟\nهل الحرارة ترتفع بالزحام فقط؟',
            'self_check_steps': 'أوقف السيارة بمكان آمن\nلا تفتح غطاء الرديتر وهي حارة\nافحص مستوى الماء بعد أن تبرد\nافحص المراوح والتهريب',
            'urgent_warning': 'إذا وصلت الحرارة للأحمر، أوقف السيارة فوراً. الاستمرار قد يضر رأس المحرك.',
            'causes': [
                ('نقص ماء الرديتر', 'نقص السائل يسبب ارتفاع حرارة سريع.', 'افحص المستوى والتهريبات بعد أن تبرد السيارة.', 'إصلاح التهريب ثم تعبئة سائل مناسب.', ''),
                ('مروحة لا تعمل', 'في الزحام تحتاج السيارة المراوح أكثر.', 'راقب تشغيل المراوح مع الحرارة أو المكيف.', 'فحص فيوز/ريليه/مروحة/حساس.', ''),
                ('ثرموستات أو رديتر مسدود', 'ضعف دوران الماء يرفع الحرارة.', 'فحص فرق حرارة الليّات وتنظيف الرديتر.', 'تبديل الثرموستات أو تنظيف/تبديل الرديتر.', ''),
            ],
        },
    ]
    for row in symptom_rows:
        causes = row.pop('causes')
        symptom, _ = CarSymptom.objects.update_or_create(slug=row['slug'], defaults=row)
        for index, cause in enumerate(causes, 1):
            SymptomCause.objects.update_or_create(
                symptom=symptom,
                priority=index,
                defaults={
                    'title': cause[0], 'description': cause[1], 'likelihood': 'high' if index == 1 else 'medium',
                    'check_method': cause[2], 'solution_hint': cause[3], 'related_obd_codes': cause[4], 'is_active': True,
                },
            )

    task_rows = [
        ('تغيير زيت المحرك', 'oil', 10000, 12, 5000, 6, 0, 'high', 'أهم مهمة لحماية المحرك.', 'في الحر والزحام الأفضل تقليل الفترة.'),
        ('تغيير فلتر الزيت', 'filters', 10000, 12, 5000, 6, 0, 'high', 'يفضل تغييره مع كل تبديل زيت.', 'الفلاتر التجارية الضعيفة تقلل حماية المحرك.'),
        ('فحص/تغيير فلتر الهواء', 'filters', 20000, 12, 10000, 6, 0, 'medium', 'فلتر الهواء يؤثر على العزم والصرفية.', 'الغبار في العراق يخلي الفحص أقرب.'),
        ('فحص شمعات القدح', 'spark', 40000, 24, 30000, 18, 30000, 'medium', 'البواجي الضعيفة تسبب رجة وتقطيع.', 'استخدم النوع المطابق للمحرك.'),
        ('فحص زيت ناقل الحركة', 'transmission', 60000, 36, 40000, 24, 40000, 'high', 'زيت القير مهم للنعومة والعمر.', 'الزحام والحرارة تعتبر ظروف شاقة.'),
        ('فحص ماء الرديتر', 'cooling', 40000, 24, 30000, 18, 20000, 'high', 'سائل التبريد يحمي من الحرارة والصدأ.', 'لا تخلط ماء عادي دائماً؛ استخدم سائل مناسب.'),
        ('فحص زيت البريك', 'brakes', 40000, 24, 30000, 18, 20000, 'high', 'زيت البريك يمتص رطوبة ويضعف مع الوقت.', 'مهم جداً قبل السفر والحر.'),
        ('فحص البطارية والدينمو', 'electrical', 20000, 12, 10000, 6, 0, 'medium', 'يفحص ضعف التشغيل والشحن.', 'حرارة الصيف تقصر عمر البطارية.'),
        ('فحص الإطارات والضغط', 'tires', 10000, 6, 5000, 3, 0, 'medium', 'الضغط والترصيص يؤثران على الأمان والصرفية.', 'الحر والطرق المتكسرة تزيد الحاجة للفحص.'),
    ]
    for row in task_rows:
        MaintenanceTask.objects.update_or_create(
            name=row[0],
            defaults={
                'category': row[1], 'interval_km': row[2], 'interval_months': row[3], 'severe_interval_km': row[4],
                'severe_interval_months': row[5], 'start_km': row[6], 'importance': row[7], 'description': row[8],
                'iraq_note': row[9], 'applies_to_engine_type': 'all', 'applies_to_transmission': 'all', 'is_active': True,
            },
        )


def unseed_maintenance(apps, schema_editor):
    apps.get_model('cars', 'MaintenanceTask').objects.all().delete()
    apps.get_model('cars', 'SymptomCause').objects.all().delete()
    apps.get_model('cars', 'CarSymptom').objects.all().delete()
    apps.get_model('cars', 'OBDCode').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('cars', '0044_carsymptom_maintenancetask_obdcode_symptomcause'),
    ]

    operations = [
        migrations.RunPython(seed_maintenance, unseed_maintenance),
    ]
