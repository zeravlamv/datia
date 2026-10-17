import logging
import io
from fpdf import FPDF

logger = logging.getLogger(__name__)

class ProReportPDF(FPDF):
    def __init__(self, title, empresa_id, ejercicio, orientation: str = "P"):
        orientation = (orientation or "P").upper()
        if orientation not in ("P", "L"):
            orientation = "P"
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.report_title = title or "Informe"
        self.empresa_id = empresa_id or "N/A"
        self.ejercicio = ejercicio or "N/A"

    def header(self):
        self.set_font("helvetica", "B", 15)
        self.set_text_color(24, 24, 27)
        self.cell(0, 10, self.report_title, new_x="LMARGIN", new_y="NEXT", align="L")
        
        self.set_font("helvetica", "", 9)
        self.set_text_color(102, 102, 102)
        meta = f"Empresa ID: {self.empresa_id} | Ejercicio: {self.ejercicio}"
        self.cell(0, 6, meta, new_x="LMARGIN", new_y="NEXT", align="L")
        
        self.line(self.get_x(), self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(153, 153, 153)
        self.line(self.get_x(), self.get_y() - 2, self.w - self.r_margin, self.get_y() - 2)
        self.cell(0, 10, "CONFIDENCIAL - Datia Intelligence Engine", align="L")
        self.set_x(self.l_margin)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="R")

