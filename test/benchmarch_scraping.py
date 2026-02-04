import time
import sys
import shutil
from pathlib import Path

# --- CONFIGURACIÓN DE IMPORTACIÓN ---
# Añadimos la raíz del proyecto para poder importar 'src'
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from src import scraping

def run_benchmark():
    print("="*70)
    print("🚀 INICIANDO BENCHMARK DE RENDIMIENTO 2.0 (MODO AVANZADO)")
    print("="*70)
    print("Objetivo: Simular descarga de 1 MES (Enero 2023) usando la nueva lógica.")
    print("Esto validará que los códigos de comunidades y las URLs son correctos.")
    print("-" * 70)

    # 1. Preparar carpeta temporal
    bench_dir = BASE_DIR / "data" / "benchmark_temp"
    if bench_dir.exists():
        shutil.rmtree(bench_dir)
    bench_dir.mkdir(parents=True)

    # Variables de medición
    year_bench = 2023
    month_bench = 1
    total_files = 0
    
    # --- FASE 1: AUTODESCUBRIMIENTO ---
    print("\n[FASE 1] Autodescubriendo códigos de Comunidades Autónomas...")
    t0_disc = time.time()
    
    # Llamamos a la nueva función del script principal
    mapa_regiones = scraping.discover_boe_codes()
    
    if not mapa_regiones:
        print("❌ ERROR CRÍTICO: No se pudieron detectar regiones. Revisa tu conexión o el script principal.")
        return

    print(f"✅ Detectadas {len(mapa_regiones)} regiones en {time.time() - t0_disc:.2f}s.")
    print("-" * 70)

    # --- FASE 2: DESCARGA ---
    print("\n[FASE 2] Descargando leyes de prueba (Enero 2023)...")
    start_time = time.time()

    for code, region_name in mapa_regiones.items():
        print(f"  > {region_name:<20} | Código BOE: {code:<5} ... ", end="", flush=True)
        
        # Búsqueda
        t0_search = time.time()
        ids = scraping.get_boe_ids_for_month(year_bench, month_bench, code)
        t1_search = time.time()
        
        if not ids:
            print(f"[0 leyes] ({t1_search - t0_search:.2f}s)")
            continue

        print(f"[{len(ids)} leyes] -> ", end="", flush=True)

        # Crear carpeta destino temporal
        region_dir = bench_dir / region_name
        region_dir.mkdir(parents=True, exist_ok=True)

        # Descarga
        for boe_id in ids:
            file_path = region_dir / f"{boe_id}.xml"
            
            # --- CORRECCIÓN AQUÍ: Usamos 'download_xml' en vez de 'download_xml_by_id' ---
            success = scraping.download_xml(boe_id, file_path)
            
            if success:
                print(".", end="", flush=True)
                total_files += 1
                # Pausa para simular condición real
                time.sleep(0.1) 
        
        print(" OK")
        # Pausa entre comunidades
        time.sleep(0.2)

    end_time = time.time()
    duration = end_time - start_time

    # --- FASE 3: RESULTADOS ---
    # Total meses aprox (2010 - Feb 2026) -> ~194 meses
    TOTAL_MESES_PROYECTO = (2026 - 2010) * 12 + 2 
    
    print("\n" + "="*70)
    print("📊 RESULTADOS DEL BENCHMARK")
    print("="*70)
    
    if total_files > 0:
        avg_speed = duration / total_files
        estimacion_segundos = duration * TOTAL_MESES_PROYECTO
        estimacion_horas = estimacion_segundos / 3600
        
        print(f"✅ ÉXITO: Se han descargado archivos XML reales.")
        print(f"Archivos descargados (1 mes): {total_files}")
        print(f"Tiempo real transcurrido:     {duration:.2f} segundos ({duration/60:.2f} min)")
        print(f"Velocidad promedio:           {avg_speed:.2f} seg/archivo")
        print("-" * 70)
        print(f"ESTIMACIÓN PARA TODO EL PROYECTO (16 AÑOS):")
        print(f"🕒 {estimacion_horas:.2f} HORAS aproximadamente.")
    else:
        print("⚠️ ALERTA: No se descargó ningún archivo.")
        print("Posibles causas: Internet caído, fallo en lógica de IDs, o mes sin leyes.")
    
    print("="*70)
    print(f"Los datos descargados están en: {bench_dir}")
    print("Revisa esa carpeta para asegurar que son XML válidos.")

if __name__ == "__main__":
    run_benchmark()