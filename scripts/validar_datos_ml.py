#!/usr/bin/env python3
"""
Script para validar datos de Excel contra la API de MercadoLibre
Lee un archivo Excel con columnas: ID, Precio, Cantidad disponible, SellerCustomSku, Status
Hace consultas multiget a ML en grupos de 20 IDs y valida la información
Genera un reporte detallado con estadísticas de validación
"""

import pandas as pd
import requests
import time
import json
import os
from datetime import datetime
from typing import List, Dict, Tuple, Any
from dotenv import load_dotenv

load_dotenv()

# === CONFIGURACIÓN ===
TIENDAS_ML = {
    "CO": {
        "access_token": os.getenv("CO_ACCESS_TOKEN"),
        "refresh_token": os.getenv("CO_REFRESH_TOKEN"),
        "client_id": os.getenv("CO_CLIENT_ID"),
        "client_secret": os.getenv("CO_CLIENT_SECRET"),
        "user_id": os.getenv("CO_SELLER_ID"),
        "nombre_tienda": "CO"
    },
    "DS": {
        "access_token": os.getenv("DS_ACCESS_TOKEN"),
        "refresh_token": os.getenv("DS_REFRESH_TOKEN"),
        "client_id": os.getenv("DS_CLIENT_ID"),
        "client_secret": os.getenv("DS_CLIENT_SECRET"),
        "user_id": os.getenv("DS_SELLER_ID"),
        "nombre_tienda": "DS"
    },
    "TE": {
        "access_token": os.getenv("TE_ACCESS_TOKEN"),
        "refresh_token": os.getenv("TE_REFRESH_TOKEN"),
        "client_id": os.getenv("TE_CLIENT_ID"),
        "client_secret": os.getenv("TE_CLIENT_SECRET"),
        "user_id": os.getenv("TE_SELLER_ID"),
        "nombre_tienda": "TE"
    },
    "TS": {
        "access_token": os.getenv("TS_ACCESS_TOKEN"),
        "refresh_token": os.getenv("TS_REFRESH_TOKEN"),
        "client_id": os.getenv("TS_CLIENT_ID"),
        "client_secret": os.getenv("TS_CLIENT_SECRET"),
        "user_id": os.getenv("TS_SELLER_ID"),
        "nombre_tienda": "TS"
    },
    "CA": {
        "access_token": os.getenv("CA_ACCESS_TOKEN"),
        "refresh_token": os.getenv("CA_REFRESH_TOKEN"),
        "client_id": os.getenv("CA_CLIENT_ID"),
        "client_secret": os.getenv("CA_CLIENT_SECRET"),
        "user_id": os.getenv("CA_SELLER_ID"),
        "nombre_tienda": "CA"
    },
}

