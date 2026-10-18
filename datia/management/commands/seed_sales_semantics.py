from django.core.management.base import BaseCommand
from django.utils import timezone
from datia.models.semantic import DataSource, DataField

class Command(BaseCommand):
    help = 'Seed semántica mínima para ventas (Cliente) en tablas DatiaDB_.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, default=1)
        parser.add_argument('--activate', action='store_true', default=True)

    def handle(self, *args, **opts):
        empresa = int(opts.get('empresa') or 1)
        # Cabecera Pedido Cliente
        cab_ped, _ = DataSource.resolver(
            empresa,
            'CabeceraPedidoCliente',
            defaults={
                'name': 'Cabecera Pedido Cliente',
                'description': 'Documentos de pedido de clientes',
                'keywords': ['cliente','clientes','pedidos','ventas'],
                'is_active': True,
                'is_virtual': False,
            },
            actualizar=True,
        )
        DataField.objects.update_or_create(
            source=cab_ped,
            field_name='CodigoCliente',
            defaults={
                'source_table_name': cab_ped.source_table,
                'business_name': 'CodigoCliente',
                'synonyms': [],
                'description': 'Código del cliente.',
                'metadata_tag': 'Comercial',
                'data_type': 'number',
                'usage_type': 'dimension',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_ped,
            field_name='CodigoEmpresa',
            defaults={
                'source_table_name': cab_ped.source_table,
                'business_name': 'CodigoEmpresa',
                'synonyms': [],
                'description': 'Código de Empresa.',
                'metadata_tag': 'Comercial',
                'data_type': 'int',
                'usage_type': 'data',
                'is_active': True,
                'is_key': True,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_ped,
            field_name='Ejercicio',
            defaults={
                'source_table_name': cab_ped.source_table,
                'business_name': 'Ejercicio',
                'synonyms': [],
                'description': 'Ejercicio del documento.',
                'metadata_tag': 'Comercial',
                'data_type': 'int',
                'usage_type': 'data',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_ped,
            field_name='NumeroPedido',
            defaults={
                'source_table_name': cab_ped.source_table,
                'business_name': 'NumeroPedido',
                'synonyms': [],
                'description': 'Número de pedido.',
                'metadata_tag': 'Comercial',
                'data_type': 'int',
                'usage_type': 'data',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_ped,
            field_name='FechaPedido',
            defaults={
                'source_table_name': cab_ped.source_table,
                'business_name': 'FechaPedido',
                'synonyms': [],
                'description': 'Fecha del pedido.',
                'metadata_tag': 'Comercial',
                'data_type': 'date',
                'usage_type': 'date',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        # Cabecera Albarán Cliente
        cab_alb, _ = DataSource.resolver(
            empresa,
            'CabeceraAlbaranCliente',
            defaults={
                'name': 'Cabecera Albarán Cliente',
                'description': 'Documentos de albarán de clientes',
                'keywords': ['cliente','clientes','albaran','albaranes','ventas'],
                'is_active': True,
                'is_virtual': False,
            },
            actualizar=True,
        )
        DataField.objects.update_or_create(
            source=cab_alb,
            field_name='CodigoCliente',
            defaults={
                'source_table_name': cab_alb.source_table,
                'business_name': 'CodigoCliente',
                'synonyms': [],
                'description': 'Código del cliente.',
                'metadata_tag': 'Comercial',
                'data_type': 'number',
                'usage_type': 'dimension',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_alb,
            field_name='CodigoEmpresa',
            defaults={
                'source_table_name': cab_alb.source_table,
                'business_name': 'CodigoEmpresa',
                'synonyms': [],
                'description': 'Código de Empresa.',
                'metadata_tag': 'Comercial',
                'data_type': 'int',
                'usage_type': 'data',
                'is_active': True,
                'is_key': True,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_alb,
            field_name='Ejercicio',
            defaults={
                'source_table_name': cab_alb.source_table,
                'business_name': 'Ejercicio',
                'synonyms': [],
                'description': 'Ejercicio del documento.',
                'metadata_tag': 'Comercial',
                'data_type': 'int',
                'usage_type': 'data',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_alb,
            field_name='NumeroAlbaran',
            defaults={
                'source_table_name': cab_alb.source_table,
                'business_name': 'NumeroAlbaran',
                'synonyms': [],
                'description': 'Número de albarán.',
                'metadata_tag': 'Comercial',
                'data_type': 'int',
                'usage_type': 'data',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        DataField.objects.update_or_create(
            source=cab_alb,
            field_name='FechaAlbaran',
            defaults={
                'source_table_name': cab_alb.source_table,
                'business_name': 'FechaAlbaran',
                'synonyms': [],
                'description': 'Fecha del albarán.',
                'metadata_tag': 'Comercial',
                'data_type': 'date',
                'usage_type': 'date',
                'is_active': True,
                'is_key': False,
                'is_pii': False,
                'auto_discovered': False,
            }
        )
        self.stdout.write(self.style.SUCCESS('✅ Semántica de ventas (Cliente) sembrada correctamente.'))
