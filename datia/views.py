import json
import time
import os
import re
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import admin
from django.contrib.auth.models import Group
from django.db import connection
from django.db.utils import ProgrammingError
from .models import WidgetState
from django.utils.translation import get_language
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from datia.models.master import Empresa, GlobalConfig
from datia.models.preferences import UserPreference


def load_global_config_safe():
    try:
        return GlobalConfig.load()
    except ProgrammingError:
        with connection.schema_editor() as editor:
            editor.create_model(GlobalConfig)
        return GlobalConfig.load()


def get_user_preferences_safe(user):
    try:
        pref, _ = UserPreference.objects.get_or_create(user=user)
        return pref
    except ProgrammingError:
        with connection.schema_editor() as editor:
            editor.create_model(UserPreference)
        pref, _ = UserPreference.objects.get_or_create(user=user)
        return pref


def login_view(request):
    if request.method == 'POST':
        user = request.POST.get('username')
        passw = request.POST.get('password')
        user_auth = authenticate(request, username=user, password=passw)
        if user_auth is not None:
            login(request, user_auth)
            # Redirect to next arg if exists, else dashboard
            next_url = request.POST.get('next') or request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            return render(request, 'datia/login.html', {'error': 'Usuario o contraseña incorrectos', 'next': request.POST.get('next', '')})
    
    return render(request, 'datia/login.html', {'next': request.GET.get('next', '')})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def dashboard(request):
    # existing code unchanged
    """
    Renders the main dashboard.
    Loads user-specific layout if available.
    """
    # Placeholder for user-specific layout retrieval
    # In V2 Strict, we would get request.user state
    # state = WidgetState.objects.filter(user=request.user).first()
    
    from django.db.models import Max
    from datia.models import MetricsTotalesEmpresaEjercicio

    try:
        first_emp = Empresa.objects.first()
    except ProgrammingError:
        first_emp = None
    default_emp = first_emp.codigo if first_emp else None
    emp_id = request.GET.get('empresa') or ''

    last_update = None
    try:
        metrics_qs = MetricsTotalesEmpresaEjercicio.objects.all()
        if emp_id:
            metrics_qs = metrics_qs.filter(empresa=int(emp_id))
        last_update = metrics_qs.aggregate(Max('calculado_at')).get('calculado_at__max')
    except Exception:
        last_update = None

    global_conf_obj = load_global_config_safe()
    global_conf = global_conf_obj.implanter_settings or {}
    user_pref = get_user_preferences_safe(request.user)
    user_vis = user_pref.visible_tabs or {}
    
    hidden_tabs = []
    
    # Check Global
    for k, v in global_conf.items():
        if v is False:
            hidden_tabs.append(k)
            
    # Check User (only if not already hidden globally)
    for k, v in user_vis.items():
        if v is False and k not in hidden_tabs:
            hidden_tabs.append(k)

    context = {
        'api_url': '/api/datia',
        'empresa': emp_id, 
        'ejercicio': request.GET.get('ejercicio') or '',
        'last_update': last_update,
        'cache_bust': int(time.time()),
        'user': request.user,
        'hidden_tabs': hidden_tabs,
    }
    is_impl = request.user.groups.filter(name__iexact='Implantador').exists() or request.user.is_superuser
    is_dev = (is_impl or
              request.user.groups.filter(name__iexact='Desarrollador').exists() or
              request.user.groups.filter(name__iexact='Consultor').exists())
    settings_modes = {'user': True, 'dev': is_dev, 'impl': is_impl}
    context['settings_modes_json'] = json.dumps(settings_modes)
    return render(request, 'datia/dashboard.html', context)

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff)
def tab_visibility_view(request):
    """GUI for staff to set tab visibility per user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = User.objects.all().order_by('username')

    TAB_IDS = [
        'tab-ia', 'tab-auto', 'tab-actualidad', 'tab-historico',
        'tab-datia', 'tab-datia-wow', 'tab-datia-2', 'tab-datia-3', 'tab-personal',
        'sub-ventas', 'sub-compras', 'sub-almacen',
        'sub-financiera', 'sub-presupuestos', 'sub-evolucion', 'sub-prediccion', 'sub-movil', 'fin-section-anatomia',
        'subtab-dashboard', 'subtab-context', 'subtab-standard-fields',
        'subtab-mapping', 'subtab-sync', 'subtab-relationships', 'subtab-training',
    ]

    global_conf_obj = load_global_config_safe()
    global_conf = global_conf_obj.implanter_settings or {}
    
    # "False" in global_conf means HIDDEN/DISABLED globally.
    # We only show tabs that are NOT False (True or missing/None = visible by default)
    # Note: 'missing' means visible in our logic, so we only exclude if explicitly False.
    
    # However, user interface shows CHECKED = VISIBLE.
    # If Global is False, it's never visible, so we shouldn't even offer it.
    
    filtered_ids = []
    for tid in TAB_IDS:
        # SOFT MODE: Show if NOT explicitly disabled (False) in Global Config.
        # This allows new tabs to appear by default even if not yet saved in GlobalConfig.
        if global_conf.get(tid) is not False:
            filtered_ids.append(tid)
            
    TAB_IDS = filtered_ids

    selected_user = None
    pref = {}
    selected_user_id = request.GET.get('user')
    if selected_user_id:
        try:
            selected_user = User.objects.get(pk=selected_user_id)
            pref_obj = get_user_preferences_safe(selected_user)
            pref = pref_obj.visible_tabs or {}
        except User.DoesNotExist:
            selected_user = None
            pref = {}

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            visible = data.get('visible_tabs', {})
            target_id = data.get('target_user_id')
            
            # Determine target user
            if target_id:
                target_user = User.objects.get(pk=target_id)
            else:
                target_user = request.user

            pref_obj = get_user_preferences_safe(target_user)
            pref_obj.visible_tabs = visible
            pref_obj.save()
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)

    # Pre-calculate selection and visibility to avoid template logic issues
    for u in users:
        u.is_selected = (selected_user and u.id == selected_user.id)
    
    tab_data = []
    for tid in TAB_IDS:
        tab_data.append({
            'id': tid,
            'is_visible': (pref.get(tid) is not False)
        })

    context = {
        'users': users,
        'selected_user': selected_user,
        'tab_data': tab_data,
        'pref': pref,
        'title': "Control de Visibilidad",
    }
    context.update(admin.site.each_context(request))
    return render(request, 'datia/tab_vis_safe.html', context)


@login_required(login_url='login')
def project_context_view(request):
    """
    Renders the PROJECT_CONTEXT.md file as a premium landing page.
    """
    import os
    file_path = os.path.join(settings.BASE_DIR, 'PROJECT_CONTEXT.md')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Error\nFile PROJECT_CONTEXT.md not found."
    
    return render(request, 'datia/project_context.html', {'content': content})

@login_required(login_url='login')
def mobile_dashboard_view(request):
    """
    Mobile First dashboard desacoplado de escritorio.
    Incluye selectores de empresa/ejercicio y gestión de logo móvil.
    """
    from .models import Empresa, MetricsTotalesEmpresaEjercicio
    first_emp = Empresa.objects.first()
    default_emp = first_emp.codigo if first_emp else None
    
    emp_id_str = request.GET.get('empresa')
    emp_id = int(emp_id_str) if (emp_id_str and emp_id_str.isdigit()) else default_emp
    
    ej_default_str = request.GET.get('ejercicio')
    ej_default = int(ej_default_str) if ej_default_str else None
    
    # [FIX] Filter companies by user permission
    from .models.permissions import UserEmpresaPermission
    
    allowed_ids = UserEmpresaPermission.objects.filter(user=request.user).values_list('empresa_id', flat=True)
    
    if allowed_ids.exists():
        # If explicit permissions exist, use them (even for superusers)
        empresas_qs = Empresa.objects.filter(codigo__in=allowed_ids).values('codigo', 'nombre')
    elif request.user.is_superuser:
        # If no explicit permissions and is superuser, show all
        empresas_qs = Empresa.objects.all().values('codigo', 'nombre')
    else:
        # Default fallback (keep existing behavior for now, or change to none if stricter needed)
        empresas_qs = Empresa.objects.all().values('codigo', 'nombre')

    empresas = list(empresas_qs)

    ejercicios = []
    if emp_id:
        # Verify if user has access to this specific requested emp_id (if filtered)
        allowed_codigos = [e['codigo'] for e in empresas]
        if emp_id not in allowed_codigos and allowed_codigos:
            # If requested company is not allowed, switch to the first allowed one
            emp_id = allowed_codigos[0]
        
        ejercicios_qs = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=emp_id).values_list('ejercicio', flat=True).distinct()
        ejercicios = sorted(set(ejercicios_qs))
    app_lang = get_language() or 'es-es'
    ctx = {
        'empresa': emp_id,
        'ejercicio': ej_default if ejercicios else None,
        'empresas': empresas,
        'ejercicios': ejercicios,
        'APP_LANG': app_lang,
        'cache_bust': int(time.time())
    }
    return render(request, 'datia/mobile_dashboard.html', ctx)

def mobile_login_view(request):
    if request.method == 'POST':
        user = request.POST.get('username')
        passw = request.POST.get('password')
        user_auth = authenticate(request, username=user, password=passw)
        if user_auth is not None:
            login(request, user_auth)
            next_url = request.POST.get('next') or request.GET.get('next', 'mobile')
            return redirect(next_url)
        else:
            return render(request, 'datia/login.html', {'error': True, 'next': request.POST.get('next', '')})
    return render(request, 'datia/login.html', {'next': request.GET.get('next', '')})

def mobile_health_view(request):
    return HttpResponse("OK-MOBILE", content_type="text/plain")

@login_required(login_url='login')
def download_whitepaper_pdf(request):
    app_name = (load_global_config_safe().implanter_settings or {}).get('app_name') or 'DATIA'
    images = [f"{settings.STATIC_URL}Captura{i}.JPG" for i in range(1, 13)]
    html = render_to_string('datia/whitepaper_pdf.html', {'app_name': app_name, 'images': images})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{app_name}_whitepaper.pdf"'
    def link_callback(uri, rel):
        if uri.startswith(settings.STATIC_URL):
            path = uri[len(settings.STATIC_URL):]
            bases = [os.path.join(settings.BASE_DIR, 'datia', 'static')]
            dirs = getattr(settings, 'STATICFILES_DIRS', [])
            for b in bases + [str(d) for d in dirs]:
                fp = os.path.join(b, path)
                if os.path.exists(fp):
                    return fp
        return uri
    pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    return response

def landing_cliente_view(request):
    SHOWCASE = {
        'Captura1.JPG': {'titulo': 'Asistente IA Conversacional', 'categoria': 'Inteligencia Artificial',
            'desc': 'Olvida los informes estáticos. Con el asistente conversacional de Datia puedes hacer cualquier pregunta sobre tu negocio en lenguaje cotidiano: "¿Cuáles son mis clientes con mayor crecimiento este año?" o "¿Qué producto ha bajado más de margen en el último trimestre?". La IA accede directamente a tus datos reales del ERP y responde en segundos con precisión analítica, sin que tengas que abrir un solo Excel ni esperar a un informe de contabilidad.'},
        'Captura2.JPG': {'titulo': 'Dashboard Financiero Completo', 'categoria': 'Financiera',
            'desc': 'Un resumen ejecutivo de la salud financiera de tu empresa disponible en pantalla en cualquier momento. Visualiza ingresos, gastos y EBITDA mes a mes con comparativas interanuales, seguimiento de liquidez corriente, margen neto, solvencia y nivel de endeudamiento. Todo actualizado automáticamente desde tu ERP sin ningún trabajo manual, y diseñado para que directivos sin perfil financiero entiendan su situación de un vistazo.'},
        'Captura3.JPG': {'titulo': 'Anatomía de la Utilidad', 'categoria': 'Estrategia',
            'desc': 'Comprende exactamente dónde se genera y dónde desaparece el beneficio de tu empresa. Este módulo descompone visualmente el resultado: qué porcentaje del ingreso se destina a coste de ventas, a gastos de estructura, a personal o a impuestos. Permite comparar ejercicios completos de un vistazo y detectar con precisión qué partidas están erosionando la rentabilidad para actuar antes de que el problema sea irreversible.'},
        'Captura4.JPG': {'titulo': 'Evolución Financiera Interactiva', 'categoria': 'Histórico',
            'desc': 'Un gráfico multianual interactivo que muestra la evolución de ventas, gastos y resultado neto desde los primeros registros disponibles hasta hoy. Filtra por ejercicios, amplía rangos concretos con zoom y detecta estacionalidades, cambios de ciclo o el impacto real de decisiones estratégicas pasadas en los números. Ideal para preparar consejos de administración, reuniones con inversores o simplemente para entender la historia financiera de tu empresa.'},
        'Captura5.JPG': {'titulo': 'Predicción Financiera con IA', 'categoria': 'IA Predictiva',
            'desc': 'La IA de Datia proyecta tu tesorería a los próximos meses combinando datos históricos, patrones de pago y escenarios configurables. Puedes ajustar variables como anticipos de clientes, aplazamientos de pagos a proveedores o probabilidad de impago, y ver al instante cómo cambia tu posición de liquidez. El sistema genera un informe ejecutivo de riesgo de tesorería con alertas anticipadas, para que nunca te pillen por sorpresa con una tensión de caja.'},
        'Captura6.JPG': {'titulo': 'Vista Móvil Personalizable', 'categoria': 'Acceso Móvil',
            'desc': 'Tu cuadro de mando en el bolsillo, configurado exactamente a tu medida. Elige desde el escritorio qué paneles quieres ver en móvil —ventas del día, posición de tesorería, estado de compras— arrastra para reordenarlos y guarda tu layout. En el móvil recibirás exactamente esa vista, actualizada en tiempo real, sin tener que navegar por menús: la información clave de tu empresa siempre a golpe de vista desde cualquier lugar.'},
        'Captura7.JPG': {'titulo': 'Análisis IA con Informes Detallados', 'categoria': 'Inteligencia Artificial',
            'desc': 'Pregunta a la IA un análisis completo de tu ejercicio y en menos de un minuto recibes un informe estructurado y profesional: diagnóstico de situación financiera, eficiencia de compras, posición competitiva por cliente, identificación de los top contributors y riesgos detectados, con recomendaciones estratégicas accionables. Un informe que antes requería horas de trabajo de un analista, generado automáticamente con tus datos reales y listo para presentar a dirección o propietarios.'},
        'Captura8.JPG': {'titulo': 'Panel Personal — Tu Cuadro de Mando', 'categoria': 'Dashboard Personal',
            'desc': 'Cada usuario puede construir su propio panel de control personalizado con los KPIs que más le importan en su día a día. Añade bloques de ventas, compras, existencias, financiera o tesorería con un clic, reorganízalos arrastrando y nómbralos como quieras. Tu panel personal queda guardado y sincronizado: siempre encontrarás exactamente lo que necesitas en el lugar donde lo dejaste, sin ruido ni información irrelevante de otros departamentos.'},
        'Captura9.JPG': {'titulo': 'Control de Tesorería en Tiempo Real', 'categoria': 'Tesorería',
            'desc': 'Una visión completa y siempre actualizada de tu posición de caja. Monitoriza el total pendiente de cobro, el volumen de impagados, los días medios de cobro y de pago, la posición con proveedores y los saldos bancarios estimados. Los gráficos comparativos de ingresos vs. gastos proyectados te permiten anticipar con semanas de antelación cualquier tensión de liquidez y tomar decisiones preventivas antes de que se conviertan en un problema real.'},
        'Captura10.JPG': {'titulo': 'Gestión de Presupuestos por Cuenta', 'categoria': 'Presupuestos',
            'desc': 'Define los objetivos económicos del próximo ejercicio cuenta a cuenta, con la precisión de un controller pero sin el trabajo tedioso. Puedes generar el presupuesto desde el año base aplicando un porcentaje de ajuste global o por línea, guardarlo y compararlo mes a mes contra el real con desviaciones coloreadas al instante. Exporta en árbol jerárquico o en grid plano, detecta en qué cuentas se está saliendo del plan y actúa antes de cerrar el trimestre.'},
        'Captura11.JPG': {'titulo': 'Histórico de Consultas IA', 'categoria': 'Historial IA',
            'desc': 'No repitas el mismo trabajo dos veces. Datia guarda automáticamente todas las consultas que realizas al asistente IA, etiquetadas con fecha y contexto. Puedes recuperar cualquier análisis anterior, actualizarlo con los datos más recientes con un solo clic y obtener el informe revisado en segundos. Crea una librería de consultas recurrentes—el resumen de ventas mensual, la evolución de margen por producto, el estado de impagados—y ejecútalas sin tener que reescribir nada.'},
        'Captura12.JPG': {'titulo': 'Informe Ejecutivo de Ventas', 'categoria': 'Informes IA',
            'desc': 'El motor de IA sintetiza automáticamente los datos de ventas del periodo seleccionado en un informe ejecutivo completo y listo para presentar: resumen de situación con métricas clave (ventas totales, margen, número de operaciones), hallazgos relevantes del periodo, evolución del ticket medio mes a mes, ranking de clientes y proveedores por volumen, e identificación de tendencias críticas. En un minuto tienes el documento que antes requería media jornada de preparación.'},
    }

    base_dir = settings.BASE_DIR
    images_dir = os.path.join(base_dir, 'datia_pro')
    screens = []
    try:
        if os.path.exists(images_dir):
            for name in sorted(os.listdir(images_dir), key=lambda n: int(re.search(r'\d+', n).group()) if re.search(r'\d+', n) else 99):
                if re.match(r'^Captura[0-9]+\.JPG$', name, re.IGNORECASE):
                    meta = SHOWCASE.get(name, {'titulo': name, 'categoria': '', 'desc': ''})
                    screens.append({'name': name, **meta})
    except Exception:
        screens = []
    ctx = {
        'screens': screens,
        'cache_bust': int(time.time()),
    }
    return render(request, 'datia/landing_cliente.html', ctx)

def landing_cliente_img(request, name: str):
    if not re.match(r'^Captura[0-9]+\.JPG$', name, re.IGNORECASE):
        raise Http404("Imagen no permitida")
    fp = os.path.join(settings.BASE_DIR, 'datia_pro', name)
    if not os.path.exists(fp):
        raise Http404("Imagen no encontrada")
    return FileResponse(open(fp, 'rb'), content_type='image/jpeg')
