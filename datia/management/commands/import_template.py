import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datia.models.semantic import DataSource, DataField, DataRelation, BusinessContext
from datia.models.ai import MetricsEmbeddings

class Command(BaseCommand):
    help = 'Importa un "Pack de Conocimiento" (Template) desde un archivo JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--pack', type=str, required=True, help='Nombre del Pack (ej: sage_v1)')
        parser.add_argument('--clean', action='store_true', help='limpia la configuración existente antes de importar (PELIGROSO)')

    def handle(self, *args, **options):
        pack_name = options['pack']
        
        # Resolve Path
        base_dir = "datia/fixtures/packs"
        input_path = f"{base_dir}/{pack_name}.json"

        if not os.path.exists(input_path):
            raise CommandError(f"No se encuentra el archivo de pack: {input_path}")

        self.stdout.write(f"📦 Abriendo Pack: {input_path}...")

        with open(input_path, 'r', encoding='utf-8') as f:
            pack_data = json.load(f)

        meta = pack_data.get('meta', {})
        self.stdout.write(f"   ℹ️  Pack: {meta.get('pack_name', 'Unknown')} (v{meta.get('version', '?')})")

        with transaction.atomic():
            if options['clean']:
                self.stdout.write(self.style.WARNING("🧹 Limpiando configuración existente..."))
                DataRelation.objects.all().delete()
                DataField.objects.all().delete()
                DataSource.objects.all().delete()
                BusinessContext.objects.all().delete()
                MetricsEmbeddings.objects.all().delete()

            # 1. Import BusinessContext
            bc_list = pack_data.get('business_context', [])
            for item in bc_list:
                BusinessContext.objects.update_or_create(
                    empresa_id=item['empresa_id'],
                    key=item['key'],
                    defaults={'content': item['content']}
                )
            self.stdout.write(f"   - Importados {len(bc_list)} Contextos de Negocio")

            # 2. Import DataSource + DataField
            ds_list = pack_data.get('datasources', [])
            for ds_data in ds_list:
                ds, created = DataSource.objects.update_or_create(
                    name=ds_data['name'], # Assuming name is unique enough or we use source_table
                    defaults={
                        'source_table': ds_data['source_table'],
                        'description': ds_data['description'],
                        'table_context': ds_data['table_context'],
                        'keywords': ds_data['keywords'],
                        'is_active': ds_data['is_active']
                    }
                )
                
                # Fields
                fields_data = ds_data.get('fields', [])
                for f_data in fields_data:
                    DataField.objects.update_or_create(
                        source=ds,
                        field_name=f_data['field_name'],
                        defaults={
                            'business_name': f_data['business_name'],
                            'synonyms': f_data['synonyms'],
                            'description': f_data['description'],
                            'metadata_tag': f_data['metadata_tag'],
                            'data_type': f_data['data_type'],
                            'usage_type': f_data['usage_type'],
                            'is_active': f_data['is_active'],
                            'is_key': f_data['is_key'],
                            'is_pii': f_data['is_pii']
                        }
                    )
            self.stdout.write(f"   - Importadas {len(ds_list)} Fuentes de Datos")

            # 3. Import DataRelation
            rel_list = pack_data.get('relations', [])
            relations_created = 0
            for r_data in rel_list:
                try:
                    # Lookup Source
                    src_ds = DataSource.objects.get(source_table=r_data['source__source_table'])
                    src_field = DataField.objects.get(source=src_ds, field_name=r_data['from_field__field_name'])
                    
                    # Lookup Target
                    tgt_ds = DataSource.objects.get(source_table=r_data['target__source_table'])
                    tgt_field = DataField.objects.get(source=tgt_ds, field_name=r_data['to_field__field_name'])

                    DataRelation.objects.update_or_create(
                        source=src_ds,
                        from_field=src_field,
                        target=tgt_ds,
                        defaults={
                            'to_field': tgt_field,
                            'cardinality': r_data['cardinality']
                        }
                    )
                    relations_created += 1
                except (DataSource.DoesNotExist, DataField.DoesNotExist) as e:
                    self.stdout.write(self.style.ERROR(f"   ⚠️  Error en relación: {e}"))

            self.stdout.write(f"   - Importadas {relations_created} Relaciones")

            # 4. Import Embeddings
            emb_list = pack_data.get('embeddings', [])
            for emb_data in emb_list:
                MetricsEmbeddings.objects.update_or_create(
                    kind=emb_data['kind'],
                    key=emb_data['key'],
                    defaults={
                        'text': emb_data['text'],
                        'metadata': emb_data['metadata'],
                        'vector': emb_data['vector']
                    }
                )
            self.stdout.write(f"   - Importados {len(emb_list)} Vectores de Conocimiento")

        self.stdout.write(self.style.SUCCESS(f"✅ Pack '{pack_name}' importado exitosamente."))
