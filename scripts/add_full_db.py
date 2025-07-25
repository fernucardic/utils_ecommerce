from pymongo import MongoClient, UpdateOne
from tqdm import tqdm

client = MongoClient("mongodb://localhost:27017")  # Ajusta si usas auth u otra URI
db = client["ecommerce"]
collection = db["items"]

total = collection.count_documents({})
print(f"Procesando {total} ítems...")

BATCH_SIZE = 1000
cursor = collection.find({}, {"_id": 1, "seller_custom_sku": 1}).batch_size(BATCH_SIZE)

updates = []
for doc in tqdm(cursor, total=total):
    sku = doc.get("seller_custom_sku", "")
    is_full = "FULL" in sku.upper() if sku else False

    updates.append(
        UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"is_full": is_full}}
        )
    )

    if len(updates) >= BATCH_SIZE:
        collection.bulk_write(updates)
        updates = []

if updates:
    collection.bulk_write(updates)

print("✅ Actualización completada.")
