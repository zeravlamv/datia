import json
from typing import Any, Dict, List, Optional


def build_monthly_financial_option(
    *,
    title: str,
    labels: List[str],
    ingresos: List[float],
    gastos: List[float],
    ebitda: Optional[List[float]] = None,
    series_suffix: str = "€",
) -> Dict[str, Any]:
    try:
        from pyecharts import options as opts
        from pyecharts.charts import Bar, Line

        bar = (
            Bar(init_opts=opts.InitOpts(bg_color="transparent", animation_opts=opts.AnimationOpts(animation=True)))
            .add_xaxis(labels)
            .add_yaxis("Ingresos", ingresos, category_gap="40%")
            .add_yaxis("Gastos", gastos, category_gap="40%")
        )

        bar.set_global_opts(
            title_opts=opts.TitleOpts(title=title, pos_left="center"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="shadow"),
            legend_opts=opts.LegendOpts(pos_top="2%"),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-30)),
            yaxis_opts=opts.AxisOpts(
                axislabel_opts=opts.LabelOpts(formatter=f"{{value}}{series_suffix}"),
                splitline_opts=opts.SplitLineOpts(is_show=True),
            ),
            grid_opts=opts.GridOpts(left="5%", right="5%", top="15%", bottom="10%", contain_label=True),
        )

        if ebitda is not None:
            line = Line().add_xaxis(labels).add_yaxis("EBITDA", ebitda, is_smooth=True, symbol="circle", symbol_size=6)
            bar.overlap(line)

        return json.loads(bar.dump_options_with_quotes())
    except Exception:
        series = [
            {"name": "Ingresos", "type": "bar", "data": ingresos, "smooth": True, "barMaxWidth": 60},
            {"name": "Gastos", "type": "bar", "data": gastos, "smooth": True, "barMaxWidth": 60},
        ]
        if ebitda is not None:
            series.append({"name": "EBITDA", "type": "line", "data": ebitda, "smooth": True, "symbol": "circle", "symbolSize": 6})
        return {
            "backgroundColor": "transparent",
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": 0},
            "grid": {"left": "5%", "right": "5%", "bottom": "8%", "top": "12%", "containLabel": True},
            "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": -30, "interval": 0}},
            "yAxis": {
                "type": "value",
                "axisLabel": {"formatter": f"{{value}}{series_suffix}"},
                "splitLine": {"show": True},
            },
            "series": series,
        }

