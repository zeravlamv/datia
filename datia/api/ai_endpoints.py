from ninja import Router, Schema
from datia.factories import ServiceFactory
import logging
import re
from datia.services.ai.dsl_query import DSLQueryExecutor

logger = logging.getLogger(__name__)

router = Router()

@router.get("/report/progress/{req_id}")
def get_report_progress(request, req_id: str):
    """
    Returns backend progress events for a given AI report request.
    If completed, includes the 'result' payload.
    """
    try:
        from datia.services.dashboard_service import AI_PROGRESS
        events = AI_PROGRESS.get(req_id, [])
        
        # Check completion
        final_result = None
        for ev in reversed(events):
            if ev.get("status") == "completed" and "result" in ev:
                final_result = ev["result"]
                break
        
        return {
            "status": "ok", 
            "request_id": req_id, 
            "events": events,
            "result": final_result # Frontend looks for this to stop polling
        }
    except Exception as e:
        logger.error(f"Progress Endpoint Error: {e}")
        return {"status": "error", "message": str(e), "events": []}

class ReportRequest(Schema):
    empresa: int
    ejercicio: int
    kind: str = 'ventas' # ventas, compras, financiera...
    model: str = None
    role: str = None

@router.post("/report/generate")
def generate_report(request, payload: ReportRequest):
    """
    Generates an AI Strategic Report on demand (Async).
    Returns {"status": "pending", "request_id": "..."} immediately.
    """
    logger.info(f"Received AI Report Request for Empresa {payload.empresa} ({payload.kind})")
    svc = ServiceFactory.get_dashboard_service()
    try:
        # returns pending status immediately
        return svc.generate_strategic_report(
            empresa=payload.empresa,
            ejercicio=payload.ejercicio,
            kind=payload.kind,
            model=payload.model,
            role=payload.role
        )
    except Exception as e:
        logger.error(f"Endpoint Error: {e}")
        return {"status": "error", "message": str(e)}

class ContextRequest(Schema):
    empresa: int
    ejercicio: int
    kind: str = 'ventas'

class BuildRequest(Schema):
    empresa: int
    ejercicio: int
    kind: str = 'ventas'

@router.post("/context/generate")
def generate_context(request, payload: ContextRequest):
    try:
        svc = ServiceFactory.get_dashboard_service()
        result = svc.generate_context(
            empresa=payload.empresa,
            ejercicio=payload.ejercicio,
            kind=payload.kind
        )
        return result
    except Exception as e:
        logger.error(f"Generate Context Error: {e}")
        return {"status": "error", "message": str(e)}

class QueryExecuteRequest(Schema):
    empresa: int
    ejercicio: int
    query_text: str

@router.post("/query/execute")
def execute_query(request, payload: QueryExecuteRequest):
    """
    Ejecuta una consulta IA sin convertir a SQL.
    Genera un DSL seguro, lo compila a ORM y persiste el resultado en JSON.
    """
    try:
        dsl = DSLQueryExecutor.generate_dsl_from_text(payload.query_text, payload.empresa, payload.ejercicio)
        result = DSLQueryExecutor.compile_and_execute(dsl, payload.empresa, payload.ejercicio)
        info = DSLQueryExecutor.persist_result(payload.empresa, payload.ejercicio, payload.query_text, dsl, result)
        return {"status": "success", "id": info["id"], "path": info["path"], "count": info["count"], "dsl": dsl}
    except Exception as e:
        logger.error(f"Query Execute Error: {e}")
        return {"status": "error", "message": str(e)}

class ComputeExecuteRequest(Schema):
    empresa: int
    ejercicio: int
    query_text: str

@router.post("/compute/execute")
def execute_compute(request, payload: ComputeExecuteRequest):
    try:
        from datia.services.ai.handlers.compute_handler import PythonComputeHandler
        h = PythonComputeHandler()
        res = h.handle({'query': payload.query_text}, {'empresa': payload.empresa, 'ejercicio': payload.ejercicio, 'lang': 'es'})
        return {"status": "success", "result": res}
    except Exception as e:
        logger.error(f"Compute Execute Error: {e}")
        return {"status": "error", "message": str(e)}

