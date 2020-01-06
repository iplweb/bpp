# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.conf import settings
import django_extensions.db.fields
import django_extensions.db.fields.json
from django.db.models import CASCADE


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uid', models.UUIDField(unique=True, editable=False, blank=True)),
                ('function', models.TextField()),
                ('arguments', django_extensions.db.fields.json.JSONField(null=True, blank=True)),
                ('ordered_on', models.DateTimeField(auto_now_add=True)),
                ('file', models.FileField(null=True, upload_to=b'report', blank=True)),
                ('started_on', models.DateTimeField(null=True, blank=True)),
                ('finished_on', models.DateTimeField(null=True, blank=True)),
                ('progress', models.FloatField(default=0.0, null=True, blank=True)),
                ('error', models.BooleanField(default=False)),
                ('traceback', models.TextField(max_length=10240, null=True, blank=True)),
                ('ordered_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=CASCADE)),
            ],
            options={
                'ordering': ['-ordered_on'],
            },
        ),
    ]
