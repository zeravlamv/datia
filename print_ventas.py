# -*- coding: utf-8 -*-
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

with open("datia/templates/datia/components/tab_actualidad.html", "r", encoding="utf-8") as f:
    html = f.read()

print(html[77000:81000])

