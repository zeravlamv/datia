
from django.core.management.base import BaseCommand
from django.conf import settings
import os
import json
import time
from datia.services.dashboard_service import DashboardService
from datia.services.ollama_service import OllamaService
from datia.factories import ServiceFactory

class Command(BaseCommand):
    help = 'Test AI Pipeline Connectivity'

    def handle(self, *args, **options):
        self.stdout.write("=== DATIA AI DIAGNOSTIC TOOL (Manage.py) ===")
        
        # 1. Directories
        ai_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        self.stdout.write(f"[1] AI Context Dir: {ai_dir}")
        
        # 2. Find Context
        files = [f for f in os.listdir(ai_dir) if f.startswith('datia_ai_context_') and f.endswith('.json')]
        if not files:
            self.stdout.write(self.style.ERROR("[ERROR] No context files found! Run ETL first."))
            return
            
        target_file = files[0]
        full_path = os.path.join(ai_dir, target_file)
        self.stdout.write(f"[2] Using Context: {target_file}")
        
        # 3. Read
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            kpis = data.get('kpis_globales') or data.get('kpis') or {}
            self.stdout.write(f"[3] JSON Loaded. KPIs keys: {list(kpis.keys())}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] JSON Corrupt: {e}"))
            return

        # 4. Ollama
        svc = OllamaService()
        self.stdout.write("[4] Testing Ollama Connection...")
        try:
            models = svc.list_models()
            self.stdout.write(f"    Models: {models}")
            if not models:
                self.stdout.write(self.style.WARNING("[WARN] No models found (Ollama running but empty?)"))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Ollama Offline: {e}"))
            return

        # 5. Embeddings Self-Test
        self.stdout.write("[5] Testing SentenceTransformers Embeddings...")
        try:
            emb = ServiceFactory.get_embedding_service()
            vec = emb.embed_text("diagnóstico CFO liquidez solvencia EBITDA margen riesgo")
            import math
            norm = math.sqrt(sum([float(x)*float(x) for x in vec]))
            self.stdout.write(f"    Vector dim: {len(vec)} | Norm: {norm:.4f}")
            if norm <= 0.0:
                self.stdout.write(self.style.WARNING("[WARN] Embedding norm is zero. Provider fallback may be active."))
            else:
                self.stdout.write(self.style.SUCCESS("[SUCCESS] Embeddings operational."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Embeddings Failed: {e}"))
            # Continue to generation probe even if embeddings fail

        # 6. Generation
        prompt = f"TEST PROMPT: Analyze this data: {str(kpis)[:100]}..."
        self.stdout.write("[6] Sending Probe Request (Timeout 20s)...")
        
        start = time.time()
        try:
            res = svc.generate_text(prompt, timeout=20, model=models[0] if models else "mistral")
            elapsed = time.time() - start
            
            if res:
                self.stdout.write(self.style.SUCCESS(f"[SUCCESS] AI Responded in {elapsed:.2f}s"))
                self.stdout.write(f"    Output Preview: {res[:100]}...")
            else:
                self.stdout.write(self.style.ERROR("[ERROR] AI Returned Empty String"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[ERROR] Generation Failed: {e}"))
