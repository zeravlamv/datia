// Entity Dashboards: Clientes, Proveedores y Artículos

console.log("Entity Dashboards JS Loaded");

const ENTITY_CONFIG = {
    clientes: {
        overviewPath: "/api/datia/dashboard/clientes/overview",
        detailPath: "/api/datia/dashboard/clientes/detail",
        moneyKpis: ["ventas_totales", "ticket_medio"],
        intKpis: ["total_clientes", "operaciones_totales"],
        charts: {
            ventas_mensuales: { type: "line", money: true },
            top_clientes: { type: "bar-horizontal", money: true },
            frecuencia: { type: "bar", money: false },
        },
    },
    proveedores: {
        overviewPath: "/api/datia/dashboard/proveedores/overview",
        detailPath: "/api/datia/dashboard/proveedores/detail",
        moneyKpis: ["compras_totales"],
        intKpis: ["total_proveedores", "operaciones_totales"],
        percentKpis: ["concentracion_top10"],
        charts: {
            compras_mensuales: { type: "line", money: true },
            top_proveedores: { type: "bar-horizontal", money: true },
        },
    },
    articulos: {
        overviewPath: "/api/datia/dashboard/articulos/overview",
        detailPath: "/api/datia/dashboard/articulos/detail",
        moneyKpis: ["ventas_totales", "compras_totales"],
        intKpis: ["total_articulos", "operaciones_totales"],
        charts: {
            top_ventas: { type: "bar-horizontal", money: true },
            top_compras: { type: "bar-horizontal", money: true },
        },
    },
};

async function loadEntityDashboard(kind, force = false) {
    const cfg = ENTITY_CONFIG[kind];
    if (!cfg) return;
    const container = document.querySelector(`.entity-dashboard[data-entity="${kind}"]`);
    if (!container) return;

    const empresa = typeof currEmpresa !== "undefined" ? currEmpresa : null;
    const ejercicio = typeof currEjercicio !== "undefined" ? currEjercicio : null;
    if (!empresa || !ejercicio) {
        return;
    }

    const searchInput = container.querySelector(`[data-entity-search="${kind}"]`);
    const q = searchInput && searchInput.value ? searchInput.value.trim() : "";
    const params = new URLSearchParams();
    params.set("empresa", String(empresa));
    params.set("ejercicio", String(ejercicio));
    if (q) params.set("q", q);

    try {
        const res = await fetch(`${cfg.overviewPath}?${params.toString()}`);
        if (!res.ok) throw new Error("API error");
        const data = await res.json();
        renderEntityOverview(kind, container, data);
    } catch (e) {
        console.error(`Error loading dashboard for ${kind}:`, e);
        if (typeof showToast === "function") {
            showToast(`Error cargando dashboard de ${kind}`, "error");
        }
    }
}

