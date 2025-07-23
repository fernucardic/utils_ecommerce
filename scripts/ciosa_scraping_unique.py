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

def busqueda(codigo):
    options = Options()
    options.add_argument("--headless")  # Descomenta si no quieres ver el navegador
    driver = webdriver.Chrome(options=options)

    busqueda = codigo  # Cambia aquí la búsqueda deseada
    base_url = "https://www.ciosa.com/productosv2/resultados"

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
    
    return productos_totales



def main():
    codigos = [
        "03369", "03383", "03390", "03455", "03456", "03457", "03471", "03477", "03478",
        "03487", "03495", "03497", "03508", "03520", "03566", "03606", "05629", "07978",
        "08983", "11363", "11712", "11846", "34334", "36081", "36333", "36374", "37194",
        "37195", "37261", "37426", "37429", "38626", "38680", "38698", "39005", "39782",
        "39820", "39821", "39862", "39863", "40198", "40297", "40298", "40303", "40304",
        "40308", "40311", "40312", "40375", "40524", "40601", "40602", "40684", "40769",
        "41421", "41693", "41783", "41784", "41792", "41796", "41799", "41800", "41801",
        "41805", "41807", "41808", "41809", "41812", "41815", "41818", "41819", "41820",
        "41821", "41822", "41823", "41824", "41825", "41826", "41827", "41828", "41829",
        "41830", "41832", "41834", "41835", "41838", "41841", "41844", "41849", "41851",
        "41852", "41854", "41856", "41861", "41864", "41865", "41869", "41871", "41872",
        "41873", "41876", "41877", "41878", "41879", "41880", "41882", "41883", "41885",
        "41886", "41887", "41888", "41889", "41890", "41891", "41892", "41894", "41895",
        "41896", "41898", "41900", "41909", "41913", "41915", "41916", "41919", "41920",
        "41921", "41922", "41924", "41925", "41926", "41928", "41930", "41932", "41933",
        "41934", "41940", "41941", "41945", "41949", "41952", "41953", "41954", "41956",
        "41959", "41962", "41965", "41968", "41969", "41975", "41976", "41977", "41978",
        "41982", "41985", "41986", "41988", "41989", "41990", "41991", "41993", "41997",
        "41999", "42001", "42003", "42005", "42006", "42007", "42008", "42010", "42011",
        "42013", "42014", "42019", "42020", "42021", "42022", "42023", "42025", "42028",
        "42029", "42030", "42031", "42032", "42034", "42036", "42037", "42038", "42039",
        "42040", "42041", "42044", "42047", "42049", "42050", "42438", "42445", "42446",
        "42602", "42603", "42604", "42605", "42608", "42611", "42612", "42613", "42614",
        "42615", "42616", "42617", "42618", "42649", "42651", "42654", "42655", "43216",
        "43250", "43255", "43314", "43334", "43336", "43673", "43722", "43725", "43727",
        "43728", "43729", "43731", "43734", "43736", "43737", "43740", "43741", "43785",
        "43787", "43788", "43789", "43791", "43796", "46228", "47234", "47235", "47240",
        "47242", "47243", "47246", "47251", "47505", "47506", "47507", "47509", "47514",
        "47515", "47517", "47578", "48279", "48280", "48281", "48282", "48285", "48286",
        "48290", "48291", "48292", "48293", "48294", "48295", "48296", "48297", "48298",
        "48299", "50191"
    ]

    with Pool(processes=min(len(codigos), cpu_count())) as pool:
        resultados = pool.map(busqueda, codigos)

    # Combinar todos los resultados en un solo DataFrame
    productos_totales = [item for sublist in resultados for item in sublist]
    df = pd.DataFrame(productos_totales)
    df['ficha_tecnica'] = df['ficha_tecnica'].apply(json.dumps)
    df['relacionados'] = df['relacionados'].apply(json.dumps)
    df.to_csv("Output/ciosa_scraping/ciosaparts_completo.csv", index=False)
    print("✅ Datos guardados en ciosaparts_completo.csv")

if __name__ == "__main__":
    main()
