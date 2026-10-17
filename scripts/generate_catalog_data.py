import ast
import os
import glob
import re

BASE_DIR = r"c:/Users/miguel vergara/Desktop/datia"
DATIA_DIR = os.path.join(BASE_DIR, "datia")

def get_ast(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return ast.parse(f.read())

def docstring_to_html(docstring):
    if not docstring:
        return "Sin descripción."
    return docstring.strip().replace("\n", "<br>")

def parse_endpoints():
    api_dir = os.path.join(DATIA_DIR, "api")
    endpoints_html = ""
    
    for file in glob.glob(os.path.join(api_dir, "*.py")):
        if "__init__" in file: continue
        
        try:
            tree = get_ast(file)
        except:
            continue
            
        filename = os.path.basename(file)
        # Group by file
        endpoints_html += f"<h3 style='margin-top: 2rem; color: var(--accent);'>{filename}</h3>"
        
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                # Check decorators for router.get, router.post, etc.
                method = None
                path = ""
                
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if hasattr(decorator.func, 'attr') and decorator.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                            method = decorator.func.attr.upper()
                            if decorator.args:
                                if isinstance(decorator.args[0], ast.Constant):
                                    path = decorator.args[0].value
                                elif isinstance(decorator.args[0], ast.Str): # Python < 3.8
                                    path = decorator.args[0].s
                
                if method:
                    doc = ast.get_docstring(node)
                    endpoints_html += f"""
                    <div class="endpoint-card">
                        <div class="endpoint-header">
                            <span class="method-badge method-{method.lower()}">{method}</span>
                            <span class="endpoint-path">{path}</span>
                        </div>
                        <p class="endpoint-desc"><strong>{node.name}</strong>: {docstring_to_html(doc)}</p>
                    </div>
                    """
    return endpoints_html

def parse_services():
    services_dir = os.path.join(DATIA_DIR, "services")
    services_html = ""
    
    for file in glob.glob(os.path.join(services_dir, "*.py")):
        if "__init__" in file: continue
        
        try:
            tree = get_ast(file)
        except:
            continue

        filename = os.path.basename(file)
        
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or "Sin descripción"
                services_html += f"""
                <div class="service-card">
                    <h3 style="color: var(--accent); margin-bottom: 0.5rem;">{node.name}</h3>
                    <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">{filename}</div>
                    <p>{docstring_to_html(doc)}</p>
                    <div style="margin-top: 1rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05);">
                        <strong>Métodos:</strong>
                        <ul style="color: var(--text-muted); font-size: 0.9rem; margin-top: 0.5rem;">
                """
                
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
                for method in methods[:5]: # Limit to 5
                     services_html += f"<li>{method}</li>"
                if len(methods) > 5:
                    services_html += f"<li>... y {len(methods)-5} más</li>"
                
                services_html += "</ul></div></div>"
    return services_html

def parse_models():
    models_dir = os.path.join(DATIA_DIR, "models")
    models_html = ""
    
    for file in glob.glob(os.path.join(models_dir, "*.py")):
        if "__init__" in file: continue
        
        try:
            tree = get_ast(file)
        except:
            continue

        filename = os.path.basename(file)
        
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                # Check if it inherits from models.Model (simple heuristic)
                is_model = any(
                    (isinstance(base, ast.Attribute) and base.attr == 'Model') or
                    (isinstance(base, ast.Name) and base.id == 'Model') 
                    for base in node.bases
                )
                
                if is_model:
                    doc = ast.get_docstring(node) or "Sin descripción"
                    models_html += f"""
                    <div class="model-card">
                        <h3 style="color: #22c55e; margin-bottom: 0.5rem;">{node.name}</h3>
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem;">{filename}</div>
                        <p>{docstring_to_html(doc)}</p>
                    </div>
                    """
    return models_html
    return models_html


def parse_patterns():
    patterns_dir = os.path.join(DATIA_DIR, "patterns")
    patterns_html = ""
    
    pattern_files = sorted(glob.glob(os.path.join(patterns_dir, "*.md")))
    
    for file in pattern_files:
        filename = os.path.basename(file)
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            # Try to find first header
            title = filename
            header_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if header_match:
                title = header_match.group(1)
            
            patterns_html += f"""
            <div class="pattern-item" onclick="loadPattern('{filename}')">
                <div style="font-weight: 600; color: var(--text);">{title}</div>
                <div style="font-size: 0.8rem; opacity: 0.7;">{filename}</div>
            </div>
            """
    return patterns_html

import json

if __name__ == "__main__":
    print("GENERATING HTML CONTENT...", flush=True)
    try:
        api_data = parse_endpoints()
        print(f"API parsed ({len(api_data)} chars)", flush=True)
        
        services_data = parse_services()
        print(f"Services parsed ({len(services_data)} chars)", flush=True)
        
        models_data = parse_models()
        print(f"Models parsed ({len(models_data)} chars)", flush=True)
        
        patterns_data = parse_patterns()
        print(f"Patterns parsed ({len(patterns_data)} chars)", flush=True)

        data = {
            "api": api_data,
            "services": services_data,
            "models": models_data,
            "patterns": patterns_data
        }
        
        with open("temp_catalog_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        print("Data written to temp_catalog_data.json", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
