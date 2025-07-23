from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import json
import time
import re
from multiprocessing import Pool, cpu_count
import os

# Setup directorios
os.makedirs("Output/ciosa_scraping", exist_ok=True)
base_url = "https://www.ciosa.com/productosv2/resultados"

# Selenium config
def iniciar_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)

def extraer_ficha_tecnica(driver):
    # Extrae ficha técnica en formato {clave: valor}
    ficha = {}
    try:
        # Esperar que esté el contenedor de especificaciones
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "especificaciones-prod"))
        )
        container = driver.find_element(By.ID, "especificaciones-prod")
        # Hay varios divs con clase bordered-box, pares de clave-valor
        cajas = container.find_elements(By.CSS_SELECTOR, "div.bordered-box")
        # Iteramos de 2 en 2 (clave y luego valor)
        for i in range(0, len(cajas), 2):
            claves = cajas[i].find_elements(By.CSS_SELECTOR, "div.row > div.col-md-4")
            valores = cajas[i+1].find_elements(By.CSS_SELECTOR, "div.row > div.col-md-4")
            for c, v in zip(claves, valores):
                clave = c.text.strip().rstrip(':')
                valor = v.text.strip()
                ficha[clave] = valor
    except Exception:
        # Si no encuentra ficha, devuelve vacio
        pass
    return ficha

def extraer_npcs_relacionados(driver):
    # Extrae lista de NPCs relacionados (solo códigos)
    npcs = []
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.owl-carousel-productos"))
        )
        contenedor = driver.find_element(By.CSS_SELECTOR, "div.owl-carousel-productos")
        productos = contenedor.find_elements(By.CSS_SELECTOR, "div.resultado_item")
        for p in productos:
            try:
                # El NPC está en un <p> con texto tipo "NPC: 39812"
                p_npc = p.find_element(By.TAG_NAME, "p")
                texto = p_npc.text.strip()
                if texto.startswith("NPC:"):
                    codigo = texto.replace("NPC:", "").strip()
                    npcs.append(codigo)
            except:
                continue
    except Exception:
        pass
    return npcs

def aplicar_filtros(driver, filtros):
    def seleccionar_checkbox(valor, nombre):
        try:
            input_elem = driver.find_element(By.CSS_SELECTOR, f"input[name='{nombre}'][value='{valor}']")
            driver.execute_script("arguments[0].click();", input_elem)
        except Exception as e:
            print(f"⚠️ No se pudo seleccionar el filtro {nombre}={valor}: {e}")

    # Abrir secciones colapsadas
    secciones = ["#filtroMarca", "#filtroGrupo", "#filtroSubgrupo"]
    for selector in secciones:
        try:
            div = driver.find_element(By.CSS_SELECTOR, selector)
            if "show" not in div.get_attribute("class"):
                driver.execute_script("arguments[0].classList.add('show');", div)
        except:
            pass

    if filtros.get("marca"):
        seleccionar_checkbox(filtros["marca"], "f_marca")
    if filtros.get("grupo"):
        seleccionar_checkbox(filtros["grupo"], "f_grupo")
    if filtros.get("sub_grupo"):
        seleccionar_checkbox(filtros["sub_grupo"], "f_subgrupo")

    try:
        driver.find_element(By.ID, "filtrosBusqueda").submit()
        time.sleep(3)
    except Exception as e:
        print("⚠️ Error al aplicar filtros:", e)

def busqueda(params):

    codigo = params["busqueda"]
    filtros = {
        "marca": params.get("marca"),
        "grupo": params.get("grupo"),
        "sub_grupo": params.get("sub_grupo")
    } 

    driver = iniciar_driver()

    productos_totales = []
    try:
        # Página inicial con búsqueda
        driver.get(base_url)
        time.sleep(2)

        # Buscar input y hacer búsqueda
        search_input = driver.find_element(By.NAME, "search")
        search_input.clear()
        search_input.send_keys(busqueda)
        search_input.send_keys(Keys.ENTER)

        # Esperar que npc_result esté cargado
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return typeof npc_result !== 'undefined' && npc_result.length > 0")
        )

        aplicar_filtros(driver, filtros)

        # Obtener total resultados desde paginación
        p_element = driver.find_element(By.CSS_SELECTOR, "div.col-md-12.text-center > p.mt-3")
        texto_rango = p_element.text.strip()
        print("Texto paginación:", texto_rango)
        match_total = re.search(r"de\s+(\d+)\s+resultados", texto_rango)
        if match_total:
            total_resultados = int(match_total.group(1))
        else:
            total_resultados = 12
        print(f"Total resultados: {total_resultados}")

        # Función para procesar página actual y extraer productos
        def procesar_pagina():
            # Extraer npc_result actual
            npc_json = driver.execute_script("return JSON.stringify(npc_result)")
            npc_data = json.loads(npc_json)
            productos = [item['_source'] for item in npc_data]

            for prod in productos:
                # Extraer datos básicos
                nombre = prod.get('descripcion_l', '')
                npc = prod.get('codigo', '')

                # Entrar al detalle del producto
                url_detalle = f"https://www.ciosa.com/productos/detalle/{npc}"
                driver.execute_script(f"window.open('{url_detalle}','_blank')")
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(2)  # esperar que cargue

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

        # Procesar primera página (offset implícito 0 no válido, esta es la inicial)
        procesar_pagina()

        while True:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "pageLinks"))
                )
                page_links = driver.find_element(By.ID, "pageLinks")
                pagina_actual = page_links.find_element(By.CSS_SELECTOR, "strong").text.strip()
                siguiente = page_links.find_element(By.CSS_SELECTOR, "a[rel='next']")

                # Hacer scroll y clic con JS para evitar errores de intercepción
                driver.execute_script("arguments[0].scrollIntoView(true);", siguiente)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", siguiente)

                WebDriverWait(driver, 10).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, "#pageLinks strong").text.strip() != pagina_actual
                )
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.resultado_item"))
                )

                procesar_pagina()  # sin argumentos
            except Exception as e:
                print("🚫 No hay más páginas o error:", e)
                break

    except Exception as e:
        print("⚠️ Error:", e)
    finally:
        driver.quit()

    # Guardar todo en CSV, convirtiendo ficha técnica y relacionados a JSON strings para mejor legibilidad
    df = pd.DataFrame(productos_totales)
    df['ficha_tecnica'] = df['ficha_tecnica'].apply(json.dumps)
    df['relacionados'] = df['relacionados'].apply(json.dumps)
    df.to_csv(f"Output/ciosa_scraping/ciosaparts_completo_{busqueda}.csv", index=False)
    print("✅ Datos guardados en ciosaparts_completo.csv")

def main():
    codigos = [
        {
            "busqueda": "40308C",
            "marca": "BOSCH",
            "grupo": "VALVULAS",
            "sub_grupo": "VALVULA IAC-BYPASS (RALENTI)"
        }
    ] 

    with Pool(processes=min(len(codigos), cpu_count())) as pool:
        pool.map(busqueda, codigos)

if __name__ == "__main__":
    main()