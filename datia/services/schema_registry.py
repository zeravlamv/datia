# Schema Registry - DEPRECATED
# This file is maintained for backward compatibility during the migration to DatiaSchema.
# The 'QueryBuilder' now dynamically fetches schema via 'datia_schema.py'.

SCHEMA_REGISTRY = {
    # Deprecated: No hardcoded entities.
    # The new QueryBuilder queries 'information_schema' for tpl_ingest_* tables.
    "entities": {},
    "metrics": {}
}
