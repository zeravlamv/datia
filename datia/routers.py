class DatiaRouter:
    """
    A router to control all database operations on models in the
    datia application.
    Route 'Metrics*' models to 'analytics' (Postgres).
    Route everything else to 'default' (SQLite).
    """
    
    route_app_labels = {'datia'}

    def _is_analytics_model(self, model_name):
        name = model_name.lower()
        return name.startswith('metrics') or name in [
            'datiacabecera', 'datialineas', 
            'businesscontext', 'datasource', 'datafield'
        ]

    def db_for_read(self, model, **hints):
        if self._is_analytics_model(model._meta.model_name):
            return 'analytics'
        return 'default'

    def db_for_write(self, model, **hints):
        if self._is_analytics_model(model._meta.model_name):
            return 'analytics'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations if both are in the same DB
        db1 = self.db_for_write(obj1)
        db2 = self.db_for_write(obj2)
        if db1 == db2:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name and self._is_analytics_model(model_name):
            return db == 'analytics'
        
        # Otherwise, migrate to default (SQLite)
        if db == 'analytics':
             return False 
        return True
