import os
import time
import pandas as pd
import requests
import logging
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import BoundedSemaphore

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("log_promociones_CA.log"),
        logging.StreamHandler()
    ]
)

# Cargar variables de entorno
load_dotenv()

PROMOTION_ID = os.getenv("CA_PROMOTION_ID")
ACCESS_TOKEN = os.getenv("CA_ACCESS_TOKEN")
EXCEL_PATH = "../Data/Promociones/Tachar_CA.xlsx"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# Límite: 20 solicitudes por segundo
RATE_LIMIT = 20
semaphore = BoundedSemaphore(RATE_LIMIT)


def aplicar_promocion(item_id, deal_price):
    url = f"https://api.mercadolibre.com/seller-promotions/items/{item_id}?app_version=v2"
    payload = {
        "deal_price": deal_price,
        "promotion_id": PROMOTION_ID,
        "promotion_type": "DEAL"
    }

    with semaphore:
        try:
            response = requests.post(url, headers=HEADERS, json=payload)
            status = response.status_code

            if response.ok:
                logging.info(f"✅ [{status}] {item_id} - {PROMOTION_ID} → promoción aplicada con precio {deal_price}")
            else:
                logging.warning(f"⚠️ [{status}] {item_id} - {PROMOTION_ID} → error aplicando promoción: {response.text}")
        except Exception as e:
            logging.error(f"❌ {item_id} → excepción al aplicar promoción: {str(e)}")

        time.sleep(1 / RATE_LIMIT)  # Espera para respetar 20/s


def main():
    try:
        df = pd.read_excel(EXCEL_PATH)
        print(df.columns)
        items = [(str(row["PublicacionID"]).strip(), float(row["PrecioOferta"])) for _, row in df.iterrows()]

        with ThreadPoolExecutor(max_workers=RATE_LIMIT) as executor:
            futures = [executor.submit(aplicar_promocion, item_id, deal_price) for item_id, deal_price in items]
            for future in as_completed(futures):
                pass  # Ya se maneja el log en `aplicar_promocion`

    except FileNotFoundError:
        logging.error(f"❌ Archivo no encontrado: {EXCEL_PATH}")
    except Exception as e:
        logging.error(f"⚠️ Error general en ejecución: {e}")

if __name__ == "__main__":
    main()