import os
import time
import requests
import pandas as pd
from multiprocessing import Pool
from dotenv import load_dotenv
import logging
import backoff

load_dotenv()

# Logging
LOG_FILE = "ml_replace_pictures.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Directorio de errores
ERROR_DIR = "Errores"
os.makedirs(ERROR_DIR, exist_ok=True)

# Tiendas
TIENDAS = {
    code: {
        "access_token": os.getenv(f"{code}_ACCESS_TOKEN"),
        "refresh_token": os.getenv(f"{code}_REFRESH_TOKEN"),
        "client_id": os.getenv(f"{code}_CLIENT_ID"),
        "client_secret": os.getenv(f"{code}_CLIENT_SECRET"),
        "name": code
    }
    for code in ["CO"]
}

def renovar_token(store):
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": store["client_id"],
        "client_secret": store["client_secret"],
        "refresh_token": store["refresh_token"]
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        store["access_token"] = data["access_token"]
        store["refresh_token"] = data["refresh_token"]
        logging.info(f"[{store['name']}] Token renovado")
        return True
    except Exception as e:
        logging.error(f"[{store['name']}] ERROR renovar token: {e}")
        return False

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_time=60, jitter=backoff.full_jitter)
def enviar_request(session, url, payload):
    resp = session.put(url, json=payload, timeout=30)
    if resp.status_code >= 500:
        resp.raise_for_status()
    return resp

def procesar_items_tienda(store_item):
    code, store = store_item
    logging.info(f"[{code}] Iniciando actualización de fotos")

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {store['access_token']}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    })

    archivo_excel = f"Data/Fotos/Fotos_{code}.xlsx"
    if not os.path.exists(archivo_excel):
        logging.error(f"[{code}] No se encontró archivo {archivo_excel}")
        return code, 0

    df = pd.read_excel(archivo_excel)

    # Detectar columnas de imágenes automáticamente
    image_columns = [col for col in df.columns if col.lower().startswith("imagen")]
    if not image_columns:
        logging.error(f"[{code}] No se encontraron columnas Imagen1..ImagenN en {archivo_excel}")
        return code, 0

    errores = []
    total_items = len(df)
    success_count = 0

    for idx, row in df.iterrows():
        item_id = str(row.get("ID")).strip()

        # Reunir todas las imágenes en lista
        fotos = [str(row[col]).strip() for col in image_columns if pd.notna(row.get(col)) and str(row.get(col)).strip()]
        payload = {"pictures": [{"source": f} for f in fotos]}

        if not item_id or not payload["pictures"]:
            msg = "Id o fotos vacías"
            logging.warning(f"[{code}] Fila {idx+2}: {msg}")
            errores.append({"Id": item_id, "Error": msg})
            continue

        url = f"https://api.mercadolibre.com/items/MLM{item_id}"

        try:
            resp = enviar_request(session, url, payload)
            if resp.status_code in (200, 201):
                logging.info(f"[{code}] Item {item_id} actualizado")
                success_count += 1
            else:
                msg = f"{resp.status_code} - {resp.text}"
                logging.error(f"[{code}] Item {item_id} ERROR: {msg}")
                errores.append({"Id": item_id, "Error": msg})

        except requests.HTTPError as e:
            if e.response.status_code == 401:
                logging.warning(f"[{code}] Token expirado, renovando...")
                if renovar_token(store):
                    session.headers["Authorization"] = f"Bearer {store['access_token']}"
                    resp = enviar_request(session, url, payload)
                    if resp.status_code in (200, 201):
                        logging.info(f"[{code}] Item {item_id} actualizado tras renovar token")
                        success_count += 1
                    else:
                        msg = f"{resp.status_code} - {resp.text}"
                        logging.error(f"[{code}] Item {item_id} ERROR tras renovar token: {msg}")
                        errores.append({"Id": item_id, "Error": msg})
                else:
                    errores.append({"Id": item_id, "Error": "No se pudo renovar token"})
            else:
                errores.append({"Id": item_id, "Error": str(e)})
        except Exception as e:
            logging.error(f"[{code}] Item {item_id} ERROR: {e}")
            errores.append({"Id": item_id, "Error": str(e)})

    # Guardar CSV de errores
    if errores:
        df_err = pd.DataFrame(errores)
        df_err.to_csv(os.path.join(ERROR_DIR, f"{code}_errores.csv"), index=False, encoding="utf-8-sig")

    logging.info(f"[{code}] Finalizado: {success_count}/{total_items} items actualizados, {len(errores)} errores")
    return code, success_count

if __name__ == "__main__":
    # Renovar tokens iniciales
    for code, store in TIENDAS.items():
        renovar_token(store)
        time.sleep(0.5)

    start_time = time.time()
    with Pool(len(TIENDAS)) as pool:
        results = pool.map(procesar_items_tienda, TIENDAS.items())

    total_actualizados = sum(count for _, count in results)
    print("\n=== RESUMEN GENERAL ===")
    for code, count in results:
        print(f"{code}: {count} items actualizados")
    print(f"Total items actualizados: {total_actualizados}")
    print(f"Tiempo total: {time.time() - start_time:.2f}s")
