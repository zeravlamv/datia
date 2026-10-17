# -*- coding: utf-8 -*-
import os

with open("datia/static/js/dashboard/core.js", "r", encoding="utf-8") as f:
    js = f.read()

# Make sure we don't have automatic fallback to Ventas overriding everything
js = js.replace("""            } else if (typeof switchSubTab === 'function') {
                setTimeout(() => switchSubTab('sub-ventas'), 10);
            }""", """            } else if (typeof switchSubTab === 'function') {
                // setTimeout(() => switchSubTab('sub-ventas'), 10);
            }""")

with open("datia/static/js/dashboard/core.js", "w", encoding="utf-8") as f:
    f.write(js)
print("core.js Ventas fallback removed completely!")

