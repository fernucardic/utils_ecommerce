import requests
import time
import csv
import os
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

TIENDA_DS = {
    "access_token": os.getenv("DS_ACCESS_TOKEN"),
    "refresh_token": os.getenv("DS_REFRESH_TOKEN"),
    "client_id": os.getenv("DS_CLIENT_ID"),
    "client_secret": os.getenv("DS_CLIENT_SECRET"),
    "user_id": os.getenv("DS_SELLER_ID"),
    "nombre_tienda": "DS"
}


def renovar_token(tienda):
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": tienda["client_id"],
        "client_secret": tienda["client_secret"],
        "refresh_token": tienda["refresh_token"]
    }
    try:
        resp = requests.post(url, data=payload)
        resp.raise_for_status()
        data = resp.json()
        tienda["access_token"] = data["access_token"]
        tienda["refresh_token"] = data["refresh_token"]
        print("🔑 Token renovado con éxito.")
        return True
    except requests.RequestException as e:
        print(f"❌ Error renovando token: {e}")
        return False


def obtener_ids_scan(user_id, token, tienda):
    url = f"https://api.mercadolibre.com/users/{user_id}/items/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"search_type": "scan", "limit": 100}
    ids = []

    try:
        print("🔍 Obteniendo IDs con SCAN...")
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 401:
            print("⚠️ Token expirado, intentando renovar...")
            if renovar_token(tienda):
                return obtener_ids_scan(user_id, tienda["access_token"], tienda)
            return []

        resp.raise_for_status()
        data = resp.json()
        ids.extend(data.get("results", []))
        scroll = data.get("scroll_id")

        with tqdm(total=data.get("paging", {}).get("total", 0), desc="Cargando publicaciones", unit="pub") as pbar:
            pbar.update(len(data.get("results", [])))
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
                pbar.update(len(results))
                scroll = data.get("scroll_id")

    except requests.RequestException as e:
        print(f"❌ Error obteniendo IDs: {e}")

    return ids


def filtrar_publicaciones(ids, token):
    headers = {"Authorization": f"Bearer {token}"}
    filtradas = []

    print("📦 Filtrando publicaciones que contienen 'Cardic'...")
    for i in tqdm(range(0, len(ids), 20), desc="Filtrando lotes", unit="lote"):
        batch = ids[i:i+20]
        url = "https://api.mercadolibre.com/items"
        params = {"ids": ",".join(batch)}

        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            for item in data:
                if item.get("code") != 200:
                    continue
                pub = item["body"]
                if contiene_cardic(pub.get("attributes", [])):
                    filtradas.append(extraer_datos(pub))
        except requests.RequestException:
            continue

    return filtradas


def contiene_cardic(atributos):
    for attr in atributos:
        for campo in ["name", "value_name"]:
            valor = attr.get(campo)
            if valor and "cardic" in valor.lower():
                return True
    return False


def extraer_datos(pub):
    sku = None
    for attr in pub.get("attributes", []):
        if attr.get("id") == "SELLER_SKU":
            sku = attr.get("value_name")
            break
    return {
        "id": pub.get("id"),
        "title": pub.get("title"),
        "status": pub.get("status"),
        "price": pub.get("price"),
        "seller_sku": sku
    }


def exportar_csv(data, nombre_archivo):
    if not data:
        print("⚠️ No se encontraron publicaciones que contengan 'Cardic'.")
        return
    with open(nombre_archivo, mode="w", newline='', encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "title", "status", "price", "seller_sku"])
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ Exportado: {nombre_archivo} ({len(data)} publicaciones)")


def main():
    tienda = TIENDA_DS
    ids = obtener_ids_scan(tienda["user_id"], tienda["access_token"], tienda)
    print(f"🔢 Total IDs obtenidos: {len(ids)}")
    filtradas = filtrar_publicaciones(ids, tienda["access_token"])
    exportar_csv(filtradas, f"publicaciones_cardic_{tienda['nombre_tienda']}.csv")


if __name__ == "__main__":
    main()