class PDFService:
    @staticmethod
    def _should_landscape(raw_data: dict) -> bool:
        try:
            if not isinstance(raw_data, dict):
                return False
            payload = raw_data.get("payload") if isinstance(raw_data, dict) else {}
            if not isinstance(payload, dict):
                payload = {}
            tables = []
            if isinstance(payload.get("tables"), list):
                tables = payload.get("tables") or []
            elif isinstance(payload.get("table"), dict):
                tables = [payload.get("table")]
            max_cols = 0
            for t in tables:
                cols = (t or {}).get("columns") if isinstance(t, dict) else None
                if isinstance(cols, list):
                    max_cols = max(max_cols, len(cols))
            return max_cols >= 10
        except Exception:
            return False

    @staticmethod
    def generate_pdf_from_html(html_content: str, title: str = "Informe", empresa_id: int = None, ejercicio: int = None, raw_data: dict = None) -> bytes:
        try:
            safe_html = PDFService._sanitize_html_for_core_fonts(html_content)
            
            orientation = "L" if PDFService._should_landscape(raw_data or {}) else "P"
            pdf = ProReportPDF(title=title, empresa_id=empresa_id, ejercicio=ejercicio, orientation=orientation)
            pdf.set_auto_page_break(auto=True, margin=20)
            pdf.set_margins(left=20, top=20, right=20)
            pdf.alias_nb_pages()
            pdf.add_page()
            pdf.set_font("helvetica", size=10)
            pdf.write_html(safe_html)

            images = PDFService._build_images(raw_data or {})
            if images:
                for img in images:
                    title_img = str(img.get("title") or "").strip()
                    data = img.get("data")
                    if not data:
                        continue
                    try:
                        data.seek(0)
                    except Exception:
                        pass
                    pdf.add_page()
                    if title_img:
                        pdf.set_font("helvetica", "B", 10)
                        pdf.multi_cell(0, 6, title_img)
                        pdf.ln(1)
                    max_w = pdf.w - pdf.l_margin - pdf.r_margin
                    pdf.image(data, x=pdf.l_margin, w=max_w)
                    pdf.ln(4)
            
            raw = pdf.output(dest="S")
            if isinstance(raw, (bytes, bytearray)):
                return bytes(raw)
            return str(raw or "").encode("latin1", "ignore")
            
        except Exception as e:
            logger.error(f"Error generando PDF con fpdf2: {e}", exc_info=True)
            return b""

    @staticmethod
    def _sanitize_html_for_core_fonts(html: str) -> str:
        s = str(html or "")
        s = s.replace("\u00a0", " ")
        replacements = {
            "€": " EUR",
            "–": "-",
            "—": "-",
            "−": "-",
            "·": " - ",
            "•": " - ",
            "…": "...",
            "“": "\"",
            "”": "\"",
            "„": "\"",
            "’": "'",
            "‘": "'",
            "´": "'",
            "→": "->",
            "⇒": "->",
            "≤": "<=",
            "≥": ">=",
            "≠": "!=",
            "×": "x",
            "Δ": "Delta ",
        }
        for k, v in replacements.items():
            s = s.replace(k, v)
        return s.encode("latin1", errors="ignore").decode("latin1")

    @staticmethod
    def _build_images(raw_data: dict):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception:
            return []

        payload = (raw_data or {}).get("payload") if isinstance(raw_data, dict) else {}
        if not isinstance(payload, dict):
            payload = {}

        out = []

        def _title_from_cfg(cfg: dict) -> str:
            try:
                return (
                    ((cfg.get("options") or {}).get("plugins") or {}).get("title") or {}
                ).get("text") or ""
            except Exception:
                return ""

        def _render_chart_cfg(cfg: dict, fallback_title: str = ""):
            if not isinstance(cfg, dict):
                return None
            ctype = str(cfg.get("type") or "").lower().strip()
            data = cfg.get("data") or {}
            if not isinstance(data, dict):
                return None
            labels = data.get("labels") or []
            datasets = data.get("datasets") or []
            if not isinstance(labels, list) or not isinstance(datasets, list) or not labels or not datasets:
                return None

            title = _title_from_cfg(cfg) or fallback_title
            buf = io.BytesIO()

            try:
                if ctype == "pie":
                    ds0 = datasets[0] if datasets else {}
                    vals = ds0.get("data") or []
                    if not isinstance(vals, list) or not vals:
                        return None
                    plt.figure(figsize=(7.2, 3.2))
                    plt.pie([float(v or 0) for v in vals], labels=[str(x) for x in labels], autopct="%1.1f%%", textprops={"fontsize": 8})
                    if title:
                        plt.title(title)
                    plt.tight_layout()
                    plt.savefig(buf, format="png", dpi=190, bbox_inches="tight", pad_inches=0.12, facecolor="white")
                    plt.close()
                    buf.seek(0)
                    return {"title": title, "data": buf}

                if ctype in ("line", "bar"):
                    plt.figure(figsize=(7.2, 3.2 if len(labels) <= 10 else 3.6))
                    x = list(range(len(labels)))

                    if ctype == "line":
                        for ds in datasets[:4]:
                            if not isinstance(ds, dict):
                                continue
                            y = ds.get("data") or []
                            if not isinstance(y, list):
                                continue
                            plt.plot(x, [float(v or 0) for v in y], label=str(ds.get("label") or ""), linewidth=1.8)
                    else:
                        width = 0.8 / max(1, min(4, len(datasets)))
                        offsets = []
                        m = min(4, len(datasets))
                        start = -((m - 1) / 2.0) * width
                        for i in range(m):
                            offsets.append(start + i * width)
                        for i, ds in enumerate(datasets[:4]):
                            if not isinstance(ds, dict):
                                continue
                            y = ds.get("data") or []
                            if not isinstance(y, list):
                                continue
                            xo = [xi + offsets[i] for xi in x]
                            plt.bar(xo, [float(v or 0) for v in y], width=width, label=str(ds.get("label") or ""))

                    if title:
                        plt.title(title)
                    if any(str((ds or {}).get("label") or "").strip() for ds in datasets[:4]):
                        plt.legend(loc="best", fontsize=8)
                    plt.grid(True, alpha=0.2)
                    plt.xticks(x, [str(s) for s in labels], rotation=45 if len(labels) > 6 else 0, ha="right" if len(labels) > 6 else "center")
                    plt.tight_layout()
                    plt.savefig(buf, format="png", dpi=190, bbox_inches="tight", pad_inches=0.12, facecolor="white")
                    plt.close()
                    buf.seek(0)
                    return {"title": title, "data": buf}

            except Exception:
                try:
                    plt.close()
                except Exception:
                    pass
                return None

            return None

        evolution = payload.get("evolution") if isinstance(payload, dict) else None
        if isinstance(evolution, dict):
            labels = evolution.get("labels") or []
            cy = evolution.get("cy") or {}
            ingresos = cy.get("ingresos") or []
            gastos = cy.get("gastos") or []
            ebitda = cy.get("ebitda") or []
            if labels and (ingresos or gastos or ebitda):
                buf = io.BytesIO()
                plt.figure(figsize=(7.2, 3.0))
                try:
                    x = list(range(len(labels)))
                    if ingresos:
                        plt.plot(x, [float(v or 0) for v in ingresos], label="Ingresos", linewidth=1.8, color="#2563eb")
                    if gastos:
                        plt.plot(x, [float(v or 0) for v in gastos], label="Gastos", linewidth=1.8, color="#ef4444")
                    if ebitda:
                        plt.plot(x, [float(v or 0) for v in ebitda], label="EBITDA", linewidth=1.8, color="#10b981")
                    plt.xticks(x, [str(s) for s in labels], rotation=45, ha="right")
                    plt.title("Evolución mensual")
                    plt.grid(True, alpha=0.2)
                    plt.legend(loc="upper left", fontsize=8)
                    plt.tight_layout()
                    plt.savefig(buf, format="png", dpi=170)
                    plt.close()
                    buf.seek(0)
                    out.append({"title": "Evolución mensual (Ingresos / Gastos / EBITDA)", "data": buf})
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        rankings = payload.get("rankings") if isinstance(payload, dict) else None
        if isinstance(rankings, dict):
            clients = rankings.get("clients") or []
            items = [(str(i.get("name") or ""), float(i.get("value") or 0)) for i in clients if isinstance(i, dict)]
            items = [(n, v) for (n, v) in items if n]
            items = sorted(items, key=lambda x: x[1], reverse=True)[:10]
            if items:
                buf = io.BytesIO()
                plt.figure(figsize=(7.2, 3.4))
                try:
                    names = [n for (n, _) in items][::-1]
                    vals = [v for (_, v) in items][::-1]
                    plt.barh(names, vals, color="#60a5fa")
                    plt.title("Top clientes (importe)")
                    plt.grid(True, axis="x", alpha=0.2)
                    plt.tight_layout()
                    plt.savefig(buf, format="png", dpi=170)
                    plt.close()
                    buf.seek(0)
                    out.append({"title": "Top clientes (importe)", "data": buf})
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        top_products = payload.get("top_products") if isinstance(payload, dict) else None
        if isinstance(top_products, list):
            items = [(str(i.get("name") or ""), float(i.get("value") or 0)) for i in top_products if isinstance(i, dict)]
            items = [(n, v) for (n, v) in items if n]
            items = sorted(items, key=lambda x: x[1], reverse=True)[:10]
            if items:
                buf = io.BytesIO()
                plt.figure(figsize=(7.2, 3.4))
                try:
                    names = [n for (n, _) in items][::-1]
                    vals = [v for (_, v) in items][::-1]
                    plt.barh(names, vals, color="#a78bfa")
                    plt.title("Top productos (importe)")
                    plt.grid(True, axis="x", alpha=0.2)
                    plt.tight_layout()
                    plt.savefig(buf, format="png", dpi=170)
                    plt.close()
                    buf.seek(0)
                    out.append({"title": "Top productos (importe)", "data": buf})
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        per100 = payload.get("per100") if isinstance(payload, dict) else None
        if isinstance(per100, dict) and (per100.get("status") == "ok"):
            parts = ((per100.get("cy") or {}).get("parts") or [])
            items = [(str(p.get("key") or ""), float(p.get("pct") or 0)) for p in parts if isinstance(p, dict)]
            items = [(k, v) for (k, v) in items if k]
            if items:
                buf = io.BytesIO()
                plt.figure(figsize=(7.2, 2.6))
                try:
                    labels = [k for (k, _) in items]
                    vals = [v for (_, v) in items]
                    plt.bar(labels, vals, color="#22c55e")
                    plt.title("Por cada 100 EUR de ventas")
                    plt.xticks(rotation=30, ha="right")
                    plt.ylabel("%")
                    plt.grid(True, axis="y", alpha=0.2)
                    plt.tight_layout()
                    plt.savefig(buf, format="png", dpi=170)
                    plt.close()
                    buf.seek(0)
                    out.append({"title": "Por cada 100 EUR de ventas", "data": buf})
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        charts_candidates = [
            ("chart_config", "Gráfico principal"),
            ("chart_pareto_clients", "Distribución (clientes)"),
            ("chart_pareto_products", "Distribución (productos)"),
            ("chart_pareto", "Distribución (top)"),
            ("chart_concentration", "Concentración"),
            ("chart_banks", "Bancos"),
            ("chart_pareto_suppliers", "Distribución (proveedores)"),
        ]
        for key, fallback_title in charts_candidates:
            if len(out) >= 4:
                break
            img = _render_chart_cfg(payload.get(key), fallback_title=fallback_title)
            if img:
                out.append(img)

        return out[:4]
