import pandas as pd
import requests
from pymongo import MongoClient
from time import sleep
from tqdm import tqdm
import logging
import os

# -----------------------------
# Configuración MongoDB
# -----------------------------
MONGO_URI = "mongodb://mongo:OtqZXbDnLBYZbmYPBQrlSUQlUXiosTgK@mainline.proxy.rlwy.net:35712"
client = MongoClient(MONGO_URI)

db = client["test"]
items_col = db["items"]
aplicaciones_col = db["aplicaciones"]

# -----------------------------
# Funciones de logging
# -----------------------------
def setup_logger(origen):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{origen}.log")
    
    logger = logging.getLogger(origen)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# -----------------------------
# Funciones de API ML
# -----------------------------
def renovar_token(store, logger):
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": store["app_id"],
        "client_secret": store["client_secret"],
        "refresh_token": store["refresh_token"]
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        store["access_token"] = data["access_token"]
        store["refresh_token"] = data["refresh_token"]
        logger.info("Token renovado correctamente.")
        return True
    except Exception as e:
        logger.error(f"ERROR renovar token: {e}")
        return False

def validar_url(url, logger):
    if not url or pd.isna(url) or str(url).strip() == "":
        logger.warning(f"URL vacía o NaN: {url}")
        return False
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        status = resp.status_code
        content_type = resp.headers.get("Content-Type", "desconocido")
        if status in (200, 206) and content_type.startswith("image"):
            logger.info(f"✅ URL válida: {url} | Status: {status} | Content-Type: {content_type}")
            return True
        else:
            logger.warning(f"❌ URL inválida: {url} | Status: {status} | Content-Type: {content_type}")
            return False
    except Exception as e:
        logger.warning(f"❌ Excepción validando URL: {url} | Error: {e}")
        return False

def descargar_imagen(url, logger):
    try:
        resp = requests.get(url, timeout=20, stream=True)
        if resp.status_code == 200:
            return resp.content
        else:
            logger.warning(f"Error al descargar {url}: {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Excepción descargando {url}: {e}")
        return None

def subir_imagen_ml(imagen_bytes, access_token, logger):
    try:
        files = {'file': ('imagen.jpg', imagen_bytes)}
        headers = {"Authorization": f"Bearer {access_token}"}
        url = "https://api.mercadolibre.com/pictures/items/upload"
        resp = requests.post(url, headers=headers, files=files, timeout=30)
        if resp.status_code in (200, 201):
            return resp.json().get("id")
        else:
            logger.warning(f"Error subiendo imagen: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Excepción subiendo imagen: {e}")
        return None

def actualizar_item_ml(item_id, picture_ids, access_token, logger):
    try:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"pictures": [{"id": pid} for pid in picture_ids]}
        resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            logger.info(f"Item {item_id} actualizado con {len(picture_ids)} imágenes.")
            return True
        else:
            logger.warning(f"Error actualizando item {item_id}: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        logger.warning(f"Excepción actualizando item {item_id}: {e}")
        return False

# -----------------------------
# Carga de archivos
# -----------------------------
tiendas_cardic = pd.read_excel("../Data/Fotos_CA/fotos_masivo.xlsx", sheet_name=0)
tiendas_tanak = pd.read_excel("../Data/Fotos_CA/fotos_masivo.xlsx", sheet_name=1)

# -----------------------------
# Selección de tienda y token
# -----------------------------
ORIGEN = "DS"
aplicacion = aplicaciones_col.find_one({"origen": ORIGEN})
logger = setup_logger(ORIGEN)

if not renovar_token(aplicacion, logger):
    raise RuntimeError("No se pudo renovar el token.")

ACCESS_TOKEN = aplicacion["access_token"]

# -----------------------------
# Flujo principal
# -----------------------------
for idx, row in tqdm(tiendas_cardic.iterrows(), total=tiendas_cardic.shape[0], desc=f"Procesando CAs ({ORIGEN})"):
    ca = str(row["CA"]).strip()
    logger.info(f"\n--- Procesando CA: {ca} ---")

    # Buscar items en MongoDB
    items = list(items_col.find({"seller_custom_sku": {"$regex": ca}, "origen": ORIGEN}))
    if not items:
        logger.warning(f"No se encontraron items para {ca}.")
        continue

    # Filtrar solo las celdas con contenido real
    picture_columns = [f"IMAGNE{i}" for i in range(1, 11)]
    urls_contenido = [str(row[col]).strip() for col in picture_columns 
                      if pd.notna(row[col]) and str(row[col]).strip() != ""]

    if not urls_contenido:
        logger.warning(f"CA {ca} no tiene imágenes con contenido. Se omite.")
        continue

    # Validar todas las URLs con contenido
    urls_validas = []
    for url in urls_contenido:
        if validar_url(url, logger):
            urls_validas.append(url)

    if len(urls_validas) != len(urls_contenido):
        logger.warning(f"CA {ca} tiene URLs inaccesibles. Se omite subida.")
        continue

    # Descargar y subir imágenes
    picture_ids = []
    for url in urls_validas:
        img_bytes = descargar_imagen(url, logger)
        if img_bytes:
            pic_id = subir_imagen_ml(img_bytes, ACCESS_TOKEN, logger)
            if pic_id:
                picture_ids.append(pic_id)

    if len(picture_ids) != len(urls_validas):
        logger.warning(f"CA {ca}: no se subieron todas las imágenes válidas. Saltando CA.")
        continue

    # Actualizar items con barra de progreso
    for item in tqdm(items, desc=f"Actualizando items CA {ca}", leave=False):
        success = actualizar_item_ml(str(item["_id"]), picture_ids, ACCESS_TOKEN, logger)
        sleep(0.5)
        if success:
            logger.info(f"Progreso: Item {item['_id']} actualizado con {len(picture_ids)} imágenes.")

print("\n🎉 Proceso finalizado para todos los CAs.")
