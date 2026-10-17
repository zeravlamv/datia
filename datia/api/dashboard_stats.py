from ninja import Router
from typing import Dict, List, Any
from django.db.models import Count, Max, Q
from datia.models import DataSource, DataField, DataRelation, MetricsEmbeddings

router = Router()

@router.get("/dashboard/stats")
def get_dashboard_stats(request):
    """
    Returns aggregated statistics for the Auto-Training Dashboard.
    """
    # 1. Datasource Stats
    total_tables = DataSource.objects.filter(is_active=True).count()
    synced_tables = DataSource.objects.filter(is_active=True, last_sync_at__isnull=False).count()
    
    # 2. Embedding/Training Stats
    # 'qa' are learned rules/queries
    # 'schema' are indexed tables coverage
    total_embeddings = MetricsEmbeddings.objects.filter(kind='qa').count()
    indexed_tables_count = MetricsEmbeddings.objects.filter(kind='schema').count()
    
    last_training = MetricsEmbeddings.objects.filter(kind='qa').aggregate(Max('updated_at'))['updated_at__max']
    
    # 3. Relationship Stats
    total_relations = DataRelation.objects.count()
    
    # 3.1. Total Synced Records (Sum of record_count of all synced tables)
    from django.db.models import Sum
    total_records = DataSource.objects.filter(is_active=True).aggregate(Sum('record_count'))['record_count__sum'] or 0

    # 4. Detailed Table Stats
    tables_qs = DataSource.objects.filter(is_active=True).prefetch_related('fields').order_by('-last_sync_at')
    
    tables_data = []
    
    # Check which tables are indexed in vector DB
    indexed_keys = set(MetricsEmbeddings.objects.filter(kind='schema').values_list('key', flat=True))
    
    for ds in tables_qs:
        # Check Sync Status
        is_synced = ds.last_sync_at is not None
        is_indexed = ds.source_table in indexed_keys
        
        # Calculate active fields count in Python to avoid annotation grouping issues
        field_count = len([f for f in ds.fields.all() if f.is_active])
        
        tables_data.append({
            "id": ds.id,
            "name": ds.name,
            "table": ds.source_table,
            "fields": field_count,
            "synced": is_synced,
            "virtual": ds.is_virtual,
            "indexed": is_indexed,
            "last_sync": ds.last_sync_at,
            "relations": ds.relations_out.count() + ds.relations_in.count()
        })

    # 5. Training Evolution (Grouped by Scope & Date)
    from django.db.models.functions import TruncDate
    from collections import defaultdict
    import datetime

    # Fetch ALL QA embeddings sorted by date to build cumulative history
    # Optimization: If dataset grows >10k, we should aggregate in DB or cache.
    # Current expected size < 5k.
    qs = MetricsEmbeddings.objects.filter(kind='qa').order_by('updated_at').values('updated_at', 'metadata', 'key')
    
    # Structure: date_str -> { 'auto_training': count, 'manual': count }
    daily_stats = defaultdict(lambda: defaultdict(int))
    recent_activity = []

    # Process
    total_auto = 0
    total_manual = 0
    
    sorted_rows = list(qs) # Evaluate
    
    # 5.1 Evolution Data
    for row in sorted_rows:
        d_str = row['updated_at'].strftime("%Y-%m-%d")
        meta = row.get('metadata', {}) or {}
        scope = meta.get('scope', 'manual') # Default to manual if missing/legacy
        
        # Merge unknown scopes into manual for simpler chart
        if scope not in ['auto_training', 'manual']:
            scope = 'manual'
            
        daily_stats[d_str][scope] += 1

    # Convert to cumulative series
    # Get all unique dates sorted
    all_dates = sorted(daily_stats.keys())
    
    series_auto = []
    series_manual = []
    running_auto = 0
    running_manual = 0
    
    for d in all_dates:
        day_data = daily_stats[d]
        running_auto += day_data.get('auto_training', 0)
        running_manual += day_data.get('manual', 0)
        
        series_auto.append(running_auto)
        series_manual.append(running_manual)

    training_evolution = {
        "dates": all_dates,
        "series": [
            {"name": "Entreno Autom.", "data": series_auto},
            {"name": "Manual / Feedback", "data": series_manual}
        ]
    }

    # 5.2 Recent Activity (Last 20)
    # Reverse iterate strictly for list
    for row in sorted_rows[-20:][::-1]:
        meta = row.get('metadata', {}) or {}
        scope = meta.get('scope', 'manual')
        snippet = row.get('key', '')
        
        # Humanize info
        if scope == 'auto_training':
            label = "Auto-Aprendizaje"
            icon = "⚡"
        else:
            label = "Ajuste Manual"
            icon = "✍️"
            
        recent_activity.append({
            "date": row['updated_at'].isoformat(),
            "scope": scope,
            "label": label,
            "icon": icon,
            "snippet": snippet[:50] + "..." if len(snippet) > 50 else snippet
        })

    # ... (Rest of logic)
    
    # 6. Relationship Network (Existing logic unchanged)
    rel_counts = {}
    relations_list = [] # [NEW] Detailed list for UI
    
    all_rels = DataRelation.objects.all().select_related('source', 'target').order_by('-id')[:50] # Last 50
    for r in all_rels:
        s = r.source.source_table
        t = r.target.source_table
        rel_counts[s] = rel_counts.get(s, 0) + 1
        rel_counts[t] = rel_counts.get(t, 0) + 1
        
        relations_list.append({
            "source": s,
            "target": t,
            "cardinality": r.cardinality,
            "from_field": r.from_field.business_name,
            "to_field": r.to_field.business_name
        })
        
    # 7. System Stats (DB Size)
    from django.db import connection
    db_size = "N/A"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
            row = cursor.fetchone()
            if row:
                db_size = row[0]
    except Exception:
        pass

    return {
        "kpi": {
            "total_tables": total_tables,
            "synced_tables": synced_tables,
            "trained_rules": total_embeddings,
            "knowledge_nodes": indexed_tables_count,
            "relationships": total_relations,
            "total_records": total_records,
            "last_training": last_training,
            "db_size": db_size
        },
        "tables": tables_data,
        "training_evolution": training_evolution, # New
        "recent_activity": recent_activity,       # New
        "relationships": rel_counts,
        "relations_list": relations_list          # [NEW] For Simple List UI
    }

@router.get("/dashboard/network")
def get_network_graph(request):
    """
    Returns Node-Link data for visualization.
    """
    nodes = []
    edges = []
    
    # Nodes: Tables
    sources = DataSource.objects.filter(is_active=True)
    for ds in sources:
        nodes.append({
            "id": ds.source_table, 
            "label": ds.name, 
            "group": "table",
            "val": 10 # Size
        })
        
    # Edges: Relationships
    rels = DataRelation.objects.all().select_related('source', 'target')
    for r in rels:
        edges.append({
            "from": r.source.source_table,
            "to": r.target.source_table,
            "label": r.cardinality,
            "arrows": "to"
        })
        
    return {"nodes": nodes, "edges": edges}
