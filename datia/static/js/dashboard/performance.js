// datia/static/js/dashboard/performance.js

console.log("Performance.js Loaded");

let sysMonitorInterval = null;

function initSystemMonitor() {
    // Start polling if settings modal is open and on 'impl' tab
    // For now, we'll just start it when this function is called (e.g. tab switch)
    fetchSystemMetrics();
    
    if (sysMonitorInterval) clearInterval(sysMonitorInterval);
    sysMonitorInterval = setInterval(fetchSystemMetrics, 2000); // 2s polling
}

function stopSystemMonitor() {
    if (sysMonitorInterval) clearInterval(sysMonitorInterval);
}

async function fetchSystemMetrics() {
    const cpuEl = document.getElementById('sys-cpu-val');
    // If element doesn't exist (modal closed/tab hidden), stop polling to save resources
    if (!cpuEl || cpuEl.offsetParent === null) {
        // stopSystemMonitor(); // Actually, don't stop, just skip. We want it running if tab is active.
        // We rely on switchSettingsTab to start/stop.
        return; 
    }

    try {
        const res = await fetch('/api/system/metrics?_=' + new Date().getTime());
        const data = await res.json();
        
        updateSystemUI(data);
    } catch (e) {
        console.error("SysMon Error:", e);
    }
}

function updateSystemUI(data) {
    const { metrics, config, preset } = data;
    
    // 1. Update Metrics
    document.getElementById('sys-cpu-val').innerText = metrics.cpu.percent + '%';
    document.getElementById('sys-ram-val').innerText = metrics.memory.used_gb + ' GB';
    document.getElementById('sys-health-val').innerText = metrics.health_score + '%';
    
    // Colorize Health
    const healthEl = document.getElementById('sys-health-val');
    if (metrics.health_score > 80) healthEl.style.color = '#34d399'; // Green
    else if (metrics.health_score > 50) healthEl.style.color = '#facc15'; // Yellow
    else healthEl.style.color = '#ef4444'; // Red

    // 2. Update Config Display
    document.getElementById('sys-rag-k').innerText = config.rag_k;
    document.getElementById('sys-timeout').innerText = config.timeout;
    
    // 3. Update Buttons State
    document.querySelectorAll('.sys-preset-btn').forEach(btn => {
        btn.style.borderColor = '#3f3f46';
        btn.style.color = '#a1a1aa';
        btn.style.background = 'rgba(255,255,255,0.05)';
    });
    
    const activeBtn = document.getElementById(`btn-preset-${preset}`);
    if (activeBtn) {
        activeBtn.style.borderColor = '#3b82f6';
        activeBtn.style.color = '#60a5fa';
        activeBtn.style.background = 'rgba(59, 130, 246, 0.2)';
    }
    
    document.getElementById('sys-mode-label').innerText = preset.charAt(0).toUpperCase() + preset.slice(1);
}

async function setSystemPreset(preset) {
    try {
        // UI Optimistic Update
        const label = document.getElementById('sys-mode-label');
        if (label) label.innerText = "Guardando...";
        
        // Robust CSRF Token Retrieval
        let token = null;
        if (typeof getCookie === 'function') {
            token = getCookie('csrftoken');
        }
        if (!token && typeof CSRF_TOKEN !== 'undefined') {
            token = CSRF_TOKEN;
        }

        const res = await fetch('/api/system/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            body: JSON.stringify({ preset: preset })
        });
        
        if (res.ok) {
            fetchSystemMetrics(); // Refresh immediately
        } else {
            console.error("Save failed:", res.status, res.statusText);
            fetchSystemMetrics(); // Revert UI
        }
    } catch (e) {
        console.error("Network Error:", e);
        fetchSystemMetrics(); // Revert UI
    }
}

// Hook into Settings Tab Switch
// We need to override or extend the existing switchSettingsTab function.
// Since we can't easily extend, we'll listen for clicks on the button if possible, 
// or just expose initSystemMonitor globally and call it from the existing onclick in HTML?
// HTML calls `switchSettingsTab('impl')`.
// We can overwrite `switchSettingsTab` safely if we call the original one.

const originalSwitchSettingsTab = window.switchSettingsTab;
window.switchSettingsTab = function(tabName) {
    if (originalSwitchSettingsTab) originalSwitchSettingsTab(tabName);
    
    if (tabName === 'dev') {
        initSystemMonitor();
    } else {
        stopSystemMonitor();
    }
};