class ValidadorML:
    def __init__(self, tienda_config: Dict[str, str]):
        self.tienda = tienda_config
        self.access_token = tienda_config["access_token"]
        self.nombre_tienda = tienda_config["nombre_tienda"]
        
    def renovar_token(self, max_intentos: int = 3, espera_inicial: int = 1) -> bool:
        """Renueva el token de acceso de MercadoLibre"""
        print(f"🔄 Iniciando renovación de token para {self.nombre_tienda}...")
        url = "https://api.mercadolibre.com/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.tienda["client_id"],
            "client_secret": self.tienda["client_secret"],
            "refresh_token": self.tienda["refresh_token"]
        }

        for intento in range(1, max_intentos + 1):
            print(f"   🔄 Intento {intento}/{max_intentos} de renovación...")
            try:
                resp = requests.post(url, data=payload)
                resp.raise_for_status()
                data = resp.json()
                self.tienda["access_token"] = data["access_token"]
                self.tienda["refresh_token"] = data["refresh_token"]
                self.access_token = data["access_token"]
                print(f"✅ Token renovado exitosamente para {self.nombre_tienda} (intento {intento})")
                return True
            except requests.RequestException as e:
                print(f"❌ Intento {intento} fallido para {self.nombre_tienda}: {e}")
                if intento < max_intentos:
                    print(f"   ⏳ Esperando {espera_inicial * intento} segundos antes del siguiente intento...")
                    time.sleep(espera_inicial * intento)
                else:
                    print(f"❌ Falló renovación del token para {self.nombre_tienda} tras {max_intentos} intentos.")
                    return False

    def obtener_detalles_multiget(self, ids: List[str], batch_size: int = 20) -> List[Dict[str, Any]]:
        """Obtiene detalles de múltiples items usando multiget API"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        todos_los_resultados = []
        total_batches = (len(ids) + batch_size - 1) // batch_size
        
        print(f"📡 Iniciando consultas a ML API: {len(ids)} IDs en {total_batches} lotes de {batch_size}")
        
        for i in range(0, len(ids), batch_size):
            batch_num = i // batch_size + 1
            batch = ids[i:i + batch_size]
            url = "https://api.mercadolibre.com/items"
            params = {"ids": ",".join(batch)}
            
            print(f"🔄 Procesando lote {batch_num}/{total_batches} ({len(batch)} IDs): {batch[0]}{'...' if len(batch) > 1 else ''}")
            
            try:
                resp = requests.get(url, headers=headers, params=params)
                
                # Si el token expiró, intentar renovarlo
                if resp.status_code == 401:
                    print(f"⚠️  Token expirado para {self.nombre_tienda}, intentando renovar...")
                    if self.renovar_token():
                        headers = {"Authorization": f"Bearer {self.access_token}"}
                        resp = requests.get(url, headers=headers, params=params)
                        print(f"✅ Token renovado, reintentando lote {batch_num}")
                    else:
                        print(f"❌ No se pudo renovar token para {self.nombre_tienda}")
                        continue
                
                resp.raise_for_status()
                resultados = resp.json()
                
                exitosos = 0
                fallidos = 0
                
                for entry in resultados:
                    if entry.get("code") == 200:
                        todos_los_resultados.append(entry["body"])
                        exitosos += 1
                    else:
                        # Agregar información de error para IDs que fallaron
                        error_info = {
                            "id": batch[resultados.index(entry)] if entry.get("code") else "unknown",
                            "error": f"Code {entry.get('code')}: {entry.get('body', {}).get('message', 'Unknown error')}"
                        }
                        todos_los_resultados.append(error_info)
                        fallidos += 1
                
                print(f"✅ Lote {batch_num} completado: {exitosos} exitosos, {fallidos} fallidos")
                
                # Pequeña pausa entre requests para no sobrecargar la API
                time.sleep(0.1)
                
            except requests.RequestException as e:
                print(f"❌ Error en lote {batch_num} para {self.nombre_tienda}: {e}")
                continue
        
        print(f"📊 Consultas completadas: {len(todos_los_resultados)} respuestas obtenidas")
        return todos_los_resultados

    def validar_item(self, excel_row: Dict[str, Any], ml_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valida un item comparando datos de Excel vs ML"""
        id_item = excel_row.get('ID', '')
        
        # Si hay error en la respuesta de ML
        if 'error' in ml_data:
            return {
                'id': id_item,
                'valido': False,
                'errores': [f"Error API ML: {ml_data['error']}"],
                'datos_excel': excel_row,
                'datos_ml': None
            }
        
        errores = []
        
        # Validar precio
        try:
            precio_excel = excel_row.get('Precio')
            precio_ml = ml_data.get('price')
            if precio_excel is not None and precio_ml is not None:
                if float(precio_excel) != float(precio_ml):
                    errores.append(f"Precio: Excel={precio_excel}, ML={precio_ml}")
        except (ValueError, TypeError) as e:
            errores.append(f"Precio: Error en conversión - {e}")
        
        # Validar cantidad disponible
        try:
            cantidad_excel = excel_row.get('Cantidad disponible')
            cantidad_ml = ml_data.get('available_quantity')
            if cantidad_excel is not None and cantidad_ml is not None:
                if int(cantidad_excel) != int(cantidad_ml):
                    errores.append(f"Cantidad: Excel={cantidad_excel}, ML={cantidad_ml}")
        except (ValueError, TypeError) as e:
            errores.append(f"Cantidad: Error en conversión - {e}")
        
        # Validar SellerCustomSku
        sku_excel = str(excel_row.get('SellerCustomSku', '') or '').strip()
        sku_ml = str(ml_data.get('seller_custom_field', '') or '').strip()
        if sku_excel and sku_ml and sku_excel != sku_ml:
            errores.append(f"SKU: Excel={sku_excel}, ML={sku_ml}")
        
        # Validar status
        status_excel = str(excel_row.get('Status', '') or '').strip().lower()
        status_ml = str(ml_data.get('status', '') or '').strip().lower()
        if status_excel and status_ml and status_excel != status_ml:
            errores.append(f"Status: Excel={status_excel}, ML={status_ml}")
        
        return {
            'id': id_item,
            'valido': len(errores) == 0,
            'errores': errores,
            'datos_excel': excel_row,
            'datos_ml': ml_data,
            'tiene_ventas': ml_data.get('sold_quantity', 0) > 0 if 'sold_quantity' in ml_data else False
        }

