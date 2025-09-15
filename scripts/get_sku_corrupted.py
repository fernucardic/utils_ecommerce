from pymongo import MongoClient
import csv
import os

# 🚀 URL de conexión (cámbiala por la tuya)
MONGO_URL = "mongodb://mongo:OtqZXbDnLBYZbmYPBQrlSUQlUXiosTgK@mainline.proxy.rlwy.net:35712"

# Nombre de la base y colección
DB_NAME = "test"
COLLECTION_NAME = "items"

def get_sku_from_attributes(attributes):
    """
    Busca en attributes el valor del campo con id='SELLER_SKU'.
    Devuelve el value_name si existe, sino None.
    """
    if not attributes:
        return None
    for attr in attributes:
        if attr.get("id") == "SELLER_SKU":
            return attr.get("value_name")
    return None

def export_items():
    print("🔍 Buscando items sin seller_custom_field...")
    # Conexión
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    items_collection = db[COLLECTION_NAME]

    # Query: seller_custom_field vacío, null o inexistente
    query = {
        "$or": [
            {"seller_custom_field": {"$exists": False}},
            {"seller_custom_field": None},
            {"seller_custom_field": ""}
        ]
    }

    # Buscar items
    cursor = items_collection.find(query, {
        "_id": 1,
        "origen": 1,
        "seller_custom_field": 1,
        "attributes": 1
    })

    total = items_collection.count_documents(query)

    print(f"Procesando {total} items encontrados...")

    # Agrupar por origen
    items_by_origin = {}
    for item in cursor:
        origen = item.get("origen", "UNKNOWN")
        seller_custom_field = item.get("seller_custom_field")
        sku = get_sku_from_attributes(item.get("attributes", []))

        if origen not in items_by_origin:
            items_by_origin[origen] = []

        items_by_origin[origen].append({
            "id": str(item["_id"]),
            "seller_custom_field": seller_custom_field,
            "sku": sku
        })

    # Crear directorio de exportación
    os.makedirs("exports", exist_ok=True)

    # Exportar un archivo por origen
    for origen, items in items_by_origin.items():
        filename = f"exports/items_sin_seller_custom_field_{origen}.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "seller_custom_field", "sku"])  # encabezado
            for item in items:
                writer.writerow([item["id"], item["seller_custom_field"], item["sku"]])

        print(f"✅ Exportado {len(items)} items para origen {origen} en {filename}")

    client.close()

if __name__ == "__main__":
    export_items()
