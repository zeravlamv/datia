# -*- coding: utf-8 -*-
import pathlib
import os
import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import seaborn as sns
from dotenv import load_dotenv

# Cargar variables desde .env
env_path = pathlib.Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

# Configuración MSSQL
driver = os.getenv('MSSQL_DRIVER', '{ODBC Driver 18 for SQL Server}')
host = os.getenv('MSSQL_HOST', 'localhost')
port = os.getenv('MSSQL_PORT', '1433')
user = os.getenv('MSSQL_USER', '')
password = os.getenv('MSSQL_PASSWORD', '')
database = os.getenv('MSSQL_NAME', '')

if user and password:
    auth_part = f"UID={user};PWD={password};"
else:
    auth_part = "Trusted_Connection=yes;"

driver_part = driver if driver.startswith('{') else f"{{{driver}}}"
CONN_STR = f"DRIVER={driver_part};SERVER={host},{port};DATABASE={database};{auth_part}Encrypt=no;TrustServerCertificate=yes;"

# Rutas de salida
BASE_STATIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datia", "static"))
IMG_DIR = os.path.join(BASE_STATIC, "images")
VID_DIR = os.path.join(BASE_STATIC, "videos")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(VID_DIR, exist_ok=True)

IMG_PATH = os.path.join(IMG_DIR, "gastos_ingresos.png")
VID_PATH = os.path.join(VID_DIR, "gastos_ingresos_evolucion.mp4")
GIF_PATH = os.path.join(VID_DIR, "gastos_ingresos_evolucion.gif")

def fetch_data(conn_str: str) -> pd.DataFrame:
    query = """
    SELECT Ejercicio AS Año,
           NumeroPeriodo AS Mes,
           SUM(CASE WHEN CodigoCuenta LIKE '6%' THEN (DebeAcum - HaberAcum) ELSE 0 END) AS Gasto,
           SUM(CASE WHEN CodigoCuenta LIKE '7%' THEN (HaberAcum - DebeAcum) ELSE 0 END) AS Ingreso
    FROM AcumuladosConta
    WHERE NumeroPeriodo BETWEEN 1 AND 12
    GROUP BY Ejercicio, NumeroPeriodo
    ORDER BY Año, Mes;
    """
    with pyodbc.connect(conn_str) as cnxn:
        df = pd.read_sql(query, cnxn)
    df['Periodo'] = df.apply(lambda r: f"{int(r['Año'])}-{int(r['Mes']):02d}", axis=1)
    return df

def plot_static(df: pd.DataFrame, out_path: str):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 6), facecolor='none')
    ax.set_facecolor('none')
    
    width = 0.35
    x = range(len(df))
    
    # Colores vibrantes para modo oscuro
    ax.bar([i - width/2 for i in x], df['Gasto'], width=width, label='Gasto', color='#ff453a', alpha=0.8)
    ax.bar([i + width/2 for i in x], df['Ingreso'], width=width, label='Ingreso', color='#34d399', alpha=0.8)
    
    ax.set_xticks(x)
    ax.set_xticklabels(df['Periodo'], rotation=45, ha='right', color='#a1a1aa')
    ax.tick_params(axis='y', colors='#a1a1aa')
    
    ax.set_ylabel('Importe', color='#e4e4e7', fontsize=10)
    ax.set_title('Evolución de Gastos e Ingresos por Periodo', color='#e4e4e7', fontsize=14, pad=20)
    
    legend = ax.legend(facecolor='#18181b', edgecolor='#3f3f46')
    plt.setp(legend.get_texts(), color='#e4e4e7')
    
    # Limpiar bordes (spines)
    for spine in ax.spines.values():
        spine.set_edgecolor('#3f3f46')
        spine.set_alpha(0.3)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, transparent=True)
    plt.close()

def animate(df: pd.DataFrame, out_path: str, writer='ffmpeg'):
    plt.style.use('dark_background')
    # Para el GIF usamos un fondo sólido que coincida con el tema, 
    # ya que la transparencia en GIFs animados con Pillow es problemática.
    bg_color = '#18181b'
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=bg_color)
    ax.set_facecolor(bg_color)
    
    width = 0.35
    x = range(len(df))
    
    def update(frame):
        ax.clear()
        ax.set_facecolor(bg_color)
        sub = df.iloc[:frame+1]
        xi = range(len(sub))
        
        ax.bar([i - width/2 for i in xi], sub['Gasto'], width=width, label='Gasto', color='#ff453a', alpha=0.9)
        ax.bar([i + width/2 for i in xi], sub['Ingreso'], width=width, label='Ingreso', color='#34d399', alpha=0.9)
        
        ax.set_xticks(xi)
        ax.set_xticklabels(sub['Periodo'], rotation=45, ha='right', color='#a1a1aa')
        ax.tick_params(axis='y', colors='#a1a1aa')
        
        ax.set_ylabel('Importe', color='#e4e4e7')
        ax.set_xlim(-1, len(df))
        ax.set_title(f'Evolución hasta {sub.iloc[-1]["Periodo"]}', color='#e4e4e7', fontsize=14)
        
        legend = ax.legend(facecolor='#27272a', edgecolor='#3f3f46')
        plt.setp(legend.get_texts(), color='#e4e4e7')
        
        for spine in ax.spines.values():
            spine.set_edgecolor('#3f3f46')
            spine.set_alpha(0.3)
            
        return []

    anim = FuncAnimation(fig, update, frames=len(df), blit=False, repeat=True)
    
    save_args = {'fps': 2}
    if writer == 'pillow':
        # Eliminamos transparencia para mayor compatibilidad en el GIF animado
        save_args['savefig_kwargs'] = {'transparent': False, 'facecolor': bg_color}
    else:
        save_args['codec'] = 'libx264'
        
    anim.save(out_path, writer=writer, **save_args)
    plt.close()

def main():
    print("Conectando a la base de datos...")
    try:
        df = fetch_data(CONN_STR)
    except Exception as e:
        print(f"Error al obtener datos: {e}")
        return

    if df.empty:
        print("No se encontraron datos.")
        return

    print(f"Datos obtenidos: {len(df)} periodos.")
    if len(df) > 24:
        print("Limitando a los últimos 24 meses...")
        df = df.tail(24).copy()

    print("Generando gráfico estático...")
    plot_static(df, IMG_PATH)
    print(f"Imagen guardada en {IMG_PATH}")
    
    print("Generando animación...")
    try:
        animate(df, VID_PATH, writer='ffmpeg')
        print(f"Video guardado en {VID_PATH}")
    except Exception as e:
        print(f"Fallo generación MP4 (ffmpeg no disponible). Intentando GIF...")
        try:
            animate(df, GIF_PATH, writer='pillow')
            print(f"GIF guardado en {GIF_PATH}")
        except Exception as e2:
            print(f"No se pudo generar animación: {e2}")

if __name__ == "__main__":
    main()
