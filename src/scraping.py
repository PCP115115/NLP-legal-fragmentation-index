# src/scraping.py

import os
import time
import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# --- CONFIGURACIÓN DEL PROYECTO ---
BASE_DIR = Path(__file__).resolve().parent.parent 
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
LOG_DIR = BASE_DIR / "logs"

# Rango
START_YEAR = 2010
END_YEAR = 2026

# Mapeo inicial (el script descubrirá los códigos numéricos reales)
NOMBRES_CARPETAS = {
    'Andalucía': 'Andalucia', 'Aragón': 'Aragon', 'Asturias': 'Asturias',
    'Balears': 'Baleares', 'Canarias': 'Canarias', 'Cantabria': 'Cantabria',
    'Castilla-La Mancha': 'CastillaLaMancha', 'Castilla y León': 'CastillaLeon',
    'Cataluña': 'Cataluna', 'Extremadura': 'Extremadura', 'Galicia': 'Galicia',
    'Madrid': 'Madrid', 'Murcia': 'Murcia', 'Navarra': 'Navarra',
    'País Vasco': 'PaisVasco', 'Rioja': 'LaRioja', 'Comunitat Valenciana': 'Valencia'
}

# --- CONFIGURACIÓN DE CAMUFLAJE (HEADER REAL DE CHROME) ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# --- LOGGING ---
if not LOG_DIR.exists(): LOG_DIR.mkdir(parents=True)
logging.basicConfig(
    filename=LOG_DIR / f"scraping_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    level=logging.INFO, format='%(asctime)s - %(message)s', encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

# --- SESIÓN GLOBAL (IMPORTANTE PARA COOKIES) ---
session = requests.Session()
session.headers.update(HEADERS)

def discover_boe_codes():
    """Fase 0: Obtener códigos numéricos del formulario avanzado"""
    logging.info("🕵️  Detectando códigos de comunidades...")
    url = "https://www.boe.es/buscar/legislacion_ava.php"
    
    try:
        r = session.get(url, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Buscamos el selector del campo 'Departamento/Origen' (dato[5])
        select = soup.find('select', attrs={'name': 'dato[5]'})
        if not select: return {}

        found = {}
        for opt in select.find_all('option'):
            txt = opt.text.strip()
            val = opt.get('value')
            if not val: continue
            
            # Cruzamos con nuestro diccionario de nombres limpios
            for key_boe, folder in NOMBRES_CARPETAS.items():
                if key_boe.lower() in txt.lower():
                    found[val] = folder
                    break
        return found
    except Exception as e:
        logging.error(f"Error autodescubrimiento: {e}")
        return {}

def get_boe_ids_for_month(year, month, region_code):
    """Busca leyes y extrae IDs"""
    url = "https://www.boe.es/buscar/legislacion_ava.php"
    
    # Parámetros exactos que funcionaron en tu navegador
    params = {
        'campo[0]': 'ID_SRC',  'dato[0]': '2', 'operador[0]': 'and', # Autonómico
        'campo[1]': 'NOVIGENTE', 'operador[1]': 'and',               # Histórico incluido
        'campo[2]': 'CONSO', 'operador[3]': 'and',                   # Consolidado (filtra basura)
        'campo[5]': 'ID_DEMS', 'dato[5]': region_code, 'operador[5]': 'and', # CÓDIGO REGION
        'campo[11]': 'FPU', 'dato[11][0]': f"{year}-{month:02d}-01", 
                            'dato[11][1]': f"{year}-{month:02d}-31", 'operador[12]': 'and',
        'page_hits': '200', 'accion': 'Buscar'
    }

    try:
        r = session.get(url, params=params, timeout=15)
        
        # Si no hay resultados, el BOE suele devolver la misma página con un mensaje
        if "No se han encontrado resultados" in r.text:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        ids = set()
        
        # Estrategia "red de arrastre": Busca cualquier link con ID BOE en los resultados
        for item in soup.select('li.resultado-busqueda'):
            for link in item.find_all('a', href=True):
                if "id=BOE-A-" in link['href']:
                    # Extraer ID limpio
                    try:
                        clean_id = link['href'].split("id=")[1].split("&")[0]
                        ids.add(clean_id)
                    except: pass
        
        return list(ids)

    except Exception as e:
        logging.error(f"Error buscando {region_code}: {e}")
        return []

def download_xml(boe_id, path):
    """Descarga el XML"""
    url = f"https://www.boe.es/diario_boe/xml.php?id={boe_id}"
    try:
        r = session.get(url, timeout=20)
        if r.status_code == 200 and b"<texto" in r.content:
            with open(path, 'wb') as f:
                f.write(r.content)
            return True
        return False
    except: return False

def run_scraper():
    logging.info("🚀 INICIANDO SCRAPING MASIVO (2010-2026)")
    
    # 1. Mapa de códigos
    regiones = discover_boe_codes()
    if not regiones:
        logging.error("❌ Fallo crítico obteniendo códigos.")
        return
    
    logging.info(f"✅ Identificadas {len(regiones)} regiones. Empezando descarga...")
    
    total = 0
    # 2. Bucle temporal
    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            # No ir al futuro
            if year == datetime.now().year and month > datetime.now().month: break
            
            logging.info(f"📅 Procesando: {month:02d}/{year}")
            
            for code, folder in regiones.items():
                # Buscar
                ids = get_boe_ids_for_month(year, month, code)
                
                if not ids: continue
                
                # Crear carpeta
                dest_dir = RAW_DATA_DIR / str(year) / f"{month:02d}" / folder
                if not dest_dir.exists(): dest_dir.mkdir(parents=True)
                
                # Descargar
                for boe_id in ids:
                    fpath = dest_dir / f"{boe_id}.xml"
                    if fpath.exists(): continue
                    
                    if download_xml(boe_id, fpath):
                        total += 1
                        time.sleep(0.1) # Pequeña pausa
                
                time.sleep(0.2) # Pausa entre comunidades

    logging.info(f"🏁 FIN. Total descargados: {total}")

if __name__ == "__main__":
    run_scraper()