function renderEntityOverview(kind, container, payload) {
    if (!payload || typeof payload !== "object") return;
    const cfg = ENTITY_CONFIG[kind];
    if (!cfg) return;

    const kpi = payload.kpi || {};
    const kpiBoxes = container.querySelectorAll(".entity-kpi-row [data-kpi]");
    kpiBoxes.forEach((box) => {
        const key = box.getAttribute("data-kpi");
        const valEl = box.querySelector("[data-kpi-value]");
        if (!key || !valEl) return;
        const raw = kpi[key];
        let txt = "--";
        if (raw !== undefined && raw !== null) {
            if (cfg.moneyKpis && cfg.moneyKpis.indexOf(key) !== -1) {
                txt = fmtMoney.format(raw);
            } else if (cfg.percentKpis && cfg.percentKpis.indexOf(key) !== -1) {
                const num = Number(raw) || 0;
                txt = `${num.toFixed(1)} %`;
            } else if (cfg.intKpis && cfg.intKpis.indexOf(key) !== -1) {
                txt = fmtInt.format(raw);
            } else {
                txt = fmtNum.format(raw);
            }
        }
        valEl.innerText = txt;
    });

    const charts = payload.charts || {};
    Object.keys(cfg.charts || {}).forEach((chartKey) => {
        const conf = cfg.charts[chartKey];
        const dom = container.querySelector(`[data-chart="${chartKey}"]`);
        const cdata = charts[chartKey] || {};
        if (!dom) return;
        if (chartKey === "ventas_mensuales" || chartKey === "compras_mensuales") {
            const labels = cdata.labels || [];
            const serie = cdata.ventas || cdata.compras || [];
            renderBarOrLineChart(dom, labels, serie, { type: conf.type, money: !!conf.money, name: chartKey });
        } else if (chartKey === "top_clientes" || chartKey === "top_proveedores" || chartKey === "top_ventas" || chartKey === "top_compras") {
            const rows = (cdata.data || []).slice(0, 20);
            const labels = rows.map((r) => r.nombre || r.descripcion || r.codigo || "");
            const values = rows.map((r) => r.ventas || r.compras || r.neto || 0);
            renderBarOrLineChart(dom, labels, values, { type: "bar-horizontal", money: !!conf.money, name: chartKey });
        } else if (chartKey === "frecuencia") {
            const labels = cdata.labels || [];
            const values = cdata.clientes || [];
            renderBarOrLineChart(dom, labels, values, { type: "bar", money: false, name: chartKey });
        }
    });

    const tableData = payload.table && payload.table.rows ? payload.table.rows : [];
    const tbody = container.querySelector(`[data-entity-table="${kind}"]`);
    if (tbody) {
        tbody.innerHTML = "";
        if (!tableData.length) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = kind === "clientes" ? 5 : 4;
            td.className = "text-center";
            td.innerText = "Sin datos";
            tr.appendChild(td);
            tbody.appendChild(tr);
        } else {
            tableData.forEach((row) => {
                const tr = document.createElement("tr");
                tr.setAttribute("data-code", row.codigo || row.proveedor || row.articulo || "");
                if (kind === "clientes") {
                    appendCell(tr, row.codigo);
                    appendCell(tr, row.nombre);
                    appendCell(tr, fmtMoney.format(row.ventas || 0), "text-right");
                    appendCell(tr, fmtInt.format(row.albaranes || 0), "text-right");
                    appendCell(tr, fmtMoney.format(row.ticket_medio || 0), "text-right");
                } else if (kind === "proveedores") {
                    appendCell(tr, row.codigo);
                    appendCell(tr, row.nombre);
                    appendCell(tr, fmtMoney.format(row.compras || 0), "text-right");
                    appendCell(tr, fmtInt.format(row.albaranes || 0), "text-right");
                } else if (kind === "articulos") {
                    appendCell(tr, row.codigo);
                    appendCell(tr, row.descripcion);
                    appendCell(tr, fmtMoney.format(row.ventas || 0), "text-right");
                    appendCell(tr, fmtInt.format(row.operaciones || 0), "text-right");
                }
                tbody.appendChild(tr);
            });
        }
    }

    if (kind === "clientes") {
        const empresa = typeof currEmpresa !== "undefined" ? currEmpresa : null;
        const ejercicio = typeof currEjercicio !== "undefined" ? currEjercicio : null;
        const searchInput = container.querySelector(`[data-entity-search="${kind}"]`);
        const q = searchInput && searchInput.value ? searchInput.value.trim() : "";
        if (empresa && ejercicio && q && tableData.length === 1) {
            const only = tableData[0] || {};
            const code = only.codigo || "";
            if (code) {
                if (typeof setEntityLayoutMode === "function") {
                    setEntityLayoutMode(kind, "detail");
                }
                if (tbody) {
                    Array.from(tbody.querySelectorAll("tr")).forEach((row) => {
                        row.classList.remove("is-selected");
                    });
                    const autoRow = tbody.querySelector('tr[data-code="' + String(code) + '"]');
                    if (autoRow) {
                        autoRow.classList.add("is-selected");
                    }
                }
                loadEntityDetail(kind, code);
            }
        }
    }
}

function appendCell(tr, text, cls) {
    const td = document.createElement("td");
    if (cls) td.className = cls;
    td.innerText = text != null ? String(text) : "";
    tr.appendChild(td);
}

