
import re

with open("datia/templates/datia/components/tab_actualidad_financiera.html", "r", encoding="utf-8") as f:
    html = f.read()

def extract_section(html, section_id):
    pattern = r"(<!-- SECTION:.*?-->\s*<div id=\"" + section_id + r"\" class=\"fin-grid-item\" draggable=\"true\" data-id=\"[^\"]+\">.*?</div>\n            </div>)"
    match = re.search(pattern, html, re.DOTALL)
    if match:
        return match.group(1), html.replace(match.group(1), "")
    
    # Try simpler pattern without comment
    pattern2 = r"(<div id=\"" + section_id + r"\" class=\"fin-grid-item\" draggable=\"true\" data-id=\"[^\"]+\">.*?</div>\n            </div>)"
    match2 = re.search(pattern2, html, re.DOTALL)
    if match2:
        return match2.group(1), html.replace(match2.group(1), "")
    return None, html

sections_to_balances = ["fin-section-detail", "fin-section-balance", "fin-section-pl-report"]
balances_html = "{% load static i18n %}\n<div id=\"tab-actualidad-balances\" class=\"financial-theme\">\n    <div class=\"dashboard-v2-container\">\n        <div id=\"fin-balances-grid\" class=\"fin-grid-container\">\n"

for sec in sections_to_balances:
    content, html = extract_section(html, sec)
    if content:
        balances_html += "\n" + content + "\n"
    else:
        print("Could not find", sec)

balances_html += "        </div>\n    </div>\n</div>"

with open("datia/templates/datia/components/tab_actualidad_balances.html", "w", encoding="utf-8") as f:
    f.write(balances_html)

sections_to_informes = ["fin-section-quarterly"]
informes_html = "{% load static i18n %}\n<div id=\"tab-actualidad-informes\" class=\"financial-theme\">\n    <div class=\"dashboard-v2-container\">\n        <div id=\"fin-informes-grid\" class=\"fin-grid-container\">\n"

for sec in sections_to_informes:
    content, html = extract_section(html, sec)
    if content:
        informes_html += "\n" + content + "\n"
    else:
        print("Could not find", sec)

informes_html += "        </div>\n    </div>\n</div>"

with open("datia/templates/datia/components/tab_actualidad_informes.html", "w", encoding="utf-8") as f:
    f.write(informes_html)

with open("datia/templates/datia/components/tab_actualidad_financiera.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Done extracting.")

