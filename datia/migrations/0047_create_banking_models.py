from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0046_merge_0044_merge_20260117_2321_0045_add_almacen_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankingBank',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.IntegerField(db_index=True)),
                ('bank_code', models.CharField(max_length=64, null=True, blank=True)),
                ('nombre', models.CharField(max_length=255)),
                ('swift', models.CharField(max_length=32, null=True, blank=True)),
                ('rating', models.CharField(max_length=32, null=True, blank=True)),
                ('contacto', models.JSONField(default=dict, blank=True)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'datia_banking_bank',
                'unique_together': {('empresa', 'nombre')},
            },
        ),
        migrations.AddIndex(
            model_name='bankingbank',
            index=models.Index(fields=['empresa', 'nombre'], name='bank_emp_name_idx'),
        ),
        migrations.AddIndex(
            model_name='bankingbank',
            index=models.Index(fields=['empresa', 'bank_code'], name='bank_emp_code_idx'),
        ),
        migrations.AddIndex(
            model_name='bankingbank',
            index=models.Index(fields=['empresa', 'activo'], name='bank_emp_active_idx'),
        ),
        migrations.CreateModel(
            name='BankingAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.IntegerField(db_index=True)),
                ('iban', models.CharField(max_length=34)),
                ('erp_account_code', models.CharField(max_length=64, null=True, blank=True)),
                ('alias', models.CharField(max_length=128, null=True, blank=True)),
                ('uso', models.CharField(max_length=64, null=True, blank=True)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bank', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts', to='datia.bankingbank')),
            ],
            options={
                'db_table': 'datia_banking_account',
                'unique_together': {('empresa', 'iban')},
            },
        ),
        migrations.AddIndex(
            model_name='bankingaccount',
            index=models.Index(fields=['empresa', 'bank'], name='acc_emp_bank_idx'),
        ),
        migrations.AddIndex(
            model_name='bankingaccount',
            index=models.Index(fields=['empresa', 'erp_account_code'], name='acc_emp_code_idx'),
        ),
        migrations.AddIndex(
            model_name='bankingaccount',
            index=models.Index(fields=['empresa', 'activo'], name='acc_emp_active_idx'),
        ),
        migrations.AddConstraint(
            model_name='bankingaccount',
            constraint=models.UniqueConstraint(fields=['empresa', 'bank', 'erp_account_code'], condition=Q(iban__isnull=True), name='uniq_bank_acc_code_when_no_iban'),
        ),
        migrations.CreateModel(
            name='BankingInstrument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.IntegerField(db_index=True)),
                ('tipo', models.CharField(max_length=16)),
                ('producto', models.CharField(max_length=64, null=True, blank=True)),
                ('fecha_inicio', models.DateField(null=True, blank=True)),
                ('fecha_fin', models.DateField(null=True, blank=True)),
                ('renovable', models.BooleanField(default=False)),
                ('estado', models.CharField(max_length=16, default='activo')),
                ('limite', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('base', models.CharField(max_length=16, default='euribor')),
                ('diferencial', models.DecimalField(max_digits=8, decimal_places=4, default=0)),
                ('com_apertura', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('com_disponibilidad', models.DecimalField(max_digits=8, decimal_places=4, default=0)),
                ('com_no_disposicion', models.DecimalField(max_digits=8, decimal_places=4, default=0)),
                ('gastos_fijos', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('garantia', models.JSONField(default=dict, blank=True)),
                ('covenants', models.JSONField(default=dict, blank=True)),
                ('notas', models.TextField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name='instruments', to='datia.bankingaccount')),
                ('bank', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instruments', to='datia.bankingbank')),
            ],
            options={
                'db_table': 'datia_banking_instrument',
            },
        ),
        migrations.AddIndex(
            model_name='bankinginstrument',
            index=models.Index(fields=['empresa', 'bank', 'tipo'], name='instr_emp_bank_tipo_idx'),
        ),
        migrations.AddIndex(
            model_name='bankinginstrument',
            index=models.Index(fields=['empresa', 'estado'], name='instr_emp_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='bankinginstrument',
            index=models.Index(fields=['empresa', 'fecha_fin'], name='instr_emp_fecha_fin_idx'),
        ),
        migrations.CreateModel(
            name='BankingInstrumentAccountMap',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.IntegerField(db_index=True)),
                ('cuenta_prefix', models.CharField(max_length=20)),
                ('prioridad', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='account_maps', to='datia.bankinginstrument')),
            ],
            options={
                'db_table': 'datia_banking_instr_map',
            },
        ),
        migrations.AddIndex(
            model_name='bankinginstrumentaccountmap',
            index=models.Index(fields=['empresa', 'cuenta_prefix'], name='instrmap_emp_prefix_idx'),
        ),
        migrations.AddConstraint(
            model_name='bankinginstrumentaccountmap',
            constraint=models.UniqueConstraint(fields=['empresa', 'instrument', 'cuenta_prefix'], name='uniq_instr_prefix'),
        ),
        migrations.CreateModel(
            name='BankingAmortization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.IntegerField(db_index=True)),
                ('fecha_cuota', models.DateField()),
                ('principal', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('interes', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('cuota', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('pendiente', models.DecimalField(max_digits=18, decimal_places=2, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='amortization', to='datia.bankinginstrument')),
            ],
            options={
                'db_table': 'datia_banking_amort',
            },
        ),
        migrations.AddIndex(
            model_name='bankingamortization',
            index=models.Index(fields=['empresa', 'instrument'], name='amort_emp_instr_idx'),
        ),
        migrations.AddIndex(
            model_name='bankingamortization',
            index=models.Index(fields=['empresa', 'fecha_cuota'], name='amort_emp_fecha_idx'),
        ),
    ]