function renderBarOrLineChart(dom, labels, values, opts) {
    if (!window.echarts) return;
    const cleanVals = Array.isArray(values) ? values.map((v) => Number(v || 0)) : [];
    if (!cleanVals.some((v) => v !== 0)) {
        const inst = echarts.getInstanceByDom(dom);
        if (inst) inst.dispose();
        dom.innerText = "Sin datos";
        return;
    }
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: "svg" });
    const isMoney = opts && opts.money;
    const horizontal = opts && opts.type === "bar-horizontal";
    const isLine = opts && opts.type === "line";
    const baseColor = "#3b82f6";
    const yFormatter = (val) => {
        if (isMoney) {
            return fmtMoneySimple.format(val);
        }
        return fmtInt.format(val);
    };
    const option = {
        backgroundColor: "transparent",
        grid: { left: "3%", right: "3%", top: 30, bottom: 30, containLabel: true },
        tooltip: {
            trigger: horizontal ? "item" : "axis",
            formatter: function (p) {
                if (Array.isArray(p)) p = p[0];
                const name = p.name || "";
                const val = p.value || 0;
                const valText = isMoney ? fmtMoneySimple.format(val) : fmtInt.format(val);
                return `${name}<br>${valText}`;
            },
        },
    };
    if (horizontal) {
        option.yAxis = {
            type: "category",
            data: labels,
            axisLine: { lineStyle: { color: "#52525b" } },
            axisLabel: { color: "#a1a1aa" },
        };
        option.xAxis = {
            type: "value",
            splitLine: { lineStyle: { color: "#27272a" } },
            axisLabel: { formatter: yFormatter, color: "#a1a1aa" },
        };
        option.series = [
            {
                type: "bar",
                data: cleanVals,
                itemStyle: { color: baseColor, borderRadius: [4, 4, 4, 4] },
            },
        ];
    } else {
        option.xAxis = {
            type: "category",
            data: labels,
            axisLine: { lineStyle: { color: "#52525b" } },
            axisLabel: { color: "#a1a1aa" },
        };
        option.yAxis = {
            type: "value",
            splitLine: { lineStyle: { color: "#27272a" } },
            axisLabel: { formatter: yFormatter, color: "#a1a1aa" },
        };
        option.series = [
            {
                type: isLine ? "line" : "bar",
                data: cleanVals,
                smooth: isLine,
                itemStyle: { color: baseColor },
                lineStyle: { color: baseColor, width: 2 },
            },
        ];
    }
    chart.setOption(option);
    if (typeof attachResizeObserver === "function") {
        attachResizeObserver(chart, dom);
    }
}

async function loadEntityDetail(kind, code) {
    const cfg = ENTITY_CONFIG[kind];
    if (!cfg || !code) return;
    const container = document.querySelector(`.entity-dashboard[data-entity="${kind}"]`);
    if (!container) return;
    const empresa = typeof currEmpresa !== "undefined" ? currEmpresa : null;
    const ejercicio = typeof currEjercicio !== "undefined" ? currEjercicio : null;
    if (!empresa || !ejercicio) {
        return;
    }

    const params = new URLSearchParams();
    params.set("empresa", String(empresa));
    params.set("ejercicio", String(ejercicio));
    params.set("codigo", String(code));

    try {
        const res = await fetch(`${cfg.detailPath}?${params.toString()}`);
        if (!res.ok) throw new Error("API error");
        const data = await res.json();
        renderEntityDetail(kind, container, data);
    } catch (e) {
        console.error(`Error loading detail for ${kind} ${code}:`, e);
    }
}

