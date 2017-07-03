# -*- coding: utf-8 -*-


from django.db import migrations, models
import integrator2.models.lista_ministerialna


class Migration(migrations.Migration):

    dependencies = [
        ('integrator2', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='listaministerialnaelement',
            options={'ordering': ['nazwa']},
        ),
        migrations.AlterModelOptions(
            name='listaministerialnaintegration',
            options={'ordering': ['-uploaded_on'], 'verbose_name': 'integracja list ministerialnych'},
        ),
        migrations.AlterField(
            model_name='listaministerialnaintegration',
            name='last_updated_on',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='listaministerialnaintegration',
            name='year',
            field=models.IntegerField(default=integrator2.models.lista_ministerialna.last_year, help_text='Rok dla kt\xf3rego zosta\u0142a wydana ta lista ministerialna', verbose_name='Rok'),
        ),
    ]