def leer_archivo_excel(ruta_archivo: str) -> pd.DataFrame:
    """Lee el archivo Excel y valida las columnas requeridas"""
    print(f"   📖 Leyendo archivo: {ruta_archivo}")
    
    try:
        # Intentar leer como Excel
        df = pd.read_excel(ruta_archivo)
        print(f"   ✅ Archivo leído exitosamente: {len(df)} filas encontradas")
    except Exception as e:
        print(f"   ❌ Error leyendo archivo Excel: {e}")
        return None
    
    # Verificar columnas requeridas
    print("   🔍 Validando estructura del archivo...")
    columnas_requeridas = ['ID', 'Precio', 'Cantidad disponible', 'SellerCustomSku', 'Status']
    columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
    
    if columnas_faltantes:
        print(f"   ❌ Columnas faltantes en el archivo: {columnas_faltantes}")
        print(f"   📋 Columnas disponibles: {list(df.columns)}")
        return None
    
    print(f"   ✅ Estructura del archivo válida: todas las columnas requeridas presentes")
    return df

def procesar_validacion(archivo_excel: str, tienda: str = "CO") -> Dict[str, Any]:
    """Procesa la validación completa de datos"""
    print(f"🚀 Iniciando validación para tienda: {tienda}")
    print("=" * 60)
    
    # Leer archivo Excel
    print("📁 Paso 1/5: Leyendo archivo Excel...")
    df = leer_archivo_excel(archivo_excel)
    if df is None:
        print("❌ Error: No se pudo leer el archivo Excel")
        return None
    print(f"✅ Archivo Excel leído exitosamente: {len(df)} filas")
    
    # Configurar validador
    print("\n🔧 Paso 2/5: Configurando validador...")
    if tienda not in TIENDAS_ML:
        print(f"❌ Error: Tienda {tienda} no encontrada. Tiendas disponibles: {list(TIENDAS_ML.keys())}")
        return None
    
    validador = ValidadorML(TIENDAS_ML[tienda])
    print(f"✅ Validador configurado para tienda: {tienda}")
    
    # Obtener IDs únicos
    print("\n🔍 Paso 3/5: Preparando IDs para consulta...")
    ids = df['ID'].dropna().unique().tolist()
    print(f"✅ Procesando {len(ids)} IDs únicos")
    
    # Obtener datos de ML
    print("\n🌐 Paso 4/5: Obteniendo datos de MercadoLibre...")
    datos_ml = validador.obtener_detalles_multiget(ids)
    print(f"✅ Obtenidos {len(datos_ml)} respuestas de ML")
    
    # Crear diccionario para búsqueda rápida
    print("\n📊 Paso 5/5: Procesando validaciones...")
    datos_ml_dict = {}
    for item in datos_ml:
        if 'id' in item:
            datos_ml_dict[item['id']] = item
    
    print(f"🔄 Validando {len(df)} filas del Excel...")
    resultados_validacion = []
    items_procesados = 0
    
    for idx, row in df.iterrows():
        id_item = row['ID']
        if pd.isna(id_item):
            continue
            
        datos_ml_item = datos_ml_dict.get(id_item, {'error': f'ID {id_item} no encontrado en ML'})
        resultado = validador.validar_item(row.to_dict(), datos_ml_item)
        resultados_validacion.append(resultado)
        
        items_procesados += 1
        if items_procesados % 50 == 0 or items_procesados == len(df):
            print(f"   📈 Progreso: {items_procesados}/{len(df)} items validados ({items_procesados/len(df)*100:.1f}%)")
    
    print(f"✅ Validación completada: {len(resultados_validacion)} items procesados")
    print("=" * 60)
    
    return {
        'tienda': tienda,
        'total_items': len(resultados_validacion),
        'resultados': resultados_validacion,
        'fecha_procesamiento': datetime.now().isoformat()
    }