function renderEntityDetail(kind, container, payload) {
    const panel = container.querySelector(`[data-entity-detail="${kind}"]`);
    if (!panel || !payload) return;

    if (kind === "clientes") {
        const cli = payload.cliente || {};
        setDetailField(panel, "nombre", cli.nombre || "");
        setDetailField(panel, "codigo", cli.codigo || "");
        setDetailField(panel, "ventas_totales", fmtMoney.format(cli.ventas_totales || 0));
        setDetailField(panel, "operaciones", fmtInt.format(cli.operaciones || 0));
        setDetailField(panel, "ticket_medio", fmtMoney.format(cli.ticket_medio || 0));

        const identity = payload.identity || {};
        if (identity) {
            setDetailField(panel, "nombre_fiscal", identity.nombre_fiscal || "");
            setDetailField(panel, "cif_nif", identity.cif_nif || "");
            setDetailField(panel, "cod_postal", identity.cod_postal || "");
            setDetailField(panel, "fecha_alta", identity.fecha_alta || "");
            if (identity.activo === true) {
                setDetailField(panel, "activo", gettext ? gettext("Activo") : "Activo");
            } else if (identity.activo === false) {
                setDetailField(panel, "activo", gettext ? gettext("Inactivo") : "Inactivo");
            } else {
                setDetailField(panel, "activo", "--");
            }
        }

        const risk = payload.risk || {};
        if (risk && risk.pendiente_cobro !== null && risk.pendiente_cobro !== undefined) {
            setDetailField(panel, "pendiente_cobro", fmtMoney.format(risk.pendiente_cobro || 0));
        } else {
            setDetailField(panel, "pendiente_cobro", "--");
        }

        const summary = payload.summary || {};
        if (summary) {
            setDetailField(panel, "total_pedidos", fmtInt.format(summary.total_pedidos || 0));
            const mp = summary.margen_pct;
            setDetailField(panel, "margen_pct", mp !== null && mp !== undefined ? `${Number(mp).toFixed(2)} %` : "--");
            const ad = summary.antiguedad_dias;
            setDetailField(panel, "antiguedad_dias", ad !== null && ad !== undefined ? fmtInt.format(ad) : "--");
            const ul = summary.ultima_compra;
            setDetailField(panel, "ultima_compra", ul || "--");
        }

        const charts = payload.charts || {};
        const vm = charts.ventas_mensuales || {};
        const labels = vm.labels || [];
        const valores = vm.ventas || [];
        const vmDom = panel.querySelector('[data-detail-chart="ventas_mensuales"]');
        if (vmDom) {
            renderBarOrLineChart(vmDom, labels, valores, { type: "line", money: true, name: "cli-detail-ventas" });
        }
        const topArt = charts.top_articulos || {};
        const rows = (topArt.data || []).slice(0, 20);
        const la = rows.map((r) => r.descripcion || r.codigo || "");
        const va = rows.map((r) => r.ventas || 0);
        const topDom = panel.querySelector('[data-detail-chart="top_articulos"]');
        if (topDom) {
            renderBarOrLineChart(topDom, la, va, { type: "bar-horizontal", money: true, name: "cli-detail-topart" });
        }

        const comparison = payload.comparison || {};
        const heatmapData = comparison.heatmap || null;
        const scatterData = comparison.scatter || null;
        const heatDom = panel.querySelector('[data-detail-chart="cliente_heatmap"]');
        if (heatDom && heatmapData && window.echarts) {
            const chart = echarts.init(heatDom, null, { renderer: "svg" });
            const metrics = heatmapData.metrics || [];
            const clienteVals = heatmapData.cliente || [];
            const restoVals = heatmapData.resto || [];
            const seriesData = [];
            for (let i = 0; i < metrics.length; i++) {
                seriesData.push([i, 0, clienteVals[i] || 0]);
                seriesData.push([i, 1, restoVals[i] || 0]);
            }
            const option = {
                tooltip: {
                    formatter: (p) => {
                        const m = metrics[p.data[0]] || "";
                        const fila = p.data[1] === 0 ? "Cliente" : "Resto";
                        const valor = Number(p.data[2] || 0);
                        return `${fila} · ${m}: ${(valor * 100).toFixed(1)}%`;
                    },
                },
                grid: { left: "5%", right: "5%", top: 20, bottom: 30, containLabel: true },
                xAxis: {
                    type: "category",
                    data: metrics,
                    axisLine: { lineStyle: { color: "#52525b" } },
                    axisLabel: { color: "#a1a1aa" },
                },
                yAxis: {
                    type: "category",
                    data: ["Cliente", "Resto"],
                    axisLine: { lineStyle: { color: "#52525b" } },
                    axisLabel: { color: "#a1a1aa" },
                },
                visualMap: {
                    min: 0,
                    max: 1,
                    calculable: false,
                    orient: "horizontal",
                    left: "center",
                    bottom: 0,
                    inRange: {
                        color: ["#020617", "#3b82f6"],
                    },
                    show: false,
                },
                series: [
                    {
                        type: "heatmap",
                        data: seriesData,
                        label: { show: false },
                    },
                ],
            };
            chart.setOption(option);
            if (typeof attachResizeObserver === "function") {
                attachResizeObserver(chart, heatDom);
            }
        }
        const scatterDom = panel.querySelector('[data-detail-chart="cliente_scatter"]');
        if (scatterDom && scatterData && scatterData.ventas_vs_operaciones && window.echarts) {
            const pts = scatterData.ventas_vs_operaciones || [];
            const seriesAll = [];
            const seriesCli = [];
            pts.forEach((r) => {
                const p = {
                    value: [Number(r.ventas || 0), Number(r.operaciones || 0)],
                    name: r.nombre || r.codigo || "",
                };
                if (r.is_selected) {
                    seriesCli.push(p);
                } else {
                    seriesAll.push(p);
                }
            });
            const chart = echarts.init(scatterDom, null, { renderer: "svg" });
            const option = {
                tooltip: {
                    trigger: "item",
                    formatter: (p) => {
                        const v = p.value || [];
                        return `${p.name}<br>Ventas: ${fmtMoneySimple.format(v[0] || 0)}<br>Operaciones: ${fmtInt.format(v[1] || 0)}`;
                    },
                },
                grid: { left: "8%", right: "5%", top: 20, bottom: 40, containLabel: true },
                xAxis: {
                    type: "value",
                    splitLine: { lineStyle: { color: "#27272a" } },
                    axisLabel: {
                        color: "#a1a1aa",
                        formatter: (v) => fmtMoneySimple.format(v),
                    },
                },
                yAxis: {
                    type: "value",
                    splitLine: { lineStyle: { color: "#27272a" } },
                    axisLabel: {
                        color: "#a1a1aa",
                        formatter: (v) => fmtInt.format(v),
                    },
                },
                series: [
                    {
                        name: "Resto",
                        type: "scatter",
                        symbolSize: 6,
                        itemStyle: { color: "#4b5563" },
                        data: seriesAll,
                    },
                    {
                        name: "Cliente",
                        type: "scatter",
                        symbolSize: 10,
                        itemStyle: { color: "#3b82f6" },
                        data: seriesCli,
                    },
                ],
            };
            chart.setOption(option);
            if (typeof attachResizeObserver === "function") {
                attachResizeObserver(chart, scatterDom);
            }
        }

        const orders = (payload.orders && payload.orders.rows) ? payload.orders.rows : [];
        const deliveries = (payload.deliveries && payload.deliveries.rows) ? payload.deliveries.rows : [];
        const ordersBody = panel.querySelector('[data-detail-table="orders"]');
        const delivBody = panel.querySelector('[data-detail-table="deliveries"]');
        if (ordersBody) {
            ordersBody.innerHTML = "";
            if (!orders.length) {
                const tr = document.createElement("tr");
                const td = document.createElement("td");
                td.colSpan = 10;
                td.className = "text-center";
                td.innerText = "Sin datos";
                tr.appendChild(td);
                ordersBody.appendChild(tr);
            } else {
                orders.forEach((order, idx) => {
                    const trHeader = document.createElement("tr");
                    trHeader.className = "orders-tree-header";
                    trHeader.dataset.orderIndex = String(idx);

                    const tdToggle = document.createElement("td");
                    tdToggle.className = "orders-tree-toggle-cell";
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = "orders-tree-toggle";
                    btn.setAttribute("aria-expanded", "false");
                    btn.innerText = "▸";
                    tdToggle.appendChild(btn);
                    trHeader.appendChild(tdToggle);

                    appendCell(trHeader, order.documento || order.numero || "");
                    appendCell(trHeader, order.fecha || "");
                    appendCell(trHeader, order.fecha_entrega || "");
                    appendCell(trHeader, order.proyecto || "");
                    appendCell(trHeader, order.seccion || "");
                    appendCell(trHeader, order.delegacion || "");
                    appendCell(trHeader, order.canal || "");
                    appendCell(trHeader, order.departamento || "");
                    appendCell(trHeader, fmtMoney.format(order.importe || 0), "text-right");
                    ordersBody.appendChild(trHeader);

                    const trLines = document.createElement("tr");
                    trLines.className = "orders-tree-lines";
                    trLines.dataset.orderIndex = String(idx);
                    trLines.style.display = "none";
                    const tdLines = document.createElement("td");
                    tdLines.colSpan = 10;
                    tdLines.className = "orders-tree-lines-cell";
                    trLines.appendChild(tdLines);
                    ordersBody.appendChild(trLines);

                    btn.addEventListener("click", () => {
                        const expanded = trLines.style.display !== "none";
                        if (expanded) {
                            trLines.style.display = "none";
                            btn.innerText = "▸";
                            btn.setAttribute("aria-expanded", "false");
                        } else {
                            if (!tdLines.dataset.initialized) {
                                const linesTable = buildOrderLinesTable(order);
                                tdLines.appendChild(linesTable);
                                tdLines.dataset.initialized = "1";
                            }
                            trLines.style.display = "table-row";
                            btn.innerText = "▾";
                            btn.setAttribute("aria-expanded", "true");
                        }
                    });
                });
            }
        }
        if (delivBody) {
            delivBody.innerHTML = "";
            if (!deliveries.length) {
                const tr = document.createElement("tr");
                const td = document.createElement("td");
                td.colSpan = 11;
                td.className = "text-center";
                td.innerText = "Sin datos";
                tr.appendChild(td);
                delivBody.appendChild(tr);
            } else {
                const hasTree = !!(deliveries[0] && Array.isArray(deliveries[0].lineas));
                if (!hasTree) {
                    deliveries.forEach((r) => {
                        const tr = document.createElement("tr");
                        appendCell(tr, "");
                        appendCell(tr, r.documento || r.numero);
                        appendCell(tr, r.fecha || "");
                        appendCell(tr, r.articulo || "");
                        appendCell(tr, r.descripcion || "");
                        appendCell(tr, fmtNum.format(r.unidades || 0), "text-right");
                        appendCell(tr, fmtMoney.format(r.precio_unitario || 0), "text-right");
                        appendCell(tr, fmtMoney.format(r.importe || 0), "text-right");
                        appendCell(tr, fmtMoney.format(r.coste || 0), "text-right");
                        const m = (r.margen != null) ? r.margen : ((r.importe || 0) - (r.coste || 0));
                        const mp = (r.margen_pct != null) ? r.margen_pct : (((r.importe || 0) !== 0) ? ((m / (r.importe || 0)) * 100) : 0);
                        appendCell(tr, fmtMoney.format(m), "text-right");
                        appendCell(tr, fmtNum.format(mp) + " %", "text-right");
                        delivBody.appendChild(tr);
                    });
                } else {
                    deliveries.forEach((d) => {
                        const trHeader = document.createElement("tr");
                        trHeader.className = "orders-tree-header";

                        const tdToggle = document.createElement("td");
                        tdToggle.className = "orders-tree-toggle-cell";
                        const btn = document.createElement("button");
                        btn.type = "button";
                        btn.className = "orders-tree-toggle";
                        btn.setAttribute("aria-expanded", "false");
                        btn.innerText = "▸";
                        tdToggle.appendChild(btn);
                        trHeader.appendChild(tdToggle);

                        appendCell(trHeader, d.documento || d.numero || "");
                        appendCell(trHeader, d.fecha || "");
                        appendCell(trHeader, "");
                        appendCell(trHeader, `${fmtInt.format(d.lineas_count || 0)} líneas`);
                        appendCell(trHeader, "", "text-right");
                        appendCell(trHeader, "", "text-right");
                        appendCell(trHeader, fmtMoney.format(d.importe_total || 0), "text-right");
                        appendCell(trHeader, fmtMoney.format(d.coste_total || 0), "text-right");
                        const mh = (d.margen_total != null) ? d.margen_total : ((d.importe_total || 0) - (d.coste_total || 0));
                        const mhp = (d.margen_total_pct != null) ? d.margen_total_pct : (((d.importe_total || 0) !== 0) ? ((mh / (d.importe_total || 0)) * 100) : 0);
                        appendCell(trHeader, fmtMoney.format(mh), "text-right");
                        appendCell(trHeader, fmtNum.format(mhp) + " %", "text-right");
                        delivBody.appendChild(trHeader);

                        const trLines = document.createElement("tr");
                        trLines.style.display = "none";
                        const tdLines = document.createElement("td");
                        tdLines.colSpan = 11;
                        tdLines.className = "orders-tree-lines-cell";
                        trLines.appendChild(tdLines);
                        delivBody.appendChild(trLines);

                        btn.addEventListener("click", () => {
                            const expanded = trLines.style.display !== "none";
                            if (expanded) {
                                trLines.style.display = "none";
                                btn.innerText = "▸";
                                btn.setAttribute("aria-expanded", "false");
                            } else {
                                if (!tdLines.dataset.initialized) {
                                    const linesTable = buildDeliveryLinesTable(d);
                                    tdLines.appendChild(linesTable);
                                    tdLines.dataset.initialized = "1";
                                }
                                trLines.style.display = "table-row";
                                btn.innerText = "▾";
                                btn.setAttribute("aria-expanded", "true");
                            }
                        });
                    });
                }
            }
        }

        const freq = payload.frequency || {};
        const serieFreq = freq.serie_mensual || {};
        const fLabels = serieFreq.labels || [];
        const fVals = serieFreq.pedidos || [];
        const freqDom = panel.querySelector('[data-detail-chart="frecuencia_compra"]');
        if (freqDom && fLabels.length) {
            renderBarOrLineChart(freqDom, fLabels, fVals, { type: "bar", money: false, name: "cli-detail-freq" });
        }
        if (freq) {
            const pedidos12 = freq.pedidos_12m;
            if (pedidos12 !== null && pedidos12 !== undefined) {
                setDetailField(panel, "pedidos_12m", fmtInt.format(pedidos12));
            } else {
                setDetailField(panel, "pedidos_12m", "--");
            }
            const gap = freq.dias_promedio_entre_pedidos;
            if (gap !== null && gap !== undefined) {
                setDetailField(panel, "dias_promedio_entre_pedidos", fmtNum.format(gap));
            } else {
                setDetailField(panel, "dias_promedio_entre_pedidos", "--");
            }
        }
    } else if (kind === "proveedores") {
        const pr = payload.proveedor || {};
        setDetailField(panel, "nombre", pr.nombre || "");
        setDetailField(panel, "codigo", pr.codigo || "");
        setDetailField(panel, "compras_totales", fmtMoney.format(pr.compras_totales || 0));
        setDetailField(panel, "operaciones", fmtInt.format(pr.operaciones || 0));

        const charts = payload.charts || {};
        const cm = charts.compras_mensuales || {};
        const labels = cm.labels || [];
        const valores = cm.compras || [];
        const cmDom = panel.querySelector('[data-detail-chart="compras_mensuales"]');
        if (cmDom) {
            renderBarOrLineChart(cmDom, labels, valores, { type: "line", money: true, name: "prov-detail-compras" });
        }
    } else if (kind === "articulos") {
        const art = payload.articulo || {};
        const ventas = payload.ventas || {};
        const compras = payload.compras || {};
        setDetailField(panel, "descripcion", art.descripcion || "");
        setDetailField(panel, "codigo", art.codigo || "");
        setDetailField(panel, "ventas_importe", fmtMoney.format(ventas.importe || 0));
        setDetailField(panel, "compras_importe", fmtMoney.format(compras.importe || 0));
        setDetailField(panel, "ventas_operaciones", fmtInt.format(ventas.operaciones || 0));
    }
}

