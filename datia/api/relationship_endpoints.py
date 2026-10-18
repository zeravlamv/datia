import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datia.api.guards import login_required_json
from django.views.decorators.http import require_http_methods
from datia.models import DataSource, DataField, DataRelation

@csrf_exempt
@login_required_json
@require_http_methods(["GET", "POST"])
def relationships_api(request):
    """
    API for listing and creating Data Relations (Foreign Keys).
    GET: List all relationships for the current company context.
    POST: Create a new relationship.
    """
    if request.method == "GET":
        raw_company = request.GET.get('empresa', '')
        try:
            int(str(raw_company).strip())
        except Exception:
            return JsonResponse({"status": "error", "message": "empresa debe ser numérica"}, status=400)
        table_id = request.GET.get('table_id')

        # [NEW] Helper to get fields for dropdowns
        if table_id:
            try:
                fields = DataField.objects.filter(source_id=table_id).values('id', 'field_name', 'business_name', 'data_type')
                field_list = []
                for f in fields:
                    name = f['business_name'] if f['business_name'] else f['field_name']
                    field_list.append({
                        "id": f['id'],
                        "name": name,
                        "type": f['data_type']
                    })
                return JsonResponse({"status": "ok", "fields": field_list})
            except Exception as e:
                return JsonResponse({"status": "error", "message": str(e)}, status=500)
        
        # Filter relations where source belongs to company (or all if simplistic)
        # Assuming DataSources are filtered by company implicitly in typical usage, 
        # but relations link two sources. Ideally we filter by source__empresa_id.
        relations = DataRelation.objects.select_related(
            'source', 'from_field', 'target', 'to_field'
        )

        data = []
        for r in relations:
            data.append({
                "id": r.id,
                # Names for Display
                "source_table": r.source.name,
                "source_field": r.from_field.field_name,
                "target_table": r.target.name,
                "target_field": r.to_field.field_name,
                "cardinality_label": r.get_cardinality_display(),
                # IDs for Editing
                "source_id": r.source.id,
                "source_field_id": r.from_field.id,
                "target_id": r.target.id,
                "target_field_id": r.to_field.id,
                "cardinality": r.cardinality, # Raw value for select
                # [NEW] Virtual Flags for UI
                "source_is_virtual": r.source.is_virtual,
                "target_is_virtual": r.target.is_virtual
            })
        
        return JsonResponse({"status": "ok", "relations": data})

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
            source_id = body.get('source_id')
            from_field_id = body.get('from_field_id')
            target_id = body.get('target_id')
            to_field_id = body.get('to_field_id')
            cardinality = body.get('cardinality', 'N-1')

            if not all([source_id, from_field_id, target_id, to_field_id]):
                return JsonResponse({"status": "error", "message": "Faltan datos obligatorios"}, status=400)

            # Validate objects exist
            try:
                source = DataSource.objects.get(id=source_id)
                target = DataSource.objects.get(id=target_id)
                from_field = DataField.objects.get(id=from_field_id)
                to_field = DataField.objects.get(id=to_field_id)
            except (DataSource.DoesNotExist, DataField.DoesNotExist) as e:
                return JsonResponse({"status": "error", "message": f"Objeto no encontrado: {str(e)}"}, status=404)

            # Create Relation
            relation, created = DataRelation.objects.get_or_create(
                source=source,
                from_field=from_field,
                target=target,
                to_field=to_field,
                defaults={'cardinality': cardinality}
            )

            if not created:
                relation.cardinality = cardinality
                relation.save()

            return JsonResponse({"status": "ok", "message": "Relación creada correctamente", "id": relation.id})

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
@login_required_json
@require_http_methods(["DELETE"])
def relationship_detail_api(request, relation_id):
    """
    API for deleting a specific relationship.
    """
    try:
        relation = DataRelation.objects.get(id=relation_id)
        relation.delete()
        return JsonResponse({"status": "ok", "message": "Relación eliminada"})
    except DataRelation.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Relación no encontrada"}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
