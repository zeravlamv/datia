from ninja import Router, File, UploadedFile, Schema
from django.core.management import call_command
from django.http import HttpResponse
from django.conf import settings
import os
import io

router = Router()

class ExportSchema(Schema):
    pack_name: str

@router.post("/export")
def export_template(request, payload: ExportSchema):
    """
    Exports a SaaS Pack to a JSON file and returns it for download.
    """
    pack_name = payload.pack_name
    
    # We want to capture the output file content directly or redirect to a file path
    # For simplicity, we stick to the file system flow used in the command
    base_dir = "datia/fixtures/packs"
    output_path = f"{base_dir}/{pack_name}.json"
    
    try:
        call_command('export_template', pack=pack_name, output=output_path)
        
        if os.path.exists(output_path):
            with open(output_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/json')
                response['Content-Disposition'] = f'attachment; filename="{pack_name}.json"'
                return response
        else:
            return router.create_response(request, {"error": "File generation failed"}, status=500)
            
    except Exception as e:
        return router.create_response(request, {"error": str(e)}, status=500)

@router.post("/import")
def import_template(request, file: UploadedFile = File(...), wipe: str = "false"):
    """
    Imports a SaaS Pack from an uploaded JSON file.
    wipe: "true" to clear existing config before import.
    """
    try:
        # Save uploaded file temporarily
        temp_path = f"datia/fixtures/packs/temp_import.json"
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        with open(temp_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        # Determine if we should wipe
        should_wipe = wipe.lower() == 'true'
        
        # Run command
        call_command('import_template', file=temp_path, wipe=should_wipe)
        
        return {"status": "ok", "message": "Pack imported successfully"}
        
    except Exception as e:
        return router.create_response(request, {"error": str(e)}, status=500)
