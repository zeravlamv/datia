import os
import json
from ninja import Router, Schema
from django.conf import settings
from typing import List, Optional

router = Router(auth=None)

class FeatureSchema(Schema):
    id: str
    title: str
    description: str = ""
    pattern: str = ""
    execution_mode: str = "refine" # from_scratch, refine
    status: str = "pending" # pending, in_progress, done
    priority: str = "medium" # high, medium, low
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

def get_features_path():
    path = os.path.join(settings.BASE_DIR, 'datia', 'patterns', 'features.json')
    if not os.path.exists(path):
        # Initial empty structure or example
        default_features = []
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_features, f, indent=4, ensure_ascii=False)
    return path

@router.get("/", response=List[FeatureSchema])
def list_features(request):
    path = get_features_path()
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Sort manually if needed, or rely on frontend
        return data

@router.post("/save")
def save_features(request, data: List[FeatureSchema]):
    path = get_features_path()
    try:
        features_list = [item.dict() for item in data]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(features_list, f, indent=4, ensure_ascii=False)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