@router.post("/context/build")
def build_context(request, payload: BuildRequest):
    try:
        svc = ServiceFactory.get_dashboard_service()
        result = svc.build_context(
            empresa=payload.empresa,
            ejercicio=payload.ejercicio,
            kind=payload.kind
        )
        return result
    except Exception as e:
        logger.error(f"Build Context Error: {e}")
        return {"status": "error", "message": str(e)}

class ReportSaveRequest(Schema):
    empresa: int
    ejercicio: int
    kind: str = 'ventas'
    origin: str
    html: str
    model_used: str = None
    raw_data: dict = None

@router.post("/report/save")
def save_report(request, payload: ReportSaveRequest):
    # Deprecated endpoint if we autosave, but kept for manual overrides or re-saves
    try:
        from datia.models import MetricsSavedQuery
        last_answer = {
            "type": "ai_report",
            "html": payload.html,
            "origin": payload.origin,
            "kind": payload.kind,
            "empresa": payload.empresa,
            "ejercicio": payload.ejercicio,
            "model_used": payload.model_used,
            "raw_data": payload.raw_data or {}
        }
        item = MetricsSavedQuery.objects.create(
            empresa=payload.empresa,
            ejercicio=payload.ejercicio,
            query=f"AI_REPORT:{payload.kind}:{payload.origin}",
            last_answer=last_answer
        )
        return {"status": "saved", "id": item.id}
    except Exception as e:
        logger.error(f"Save Report Error: {e}")
        return {"status": "error", "message": str(e)}

class ReportExportRequest(Schema):
    html: str
    title: str = "Informe Estratégico"
    empresa: int
    ejercicio: int
    raw_data: dict = None

class NotebookLMPodcastRequest(Schema):
    empresa: int
    ejercicio: int
    html: str = ""
    raw_data: dict = {}

@router.post("/report/export/pdf")
def export_report_pdf(request, payload: ReportExportRequest):
    """
    Generates a PDF file from the report HTML content.
    """
    from datia.services.pdf_service import PDFService
    from django.http import HttpResponse, JsonResponse

    try:
        if not (payload and payload.html and str(payload.html).strip()):
            return JsonResponse({"status": "error", "message": "HTML vacío para exportación"}, status=400)

        username = "anon"
        try:
            u = getattr(request, "user", None)
            if u and getattr(u, "is_authenticated", False) and getattr(u, "username", None):
                username = str(u.username)
        except Exception:
            username = "anon"
        username = re.sub(r"[^A-Za-z0-9_-]+", "_", username).strip("_") or "anon"

        pdf_bytes = PDFService.generate_pdf_from_html(
            html_content=payload.html,
            title=payload.title,
            empresa_id=payload.empresa,
            ejercicio=payload.ejercicio,
            raw_data=payload.raw_data or {}
        )
        
        if not pdf_bytes:
            return JsonResponse({"status": "error", "message": "PDF Generation failed"}, status=500)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"Informe_Financiero_{payload.empresa}_{payload.ejercicio}_{username}_{ts}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"PDF Export Error: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@router.post("/notebooklm/podcast")
def generate_notebooklm_podcast(request, payload: NotebookLMPodcastRequest):
    """
    Toma los datos/HTML del informe actual y los envía a NotebookLM vía MCP para generar un Audio Overview.
    """
    from datia.services.ai.notebooklm_service import NotebookLMService
    from django.http import JsonResponse
    try:
        res = NotebookLMService.create_podcast_from_payload(
            empresa=payload.empresa,
            ejercicio=payload.ejercicio,
            payload=payload.raw_data or {"html": payload.html}
        )
        
        if not res.get("success"):
            return JsonResponse({"success": False, "error": res.get("error")}, status=500)
            
        return JsonResponse(res)
    except Exception as e:
        logger.error(f"Error llamando a NotebookLM MCP: {str(e)}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)}, status=500)
