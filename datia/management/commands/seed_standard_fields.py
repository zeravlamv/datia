from django.core.management.base import BaseCommand
from datia.models.semantic import StandardField

class Command(BaseCommand):
    help = 'Seeds the StandardField repository with common ERP dimensions.'

    def handle(self, *args, **options):
        # List of standard fields to seed
        # Format: (name, business_name, description, semantic_role, is_key)
        definitions = [
            ('CodigoEmpresa', 'Empresa', 'Identificador único de la empresa/delegación.', 'DIMENSION', True),
            ('CodigoCliente', 'Cliente', 'Código identificador del cliente.', 'DIMENSION', True),
            ('CodigoProveedor', 'Proveedor', 'Código identificador del proveedor.', 'DIMENSION', True),
            ('CodigoArticulo', 'Artículo', 'Código único del producto/artículo.', 'DIMENSION', True),
            ('CodigoFamilia', 'Familia', 'Código de la familia de productos.', 'DIMENSION', False),
            ('CodigoSubFamilia', 'SubFamilia', 'Código de la subfamilia de productos.', 'DIMENSION', False),
            ('CodigoCuenta', 'Cuenta Contable', 'Código de la cuenta contable asociada.', 'DIMENSION', False),
            ('NumeroSerie', 'Número Serie', 'Número de serie único del artículo.', 'DIMENSION', True),
            ('NumeroPedido', 'Num. Pedido', 'Número identificador del pedido.', 'PK', True),
            ('NumeroLinea', 'Num. Línea', 'Número de línea dentro del documento.', 'PK', True),
            ('NumeroAlbaran', 'Num. Albarán', 'Número identificador del albarán de entrega.', 'PK', True),
            ('LineaAlbaran', 'Línea Albarán', 'Línea del albarán de entrega.', 'PK', True),
            ('NumeroFactura', 'Num. Factura', 'Número identificador de la factura.', 'PK', True),
            ('LineaFactura', 'Línea Factura', 'Línea de la factura.', 'PK', True),
            ('CodigoCanal', 'Canal Venta', 'Código del canal de venta.', 'DIMENSION', False),
            ('CodigoDelegacion', 'Delegación', 'Código de la delegación comercial.', 'DIMENSION', False),
            ('CodigoSeccion', 'Sección', 'Código de la sección departamental.', 'DIMENSION', False),
            ('CodigoDepartamento', 'Departamento', 'Código del departamento.', 'DIMENSION', False),
            ('CodigoProyecto', 'Proyecto', 'Código del proyecto asociado.', 'DIMENSION', False),
            
            # Common Time Dimensions (Added proactively)
            ('Ejercicio', 'Ejercicio', 'Año fiscal del registro.', 'DIMENSION', True),
            ('Fecha', 'Fecha', 'Fecha principal del documento.', 'DATE', False),
            ('FechaPedido', 'Fecha Pedido', 'Fecha asociada al pedido.', 'DATE', False),
            ('FechaAlbaran', 'Fecha Albarán', 'Fecha del albarán de entrega.', 'DATE', False),
        ]

        count = 0
        for name, bus_name, desc, role, is_key in definitions:
            obj, created = StandardField.objects.update_or_create(
                name__iexact=name, # Check case-insensitive existence if possible, but for now we use name as unique.
                # Actually, our model has name unique=True. So we filter by name.
                defaults={
                    'name': name, # Normalize casing to seed
                    'business_name': bus_name,
                    'description': desc,
                    'semantic_role': role,
                    'is_key': is_key,
                    'fix_type': True # Mark as system-defined
                }
            )
            # Since unique is on 'name' (exact), we rely on that.
            # To be safer with casing, we could first search logic, but exact match is fine for Seeder.
            StandardField.objects.update_or_create(
                name=name,
                defaults={
                    'business_name': bus_name,
                    'description': desc,
                    'semantic_role': role,
                    'is_key': is_key,
                    'fix_type': True
                }
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Successfully seeded {count} Standard Fields.'))
