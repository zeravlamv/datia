// datia/static/js/tab_auto_dashboard.js

function getCssVar(name, fallback) {
    try {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name);
        return v && v.trim() ? v.trim() : fallback;
    } catch (_) {
        return fallback;
    }
}

// Global state for dashboard
const dashboardState = {
    isLoading: false,
    lastUpdate: null
};

// Colors for charts
const DASH_COLORS = {
    primary: '#a855f7', // Purple
    secondary: '#3b82f6', // Blue
    success: '#10b981', // Green
    warning: '#f59e0b', // Amber
    background: '#18181b',
    text: getCssVar('--text-muted', '#a1a1aa')
};

async function loadDashboardStats() {
    if (dashboardState.isLoading) return;

    const container = document.getElementById('subtab-dashboard');
    if (!container || container.style.display === 'none') {
        // Only load if visible or first load? 
        // We'll let the caller decide, but usually we load on tab switch
    }

    try {
        dashboardState.isLoading = true;
        updateDashboardLoading(true);

        const response = await fetch('/api/auto-training/dashboard/stats');
        if (!response.ok) throw new Error('Error loading stats');

        const data = await response.json();

        try { renderKpis(data); } catch (e) { console.error("Render KPIs failed", e); }
        try { renderTablesList(data.tables); } catch (e) { console.error("Render Tables failed", e); }
        try { renderActivityChart(data.training_evolution); } catch (e) { console.error("Render Chart failed", e); }
        try { renderRecentActivity(data.recent_activity); } catch (e) { console.error("Render Recent Activity failed", e); }

        // [FIX] Pass the detailed list instead of counts
        try { renderNetworkGraph(data.relations_list || []); } catch (e) { console.error("Render Network failed", e); }

        dashboardState.lastUpdate = new Date();
        updateLastRefreshedLabel();

    } catch (error) {
        console.error('Dashboard Error:', error);
        showToast('Error al cargar datos del dashboard', 'error');
    } finally {
        dashboardState.isLoading = false;
        updateDashboardLoading(false);
    }
}

function updateDashboardLoading(loading) {
    const btn = document.getElementById('btn-refresh-dashboard');
    if (btn) {
        if (loading) {
            btn.innerHTML = '⏳ Cargando...';
            btn.disabled = true;
        } else {
            btn.innerHTML = '🔄 Actualizar';
            btn.disabled = false;
        }
    }
}

function updateLastRefreshedLabel() {
    const el = document.getElementById('dashboard-last-updated');
    if (el && dashboardState.lastUpdate) {
        el.innerText = `Actualizado: ${dashboardState.lastUpdate.toLocaleTimeString()}`;
    }
}

function renderKpis(data) {
    // Helper to animate numbers
    const animateValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.innerText = value !== undefined ? value : '-';
    };

    if (data.kpi) {
        animateValue('kpi-total-tables', data.kpi.total_tables);

        // Synced Tables + Records
        const syncedEl = document.getElementById('kpi-synced-tables');
        if (syncedEl) {
            syncedEl.innerHTML = `
                <div style="font-size: 1.5rem; font-weight: bold;">${data.kpi.synced_tables}</div>
                <div style="font-size: 0.75rem; color: #a1a1aa; margin-top: 4px;">
                    ${parseFloat(data.kpi.total_records || 0).toLocaleString()} records • ${data.kpi.db_size || 'N/A'}
                </div>
             `;
        }

        // Training + SQLs + Last Date
        const trainingEl = document.getElementById('kpi-total-training');
        if (trainingEl) {
            const lastDate = data.kpi.last_training ? new Date(data.kpi.last_training).toLocaleDateString() : 'Nunca';
            trainingEl.innerHTML = `
                <div style="font-size: 1.5rem; font-weight: bold;">${data.kpi.trained_rules}</div>
                <div style="font-size: 0.75rem; color: #a1a1aa; margin-top: 4px;">
                   SQLs Generados • Último: <span style="color:#a855f7">${lastDate}</span>
                </div>
            `;
        }

        animateValue('kpi-relations', data.kpi.relationships);
    }
}

