# -*- coding: utf-8 -*-
import os

with open("datia/static/js/dashboard/actualidad.js", "r", encoding="utf-8") as f:
    js = f.read()

js = js.replace("""function toggleFavoriteActTab(e, tabId) {
    if (e) e.stopPropagation();
    const currentFav = localStorage.getItem('datia-fav-act-tab');""", """function toggleFavoriteActTab(e, tabId) {
    if (e) e.stopPropagation();
    const currentFav = localStorage.getItem('datia-fav-act-tab');""")

with open("datia/static/js/dashboard/actualidad.js", "w", encoding="utf-8") as f:
    f.write(js)
print("done")