def generar_reporte(resultados: Dict[str, Any], archivo_salida: str = None) -> str:
    """Genera un reporte detallado de la validación"""
    if not resultados:
        return "No hay resultados para reportar"
    
    print("📊 Generando reporte detallado...")
    
    # Calcular estadísticas
    total_items = resultados['total_items']
    items_validos = sum(1 for r in resultados['resultados'] if r['valido'])
    items_invalidos = total_items - items_validos
    items_con_ventas = sum(1 for r in resultados['resultados'] if r.get('tiene_ventas', False))
    items_sin_ventas = total_items - items_con_ventas
    
    print(f"   📈 Calculando estadísticas: {total_items} items totales")
    
    # Contar errores por tipo
    print("   🔍 Analizando errores...")
    errores_por_tipo = {}
    for resultado in resultados['resultados']:
        if not resultado['valido']:
            for error in resultado['errores']:
                tipo_error = error.split(':')[0] if ':' in error else error
                errores_por_tipo[tipo_error] = errores_por_tipo.get(tipo_error, 0) + 1
    
    # Generar reporte
    reporte = f"""
REPORTE DE VALIDACIÓN MERCADOLIBRE
==================================
Tienda: {resultados['tienda']}
Fecha: {resultados['fecha_procesamiento']}
Total de items procesados: {total_items}

ESTADÍSTICAS GENERALES
=====================
Items válidos (datos coinciden): {items_validos} ({items_validos/total_items*100:.1f}%)
Items inválidos (datos no coinciden): {items_invalidos} ({items_invalidos/total_items*100:.1f}%)

ESTADÍSTICAS DE VENTAS
=====================
Items con ventas: {items_con_ventas} ({items_con_ventas/total_items*100:.1f}%)
Items sin ventas: {items_sin_ventas} ({items_sin_ventas/total_items*100:.1f}%)

ERRORES MÁS COMUNES
==================
"""
    
    for tipo_error, cantidad in sorted(errores_por_tipo.items(), key=lambda x: x[1], reverse=True):
        reporte += f"{tipo_error}: {cantidad} ocurrencias\n"
    
    reporte += f"""
DETALLE DE ITEMS INVÁLIDOS
=========================
"""
    
    for resultado in resultados['resultados']:
        if not resultado['valido']:
            reporte += f"\nID: {resultado['id']}\n"
            reporte += f"Errores: {', '.join(resultado['errores'])}\n"
            if resultado['datos_excel']:
                reporte += f"Datos Excel: Precio={resultado['datos_excel'].get('Precio')}, "
                reporte += f"Cantidad={resultado['datos_excel'].get('Cantidad disponible')}, "
                reporte += f"SKU={resultado['datos_excel'].get('SellerCustomSku')}, "
                reporte += f"Status={resultado['datos_excel'].get('Status')}\n"
            if resultado['datos_ml'] and 'error' not in resultado['datos_ml']:
                reporte += f"Datos ML: Precio={resultado['datos_ml'].get('price')}, "
                reporte += f"Cantidad={resultado['datos_ml'].get('available_quantity')}, "
                reporte += f"SKU={resultado['datos_ml'].get('seller_custom_field')}, "
                reporte += f"Status={resultado['datos_ml'].get('status')}\n"
            reporte += "-" * 50 + "\n"
    
    # Guardar reporte si se especifica archivo
    if archivo_salida:
        print(f"💾 Guardando reporte en: {archivo_salida}")
        with open(archivo_salida, 'w', encoding='utf-8') as f:
            f.write(reporte)
        print(f"✅ Reporte guardado exitosamente")
    
    return reporte

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validar datos de Excel contra MercadoLibre')
    parser.add_argument('archivo_excel', help='Ruta al archivo Excel con los datos')
    parser.add_argument('--tienda', default='CO', choices=list(TIENDAS_ML.keys()), 
                       help='Tienda a procesar (default: CO)')
    parser.add_argument('--salida', help='Archivo de salida para el reporte')
    
    args = parser.parse_args()
    
    print("🎯 VALIDADOR DE DATOS MERCADOLIBRE")
    print("=" * 50)
    print(f"📁 Archivo: {args.archivo_excel}")
    print(f"🏪 Tienda: {args.tienda}")
    print(f"⏰ Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Verificar que el archivo existe
    if not os.path.exists(args.archivo_excel):
        print(f"❌ Error: El archivo {args.archivo_excel} no existe")
        return
    
    # Procesar validación
    print("\n🚀 Iniciando proceso de validación...")
    resultados = procesar_validacion(args.archivo_excel, args.tienda)
    
    if not resultados:
        print("❌ Error en el procesamiento")
        return
    
    # Generar reporte
    archivo_reporte = args.salida or f"reporte_validacion_{args.tienda}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    print(f"\n📋 Generando reporte: {archivo_reporte}")
    reporte = generar_reporte(resultados, archivo_reporte)
    
    # Mostrar resumen en consola
    print("\n" + "="*60)
    print("📊 RESUMEN EJECUTIVO")
    print("="*60)
    
    total_items = resultados['total_items']
    items_validos = sum(1 for r in resultados['resultados'] if r['valido'])
    items_con_ventas = sum(1 for r in resultados['resultados'] if r.get('tiene_ventas', False))
    
    print(f"📈 Total items: {total_items}")
    print(f"✅ Items válidos: {items_validos} ({items_validos/total_items*100:.1f}%)")
    print(f"❌ Items inválidos: {total_items - items_validos} ({(total_items - items_validos)/total_items*100:.1f}%)")
    print(f"💰 Items con ventas: {items_con_ventas} ({items_con_ventas/total_items*100:.1f}%)")
    print(f"📄 Reporte completo: {archivo_reporte}")
    print(f"⏰ Finalizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print("🎉 ¡Proceso completado exitosamente!")

if __name__ == "__main__":
    main()
