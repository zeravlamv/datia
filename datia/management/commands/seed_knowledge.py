from django.core.management.base import BaseCommand
from datia.models import MetricsEmbeddings, DataSource, DataField
from datia.services.embedding_service import EmbeddingService
import random

class Command(BaseCommand):
    help = 'Seeds the AI Knowledge Base with Dynamic Examples based on Active DataSources (No Hardcoding)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Start seeding AI Knowledge (Dynamic Mode)...'))
        
        # 1. PURGE OLD TEMPLATE DATA
        deleted_count, _ = MetricsEmbeddings.objects.filter(kind='template', metadata__source='generated_seed').delete()
        self.stdout.write(self.style.SUCCESS(f'Purged {deleted_count} old template entries.'))
        
        svc = EmbeddingService()
        examples = []
        
        # 2. FETCH ACTIVE DATA SOURCES
        sources = DataSource.objects.filter(is_active=True)
        if not sources.exists():
            self.stdout.write(self.style.ERROR('No active DataSources found. Cannot seed knowledge.'))
            return

        total_generated = 0

        for source in sources:
            table_name = source.get_local_table_name()
            if not table_name:
                continue # Skip virtual tables
            
            self.stdout.write(f"Processing source: {source.name} ({table_name})...")
            
            fields = DataField.objects.filter(source=source, is_active=True)
            
            # Categorize fields
            metrics = [f for f in fields if f.usage_type == 'metric']
            dimensions = [f for f in fields if f.usage_type == 'dimension']
            dates = [f for f in fields if f.usage_type == 'date' and f.data_type in ['date', 'datetime', 'timestamp']]
            
            # Find Enterprise/Year columns (Dynamic!)
            col_empresa = next((f.field_name for f in dimensions if 'empresa' in f.field_name.lower() or 'codemp' in f.field_name.lower()), None)
            col_ejercicio = next((f.field_name for f in dimensions+dates if 'ejercicio' in f.field_name.lower() or 'year' in f.field_name.lower()), None)
            
            # Base filters pattern
            base_filters = []
            if col_empresa:
                base_filters.append(f'"{col_empresa}" = {{empresa}}')
            if col_ejercicio:
                base_filters.append(f'"{col_ejercicio}" = {{ejercicio}}')
                
            where_clause_base = " AND ".join(base_filters)
            if where_clause_base:
                where_clause_base = "WHERE " + where_clause_base

            # --- EXHAUSTIVE GENERATOR 1: METRIC FILTERS ---
            # Generate MANY value variations for each metric
            value_ranges = [10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 50000, 100000]
            comparison_ops = [
                ('>', 'mayor', 'mayores', 'superiores', 'mas de'),
                ('<', 'menor', 'menores', 'inferiores', 'menos de'),
                ('>=', 'al menos', 'minimo'),
                ('<=', 'maximo', 'como mucho')
            ]
            
            for metric in metrics:
                syns = metric.synonyms + [metric.business_name] if metric.synonyms else [metric.business_name]
                
                # Generate queries for each value range
                for val in value_ranges:
                    for op_symbol, *op_words in comparison_ops:
                        # Pick a random synonym and operator word
                        term = random.choice(syns)
                        op_word = random.choice(op_words)
                        
                        sql = f'SELECT * FROM "{table_name}" {where_clause_base} AND "{metric.field_name}" {op_symbol} {val}'
                        if where_clause_base: sql = sql.replace("WHERE AND", "WHERE")
                        
                        text = f"{source.name} con {term} {op_word} {val}"
                        
                        examples.append({
                            "text": text,
                            "sql": sql,
                            "label": f"Gen.{source.name}.{metric.field_name}.{op_symbol.replace('>', 'gt').replace('<', 'lt').replace('=', 'eq')}.{val}"
                        })

            # --- EXHAUSTIVE GENERATOR 2: DIMENSION FILTERS ---
            # Generate multiple example values for each dimension
            example_values = {
                'cliente': ['MERCADONA', 'CARREFOUR', 'DIA', 'EROSKI', 'ALCAMPO', 'LIDL'],
                'provincia': ['MADRID', 'BARCELONA', 'VALENCIA', 'SEVILLA', 'ZARAGOZA', 'MALAGA', 'MURCIA', 'BILBAO'],
                'nacion': ['ESPAÑA', 'FRANCIA', 'PORTUGAL', 'ITALIA', 'ALEMANIA'],
                'pais': ['ESPAÑA', 'FRANCIA', 'PORTUGAL', 'ITALIA'],
                'ciudad': ['MADRID', 'BARCELONA', 'VALENCIA'],
                'vendedor': ['JUAN', 'MARIA', 'PEDRO', 'ANA'],
                'agente': ['NORTE', 'SUR', 'ESTE', 'OESTE']
            }
            
            for dim in dimensions:
                if 'id' in dim.business_name.lower() or 'guid' in dim.field_name.lower():
                    continue
                    
                term = dim.business_name
                
                # Detect type and use relevant examples
                vals_to_use = ['VALOR_EJEMPLO']
                for keyword, values in example_values.items():
                    if keyword in dim.business_name.lower() or keyword in dim.field_name.lower():
                        vals_to_use = values
                        break
                
                # Generate query for EACH value
                for val in vals_to_use:
                    sql = f'SELECT * FROM "{table_name}" {where_clause_base} AND "{dim.field_name}" = \'{val}\''
                    if where_clause_base: sql = sql.replace("WHERE AND", "WHERE")
                    
                    # Multiple language variations
                    variations = [
                        f"{source.name} de {term} {val}",
                        f"{source.name} del {term} {val}",
                        f"{source.name} para {term} {val}",
                        f"{term} {val}",
                        f"dame {source.name} de {val}"
                    ]
                    
                    for text_var in variations:
                        examples.append({
                            "text": text_var,
                            "sql": sql,
                            "label": f"Gen.{source.name}.{dim.field_name}.eq.{val.replace(' ', '_')}"
                        })

            # --- EXHAUSTIVE GENERATOR 3: DATE FILTERS (Temporal Intelligence) ---
            months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                     'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
            month_abbr = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
            
            for date_col in dates:
                # Month-based queries
                for idx, (m_name, m_abbr) in enumerate(zip(months, month_abbr), 1):
                    sql_date = f'SELECT * FROM "{table_name}" {where_clause_base} AND EXTRACT(MONTH FROM "{date_col.field_name}") = {idx}'
                    if not where_clause_base:
                        sql_date = f'SELECT * FROM "{table_name}" WHERE EXTRACT(MONTH FROM "{date_col.field_name}") = {idx}'
                    else:
                        sql_date = sql_date.replace("WHERE AND", "WHERE")
                    
                    # Language variations
                    variations = [
                        f"{source.name} de {m_name}",
                        f"{source.name} del mes de {m_name}",
                        f"{source.name} en {m_name}",
                        f"{source.name} mes {idx}",
                        f"{source.name} {m_abbr}",
                        f"dame {source.name} de {m_name}",
                        f"ver {source.name} {m_name}"
                    ]
                    
                    for text_var in variations:
                        examples.append({
                            "text": text_var,
                            "sql": sql_date,
                            "label": f"Gen.{source.name}.{date_col.field_name}.month.{idx}"
                        })
                
                # Year-based queries (if not ejercicio)
                if 'ejercicio' not in date_col.field_name.lower():
                    for year in range(2020, 2026):
                        sql_year = f'SELECT * FROM "{table_name}" {where_clause_base} AND EXTRACT(YEAR FROM "{date_col.field_name}") = {year}'
                        if where_clause_base: sql_year = sql_year.replace("WHERE AND", "WHERE")
                        
                        text_year = f"{source.name} del año {year}"
                        examples.append({
                            "text": text_year,
                            "sql": sql_year,
                            "label": f"Gen.{source.name}.{date_col.field_name}.year.{year}"
                        })
                
                # Date ranges (last 7 days, last month, etc.)
                ranges = [
                    ("últimos 7 días", "7 DAY"),
                    ("última semana", "7 DAY"),
                    ("último mes", "1 MONTH"),
                    ("últimos 30 días", "30 DAY"),
                    ("últimos 3 meses", "3 MONTH"),
                    ("último año", "1 YEAR")
                ]
                
                for range_text, interval in ranges:
                    sql_range = f'SELECT * FROM "{table_name}" {where_clause_base} AND "{date_col.field_name}" >= CURRENT_DATE - INTERVAL \'{interval}\''
                    if where_clause_base: sql_range = sql_range.replace("WHERE AND", "WHERE")
                    
                    text_range = f"{source.name} de los {range_text}"
                    examples.append({
                        "text": text_range,
                        "sql": sql_range,
                        "label": f"Gen.{source.name}.{date_col.field_name}.range.{interval.replace(' ', '_')}"
                    })
        
        # --- BATCH PROCESS ---
        count = 0
        total = len(examples)
        self.stdout.write(f"Generating embeddings for {total} dynamic examples...")
        
        batch_size = 50
        for i in range(0, total, batch_size):
            batch = examples[i:i+batch_size]
            self.stdout.write(f"Processing batch {i}-{i+len(batch)}/{total}...")
            
            # Bulk Create
            objs_to_create = []
            for item in batch:
                key = f"seed_{item['label']}"
                vector = svc.embed_text(item['text'])
                
                objs_to_create.append(MetricsEmbeddings(
                    kind='template',
                    key=key,
                    text=item['text'],
                    vector=vector,
                    metadata={
                        "sql": item['sql'],
                        "scope": "global",
                        "label": item['label'],
                        "source": "generated_seed"
                    }
                ))
            
            MetricsEmbeddings.objects.bulk_create(objs_to_create, ignore_conflicts=True)
            count += len(batch)
            
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {count} new knowledge items (Dynamic Schema).'))

