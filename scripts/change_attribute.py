import asyncio
import aiohttp
import time

ACCESS_TOKEN = "TU_ACCESS_TOKEN_AQUI"
ITEM_IDS = [
    "MLM3704500812", "MLM3704500813", "MLM3704500814",  # Agrega tus IDs aquí
    # ...
]

# Valor que deseas asignar (puede ser "Sí" o "No" según API)
IS_FLAMMABLE_VALUE_ID = "242084"  # No
# IS_FLAMMABLE_VALUE_ID = "242085"  # Sí

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

async def update_attribute(session, item_id, seller_sku):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    payload = {
        "attributes": [
            {
                "id": "SELLER_SKU",
                "value_id": seller_sku
            }
        ]
    }

    try:
        async with session.put(url, json=payload, headers=HEADERS) as response:
            data = await response.json()
            if response.status == 200:
                print(f"✅ Actualizado: {item_id}")
            else:
                print(f"❌ Error {response.status} en {item_id}: {data}")
    except Exception as e:
        print(f"💥 Excepción en {item_id}: {e}")

async def process_items():
    connector = aiohttp.TCPConnector(limit=20)  # Max 20 conexiones concurrentes
    async with aiohttp.ClientSession(connector=connector) as session:
        for i in range(0, len(ITEM_IDS), 20):
            batch = ITEM_IDS[i:i+20]
            tasks = [update_attribute(session, item_id) for item_id in batch]
            await asyncio.gather(*tasks)
            print("⏱️ Esperando 1 segundo para el siguiente batch...")
            await asyncio.sleep(1)  # Esperar 1 segundo entre batches

if __name__ == "__main__":
    start = time.time()
    asyncio.run(process_items())
    print(f"🏁 Finalizado en {time.time() - start:.2f}s")
