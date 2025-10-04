import pandas as pd
from pymongo import MongoClient
import re

# -----------------------------
# Conexión a MongoDB
# -----------------------------
MONGO_URI = "mongodb://mongo:OtqZXbDnLBYZbmYPBQrlSUQlUXiosTgK@mainline.proxy.rlwy.net:35712"
client = MongoClient(MONGO_URI)
db = client["test"]
items_col = db["items"]

# -----------------------------
# Leer Excel con NPC
# -----------------------------
excel_file = "../Data/ELIMINAR/proveedores_conservar.xlsx"  # reemplaza con la ruta correcta
df_npc = pd.read_excel(excel_file)

# Construir diccionario CA -> lista de NPC
ca_npc_dict = {}
for _, row in df_npc.iterrows():
    ca = str(row["CA"]).strip()
    npcs = []
    for col in ["NPC", "NPC.1", "NPC.2"]:  # ajusta nombres de columnas si cambian
        val = row.get(col)
        if pd.notna(val):
            npcs.append(str(val).strip())
    ca_npc_dict[ca] = npcs

# -----------------------------
# Filtrar items sin ventas y sin "CRD" en SKU
# -----------------------------
filtro_items = {
    "sold_quantity": 0,
    "seller_custom_sku": {"$not": re.compile("CRD", re.IGNORECASE)}
}

items = list(items_col.find(filtro_items))
print(f"Total items iniciales sin ventas y sin CRD: {len(items)}")

# -----------------------------
# Filtrar por NPC por CA
# -----------------------------
items_filtrados = []

for item in items:
    ca = item.get("numero_parte")
    if not ca:
        continue
    ca = str(ca).strip()
    seller_sku = str(item.get("seller_custom_sku", "")).upper()

    # Obtener NPC de esa CA
    npcs = ca_npc_dict.get(ca, [])

    # Si el seller_sku contiene algún NPC, lo ignoramos (lo conservamos)
    if any(npc.upper() in seller_sku for npc in npcs):
        continue

    items_filtrados.append(item)

print(f"Total items después de filtrar NPC: {len(items_filtrados)}")

# -----------------------------
# Separar por origen
# -----------------------------
origenes = set(item.get("origen", "SIN_ORIGEN") for item in items_filtrados)
writer = pd.ExcelWriter("ELIMINAR_SIN_VENTAS.xlsx", engine="xlsxwriter")

for origen in origenes:
    items_origen = [item for item in items_filtrados if item.get("origen") == origen]

    # Construir DataFrame con columnas requeridas
    data = []
    for item in items_origen:
        data.append({
            "ID de la publicación": item.get("_id"),
            "Numero de ventas": item.get("sold_quantity"),
            "seller_custom_sku": item.get("seller_custom_sku"),
            "Numero de parte": item.get("numero_parte"),
            "Fecha de publicacion": item.get("date_created")
        })

    df_origen = pd.DataFrame(data)
    df_origen.to_excel(writer, sheet_name=origen[:31], index=False)  # Excel limita nombres a 31 chars

writer.save()
print("Archivo ELIMINAR_SIN_VENTAS.xlsx generado correctamente.")
