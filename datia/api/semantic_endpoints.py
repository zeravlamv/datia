from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datia.api.guards import login_required_json
from django.contrib.auth.decorators import login_required
import json
from datia.models.semantic import BusinessContext, DataSource, DataField
from datia.services.ollama_service import OllamaService
from datia.models.semantic import StandardField
from django.http import JsonResponse
def _normalize_empresa_id(e):
    try:
        return int(str(e).strip())
    except Exception:
        return None

@csrf_exempt
@login_required_json
def generate_metadata_api(request):
    """
    POST /api/semantic/generate-metadata
    Body: { "table_name": "...", "fields": [{"name": "..."}] }
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        table_name = data.get('table_name')
        fields = data.get('fields', [])
        
        table_context = data.get('table_context', '')
        
        if not table_name or not fields:
             return JsonResponse({'status': 'error', 'message': 'Missing table or fields'}, status=400)

        model = data.get('model')
        
        # Fetch Business Context
        # Try generic fetch for this company
        empresa_id = _normalize_empresa_id(data.get('empresa_id') or (request.GET.get('empresa') or ''))
        if empresa_id is None:
            return JsonResponse({'status': 'error', 'message': 'empresa_id requerido'}, status=400)
        cx_obj = BusinessContext.objects.filter(empresa_id=empresa_id, key='descripcion_negocio').first()
        business_context = cx_obj.content if cx_obj else ""

        # Call Ollama
        if model:
            service = OllamaService(model=model)
        else:
            service = OllamaService()

        if not service.check_connection():
             return JsonResponse({'status': 'error', 'message': 'Ollama not connected on port 11434'}, status=503)
             
        descriptions = service.generate_field_descriptions(table_name, fields, table_context, business_context)
        
        return JsonResponse({'status': 'ok', 'descriptions': descriptions})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def business_context_api(request, empresa):
    """
    API for retrieving and updating Business Context.
    Path: /api/semantic/context/<empresa>
    """
    if request.method == 'GET':
        norm_id = _normalize_empresa_id(empresa)
        if norm_id is None:
            return JsonResponse({'status': 'error', 'message': 'empresa debe ser numérica'}, status=400)
        contexts = BusinessContext.objects.filter(empresa_id=norm_id)

        data = {c.key: c.content for c in contexts}
        return JsonResponse({'status': 'ok', 'context': data})

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            key = body.get('key')
            content = body.get('content', '')
            if not key:
                import os
                from django.conf import settings
                if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                    print("DEBUG: Missing key")
                return JsonResponse({'status': 'error', 'message': 'Missing key'}, status=400)

            # Escritura estricta: siempre bajo ID numérico normalizado
            target_empresa = _normalize_empresa_id(empresa)
            if target_empresa is None:
                return JsonResponse({'status': 'error', 'message': 'empresa debe ser numérica'}, status=400)
                
            obj, created = BusinessContext.objects.update_or_create(
                empresa_id=target_empresa,
                key=key,
                defaults={'content': content or ''}
            )
            print(f"DEBUG: Saved successfully to '{target_empresa}' (Created: {created})")
            
            return JsonResponse({
                'status': 'saved', 
                'key': obj.key, 
                'created': created,
                'target_id': target_empresa
            })
        except Exception as e:
            print(f"ERROR SAVING CONTEXT: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@csrf_exempt
@login_required_json
def standard_fields_list_api(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        q = (request.GET.get('q') or '').strip()
        role = (request.GET.get('role') or '').strip().upper()
        limit = int(request.GET.get('limit') or 200)
        qs = StandardField.objects.all()
        if q:
            qs = qs.filter(name__icontains=q)
        if role:
            qs = qs.filter(semantic_role=role)
        qs = qs.order_by('name')[:limit]
        items = [{
            'id': sf.id,
            'name': sf.name,
            'business_name': sf.business_name,
            'description': sf.description,
            'semantic_role': sf.semantic_role,
            'is_key': sf.is_key,
            'fix_type': sf.fix_type
        } for sf in qs]
        return JsonResponse({'status': 'ok', 'items': items})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def standard_fields_save_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        import json
        body = json.loads(request.body or '{}')
        name = (body.get('name') or '').strip()
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Missing name'}, status=400)
        force = bool(body.get('force') or False)
        sf = StandardField.objects.filter(name=name).first()
        if sf:
            if sf.fix_type and not force:
                # Solo actualizar descripción
                sf.description = body.get('description') or sf.description
                sf.save(update_fields=['description'])
                return JsonResponse({'status': 'ok', 'partial': True})
            # Actualización completa
            sf.business_name = body.get('business_name') or sf.business_name or name
            sf.description = body.get('description') or sf.description
            sf.semantic_role = body.get('semantic_role') or sf.semantic_role or 'DIMENSION'
            sf.is_key = bool(body.get('is_key')) if body.get('is_key') is not None else sf.is_key
            sf.save()
            return JsonResponse({'status': 'ok'})
        else:
            StandardField.objects.create(
                name=name,
                business_name=body.get('business_name') or name,
                description=body.get('description') or '',
                semantic_role=(body.get('semantic_role') or 'DIMENSION'),
                is_key=bool(body.get('is_key') or False),
                fix_type=True
            )
            return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def standard_fields_delete_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        import json
        body = json.loads(request.body or '{}')
        name = (body.get('name') or '').strip()
        force = bool(body.get('force') or False)
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Missing name'}, status=400)
        sf = StandardField.objects.filter(name=name).first()
        if not sf:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
        if sf.fix_type and not force:
            return JsonResponse({'status': 'error', 'message': 'System field requires force=true to delete'}, status=400)
        sf.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
