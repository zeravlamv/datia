
import time
from datia.services.financial_service import FinancialService

def profile():
    try:
        svc = FinancialService()
        empresa = 1
        ejercicio = 2025
        
        print("--- START PROFILE ---")
        
        t0 = time.time()
        svc.get_snapshot(empresa, ejercicio)
        print(f"Snapshot: {time.time()-t0:.4f}s")
        
        t0 = time.time()
        svc.get_pl_report(empresa, ejercicio)
        print(f"PL Report: {time.time()-t0:.4f}s")
        
        t0 = time.time()
        svc.get_balance_summary(empresa, ejercicio)
        print(f"Balance: {time.time()-t0:.4f}s")
        
        t0 = time.time()
        try:
            svc.get_treasury_snapshot(empresa, ejercicio)
            print(f"Treasury Snap: {time.time()-t0:.4f}s")
        except Exception as e: 
            print(f"Treasury Snap: Error {e}")

        t0 = time.time()
        try:
            svc.get_treasury_forecast(empresa, ejercicio, months=3)
            print(f"Treasury Forecast: {time.time()-t0:.4f}s")
        except Exception as e:
            print(f"Treasury Forecast: Error {e}")

        t0 = time.time()
        try:
            svc.get_quarterly_report(empresa, ejercicio)
            print(f"Quarterly: {time.time()-t0:.4f}s")
        except Exception as e:
            print(f"Quarterly: Error {e}")
            
        t0 = time.time()
        try:
            svc.get_advanced_analysis(empresa, ejercicio)
            print(f"Advanced Analysis: {time.time()-t0:.4f}s")
        except Exception as e:
            print(f"Advanced: Error {e}")

    except Exception as e:
        print(f"Main Error: {e}")

profile()
