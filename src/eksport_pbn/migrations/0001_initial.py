# -*- coding: utf-8 -*-


from django.db import models, migrations
from django.conf import settings
from django.db.models import CASCADE


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlikEksportuPBN',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('file', models.FileField(upload_to=b'eksport_pbn', verbose_name=b'Plik')),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=CASCADE)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
