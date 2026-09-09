from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cars', '0036_marketcarpricecandidate'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketcarpricecandidate',
            name='engine',
            field=models.CharField(blank=True, max_length=80, verbose_name='المحرك'),
        ),
        migrations.AddField(
            model_name='marketcarpricecandidate',
            name='fuel_economy',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='صرف الوقود'),
        ),
        migrations.AddField(
            model_name='marketcarpricecandidate',
            name='maintenance',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='الصيانة'),
        ),
        migrations.AddField(
            model_name='marketcarpricecandidate',
            name='pros',
            field=models.CharField(blank=True, max_length=240, verbose_name='سبب الترشيح'),
        ),
    ]
