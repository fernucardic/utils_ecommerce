import pandas as pd
from pymongo import MongoClient
import re
from tqdm import tqdm
import logging
from datetime import datetime
from collections import defaultdict

# -----------------------------
# Configuración de Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'../logs/get_delete_items_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -----------------------------
# Conexión a MongoDB
# -----------------------------
logger.info("=" * 60)
logger.info("INICIO DEL PROCESO DE FILTRADO DE ITEMS PARA ELIMINAR")
logger.info("=" * 60)

MONGO_URI = "mongodb://mongo:OtqZXbDnLBYZbmYPBQrlSUQlUXiosTgK@mainline.proxy.rlwy.net:35712"
logger.info("Conectando a MongoDB...")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["test"]
items_col = db["items"]
logger.info("✓ Conexión exitosa a MongoDB")

# -----------------------------
# Leer Excel con NPC
# -----------------------------
excel_file = "../Data/ELIMINAR/proveedores_conservar.xlsx"
logger.info(f"Leyendo archivo Excel: {excel_file}")
try:
    df_npc = pd.read_excel(excel_file)
    logger.info(f"✓ Excel cargado correctamente: {len(df_npc)} filas")
except Exception as e:
    logger.error(f"✗ Error al leer Excel: {e}")
    raise

# -----------------------------
# Construir diccionario CA -> lista de NPC (Optimizado)
# -----------------------------
logger.info("Construyendo diccionario CA -> NPC...")
ca_npc_dict = {}
npc_columns = ["NPC", "NPC.1", "NPC.2"]

for _, row in tqdm(df_npc.iterrows(), total=len(df_npc), desc="Procesando Excel", unit="filas"):
    ca = str(row["CA"]).strip()
    npcs = []
    for col in npc_columns:
        val = row.get(col)
        if pd.notna(val):
            npcs.append(str(val).strip().upper())  # Pre-convertir a mayúsculas
    if npcs:  # Solo agregar si tiene NPCs
        ca_npc_dict[ca] = npcs

logger.info(f"✓ Diccionario construido: {len(ca_npc_dict)} CAs con NPCs")

# -----------------------------
# Filtrar items sin ventas y sin "CRD" en SKU (Optimizado con proyección)
# -----------------------------
logger.info("Consultando items en MongoDB...")
filtro_items = {
    "sold_quantity": 0,
    "seller_custom_sku": {"$not": re.compile("CRD", re.IGNORECASE)}
}

# Proyección: solo traer campos necesarios para mejorar rendimiento
projection = {
    "_id": 1,
    "sold_quantity": 1,
    "seller_custom_sku": 1,
    "numero_parte": 1,
    "date_created": 1,
    "origen": 1
}

logger.info("Ejecutando query en MongoDB (esto puede tardar)...")
# Contar primero para mostrar progreso
total_count = items_col.count_documents(filtro_items)
logger.info(f"Total de items a procesar: {total_count}")

# Usar cursor con proyección en lugar de cargar todo en memoria
cursor = items_col.find(filtro_items, projection)
items = []
for item in tqdm(cursor, total=total_count, desc="Cargando items", unit="items"):
    items.append(item)

logger.info(f"✓ Items cargados: {len(items)}")

# -----------------------------
# Filtrar por NPC por CA (Optimizado)
# -----------------------------
logger.info("Filtrando items por NPC...")
items_filtrados = []
items_conservados = 0

for item in tqdm(items, desc="Filtrando por NPC", unit="items"):
    ca = item.get("numero_parte")
    if not ca:
        continue
    
    ca = str(ca).strip()
    seller_sku = str(item.get("seller_custom_sku", "")).upper()
    
    # Obtener NPC de esa CA
    npcs = ca_npc_dict.get(ca, [])
    
    # Si el seller_sku contiene algún NPC, lo ignoramos (lo conservamos)
    if npcs and any(npc in seller_sku for npc in npcs):  # Ya están en mayúsculas
        items_conservados += 1
        continue
    
    items_filtrados.append(item)

logger.info(f"✓ Filtrado completado:")
logger.info(f"  - Items conservados (con NPC): {items_conservados}")
logger.info(f"  - Items para eliminar: {len(items_filtrados)}")

# -----------------------------
# Separar por origen y generar Excel (Optimizado)
# -----------------------------
logger.info("Agrupando items por origen...")
items_por_origen = defaultdict(list)

for item in tqdm(items_filtrados, desc="Agrupando por origen", unit="items"):
    origen = item.get("origen", "SIN_ORIGEN")
    items_por_origen[origen].append({
        "ID de la publicación": item.get("_id"),
        "Numero de ventas": item.get("sold_quantity"),
        "seller_custom_sku": item.get("seller_custom_sku"),
        "Numero de parte": item.get("numero_parte"),
        "Fecha de publicacion": item.get("date_created")
    })

logger.info(f"✓ Items agrupados en {len(items_por_origen)} orígenes:")
for origen, items_list in sorted(items_por_origen.items()):
    logger.info(f"  - {origen}: {len(items_list)} items")

# -----------------------------
# Escribir Excel
# -----------------------------
output_file = "ELIMINAR_SIN_VENTAS.xlsx"
logger.info(f"Generando archivo Excel: {output_file}")

writer = pd.ExcelWriter(output_file, engine="xlsxwriter")

for origen in tqdm(sorted(items_por_origen.keys()), desc="Escribiendo Excel", unit="hojas"):
    df_origen = pd.DataFrame(items_por_origen[origen])
    sheet_name = origen[:31]  # Excel limita nombres a 31 chars
    df_origen.to_excel(writer, sheet_name=sheet_name, index=False)
    logger.info(f"  ✓ Hoja '{sheet_name}' creada con {len(df_origen)} items")

writer.close()
logger.info(f"✓ Archivo {output_file} generado correctamente")

# -----------------------------
# Resumen final
# -----------------------------
logger.info("=" * 60)
logger.info("RESUMEN FINAL:")
logger.info(f"  - Total items iniciales: {total_count}")
logger.info(f"  - Items conservados (con NPC protegido): {items_conservados}")
logger.info(f"  - Items para eliminar: {len(items_filtrados)}")
logger.info(f"  - Orígenes diferentes: {len(items_por_origen)}")
logger.info(f"  - Archivo generado: {output_file}")
logger.info("=" * 60)
logger.info("PROCESO COMPLETADO EXITOSAMENTE")
logger.info("=" * 60)
