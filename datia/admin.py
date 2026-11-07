from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import UserEmpresaPermission, Empresa, UserPreference, GlobalConfig

admin.site.site_header = "Datia"
admin.site.site_title = "Datia"
admin.site.index_title = "Configuración de plataforma"

VISIBILITY_TABS = [
    ('tab-ia', 'IA'),
    ('tab-auto', 'Auto entreno'),
    ('tab-actualidad', 'Actualidad'),
    ('tab-personal', 'Pestaña personal'),
    ('tab-historico', 'Histórico'),
    ('tab-datia', 'Datia'),
    ('tab-datia-wow', 'Datia 1'),
    ('tab-datia-2', 'Datia 2'),
    ('tab-datia-3', 'Arquitectura'),
    ('sub-ventas', 'Ventas'),
    ('sub-compras', 'Compras'),
    ('sub-almacen', 'Existencias'),
    ('sub-financiera', 'Financiera'),
    ('sub-ratios', 'Ratios'),
    ('sub-presupuestos', 'Presupuestos'),
    ('sub-evolucion', 'Evolución'),
    ('sub-tesoreria', 'Tesorería'),
    ('sub-pool', 'Pool bancario'),
    ('sub-prediccion', 'Predicción'),
    ('sub-movil', 'Móvil'),
    ('sub-anatomia', 'Anatomía de la utilidad'),
    ('sub-clientes', 'Clientes'),
    ('sub-proveedores', 'Proveedores'),
    ('sub-articulos', 'Artículos'),
    ('subtab-dashboard', 'Auto entreno · Dashboard'),
    ('subtab-context', 'Auto entreno · Contexto'),
    ('subtab-standard-fields', 'Auto entreno · Campos estándar'),
    ('subtab-mapping', 'Auto entreno · Mapeo'),
    ('subtab-sync', 'Auto entreno · Sincronización'),
    ('subtab-relationships', 'Auto entreno · Relaciones'),
    ('subtab-training', 'Auto entreno · Entrenamiento'),
]


