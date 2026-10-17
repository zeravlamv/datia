# -*- coding: utf-8 -*-
import os

with open("datia/static/js/dashboard/core.js", "r", encoding="utf-8") as f:
    js = f.read()

# Remove the monkey patch
patch_code = """// Parchear switchSubTab para emitir evento
const originalSwitchSubTab = window.switchSubTab;
if (typeof originalSwitchSubTab === 'function' && !window._switchSubTabPatched) {
    window.switchSubTab = function(tabId) {
        originalSwitchSubTab(tabId);
        document.dispatchEvent(new CustomEvent('subTabChanged', { detail: tabId }));
    };
    window._switchSubTabPatched = true;
}"""

js = js.replace(patch_code, "")

with open("datia/static/js/dashboard/core.js", "w", encoding="utf-8") as f:
    f.write(js)
print("Removed monkey patch!")

