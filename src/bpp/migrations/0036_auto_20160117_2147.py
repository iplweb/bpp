# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.core.validators
import bpp.models.profile


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0035_nomorefixtures_data_migration'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='bppuser',
            managers=[
                ('objects', bpp.models.profile.BppUserManager()),
            ],
        ),
        migrations.AlterField(
            model_name='autor',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='email',
            field=models.EmailField(max_length=254, verbose_name='email address', blank=True),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='groups',
            field=models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', verbose_name='groups'),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='last_login',
            field=models.DateTimeField(null=True, verbose_name='last login', blank=True),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='bppuser',
            name='username',
            field=models.CharField(error_messages={'unique': 'A user with that username already exists.'}, max_length=30, validators=[django.core.validators.RegexValidator('^[\\w.@+-]+$', 'Enter a valid username. This value may contain only letters, numbers and @/./+/-/_ characters.', 'invalid')], help_text='Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.', unique=True, verbose_name='username'),
        ),
        migrations.AlterField(
            model_name='jednostka',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='patent',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='patent',
            name='utworzono',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'Utworzono', null=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='autor',
            field=models.OneToOneField(to='bpp.Autor', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='praca_doktorska',
            name='utworzono',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'Utworzono', null=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='autor',
            field=models.OneToOneField(to='bpp.Autor', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='praca_habilitacyjna',
            name='utworzono',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'Utworzono', null=True),
        ),
        migrations.AlterField(
            model_name='uczelnia',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_ciagle',
            name='utworzono',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'Utworzono', null=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='wydawnictwo_zwarte',
            name='utworzono',
            field=models.DateTimeField(auto_now_add=True, verbose_name=b'Utworzono', null=True),
        ),
        migrations.AlterField(
            model_name='wydzial',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='zrodlo',
            name='ostatnio_zmieniony',
            field=models.DateTimeField(db_index=True, auto_now=True, null=True),
        ),
    ]
