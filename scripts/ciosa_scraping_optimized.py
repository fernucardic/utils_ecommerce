from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import pandas as pd
import os
import time

def extraer_ficha_tecnica_desde_json(prod):
    # Si la ficha técnica está en el JSON, extraerla aquí
    # (Ejemplo, adaptar según datos reales)
    ficha = {}
    if 'ficha_tecnica' in prod:
        ficha = prod['ficha_tecnica']
    return ficha

def extraer_npcs_relacionados_desde_json(prod):
    relacionados = []
    if 'relacionados' in prod:
        relacionados = prod['relacionados']
    return relacionados

def iniciar_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--headless")
    options.add_argument("--log-level=3")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    return driver

def busqueda_optimizada(param):
    busqueda_texto = param.get("busqueda", "")
    base_url = "https://www.ciosa.com/productosv2/resultados"
    productos_totales = []

    driver = iniciar_driver()

    try:
        driver.get(base_url)

        # Realizar búsqueda
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "search"))
        )
        search_input.clear()
        search_input.send_keys(busqueda_texto)
        search_input.send_keys(u'\ue007')  # Enter

        print(f"✅ Búsqueda '{busqueda_texto}' enviada")

        # Esperar que resultados carguen (usamos condición que npc_result esté definido)
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return typeof npc_result !== 'undefined' && npc_result.length > 0")
        )

        while True:
            # Extraer JSON con todos los productos visibles en la página
            npc_json = driver.execute_script(
                "return JSON.stringify(npc_result)"
            )
            npc_data = json.loads(npc_json)

            productos = [item['_source'] for item in npc_data if '_source' in item]
            print(f"Procesando {len(productos)} productos en esta página")

            for prod in productos:
                npc = prod.get('codigo', None)
                nombre = prod.get('descripcion_l', '')

                if not npc:
                    continue

                # Extraemos ficha técnica y relacionados desde JSON si existe
                ficha = extraer_ficha_tecnica_desde_json(prod)
                relacionados = extraer_npcs_relacionados_desde_json(prod)

                productos_totales.append({
                    "nombre": nombre,
                    "npc": npc,
                    "ficha_tecnica": ficha,
                    "relacionados": relacionados
                })

            # Intentar ir a siguiente página si existe
            try:
                page_links = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "pageLinks"))
                )
                siguiente = page_links.find_element(By.CSS_SELECTOR, "a[rel='next']")
                driver.execute_script("arguments[0].scrollIntoView(true);", siguiente)
                time.sleep(0.5)  # espera mínima para que el click sea efectivo
                siguiente.click()

                # Esperar que la página cambie
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return typeof npc_result !== 'undefined' && npc_result.length > 0")
                )

            except (TimeoutException, NoSuchElementException):
                print("No hay más páginas o error paginando")
                break

    finally:
        driver.quit()

    # Guardar resultados
    os.makedirs("Output/ciosa_scraping", exist_ok=True)
    if productos_totales:
        filename = f"Output/ciosa_scraping/ciosaparts_{busqueda_texto.replace(' ', '_')}.csv"
        df = pd.DataFrame(productos_totales)
        df['ficha_tecnica'] = df['ficha_tecnica'].apply(json.dumps)
        df['relacionados'] = df['relacionados'].apply(json.dumps)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"Guardados {len(productos_totales)} productos en {filename}")

    return productos_totales

def main():
    params = {"busqueda": "total parts"}
    print("🚀 Iniciando scraping optimizado...")
    productos = busqueda_optimizada(params)
    print(f"Scraping completado. Total productos: {len(productos)}")

if __name__ == "__main__":
    main()
