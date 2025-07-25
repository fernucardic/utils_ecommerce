import os
import asyncio
import aiohttp
import pandas as pd
import logging
from dotenv import load_dotenv
from datetime import datetime
from tqdm.asyncio import tqdm_asyncio

load_dotenv()

TIENDA = {
    "access_token": os.getenv("CO_ACCESS_TOKEN"),
    "refresh_token": os.getenv("CO_REFRESH_TOKEN"),
    "client_id": os.getenv("CO_CLIENT_ID"),
    "client_secret": os.getenv("CO_CLIENT_SECRET"),
    "user_id": os.getenv("CO_SELLER_ID"),
    "nombre_tienda": "CO"
}

RATE_LIMIT = 20
BATCH_SIZE = 19
SLEEP_BETWEEN_BATCHES = 1.0

nombre_tienda = TIENDA["nombre_tienda"]
LOG_FILENAME = f"../logs/{nombre_tienda}_eliminados.log"
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

semaforo = asyncio.Semaphore(RATE_LIMIT)

async def cerrar_item(session, item_id, token, tienda):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"https://api.mercadolibre.com/items/{item_id}"
    
    async with semaforo:
        for intento in range(5):
            try:
                async with session.put(url, headers=headers, json={"status": "closed"}) as response:
                    text = await response.text()
                    if response.status == 429:
                        await asyncio.sleep(2 ** intento)
                        continue
                    elif response.status >= 400:
                        logging.error(f"[CLOSE ❌] {item_id} - {tienda['nombre_tienda']} → {text}")
                    else:
                        logging.info(f"[CLOSE ✅] {item_id} - {tienda['nombre_tienda']}")
                    return
            except Exception as e:
                logging.error(f"[ERROR ❌] {item_id} - {tienda['nombre_tienda']} → {str(e)}")
                await asyncio.sleep(2 ** intento)

async def procesar_items(ids, tienda):
    token = tienda["access_token"]
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(limit=RATE_LIMIT)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [cerrar_item(session, item_id, token, tienda) for item_id in ids]
        await tqdm_asyncio.gather(*tasks, desc=f"🔧 Cerrando {len(ids)} ítems")

def main():
    try:
        df = pd.read_excel("../Data/Eliminar/Eliminar_CO.xlsx", dtype=str)
    except Exception as e:
        print(f"❌ Error leyendo el archivo Excel: {e}")
        return

    if "ID" not in df.columns:
        print("❌ El archivo Excel debe contener la columna 'ID'")
        return

    ids = df["ID"].dropna().astype(str)
    ids = ids.apply(lambda x: x if x.startswith("MLM") else f"MLM{x}").tolist()

    asyncio.run(procesar_items(ids, TIENDA))
    print(f"✅ Proceso finalizado. Revisa el log en {LOG_FILENAME}")

if __name__ == "__main__":
    main()
