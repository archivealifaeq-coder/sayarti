from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0037_marketcarpricecandidate_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketcarprice',
            name='trim',
            field=models.CharField(blank=True, max_length=80, verbose_name='الفئة / الكلاس'),
        ),
        migrations.AddField(
            model_name='marketcarpricecandidate',
            name='trim',
            field=models.CharField(blank=True, max_length=80, verbose_name='الفئة / الكلاس'),
        ),
    ]
