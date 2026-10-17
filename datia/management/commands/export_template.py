import json
import os
from django.core.management.base import BaseCommand
from datia.models.semantic import DataSource, DataField, DataRelation, BusinessContext
from datia.models.ai import MetricsEmbeddings

class Command(BaseCommand):
    help = 'Exporta el "Pack de Conocimiento" (Template) a un archivo JSON para su redistribución.'

    def add_arguments(self, parser):
        parser.add_argument('--pack', type=str, required=True, help='Nombre del Pack (ej: sage_v1)')
        parser.add_argument('--output', type=str, required=False, help='Ruta de salida (opcional)')

    def handle(self, *args, **options):
        pack_name = options['pack']
        
        # Define output path
        if options['output']:
            output_path = options['output']
        else:
            # Default to fixtures/packs
            base_dir = "datia/fixtures/packs"
            os.makedirs(base_dir, exist_ok=True)
            output_path = f"{base_dir}/{pack_name}.json"

        self.stdout.write(f"📦 Exportando Pack: {pack_name}...")

        # 1. Export BusinessContext
        business_contexts = []
        for bc in BusinessContext.objects.all():
            business_contexts.append({
                'empresa_id': bc.empresa_id,
                'key': bc.key,
                'content': bc.content
            })
        self.stdout.write(f"   - {len(business_contexts)} Contextos de Negocio")

        # 2. Export DataSource + DataField (Nested)
        datasources = []
        for ds in DataSource.objects.all():
            ds_data = {
                'name': ds.name,
                'source_table': ds.source_table,
                'description': ds.description,
                'table_context': ds.table_context,
                'keywords': ds.keywords,
                'is_active': ds.is_active,
                'fields': []
            }

            # Export Fields for this Source
            for field in ds.fields.all():
                ds_data['fields'].append({
                    'field_name': field.field_name,
                    'business_name': field.business_name,
                    'synonyms': field.synonyms,
                    'description': field.description,
                    'metadata_tag': field.metadata_tag,
                    'data_type': field.data_type,
                    'usage_type': field.usage_type,
                    'is_active': field.is_active,
                    'is_key': field.is_key,
                    'is_pii': field.is_pii
                })
            
            datasources.append(ds_data)
        self.stdout.write(f"   - {len(datasources)} Fuentes de Datos (Tablas)")

        # 3. Export DataRelation
        relations = []
        for rel in DataRelation.objects.all():
            relations.append({
                'source__source_table': rel.source.source_table,
                'from_field__field_name': rel.from_field.field_name,
                'target__source_table': rel.target.source_table,
                'to_field__field_name': rel.to_field.field_name,
                'cardinality': rel.cardinality
            })
        self.stdout.write(f"   - {len(relations)} Relaciones (Joins)")

        # 4. Export MetricsEmbeddings (Knowledge)
        embeddings = []
        for emb in MetricsEmbeddings.objects.all():
            embeddings.append({
                'kind': emb.kind,
                'key': emb.key,
                'text': emb.text,
                'metadata': emb.metadata,
                'vector': emb.vector
            })
        self.stdout.write(f"   - {len(embeddings)} Vectores de Conocimiento (IA)")

        # Compile Final Pack
        pack_data = {
            'meta': {
                'pack_name': pack_name,
                'version': '1.0',
                'exported_at': str(os.path.exists(output_path)) # timestamp could be added
            },
            'business_context': business_contexts,
            'datasources': datasources,
            'relations': relations,
            'embeddings': embeddings
        }

        # Write to File
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(pack_data, f, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"✅ Pack exportado exitosamente a: {output_path}"))
