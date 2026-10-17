import json
import time
import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.ollama_service import OllamaService

def benchmark():
    DUMP_FILE = 'datia_ai_context_dump.json'
    
    if not os.path.exists(DUMP_FILE):
        print(f"ERROR: {DUMP_FILE} not found. Cannot benchmark without context.")
        return

    print(f"[{datetime.now().time()}] Loading Context from {DUMP_FILE}...")
    with open(DUMP_FILE, 'r', encoding='utf-8') as f:
        context = json.load(f)
    
    context_str = json.dumps(context, ensure_ascii=False, indent=2)
    print(f"Context loaded. Size: {len(context_str)} chars")
    
    models_to_test = ['qwen2.5:7b', 'mistral', 'deepseek-r1:8b', 'llama3.1:8b']
    
    ollama = OllamaService()
    available = [m for m in ollama.list_models()]
    print(f"Available Models: {available}")

    prompt_template = f"""
    Actúa como Controller Financiero. Analiza estos datos:
    {context_str}
    
    Genera un informe HTML breve con: Resumen, Hallazgos, Recomendaciones.
    """

    results = []

    for model in models_to_test:
        # Check if model exists (fuzzy match)
        real_model = next((m for m in available if model in m), None)
        if not real_model:
            print(f"SKIP: {model} not found in Ollama.")
            continue
            
        print(f"\n--- TESTING MODEL: {real_model} ---")
        start = time.time()
        try:
            # Short timeout check
            response = ollama.generate_text(prompt_template, model=real_model, timeout=120)
            duration = time.time() - start
            print(f"SUCCESS. Time: {duration:.2f}s")
            print(f"Output Preview: {response[:100]}...")
            results.append({"model": real_model, "time": duration, "status": "OK"})
        except Exception as e:
            duration = time.time() - start
            print(f"FAILED. Time: {duration:.2f}s. Error: {e}")
            results.append({"model": real_model, "time": duration, "status": "ERROR"})

    print("\n--- SUMMARY ---")
    print(f"{'Model':<20} | {'Time (s)':<10} | {'Status'}")
    print("-" * 45)
    for r in results:
        print(f"{r['model']:<20} | {r['time']:<10.2f} | {r['status']}")

if __name__ == "__main__":
    benchmark()
