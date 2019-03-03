# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.db.models import CASCADE


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0054_obiekt_jednostka_pole_aktualna'),
    ]

    operations = [
        migrations.CreateModel(
            name='Jednostka_Wydzial',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('od', models.DateField(null=True, blank=True)),
                ('do', models.DateField(null=True, blank=True)),
                ('jednostka', models.ForeignKey(on_delete=models.CASCADE, to='bpp.Jednostka')),
                ('wydzial', models.ForeignKey(on_delete=models.CASCADE, to='bpp.Wydzial')),
            ],
        ),
    ]