class GlobalConfigAdminForm(forms.ModelForm):
    mssql_password_new = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label="Nueva contraseña SQL Server",
        help_text="Déjala vacía para conservar la actual. Si el servidor también está vacío, se usa la contraseña del entorno.",
    )
    for _key, _label in VISIBILITY_TABS:
        locals()[f'vis_{_key}'] = forms.BooleanField(label=_label, required=False)
    del _key, _label

    class Meta:
        model = GlobalConfig
        exclude = ('mssql_password', 'implanter_settings')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = {}
        if getattr(self.instance, 'pk', None):
            current = self.instance.implanter_settings or {}
        self.fields['ai_provider'].widget = forms.Select(choices=[('ollama', 'Ollama'), ('gemini', 'Gemini')])
        self.fields['perf_preset'].widget = forms.Select(choices=[('eco', 'Eco'), ('auto', 'Auto'), ('turbo', 'Turbo')])
        etiquetas = {
            'mssql_driver': 'Driver ODBC',
            'mssql_host': 'Servidor',
            'mssql_port': 'Puerto',
            'mssql_name': 'Base de datos',
            'mssql_user': 'Usuario',
            'mssql_sync_enabled': 'Sincronización activa',
        }
        for nombre, etiqueta in etiquetas.items():
            if nombre in self.fields:
                self.fields[nombre].label = etiqueta
        if 'mssql_name' in self.fields:
            self.fields['mssql_name'].help_text = (
                "Única base de datos del ERP. Si un campo queda vacío, se completa con el .env."
            )
        if 'mssql_password_new' in self.fields and getattr(self.instance, 'mssql_password', ''):
            self.fields['mssql_password_new'].widget.attrs['placeholder'] = 'Contraseña ya guardada'
        from datia.services.suite_conexion import leer
        suite = leer()
        if suite is not None:
            aviso = suite.get('message') or 'El servidor, el usuario, el secreto y la base los marca Devia.'
            for nombre in (
                'mssql_driver', 'mssql_host', 'mssql_port', 'mssql_name',
                'mssql_user', 'mssql_password_new',
            ):
                if nombre in self.fields:
                    self.fields[nombre].disabled = True
                    self.fields[nombre].required = False
            if 'mssql_host' in self.fields:
                self.fields['mssql_host'].help_text = aviso
        for key, _label in VISIBILITY_TABS:
            visible = current.get(key, True) is not False
            self.fields[f'vis_{key}'].initial = visible
            self.initial[f'vis_{key}'] = visible

    def save(self, commit=True):
        obj = super().save(commit=False)
        password = (self.cleaned_data.get('mssql_password_new') or '').strip()
        if password:
            obj.mssql_password = password
        data = dict(obj.implanter_settings or {})
        for key, _label in VISIBILITY_TABS:
            data[key] = bool(self.cleaned_data.get(f'vis_{key}'))
        obj.implanter_settings = data
        if commit:
            obj.save()
        return obj


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'updated_at')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    form = GlobalConfigAdminForm
    list_display = ('__str__', 'base_en_uso', 'servidor_en_uso', 'updated_at')
    readonly_fields = ('conexion_en_uso', 'carga_inicial_link', 'updated_at')

    fieldsets = (
        ('Acceso SQL Server', {
            'description': (
                'Aquí se indica la base de datos del ERP. Cada campo vacío se completa con el .env. '
                'Postgres sigue siendo la base de esta aplicación.'
            ),
            'fields': (
                'conexion_en_uso',
                'mssql_driver', 'mssql_host', 'mssql_port', 'mssql_name',
                'mssql_user', 'mssql_password_new', 'mssql_sync_enabled',
            ),
        }),
        ('Modelos de lenguaje', {
            'fields': (
                'ai_provider', 'ollama_host', 'llm_chat', 'llm_report',
                'llm_semantic', 'llm_sql_training', 'gemini_model',
            ),
        }),
        ('Entorno de ejecución', {
            'fields': (
                'show_sql', 'training_mode', 'auto_load_actualidad',
                'mobile_specialized', 'perf_preset', 'fast_bulk',
            ),
        }),
        ('Identidad', {
            'fields': ('app_name', 'erp_name', 'global_logo_url', 'global_accent'),
        }),
        ('Visibilidad de pestañas', {
            'fields': tuple(f'vis_{key}' for key, _label in VISIBILITY_TABS),
        }),
        ('Operación', {
            'description': 'La carga inicial se abre en la aplicación. Los paquetes de plantilla se exportan e importan con los comandos export_template e import_template.',
            'fields': ('carga_inicial_link', 'updated_at'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        from datia.services.suite_conexion import leer
        suite = leer()
        if suite is None:
            return fieldsets
        aviso = suite.get('message') or (
            "La base activa de la suite es " + str(suite.get('active_database') or "—") + "."
        )
        titulo, opciones = fieldsets[0]
        if titulo == 'Acceso SQL Server':
            opciones = dict(opciones)
            opciones['description'] = (
                "Este acceso lo marca Devia. Aquí no se escribe otro servidor ni otro secreto. "
                + aviso
            )
            fieldsets[0] = (titulo, opciones)
        return fieldsets

    def has_add_permission(self, request):
        return not GlobalConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def carga_inicial_link(self, obj):
        return format_html('<a class="button" href="/#carga-inicial">Abrir carga inicial en la aplicación</a>')
    carga_inicial_link.short_description = "Carga inicial"

    def _params(self, obj):
        from datia.services.runtime_config import mssql_params
        if obj is None or not getattr(obj, 'pk', None):
            obj = GlobalConfig.load()
        return obj, mssql_params()

    @admin.display(description="Base de datos en uso")
    def base_en_uso(self, obj):
        _obj, params = self._params(obj)
        return params.get('name') or '—'

    @admin.display(description="Servidor en uso")
    def servidor_en_uso(self, obj):
        _obj, params = self._params(obj)
        return params.get('host') or '—'

    @admin.display(description="Conexión en uso")
    def conexion_en_uso(self, obj):
        obj, params = self._params(obj)
        if params.get('suite') or params.get('suite_blocked'):
            return format_html(
                "<p style='line-height:1.6'>"
                "<strong>Origen:</strong> Devia<br>"
                "<strong>Servidor:</strong> {}<br>"
                "<strong>Puerto:</strong> {}<br>"
                "<strong>Base de datos:</strong> {}<br>"
                "<strong>Usuario:</strong> {}<br>"
                "<strong>Aviso:</strong> {}"
                "</p>",
                params.get('host') or '—',
                params.get('port') or '—',
                params.get('name') or '—',
                params.get('user') or '—',
                params.get('suite_message') or '—',
            )
        guardados = [
            (getattr(obj, campo, "") or "").strip()
            for campo in ("mssql_host", "mssql_name", "mssql_user")
        ]
        if all(guardados):
            origen = "esta ficha"
        elif any(guardados):
            origen = "esta ficha, completada con el .env"
        else:
            origen = "archivo .env"
        return format_html(
            "<p style='line-height:1.6'>"
            "<strong>Origen:</strong> {}<br>"
            "<strong>Servidor:</strong> {}<br>"
            "<strong>Puerto:</strong> {}<br>"
            "<strong>Base de datos:</strong> {}<br>"
            "<strong>Usuario:</strong> {}<br>"
            "<strong>Contraseña definida:</strong> {}"
            "</p>",
            origen,
            params.get('host') or '—',
            params.get('port') or '—',
            params.get('name') or '—',
            params.get('user') or '—',
            "sí" if params.get('password') else "no",
        )


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'language', 'updated_at')
    search_fields = ('user__username',)


# Inline para mostrar permisos de empresa en el formulario de usuario
class UserEmpresaPermissionInline(admin.TabularInline):
    model = UserEmpresaPermission
    extra = 1
    fields = ('empresa_id', 'created_at')
    readonly_fields = ('created_at',)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "empresa_id":
            # Aquí podríamos filtrar empresas si fuera FK, pero es CharField
            pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Formularios personalizados
class CustomUserCreationForm(UserCreationForm):
    empresas_autorizadas = forms.ModelMultipleChoiceField(
        queryset=Empresa.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple('Empresas', False),
        label="Empresas Autorizadas",
        help_text="Si no seleccionas ninguna, el usuario tendrá acceso a TODAS las empresas. Si seleccionas alguna, solo tendrá acceso a las seleccionadas."
    )
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserEmpresaPermission.objects.filter(user=user).delete()
            empresas_seleccionadas = self.cleaned_data.get('empresas_autorizadas', [])
            for empresa in empresas_seleccionadas:
                UserEmpresaPermission.objects.create(user=user, empresa_id=empresa.codigo)
        
        return user

class CustomUserChangeForm(UserChangeForm):
    empresas_autorizadas = forms.ModelMultipleChoiceField(
        queryset=Empresa.objects.all(),
        required=False,
        widget=admin.widgets.FilteredSelectMultiple('Empresas', False),
        label="Empresas Autorizadas",
        help_text="Si no seleccionas ninguna, el usuario tendrá acceso a TODAS las empresas. Si seleccionas alguna, solo tendrá acceso a las seleccionadas."
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['empresas_autorizadas'].initial = Empresa.objects.filter(
                codigo__in=UserEmpresaPermission.objects.filter(user=self.instance).values_list('empresa_id', flat=True)
            )
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserEmpresaPermission.objects.filter(user=user).delete()
            empresas_seleccionadas = self.cleaned_data.get('empresas_autorizadas', [])
            for empresa in empresas_seleccionadas:
                UserEmpresaPermission.objects.create(user=user, empresa_id=empresa.codigo)
        return user


# Extender el UserAdmin de Django
class CustomUserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    
    list_display = BaseUserAdmin.list_display + ('tab_visibility_link',)
    
    def tab_visibility_link(self, obj):
        url = reverse('user_tab_visibility') + f'?user={obj.id}'
        return format_html('<a class="button" href="{}">Gestionar Pestañas</a>', url)
    tab_visibility_link.short_description = "Visibilidad Pestañas"
    tab_visibility_link.allow_tags = True
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Permisos de Empresa', {
            'fields': ('empresas_autorizadas',),
            'description': 'Configura qué empresas puede ver este usuario en la aplicación.'
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Permisos de Empresa', {
            'fields': ('empresas_autorizadas',),
            'description': 'Configura qué empresas puede ver este usuario en la aplicación.'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        form.save(commit=True)
    
    class Media:
        css = {
            'all': ('/static/admin/css/widgets.css',)
        }


# Re-registrar User con el admin personalizado
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


