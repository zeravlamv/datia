import json
import os
import re

BASE_DIR = r"c:/Users/miguel vergara/Desktop/datia"
CATALOG_PATH = os.path.join(BASE_DIR, "datia/templates/datia/catalog.html")
DATA_PATH = os.path.join(BASE_DIR, "temp_catalog_data.json")

def update_catalog():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        html = f.read()
        
    # Helper to replace section content
    def replace_section(html_content, section_id, new_inner_content):
        # Regex to find <div id="section_id" class="section"> ... </div>
        # We assume the div ends with </div> on a new line or similar indentation
        # But nested divs make regex hard.
        # However, looking at the file, the indentations are clean.
        # <div id="api" class="section"> ... </div> (line 887)
        
        start_marker = f'<div id="{section_id}" class="section">'
        start_idx = html_content.find(start_marker)
        if start_idx == -1:
            print(f"Warning: Section {section_id} not found")
            return html_content
            
        # Find the header title to preserve it?
        # The generated data (new_inner_content) DOES NOT have the <h2> header.
        # The existing file DOES have it.
        # Let's extract the header from existing if possible, or just hardcode standard headers.
        
        # Simple approach: Find the start index, find the next </div> corresponding to this one.
        # Since it's indented, maybe we can assume the closing </div> is at the same indentation level?
        # <div id="api" ...> is at col 4.
        # </div> is at col 4.
        
        # Let's try to find the "next" </div> that is at the start of a line (with padding).
        # Actually, simpler: Split by lines.
        
        lines = html_content.splitlines()
        new_lines = []
        in_target_section = False
        section_indent = ""
        
        # Buffer for new content
        header_map = {
            "api": "<h2>🔌 API Endpoints Exhaustivo (Auto-Generated)</h2>",
            "services": "<h2>🏗️ Backend Services Deep-Dive (Auto-Generated)</h2>",
            "models": "<h2>🗄️ Modelos de Datos (Arquitectura Analytics) (Auto-Generated)</h2>"
        }
        
        # We will iterate and rebuilt.
        i = 0
        while i < len(lines):
            line = lines[i]
            if start_marker in line:
                # Found start
                new_lines.append(line)
                
                # Check indentation
                indent = line[:line.find('<')]
                
                # Inject new content
                header = header_map.get(section_id, "<h2>Section</h2>")
                new_lines.append(indent + "    " + header)
                new_lines.append(new_inner_content) # This might skip indentation of inner content, but HTML is forgiving.
                
                # Skip existing lines until closing div
                # We assume the closing div is `    </div>` (same indent as start)
                # But we have nested divs.
                # We need to count divs? Or just look for the known closing line for that section?
                # In catalog.html, the sections are top-level within .catalog-content
                
                # Let's count balance of <div>
                balance = 1
                i += 1
                while i < len(lines) and balance > 0:
                    l = lines[i]
                    # Count <div and </div
                    # Simple count
                    balance += l.count("<div") - l.count("</div>")
                    if balance == 0:
                        # This line is the closing div
                        new_lines.append(l)
                    i += 1
                # i is now after the closing line (or at it if not incremented in last loop)
                # wait, if balance == 0, we appended l and i+=1. Correct.
                continue
            else:
                new_lines.append(line)
                i += 1
                
        return "\n".join(new_lines)

    # Update API
    html = replace_section(html, "api", data['api'])
    # Update Services
    html = replace_section(html, "services", data['services'])
    # Update Models
    html = replace_section(html, "models", data['models'])
    # Update Patterns ?
    # html = replace_section(html, "patterns", data['patterns']) 
    # Skip patterns as decided.
    
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("Catalog HTML updated successfully.")

if __name__ == "__main__":
    update_catalog()
