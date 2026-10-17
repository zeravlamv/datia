from django.core.management.base import BaseCommand
from datia.models import DataSource
from datia.services.ollama_service import OllamaService
from datia.services.sql_generator import SQLExampleGenerator
import time

class Command(BaseCommand):
    help = 'Entrena la IA generando queries SQL de ejemplo para las tablas activas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--queries',
            type=int,
            default=15,
            help='Número de queries a generar por tabla'
        )
        parser.add_argument(
            type=str,
            help='Filtrar por nombre de tabla específica (opcional)'
        )
        parser.add_argument(
            '--model',
            type=str,
            default=None,
            help='Nombre del modelo Ollama a utilizar (opcional, p.ej: llama3:8b)'
        )

    def handle(self, *args, **options):
        queries_per_table = options['queries']
        specific_table = options['table']
        target_model = options['model']
        
        self.stdout.write(self.style.MIGRATE_HEADING('=== Iniciando Entrenamiento Masivo de IA (CLI) ==='))
        if target_model:
            self.stdout.write(self.style.MIGRATE_HEADING(f'🤖 Modelo seleccionado: {target_model}'))

        # 1. Initialize Services
        try:
            llm_client = OllamaService()
            generator = SQLExampleGenerator(llm_client)
            self.stdout.write(self.style.SUCCESS('✅ Servicios de IA inicializados'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error conectando con servicios: {e}'))
            return

        # 2. Get Tables
        if specific_table:
            tables = DataSource.objects.filter(name__icontains=specific_table, is_active=True)
        else:
            tables = DataSource.objects.filter(is_active=True)
        
        total_tables = tables.count()
        if total_tables == 0:
            self.stdout.write(self.style.WARNING('⚠️ No se encontraron tablas activas para entrenar.'))
            return

        self.stdout.write(f'📋 Tablas a procesar: {total_tables}')
        self.stdout.write(f'🤖 Queries por tabla: {queries_per_table}')
        self.stdout.write('----------------------------------------')

        total_saved_global = 0

        # 3. Process Logic
        for idx, table in enumerate(tables, 1):
            physical_name = table.get_local_table_name()
            self.stdout.write(f'\n[{idx}/{total_tables}] Procesando tabla: {table.name}')
            self.stdout.write(self.style.DIM(f'      Target Postgres: {physical_name}'))
            
            try:
                # Generate
                timeout_msg = f'      Generando ejemplos con {target_model or "Default"}... (paciencia, timeout=300s)'
                self.stdout.write(timeout_msg)
                start_time = time.time()
                
                queries = generator.generate_for_table(table, count=queries_per_table, model=target_model)
                
                duration = time.time() - start_time
                self.stdout.write(f'      ✅ Generadas {len(queries)} queries en {duration:.1f}s')

                # Save
                saved_count = generator.save_to_knowledge_base(queries, table.name)
                
                if saved_count > 0:
                    self.stdout.write(self.style.SUCCESS(f'      💾 Guardadas {saved_count} queries en MetricsEmbeddings'))
                    total_saved_global += saved_count
                else:
                    self.stdout.write(self.style.WARNING(f'      ⚠️ No se guardó ninguna query (revisar logs de debug)'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'      ❌ Error procesando tabla: {str(e)}'))

        self.stdout.write('----------------------------------------')
        self.stdout.write(self.style.SUCCESS(f'🎉 ENTRENAMIENTO FINALIZADO. Total queries aprendidas: {total_saved_global}'))
