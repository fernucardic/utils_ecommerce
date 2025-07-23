import requests
import time
import pandas as pd
import os
import csv
from multiprocessing import Pool
from dotenv import load_dotenv

load_dotenv()

# === CONFIGURACIÓN ===

TIENDAS_ML = {
    "CO": {
        "access_token": os.getenv("CO_ACCESS_TOKEN"),
        "refresh_token": os.getenv("CO_REFRESH_TOKEN"),
        "client_id": os.getenv("CO_CLIENT_ID"),
        "client_secret": os.getenv("CO_CLIENT_SECRET"),
        "user_id": os.getenv("CO_SELLER_ID"),
        "nombre_tienda": "CO"
    },
    "DS": {
        "access_token": os.getenv("DS_ACCESS_TOKEN"),
        "refresh_token": os.getenv("DS_REFRESH_TOKEN"),
        "client_id": os.getenv("DS_CLIENT_ID"),
        "client_secret": os.getenv("DS_CLIENT_SECRET"),
        "user_id": os.getenv("DS_SELLER_ID"),
        "nombre_tienda": "DS"
    },
    "TE": {
        "access_token": os.getenv("TE_ACCESS_TOKEN"),
        "refresh_token": os.getenv("TE_REFRESH_TOKEN"),
        "client_id": os.getenv("TE_CLIENT_ID"),
        "client_secret": os.getenv("TE_CLIENT_SECRET"),
        "user_id": os.getenv("TE_SELLER_ID"),
        "nombre_tienda": "TE"
    },
    "TS": {
        "access_token": os.getenv("TS_ACCESS_TOKEN"),
        "refresh_token": os.getenv("TS_REFRESH_TOKEN"),
        "client_id": os.getenv("TS_CLIENT_ID"),
        "client_secret": os.getenv("TS_CLIENT_SECRET"),
        "user_id": os.getenv("TS_SELLER_ID"),
        "nombre_tienda": "TS"
    },
    "CA": {
        "access_token": os.getenv("CA_ACCESS_TOKEN"),
        "refresh_token": os.getenv("CA_REFRESH_TOKEN"),
        "client_id": os.getenv("CA_CLIENT_ID"),
        "client_secret": os.getenv("CA_CLIENT_SECRET"),
        "user_id": os.getenv("CA_SELLER_ID"),
        "nombre_tienda": "CA"
    },
}


def renovar_token(tienda, max_intentos=3, espera_inicial=1):
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": tienda["client_id"],
        "client_secret": tienda["client_secret"],
        "refresh_token": tienda["refresh_token"]
    }

    for intento in range(1, max_intentos + 1):
        try:
            resp = requests.post(url, data=payload)
            resp.raise_for_status()
            data = resp.json()
            tienda["access_token"] = data["access_token"]
            tienda["refresh_token"] = data["refresh_token"]
            print(f"Token renovado para {tienda['nombre_tienda']} (intento {intento})")
            return True
        except requests.RequestException as e:
            print(f"Intento {intento} fallido para {tienda['nombre_tienda']}: {e}")
            if intento < max_intentos:
                time.sleep(espera_inicial * intento)
            else:
                print(f"Falló renovación del token para {tienda['nombre_tienda']} tras {max_intentos} intentos.")
                return False


def obtener_ids_scan(user_id, token, tienda, intento_renovado=False):
    if not intento_renovado:
        print(f"Obteniendo IDs de publicaciones para {tienda['nombre_tienda']}...")

    url = f"https://api.mercadolibre.com/users/{user_id}/items/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"search_type": "scan", "limit": 100}
    ids = []

    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 401 and not intento_renovado:
            print(f"Token expirado: {tienda['nombre_tienda']} → intentando renovar")
            if renovar_token(tienda):
                return obtener_ids_scan(user_id, tienda["access_token"], tienda, True)
            else:
                return []

        resp.raise_for_status()
        data = resp.json()
        scroll = data.get("scroll_id")
        ids.extend(data.get("results", []))

        while scroll:
            time.sleep(0.05)
            params["scroll_id"] = scroll
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            ids.extend(results)
            scroll = data.get("scroll_id")

    except requests.RequestException as e:
        print(f"Error obteniendo IDs: {tienda['nombre_tienda']} → {e}")

    return ids


def obtener_detalles_multiples_gen(ids, token, batch_size=20):
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        url = "https://api.mercadolibre.com/items"
        params = {"ids": ",".join(batch)}
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            resultados = resp.json()
            for entry in resultados:
                if entry.get("code") == 200:
                    yield entry["body"]
        except requests.RequestException:
            continue


def exportar_csv_incremental(data_gen, nombre):
    nombre_archivo = f"{nombre}.csv"
    primer_registro = next(data_gen, None)
    if not primer_registro:
        print(f"No hay datos para {nombre}")
        return

    with open(nombre_archivo, mode="w", newline='', encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(primer_registro.keys()))
        writer.writeheader()
        writer.writerow(primer_registro)
        for registro in data_gen:
            writer.writerow(registro)

    print(f"Exportado {nombre_archivo}")


def procesar_tienda(args):
    clave, tienda = args
    start = time.time()

    ids = obtener_ids_scan(tienda["user_id"], tienda["access_token"], tienda)
    detalles_gen = obtener_detalles_multiples_gen(ids, tienda["access_token"])
    exportar_csv_incremental(detalles_gen, tienda["nombre_tienda"])

    end = time.time()
    return clave, len(ids), end - start


def main():
    global_start = time.time()
    print(f"Ejecutando con multiprocessing ({len(TIENDAS_ML)} workers)\n")

    with Pool(processes=len(TIENDAS_ML)) as pool:
        resultados = pool.map(procesar_tienda, list(TIENDAS_ML.items()))

    global_end = time.time()
    print("\nRESUMEN FINAL")
    print("==========================")
    print(f"Tiempo total global: {global_end - global_start:.2f} s")
    total_pub = 0
    for clave, count, tiempo in resultados:
        print(f"{clave}: {count} publicaciones en {tiempo:.2f} s")
        total_pub += count
    print(f"Total publicaciones: {total_pub}")
    print("==========================")

if __name__ == "__main__":
    main()