function renderTablesList(tables) {
    const list = document.getElementById('dashboard-tables-list');
    if (!list) return;

    if (!tables || tables.length === 0) {
        list.innerHTML = '<div style="text-align:center; padding: 2rem; color: #52525b;">No hay tablas analizadas</div>';
        return;
    }

    list.innerHTML = tables.map(t => {
        let syncStatus;
        if (t.virtual) {
            syncStatus = '<span style="color:#60a5fa">🌐 Virtual (Directo)</span>';
        } else {
            syncStatus = t.synced
                ? '<span style="color:#34d399">✅ Sincronizada</span>'
                : '<span style="color:#71717a">⏳ Pendiente</span>';
        }

        // t.indexed is a boolean
        const trainingStatus = t.indexed
            ? '<span style="color:#a855f7; font-weight:500;">🧠 Indexada</span>'
            : '<span style="color:#52525b">⚫ No Indexada</span>';

        const lastSync = t.last_sync
            ? new Date(t.last_sync).toLocaleDateString() + ' ' + new Date(t.last_sync).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : '-';

        return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px; margin-bottom: 0.5rem; transition: background 0.2s;" class="table-dash-item">
            <div>
                <div style="font-weight: 600; font-size: 0.95rem; color: #e4e4e7;">${t.friendly_name || t.name}</div>
                <div style="font-size: 0.8rem; color: #a1a1aa; margin-top:2px;">${t.table}</div>
                <div style="font-size: 0.75rem; color: #52525b; margin-top:2px;">Última sinc: ${lastSync}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.85rem; margin-bottom: 4px;">${syncStatus}</div>
                <div style="font-size: 0.8rem;">${trainingStatus}</div>
            </div>
        </div>
        `;
    }).join('');
}


function renderActivityChart(evolution) {
    const el = document.getElementById('dashboard-activity-chart');
    if (!el) return;

    try {
        if (!evolution || !evolution.series || evolution.series.length === 0) {
            el.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; color:#52525b; font-size:0.9rem;">Sin actividad reciente</div>';
            return;
        }

        const dates = evolution.dates.map(d => {
            // Basic format DD/MM
            const p = d.split('-');
            return `${p[2]}/${p[1]}`;
        });

        // Compute Total for Header (Manual + Auto Latest)
        let totalVal = 0;
        evolution.series.forEach(s => {
            if (s.data.length > 0) totalVal += s.data[s.data.length - 1];
        });

        // Update card header if possible? 
        // We'll just render the chart.

        const options = {
            series: evolution.series, // Already in {name, data} format
            chart: {
                type: 'area',
                stacked: true, // Stacked accumulative
                height: 250,
                background: 'transparent',
                toolbar: { show: false },
                animations: { enabled: true }
            },
            colors: ['#a855f7', '#3b82f6'], // Purple (Auto), Blue (Manual)
            fill: {
                type: 'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.6,
                    opacityTo: 0.2,
                    stops: [0, 90, 100]
                }
            },
            dataLabels: { enabled: false },
            stroke: {
                curve: 'smooth',
                width: 2
            },
            xaxis: {
                categories: dates,
                labels: { style: { colors: DASH_COLORS.text, fontSize: '11px' } },
                axisBorder: { show: false },
                axisTicks: { show: false },
                tooltip: { enabled: false }
            },
            yaxis: {
                labels: {
                    style: { colors: DASH_COLORS.text },
                    formatter: (val) => val.toFixed(0)
                }
            },
            grid: {
                borderColor: '#27272a',
                strokeDashArray: 4,
                yaxis: { lines: { show: true } }
            },
            theme: { mode: 'dark' },
            tooltip: {
                theme: 'dark',
                y: {
                    formatter: function (val) {
                        return val + " reglas"
                    }
                }
            },
            legend: {
                position: 'top',
                horizontalAlign: 'right',
                labels: { colors: DASH_COLORS.text }
            }
        };

        el.innerHTML = '';
        new ApexCharts(el, options).render();

        // Add Total Badge overlay if needed?
        // el.innerHTML += `<div style="position:absolute; top:10px; left:10px; font-weight:bold; color:white;">Total: ${totalVal}</div>`;
        // Better leave it clean.

    } catch (e) {
        console.error("Chart Error:", e);
        el.innerHTML = `<div style="color:red; font-size:0.8rem; padding:20px;">Error gráfico: ${e.message}</div>`;
    }
}

function renderRecentActivity(activity) {
    // Attempt to find or create container
    let container = document.getElementById('dashboard-recent-activity');

    // If it doesn't exist, we must create it dynamically in the grid
    if (!container) {
        const grid = document.querySelector('#subtab-dashboard .grid'); // Assume standard grid class or id layout
        // Fallback: If we can't find the grid easily, assume layout is fixed and we append to main container

        // Actually, let's look for "dashboard-tables-list" container and maybe append below it?
        // Or finding the parent of 'dashboard-activity-chart'

        const chartCard = document.getElementById('dashboard-activity-chart')?.parentElement;
        if (chartCard && chartCard.parentElement) {
            // Create a NEW Card
            const card = document.createElement('div');
            card.className = chartCard.className; // mimic styling
            card.style.cssText = chartCard.style.cssText; // mimic styles

            card.innerHTML = `
                <div style="padding: 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); font-weight: 600; color: #e4e4e7; display:flex; justify-content:space-between;">
                    <span>📜 Actividad Reciente</span>
                    <span style="font-size:0.7rem; color:#71717a;">Últimos 20</span>
                </div>
                <div id="dashboard-recent-activity" style="max-height: 300px; overflow-y: auto;"></div>
            `;

            // Insert after the chart card
            chartCard.parentElement.insertBefore(card, chartCard.nextSibling);
            container = card.querySelector('#dashboard-recent-activity');
        }
    }

    if (!container) return; // Should not happen if injection works

    if (!activity || activity.length === 0) {
        container.innerHTML = '<div style="padding:1rem; color:#52525b; text-align:center;">Sin actividad</div>';
        return;
    }

    container.innerHTML = activity.map(item => {
        const date = new Date(item.date).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        return `
            <div style="padding: 0.75rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.03); display: flex; align-items: start; gap: 10px;">
                <div style="font-size: 1.2rem;">${item.icon}</div>
                <div style="flex: 1;">
                    <div style="font-size: 0.85rem; color: #e4e4e7;">${item.label}</div>
                    <div style="font-size: 0.75rem; color: #a1a1aa; margin-top:2px;">${item.snippet}</div>
                </div>
                <div style="font-size: 0.7rem; color: #52525b; white-space: nowrap;">${date}</div>
            </div>
        `;
    }).join('');
}


// Render network of relationships (Simplified as a Bar Chart or Heatmap if Graph not available)
// Ideally force-directed graph is best, but ApexCharts doesn't support it well.
// We'll use a horizontal bar chart showing "Most Connected Tables"
function renderNetworkGraph(relationsList) {
    const el = document.getElementById('dashboard-network-chart');
    if (!el) return;

    if (!relationsList || !Array.isArray(relationsList) || relationsList.length === 0) {
        // Fallback for empty state or if data structure is wrong (legacy dict check)
        el.innerHTML = '<div style="display:flex; justify-content:center; align-items:center; height:250px; color:#52525b;">Sin relaciones recientes</div>';
        return;
    }

    // Render simple List
    const html = relationsList.map(r => {
        return `
            <div style="display:flex; align-items:center; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                <div style="flex:1;">
                    <span style="color:#e4e4e7; font-weight:500;">${r.source}</span>
                    <span style="color:#71717a; font-size: 0.8em; margin: 0 4px;">(${r.from_field})</span>
                </div>
                <div style="margin: 0 1rem; color: #a855f7;">➔</div>
                <div style="flex:1; text-align:right;">
                    <span style="color:#e4e4e7; font-weight:500;">${r.target}</span>
                    <span style="color:#71717a; font-size: 0.8em; margin: 0 4px;">(${r.to_field})</span>
                </div>
                <div style="margin-left: 1rem;">
                    <span style="font-size:0.7em; background:rgba(255,255,255,0.1); padding: 2px 6px; borderRadius:4px;">${r.cardinality}</span>
                </div>
            </div>
        `;
    }).join('');

    el.innerHTML = `<div style="max-height: 250px; overflow-y: auto; padding: 0.5rem;" class="custom-chk-scroll">${html}</div>`;
}
