import numpy as np
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class AnalysisService:
    """
    Service responsible for advanced data analysis:
    - Anomaly Detection (Z-Score / IQR)
    - Trend Analysis & Forecasting (Linear Regression)
    - Strategic Segmentation (Pareto ABC)
    """

    @staticmethod
    def detect_anomalies(series: List[float], method: str = 'zscore', threshold: float = 2.0) -> List[Dict[str, Any]]:
        """
        Detects anomalies in a time series.
        Returns a list of detected anomalies with index and severity.
        """
        if not series or len(series) < 3:
            return []

        anomalies = []
        data = np.array(series)

        if method == 'zscore':
            mean = np.mean(data)
            std = np.std(data)
            
            if std == 0:
                return []

            z_scores = (data - mean) / std
            
            for i, score in enumerate(z_scores):
                if abs(score) > threshold:
                    anomalies.append({
                        'index': i,
                        'value': float(data[i]),
                        'score': float(score),
                        'type': 'spike' if score > 0 else 'drop',
                        'severity': 'high' if abs(score) > 3 else 'medium'
                    })
        
        return anomalies

    @staticmethod
    def calculate_trend(series: List[float]) -> Dict[str, Any]:
        """
        Calculates simple linear trend.
        """
        if not series or len(series) < 2:
            return {'slope': 0, 'direction': 'flat'}

        n = len(series)
        x = np.arange(n)
        y = np.array(series)
        
        # Linear Regression (y = mx + c)
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        
        direction = 'stable'
        if m > 0.05 * np.mean(y): direction = 'growing'
        elif m < -0.05 * np.mean(y): direction = 'declining'

        return {
            'slope': float(m),
            'intercept': float(c),
            'direction': direction,
            'prediction_next': float(m * n + c)
        }

    @staticmethod
    def segment_pareto(items: List[Dict[str, Any]], value_key: str = 'total') -> Dict[str, List[Dict[str, Any]]]:
        """
        Segments items into A (Top 80%), B (Next 15%), C (Bottom 5%).
        Expects list of dicts with 'value_key'.
        """
        if not items:
            return {'A': [], 'B': [], 'C': []}

        # Sort descending
        sorted_items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)
        total_value = sum(item.get(value_key, 0) for item in sorted_items)
        
        if total_value == 0:
             return {'A': [], 'B': [], 'C': sorted_items}

        segments = {'A': [], 'B': [], 'C': []}
        accumulated = 0
        
        for item in sorted_items:
            val = item.get(value_key, 0)
            accumulated += val
            pct = accumulated / total_value
            
            if pct <= 0.80:
                segments['A'].append(item)
            elif pct <= 0.95:
                segments['B'].append(item)
            else:
                segments['C'].append(item)
                
        return segments

    @staticmethod
    def generate_recommendations(kpis: Dict[str, float], trends: Dict[str, Any]) -> List[str]:
        """
        Generates strategic recommendations based on financial KPIs and Trends.
        """
        recs = []
        
        # Margin Analysis
        margin = kpis.get('margin', 0)
        if margin < 10:
            recs.append("⚠️ **Alerta de Rentabilidad**: El margen es crítico (<10%). Revisar política de precios o costes de proveedores inmediatamente.")
        elif margin < 25:
            recs.append("📉 **Optimización de Margen**: Margen saludable pero mejorable. Enfocar ventas en productos de Categoría A (Pareto).")
            
        # Growth Analysis
        growth = kpis.get('growth_pct', 0)
        if growth < 0:
            recs.append("🔻 **Acción Comercial**: Ventas en declive. Activar campañas de reactivación de clientes inactivos.")
        elif growth > 20:
            recs.append("🚀 **Gestión de Crecimiento**: Crecimiento acelerado. Vigilar stock y flujo de caja para soportar la demanda.")

        # Trend Direction
        if trends.get('sales_trend', {}).get('direction') == 'declining':
            recs.append("📉 **Tendencia Negativa**: La tendencia lineal de ventas es negativa. Investigar estacionalidad o pérdida de cuota.")

        return recs
