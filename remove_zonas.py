
import os

with open("datia/templates/datia/components/tab_actualidad.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's remove the Top Zonas div
import re
# We need to find the exact block for "Top Zonas"
start_str = "<!-- Top Zonas -->"
end_str = "</div> <!-- End Sub Tab: Ventas -->"

start_idx = html.find(start_str)
end_idx = html.find(end_str)

if start_idx != -1 and end_idx != -1:
    # also remove the closing div of the grid-cols-3
    html = html[:start_idx] + html[end_idx-18:end_idx] + html[end_idx:]
    with open("datia/templates/datia/components/tab_actualidad.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Top Zonas removed.")
else:
    print("Could not find boundaries")

