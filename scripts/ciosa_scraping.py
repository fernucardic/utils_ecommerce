from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import json
import time
import re
import os

def extraer_ficha_tecnica(driver):
    ficha = {}
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "especificaciones-prod"))
        )
        container = driver.find_element(By.ID, "especificaciones-prod")
        cajas = container.find_elements(By.CSS_SELECTOR, "div.bordered-box")
        if cajas and len(cajas) >= 2:
            for i in range(0, len(cajas), 2):
                if i + 1 < len(cajas):
                    claves = cajas[i].find_elements(By.CSS_SELECTOR, "div.row > div")
                    valores = cajas[i+1].find_elements(By.CSS_SELECTOR, "div.row > div")
                    for c, v in zip(claves, valores):
                        clave = c.text.strip().rstrip(':')
                        valor = v.text.strip()
                        if clave and valor:
                            ficha[clave] = valor
    except TimeoutException:
        print("⚠️ No se encontró contenedor de especificaciones")
    return ficha

def extraer_npcs_relacionados(driver):
    npcs = []
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.owl-carousel-productos"))
        )
        contenedor = driver.find_element(By.CSS_SELECTOR, "div.owl-carousel-productos")
        productos = contenedor.find_elements(By.CSS_SELECTOR, "div.resultado_item")
        for p in productos:
            try:
                texto = p.find_element(By.TAG_NAME, "p").text.strip()
                if texto.startswith("NPC:"):
                    codigo = texto.replace("NPC:", "").strip()
                    if codigo.isdigit():
                        npcs.append(codigo)
            except:
                continue
    except TimeoutException:
        print("⚠️ No se encontraron productos relacionados")
    return list(dict.fromkeys(npcs))  # elimina duplicados manteniendo orden

def busqueda(param):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--headless")  # Puedes activar modo headless si deseas
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)

    busqueda_texto = param.get("busqueda", "")
    base_url = "https://www.ciosa.com/productosv2/resultados"
    productos_totales = []

    try:
        print(f"🔍 Iniciando búsqueda: '{busqueda_texto}'")
        driver.get(base_url)
        time.sleep(3)

        # Realizar búsqueda
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "search"))
            )
            search_input.clear()
            search_input.send_keys(busqueda_texto)
            search_input.send_keys(Keys.ENTER)
            print("✅ Búsqueda inicial enviada")
        except TimeoutException:
            print("⚠️ No se encontró el campo de búsqueda")
            return []

        # Esperar para que el usuario aplique filtros manualmente
        print("⏳ Esperando 20 segundos para aplicar filtros manualmente...")
        time.sleep(20)

        # Verificar si hay resultados
        try:
            WebDriverWait(driver, 15).until(
                lambda d: (
                    d.execute_script("return typeof npc_result !== 'undefined' && npc_result && npc_result.length >= 0") or
                    len(d.find_elements(By.CSS_SELECTOR, "div.no-results-message")) > 0
                )
            )
            print("✅ Resultados cargados")
        except TimeoutException:
            print("⚠️ Timeout esperando resultados")
            return []

        def procesar_pagina():
            nonlocal productos_totales
            try:
                npc_json = driver.execute_script(
                    "return typeof npc_result !== 'undefined' ? JSON.stringify(npc_result) : '[]'"
                )
                npc_data = json.loads(npc_json) if npc_json != '[]' else []

                productos = [item['_source'] for item in npc_data if '_source' in item]

                print(f"📦 Procesando {len(productos)} productos en esta página")

                for i, prod in enumerate(productos):
                    try:
                        nombre = prod.get('descripcion_l', '')
                        npc = prod.get('codigo', '')

                        if not npc:
                            continue

                        print(f"🔍 Procesando producto {i+1}/{len(productos)}: {npc}")

                        url_detalle = f"https://www.ciosa.com/productos/detalle/{npc}"
                        driver.execute_script(f"window.open('{url_detalle}','_blank')")
                        driver.switch_to.window(driver.window_handles[1])

                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(2)

                        ficha = extraer_ficha_tecnica(driver)
                        relacionados = extraer_npcs_relacionados(driver)

                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

                        productos_totales.append({
                            "nombre": nombre,
                            "npc": npc,
                            "ficha_tecnica": ficha,
                            "relacionados": relacionados
                        })

                        print(f"✅ Producto {npc} procesado.")
                    except Exception as e:
                        print(f"⚠️ Error procesando producto: {e}")
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        continue
            except Exception as e:
                print(f"⚠️ Error procesando página: {e}")

        # Procesar página actual
        procesar_pagina()

        # Navegar por páginas adicionales
        while True:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "pageLinks"))
                )
                page_links = driver.find_element(By.ID, "pageLinks")
                pagina_actual_elem = page_links.find_element(By.CSS_SELECTOR, "strong")
                pagina_actual_num = pagina_actual_elem.text.strip()

                try:
                    siguiente = page_links.find_element(By.CSS_SELECTOR, "a[rel='next']")
                except NoSuchElementException:
                    print("📄 No hay más páginas")
                    break

                driver.execute_script("arguments[0].scrollIntoView(true);", siguiente)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", siguiente)

                WebDriverWait(driver, 15).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, "#pageLinks strong").text.strip() != pagina_actual_num
                )
                WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.resultado_item"))
                )

                procesar_pagina()

            except Exception as e:
                print(f"🚫 Fin de paginación o error: {e}")
                break

    except Exception as e:
        print(f"⚠️ Error general: {e}")
    finally:
        driver.quit()

    # Guardar resultados
    os.makedirs("Output/ciosa_scraping", exist_ok=True)

    if productos_totales:
        filename = f"Output/ciosa_scraping/ciosaparts_completo_{busqueda_texto.replace(' ', '_')}.csv"
        df = pd.DataFrame(productos_totales)
        df['ficha_tecnica'] = df['ficha_tecnica'].apply(json.dumps)
        df['relacionados'] = df['relacionados'].apply(json.dumps)
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"✅ {len(productos_totales)} productos guardados en {filename}")
    else:
        print("❌ No se extrajeron productos")

    return productos_totales

def main():
    params = {
        "busqueda": "injetech"
    }
    print("🚀 Iniciando scraping de Ciosa...")
    productos = busqueda(params)
    print(f"🎯 Scraping completado. Total productos: {len(productos)}")

if __name__ == "__main__":
    main()
