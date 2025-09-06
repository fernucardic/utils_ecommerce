import os
import time
import requests
import pandas as pd
from multiprocessing import Pool
from dotenv import load_dotenv
import backoff

load_dotenv()

PROMO_TYPE = "DEAL"
OUTPUT_DIR = os.path.join("Output", "Started")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIENDAS = {
    code: {
        "access_token": os.getenv(f"{code}_ACCESS_TOKEN"),
        "refresh_token": os.getenv(f"{code}_REFRESH_TOKEN"),
        "client_id": os.getenv(f"{code}_CLIENT_ID"),
        "client_secret": os.getenv(f"{code}_CLIENT_SECRET"),
        "user_id": os.getenv(f"{code}_SELLER_ID"),
        "promotion_id": os.getenv(f"{code}_PROMOTION_ID"),
        "name": code
    }
    for code in ["CO", "DS", "TE", "TS", "CA"]
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
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        store["access_token"] = data["access_token"]
        store["refresh_token"] = data["refresh_token"]
        print(f"[{store['name']}] Nuevo access_token: {store['access_token']}")
        return True
    except requests.RequestException as e:
        print(f"[{store['name']}] ERROR al renovar token: {e}")
        return False

@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_time=60, jitter=backoff.full_jitter)
def fetch_page(session, url, params):
    resp = session.get(url, params=params, timeout=10)
    if resp.status_code >= 500:
        resp.raise_for_status()
    return resp.json()

def procesar_tienda(item):
    code, store = item
    print(f"[{code}] Iniciando...")

    base_url = f"https://api.mercadolibre.com/seller-promotions/promotions/{store['promotion_id']}/items"
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {store['access_token']}", "version": "v2"})

    params = {
        "promotion_type": PROMO_TYPE,
        # "status": "started",
        "limit": 100,
        "app_version": "v2"
    }

    search_after = None
    all_items = []
    max_items = None  # se determinará con la primera llamada

    # Primera llamada para obtener total y comenzar iteración
    try:
        data = fetch_page(session, base_url, params)
    except Exception as e:
        print(f"[{code}] ERROR en la primera llamada: {e}")
        return code, 0

    total_items = data.get("paging", {}).get("total")
    if not total_items:
        print(f"[{code}] No se encontró información de total_items.")
        return code, 0

    max_items = total_items
    print(f"[{code}] Total registrado por API: {max_items}")

    items = data.get("results", [])
    all_items.extend(items)
    print(f"[{code}] Obtenidos {len(items)} items (total {len(all_items)})")
    search_after = data.get("paging", {}).get("searchAfter")

    # Iterar hasta alcanzar el total
    while search_after and len(all_items) < max_items:
        params["search_after"] = search_after

        try:
            data = fetch_page(session, base_url, params)
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[{code}] Token expirado. Intentando renovar...")
                if renovar_token(store):
                    session.headers["Authorization"] = f"Bearer {store['access_token']}"
                    continue
                else:
                    break
            print(f"[{code}] ERROR HTTP: {e}")
            break
        except Exception as e:
            print(f"[{code}] ERROR de conexión: {e}")
            break

        items = data.get("results", [])
        if not items:
            break
        all_items.extend(items)
        print(f"[{code}] Obtenidos {len(items)} items (total {len(all_items)} / {max_items})")

        # Verifica si se alcanzó el límite total
        if len(all_items) >= max_items:
            print(f"[{code}] Se alcanzó el límite máximo de items: {max_items}")
            break

        search_after = data.get("paging", {}).get("searchAfter")
        if not search_after:
            break

        time.sleep(0.1)

    df = pd.DataFrame(all_items)
    output_path = os.path.join(OUTPUT_DIR, f"{code}.csv")
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"[{code}] Guardado {len(all_items)} items en {output_path}")
    return code, len(all_items)

if __name__ == "__main__":

    for code, store in TIENDAS.items():
        renovar_token(store)
        time.sleep(1)

    start = time.time()
    with Pool(len(TIENDAS)) as pool:
        results = pool.map(procesar_tienda, TIENDAS.items())

    total = sum(count for _, count in results)
    print("\n=== RESUMEN ===")
    for code, count in results:
        print(f"{code}: {count} items")
    print(f"Total items: {total}")
    print(f"Duración total: {time.time() - start:.2f} segundos")