function buildOrderLinesTable(order) {
    const wrapper = document.createElement("div");
    wrapper.className = "orders-lines-wrapper";

    const table = document.createElement("table");
    table.className = "fin-table orders-lines-table";

    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");
    const headers = ["Artículo", "Descripción", "Unidades", "Precio", "Importe", "Coste"];
    headers.forEach((label, idx) => {
        const th = document.createElement("th");
        if (idx >= 2) {
            th.className = "text-right";
        }
        th.innerText = label;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    const lines = Array.isArray(order && order.lineas) ? order.lineas : [];
    if (!lines.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 6;
        td.className = "text-center";
        td.innerText = "Sin líneas";
        tr.appendChild(td);
        tbody.appendChild(tr);
    } else {
        lines.forEach((ln) => {
            const tr = document.createElement("tr");
            appendCell(tr, ln.articulo || "");
            appendCell(tr, ln.descripcion || "");
            appendCell(tr, fmtNum.format(ln.unidades || 0), "text-right");
            appendCell(tr, fmtMoney.format(ln.precio_unitario || 0), "text-right");
            appendCell(tr, fmtMoney.format(ln.importe || 0), "text-right");
            appendCell(tr, fmtMoney.format(ln.coste || 0), "text-right");
            tbody.appendChild(tr);
        });
    }
    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
}

function buildDeliveryLinesTable(delivery) {
    const wrapper = document.createElement("div");
    wrapper.className = "orders-lines-wrapper";

    const table = document.createElement("table");
    table.className = "fin-table orders-lines-table";

    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");
    const headers = ["Artículo", "Descripción", "Unidades", "Precio", "Importe", "Coste", "Margen", "Margen %"];
    headers.forEach((label, idx) => {
        const th = document.createElement("th");
        if (idx >= 2) {
            th.className = "text-right";
        }
        th.innerText = label;
        trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    const lines = Array.isArray(delivery && delivery.lineas) ? delivery.lineas : [];
    if (!lines.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 8;
        td.className = "text-center";
        td.innerText = "Sin líneas";
        tr.appendChild(td);
        tbody.appendChild(tr);
    } else {
        lines.forEach((ln) => {
            const tr = document.createElement("tr");
            appendCell(tr, ln.articulo || "");
            appendCell(tr, ln.descripcion || "");
            appendCell(tr, fmtNum.format(ln.unidades || 0), "text-right");
            appendCell(tr, fmtMoney.format(ln.precio_unitario || 0), "text-right");
            appendCell(tr, fmtMoney.format(ln.importe || 0), "text-right");
            appendCell(tr, fmtMoney.format(ln.coste || 0), "text-right");
            const m = (ln.margen != null) ? ln.margen : ((ln.importe || 0) - (ln.coste || 0));
            const mp = (ln.margen_pct != null) ? ln.margen_pct : (((ln.importe || 0) !== 0) ? ((m / (ln.importe || 0)) * 100) : 0);
            appendCell(tr, fmtMoney.format(m), "text-right");
            appendCell(tr, fmtNum.format(mp) + " %", "text-right");
            tbody.appendChild(tr);
        });
    }

    table.appendChild(tbody);
    wrapper.appendChild(table);
    return wrapper;
}

function setDetailField(panel, field, text) {
    const el = panel.querySelector(`[data-detail-field="${field}"]`);
    if (el) el.innerText = text != null ? String(text) : "";
}

function setEntityLayoutMode(kind, mode) {
    if (kind !== "clientes") return;
    const container = document.querySelector(`.entity-dashboard[data-entity="${kind}"]`);
    if (!container) return;
    const layout = container.querySelector(".entity-dashboard-layout");
    if (!layout) return;
    layout.classList.remove("mode-overview", "mode-detail");
    if (mode === "detail") {
        layout.classList.add("mode-detail");
    } else {
        layout.classList.add("mode-overview");
    }
}

function initEntityDashboard(kind) {
    const container = document.querySelector(`.entity-dashboard[data-entity="${kind}"]`);
    if (!container) return;

    const refreshBtn = container.querySelector(`[data-entity-refresh="${kind}"]`);
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            if (kind === "clientes") {
                const searchInput = container.querySelector(`[data-entity-search="${kind}"]`);
                const q = searchInput && searchInput.value ? searchInput.value.trim() : "";
                if (!q) {
                    setEntityLayoutMode(kind, "overview");
                }
            }
            loadEntityDashboard(kind, true);
        });
    }
    const searchInput = container.querySelector(`[data-entity-search="${kind}"]`);
    if (searchInput) {
        searchInput.addEventListener("keyup", (e) => {
            if (e.key === "Enter") {
                if (kind === "clientes") {
                    const q = searchInput.value ? searchInput.value.trim() : "";
                    if (!q) {
                        setEntityLayoutMode(kind, "overview");
                    }
                }
                loadEntityDashboard(kind, true);
            }
        });
    }
    const tbody = container.querySelector(`[data-entity-table="${kind}"]`);
    if (tbody) {
        tbody.addEventListener("click", (e) => {
            const tr = e.target.closest("tr");
            if (!tr) return;
            Array.from(tbody.querySelectorAll("tr")).forEach((row) => {
                row.classList.remove("is-selected");
            });
            tr.classList.add("is-selected");
            const code = tr.getAttribute("data-code");
            if (!code) return;
            if (kind === "clientes") {
                setEntityLayoutMode(kind, "detail");
            }
            loadEntityDetail(kind, code);
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    ["clientes", "proveedores", "articulos"].forEach((kind) => initEntityDashboard(kind));
    setEntityLayoutMode("clientes", "overview");
});

window.loadClientesDashboard = function () {
    loadEntityDashboard("clientes", true);
};
window.loadProveedoresDashboard = function () {
    loadEntityDashboard("proveedores", true);
};
window.loadArticulosDashboard = function () {
    loadEntityDashboard("articulos", true);
};

function exportEntityDashboard(kind, format) {
    const empresa = typeof currEmpresa !== "undefined" ? currEmpresa : null;
    const ejercicio = typeof currEjercicio !== "undefined" ? currEjercicio : null;
    if (!empresa || !ejercicio) return;
    const container = document.querySelector(`.entity-dashboard[data-entity="${kind}"]`);
    if (!container) return;
    const searchInput = container.querySelector(`[data-entity-search="${kind}"]`);
    const q = searchInput && searchInput.value ? searchInput.value.trim() : "";
    const params = new URLSearchParams();
    params.set("empresa", String(empresa));
    params.set("ejercicio", String(ejercicio));
    if (q) params.set("q", q);
    params.set("format", String(format || "csv"));
    const url = `/api/datia/dashboard/${kind}/export?${params.toString()}`;
    window.location.href = url;
}

window.exportClientesDashboard = function (format) {
    exportEntityDashboard("clientes", format || "csv");
};
window.exportProveedoresDashboard = function (format) {
    exportEntityDashboard("proveedores", format || "csv");
};
window.exportArticulosDashboard = function (format) {
    exportEntityDashboard("articulos", format || "csv");
};

document.addEventListener("datia:empresa-change", () => {
    ["clientes", "proveedores", "articulos"].forEach((kind) => {
        const subId = `sub-${kind}`;
        const tab = document.getElementById(subId);
        if (tab && tab.classList.contains("active")) {
            loadEntityDashboard(kind, true);
        }
    });
});

document.addEventListener("datia:ejercicio-change", () => {
    ["clientes", "proveedores", "articulos"].forEach((kind) => {
        const subId = `sub-${kind}`;
        const tab = document.getElementById(subId);
        if (tab && tab.classList.contains("active")) {
            loadEntityDashboard(kind, true);
        }
    });
});
