
import logging
from typing import List, Dict, Any
import math

logger = logging.getLogger(__name__)

class PredictionService:
    """
    Service for generating simple forecasts based on historical data.
    """

    @staticmethod
    def forecast(rows: List[Dict], target_year: int) -> List[Dict]:
        """
        Generates forecasted rows for the target year based on historical data in 'rows'.
        Assumes 'rows' contains monthly data with 'val' (metric) and 'label' (month).
        """
        if not rows:
            return []

        # 1. Organize data by Month and Year
        # We expect rows to have 'label' (1-12) and 'val'.
        # We need to know which year each row belongs to. 
        # The current SQL might aggregate multiple years if we use IN (2024, 2025) but usually groups by month.
        # If the SQL groups by Month ONLY, it sums up all years? No, that would be bad for trend.
        # We need the SQL to group by Year, Month OR we need to infer trend from the aggregated 'prev' columns.
        
        # Scenario A: The SQL returns data for Previous Year in 'val_prev'.
        # This is common in our current 'Yearly Overview' logic.
        # If so, we have Year X (val) and Year X-1 (val_prev).
        # We can calculate trend.
        
        # Scenario B: The SQL returns raw rows for multiple years.
        # We need to group them.
        
        # Let's assume Scenario A for now as it fits the current 'Yearly Overview' pattern.
        # If we forced the query to be for 'target_year - 1' (e.g. 2025), 
        # then 'val' is 2025 and 'val_prev' is 2024.
        # We want to predict 2026.
        
        forecasted_rows = []
        
        for row in rows:
            try:
                val_last_year = float(row.get('val', 0) or 0)       # e.g. 2025
                val_prev_year = float(row.get('val_prev', 0) or 0)  # e.g. 2024
                
                # Simple Linear Projection
                # Trend = (Last - Prev)
                # Next = Last + Trend
                
                # Damping factor to be conservative (0.8)
                trend = (val_last_year - val_prev_year) * 0.8
                
                # Avoid extreme negative trends if valuable
                if val_last_year > 0 and (val_last_year + trend) < 0:
                    predicted_val = val_last_year * 0.9 # Fallback to -10% if trend is too negative
                else:
                    predicted_val = val_last_year + trend
                
                # Create a new row for the forecast
                # We won't append it to 'rows' directly because that would confuse the Table renderer (maybe).
                # Instead, we return a list of predicted values to be added as a new dataset.
                
                forecasted_rows.append({
                    'mes': row.get('mes') or row.get('label'), # Month index
                    'val': predicted_val,
                    'year': target_year
                })
                
            except Exception as e:
                logger.warning(f"Prediction error for row {row}: {e}")
                continue
                
        return forecasted_rows

    @staticmethod
    def calculate_regression(values_x: List[float], values_y: List[float], target_x: float) -> float:
        """
        Simple Linear Regression: y = mx + c
        """
        n = len(values_x)
        if n < 2:
            return values_y[0] if n > 0 else 0
            
        sum_x = sum(values_x)
        sum_y = sum(values_y)
        sum_xy = sum(x*y for x,y in zip(values_x, values_y))
        sum_xx = sum(x*x for x in values_x)
        
        denominator = (n * sum_xx - sum_x * sum_x)
        if denominator == 0:
            return sum_y / n
            
        m = (n * sum_xy - sum_x * sum_y) / denominator
        c = (sum_y - m * sum_x) / n
        
        return m * target_x + c
