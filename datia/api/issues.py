import os
import json
from ninja import Router, Schema
from django.conf import settings
from typing import List, Optional

router = Router(auth=None)

class IssueSchema(Schema):
    id: str
    title: str
    description: str = ""
    pattern: str = ""
    solution: str = ""
    status: str = "open"
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None

def get_issues_path():
    path = os.path.join(settings.BASE_DIR, 'datia', 'patterns', 'issues.json')
    # Default content if not exists
    if not os.path.exists(path):
        default_issues = [
            {
                "id": "ISS-001",
                "title": "❌ Endpoint /api/etl/sync NO EXISTE",
                "description": "El frontend llama a POST /api/etl/sync pero este endpoint no está implementado en el backend.",
                "pattern": "Auto entreno.md",
                "solution": "Crear endpoint que sincronice TODOS los ejercicios de UNA empresa."
            },
            {
                "id": "ISS-002",
                "title": "⚠️ sync_mssql_sales() solo sincroniza UN ejercicio",
                "description": "La función actual sincroniza un ejercicio específico. Se necesita una función que sincronice todos los ejercicios de una empresa.",
                "pattern": "Auto entreno.md",
                "solution": "Crear sync_all_years_for_empresa(empresa_id)"
            }
        ]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_issues, f, indent=4, ensure_ascii=False)
    return path

@router.get("/", response=List[IssueSchema])
def list_issues(request):
    path = get_issues_path()
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Sort by resolved_at descending (Newest resolved first)
        # Items with None (Open) will be considered "empty string" -> smaller than date -> Last in reverse sort
        data.sort(key=lambda x: x.get('resolved_at') or "", reverse=True)
        return data

@router.post("/save")
def save_issues(request, data: List[IssueSchema]):
    print(f"DEBUG SAVE ISSUES: Received {len(data)} items")
    path = get_issues_path()
    try:
        issues_list = [item.dict() for item in data]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(issues_list, f, indent=4, ensure_ascii=False)
        return {"status": "success"}
    except Exception as e:
        print(f"ERROR SAVE ISSUES: {e}")
        return {"status": "error", "message": str(e)}
