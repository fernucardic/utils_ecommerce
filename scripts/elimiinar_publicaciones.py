import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from collections import deque
from datetime import datetime, timedelta

load_dotenv()

TIENDAS_ML = {
    "CO": {
        "access_token": os.getenv("CO_ACCESS_TOKEN"),
        "refresh_token": os.getenv("CO_REFRESH_TOKEN"),
        "client_id": os.getenv("CO_CLIENT_ID"),
        "client_secret": os.getenv("CO_CLIENT_SECRET"),
        "user_id": os.getenv("CO_SELLER_ID"),
        "nombre_tienda": "CO"
    },
    # "DS": {
    #     "access_token": os.getenv("DS_ACCESS_TOKEN"),
    #     "refresh_token": os.getenv("DS_REFRESH_TOKEN"),
    #     "client_id": os.getenv("DS_CLIENT_ID"),
    #     "client_secret": os.getenv("DS_CLIENT_SECRET"),
    #     "user_id": os.getenv("DS_SELLER_ID"),
    #     "nombre_tienda": "DS"
    # },
    # "TE": {
    #     "access_token": os.getenv("TE_ACCESS_TOKEN"),
    #     "refresh_token": os.getenv("TE_REFRESH_TOKEN"),
    #     "client_id": os.getenv("TE_CLIENT_ID"),
    #     "client_secret": os.getenv("TE_CLIENT_SECRET"),
    #     "user_id": os.getenv("TE_SELLER_ID"),
    #     "nombre_tienda": "TE"
    # },
    # "TS": {
    #     "access_token": os.getenv("TS_ACCESS_TOKEN"),
    #     "refresh_token": os.getenv("TS_REFRESH_TOKEN"),
    #     "client_id": os.getenv("TS_CLIENT_ID"),
    #     "client_secret": os.getenv("TS_CLIENT_SECRET"),
    #     "user_id": os.getenv("TS_SELLER_ID"),
    #     "nombre_tienda": "TS"
    # },
    # "CA": {
    #     "access_token": os.getenv("CA_ACCESS_TOKEN"),
    #     "refresh_token": os.getenv("CA_REFRESH_TOKEN"),
    #     "client_id": os.getenv("CA_CLIENT_ID"),
    #     "client_secret": os.getenv("CA_CLIENT_SECRET"),
    #     "user_id": os.getenv("CA_SELLER_ID"),
    #     "nombre_tienda": "CA"
    # },
}

RATE_LIMIT = 20  # máximo de peticiones por segundo por tienda


def rate_limiter(queue, max_requests=RATE_LIMIT, interval=1.0):
    """Controla que no se hagan más de max_requests por intervalo (segundos)."""
    now = time.time()
    queue.append(now)

    # Eliminar timestamps viejos fuera del intervalo
    while queue and now - queue[0] > interval:
        queue.popleft()

    if len(queue) > max_requests:
        wait = interval - (now - queue[0])
        time.sleep(wait)

def request_with_backoff(method, url, headers, json=None, max_retries=5):
    delay = 0.5
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, headers=headers, json=json)
            if response.status_code == 429:
                print(f"⚠️ Rate limit alcanzado, reintentando en {delay}s...")
                time.sleep(delay)
                delay *= 2  # backoff exponencial
                continue
            return response
        except requests.RequestException as e:
            print(f"❌ Error de red: {e}, reintentando en {delay}s...")
            time.sleep(delay)
            delay *= 2
    return None

def pausar_y_cerrar(item_id, token, tienda, queue):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    base_url = "https://api.mercadolibre.com/items/"

    # # PAUSE
    # rate_limiter(queue)
    # resp_pause = request_with_backoff("PUT", base_url + item_id, headers, json={"status": "paused"})
    # if not resp_pause or not resp_pause.ok:
    #     print(f"[PAUSE ❌] {item_id} - {tienda['nombre_tienda']} → {resp_pause.text if resp_pause else 'No response'}")
    #     return
    # print(f"[PAUSE ✅] {item_id} - {tienda['nombre_tienda']}")

    # time.sleep(0.1)

    # CLOSE
    rate_limiter(queue)
    resp_close = request_with_backoff("PUT", base_url + item_id, headers, json={"status": "closed"})
    if not resp_close or not resp_close.ok:
        print(f"[CLOSE ❌] {item_id} - {tienda['nombre_tienda']} → {resp_close.text if resp_close else 'No response'}")
        return
    print(f"[CLOSE ✅] {item_id} - {tienda['nombre_tienda']}")

def procesar_por_tienda(clave, tienda, df):
    access_token = tienda["access_token"]
    nombre = tienda["nombre_tienda"]
    queue = deque()  # Para control del rate limit

    if df.empty:
        print(f"⚠️ No hay publicaciones para la tienda: {nombre} ({clave})")
        return

    ids = df["ID"].dropna().astype(str).tolist()
    ids = ["MLM" + id if not id.startswith("MLM") else id for id in ids]
    print(f"🔧 Procesando {len(ids)} publicaciones para {nombre} ({clave})...")

    for item_id in ids:
        pausar_y_cerrar(item_id, access_token, tienda, queue)

def main():
    try:
        df = pd.read_excel("../Data/Eliminar/Eliminar_CO_1.xlsx", dtype=str)
    except Exception as e:
        print(f"❌ Error leyendo el archivo Excel: {e}")
        return

    if "ID" not in df.columns:
        print("❌ El archivo Excel debe contener la columna 'ID'")
        return

    for clave, tienda in TIENDAS_ML.items():
        procesar_por_tienda(clave, tienda, df)

if __name__ == "__main__":
    main()
