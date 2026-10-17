import os
from ninja import Router, Schema
from django.conf import settings
from typing import List

router = Router(auth=None)

class PatternFile(Schema):
    name: str
    content: str = ""

@router.get("/", response=List[str])
def list_patterns(request):
    """
    Lists all markdown files in the patterns directory.
    """
    patterns_dir = os.path.join(settings.BASE_DIR, 'datia', 'patterns')
    if not os.path.exists(patterns_dir):
        return []
    
    files = [f for f in os.listdir(patterns_dir) if f.endswith('.md')]
    return files

@router.post("/save")
def save_pattern(request, data: PatternFile):
    """
    Saves/Updates the content of a pattern file.
    """
    patterns_dir = os.path.join(settings.BASE_DIR, 'datia', 'patterns')
    file_path = os.path.join(patterns_dir, data.name)
    
    # Security: Ensure we stay within patterns directory
    if not data.name.endswith('.md') or '..' in data.name:
        return {"status": "error", "message": "Nombre de archivo inválido"}
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(data.content)
        return {"status": "success", "filename": data.name}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/{filename}", response=PatternFile)
def get_pattern(request, filename: str):
    """
    Reads the content of a specific pattern file.
    """
    patterns_dir = os.path.join(settings.BASE_DIR, 'datia', 'patterns')
    file_path = os.path.join(patterns_dir, filename)
    
    if not os.path.exists(file_path):
        return {"name": filename, "content": "Error: Archivo no encontrado"}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {"name": filename, "content": content}
