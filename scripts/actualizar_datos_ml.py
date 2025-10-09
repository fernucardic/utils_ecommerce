#!/usr/bin/env python3
"""
Script para actualizar datos de publicaciones en MercadoLibre
Lee un archivo Excel con columnas: ID, Precio, Cantidad disponible, SellerCustomSku, Status
Hace requests PUT a ML para actualizar cada publicación
Genera un reporte detallado con estadísticas de actualización
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

class ActualizadorML:
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

    def construir_payload(self, excel_row: Dict[str, Any]) -> Dict[str, Any]:
        """Construye el payload JSON para la actualización basado en los datos del Excel"""
        payload = {}
        
        # Precio
        precio = excel_row.get('Precio')
        if precio is not None and str(precio).strip() != '':
            try:
                payload['price'] = float(precio)
            except (ValueError, TypeError):
                print(f"   ⚠️  Precio inválido ignorado: {precio}")
        
        # Cantidad disponible
        cantidad = excel_row.get('Cantidad disponible')
        if cantidad is not None and str(cantidad).strip() != '':
            try:
                payload['available_quantity'] = int(cantidad)
            except (ValueError, TypeError):
                print(f"   ⚠️  Cantidad inválida ignorada: {cantidad}")
        
        # Seller Custom Field (SKU)
        sku = excel_row.get('SellerCustomSku')
        if sku is not None and str(sku).strip() != '':
            payload['seller_custom_field'] = str(sku).strip()
        
        # Status
        status = excel_row.get('Status')
        if status is not None and str(status).strip() != '':
            status_str = str(status).strip().lower()
            if status_str in ['active', 'paused', 'closed']:
                payload['status'] = status_str
            else:
                print(f"   ⚠️  Status inválido ignorado: {status} (debe ser: active, paused, closed)")
        
        return payload

    def actualizar_item(self, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza un item específico en MercadoLibre"""
        url = f"https://api.mercadolibre.com/items/{item_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.put(url, headers=headers, json=payload)
            
            # Si el token expiró, intentar renovarlo
            if resp.status_code == 401:
                print(f"⚠️  Token expirado para {self.nombre_tienda}, intentando renovar...")
                if self.renovar_token():
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    resp = requests.put(url, headers=headers, json=payload)
                    print(f"✅ Token renovado, reintentando actualización de {item_id}")
                else:
                    return {
                        'id': item_id,
                        'exitoso': False,
                        'error': 'No se pudo renovar token',
                        'codigo_respuesta': 401
                    }
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'id': item_id,
                    'exitoso': True,
                    'datos_actualizados': payload,
                    'respuesta_ml': data,
                    'codigo_respuesta': 200
                }
            else:
                error_data = resp.json() if resp.content else {}
                return {
                    'id': item_id,
                    'exitoso': False,
                    'error': error_data.get('message', f'Error HTTP {resp.status_code}'),
                    'codigo_respuesta': resp.status_code,
                    'datos_enviados': payload
                }
                
        except requests.RequestException as e:
            return {
                'id': item_id,
                'exitoso': False,
                'error': f'Error de conexión: {str(e)}',
                'codigo_respuesta': None,
                'datos_enviados': payload
            }

    def actualizar_items_lote(self, items_data: List[Dict[str, Any]], batch_size: int = 10) -> List[Dict[str, Any]]:
        """Actualiza múltiples items en lotes con logs de progreso"""
        total_items = len(items_data)
        total_batches = (total_items + batch_size - 1) // batch_size
        
        print(f"📡 Iniciando actualizaciones: {total_items} items en {total_batches} lotes de {batch_size}")
        
        todos_los_resultados = []
        
        for i in range(0, total_items, batch_size):
            batch_num = i // batch_size + 1
            batch = items_data[i:i + batch_size]
            
            print(f"🔄 Procesando lote {batch_num}/{total_batches} ({len(batch)} items)")
            
            exitosos = 0
            fallidos = 0
            
            for item_data in batch:
                item_id = item_data['id']
                payload = item_data['payload']
                
                print(f"   🔄 Actualizando {item_id}...")
                resultado = self.actualizar_item(item_id, payload)
                todos_los_resultados.append(resultado)
                
                if resultado['exitoso']:
                    exitosos += 1
                    print(f"   ✅ {item_id} actualizado exitosamente")
                else:
                    fallidos += 1
                    print(f"   ❌ {item_id} falló: {resultado.get('error', 'Error desconocido')}")
                
                # Pausa entre requests para no sobrecargar la API
                time.sleep(0.5)
            
            print(f"✅ Lote {batch_num} completado: {exitosos} exitosos, {fallidos} fallidos")
            
            # Pausa entre lotes
            if batch_num < total_batches:
                print(f"⏳ Pausa entre lotes...")
                time.sleep(2)
        
        print(f"📊 Actualizaciones completadas: {len(todos_los_resultados)} items procesados")
        return todos_los_resultados

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

def procesar_actualizacion(archivo_excel: str, tienda: str = "CO") -> Dict[str, Any]:
    """Procesa la actualización completa de datos"""
    print(f"🚀 Iniciando actualización para tienda: {tienda}")
    print("=" * 60)
    
    # Leer archivo Excel
    print("📁 Paso 1/4: Leyendo archivo Excel...")
    df = leer_archivo_excel(archivo_excel)
    if df is None:
        print("❌ Error: No se pudo leer el archivo Excel")
        return None
    print(f"✅ Archivo Excel leído exitosamente: {len(df)} filas")
    
    # Configurar actualizador
    print("\n🔧 Paso 2/4: Configurando actualizador...")
    if tienda not in TIENDAS_ML:
        print(f"❌ Error: Tienda {tienda} no encontrada. Tiendas disponibles: {list(TIENDAS_ML.keys())}")
        return None
    
    actualizador = ActualizadorML(TIENDAS_ML[tienda])
    print(f"✅ Actualizador configurado para tienda: {tienda}")
    
    # Preparar datos para actualización
    print("\n📊 Paso 3/4: Preparando datos para actualización...")
    items_data = []
    items_ignorados = 0
    
    for idx, row in df.iterrows():
        item_id = row['ID']
        if pd.isna(item_id):
            items_ignorados += 1
            continue
        
        payload = actualizador.construir_payload(row.to_dict())
        if not payload:
            print(f"   ⚠️  Item {item_id} ignorado: no hay datos válidos para actualizar")
            items_ignorados += 1
            continue
        
        items_data.append({
            'id': str(item_id),
            'payload': payload,
            'datos_originales': row.to_dict()
        })
    
    print(f"✅ Preparados {len(items_data)} items para actualización")
    if items_ignorados > 0:
        print(f"⚠️  {items_ignorados} items ignorados (sin datos válidos)")
    
    # Actualizar items
    print("\n🌐 Paso 4/4: Actualizando items en MercadoLibre...")
    resultados = actualizador.actualizar_items_lote(items_data)
    
    print(f"✅ Actualización completada: {len(resultados)} items procesados")
    print("=" * 60)
    
    return {
        'tienda': tienda,
        'total_items': len(resultados),
        'items_exitosos': sum(1 for r in resultados if r['exitoso']),
        'items_fallidos': sum(1 for r in resultados if not r['exitoso']),
        'items_ignorados': items_ignorados,
        'resultados': resultados,
        'fecha_procesamiento': datetime.now().isoformat()
    }

def generar_reporte(resultados: Dict[str, Any], archivo_salida: str = None) -> str:
    """Genera un reporte detallado de la actualización"""
    if not resultados:
        return "No hay resultados para reportar"
    
    print("📊 Generando reporte detallado...")
    
    # Calcular estadísticas
    total_items = resultados['total_items']
    items_exitosos = resultados['items_exitosos']
    items_fallidos = resultados['items_fallidos']
    items_ignorados = resultados['items_ignorados']
    
    print(f"   📈 Calculando estadísticas: {total_items} items totales")
    
    # Contar errores por tipo
    print("   🔍 Analizando errores...")
    errores_por_tipo = {}
    for resultado in resultados['resultados']:
        if not resultado['exitoso']:
            error = resultado.get('error', 'Error desconocido')
            tipo_error = error.split(':')[0] if ':' in error else error
            errores_por_tipo[tipo_error] = errores_por_tipo.get(tipo_error, 0) + 1
    
    # Generar reporte
    reporte = f"""
REPORTE DE ACTUALIZACIÓN MERCADOLIBRE
=====================================
Tienda: {resultados['tienda']}
Fecha: {resultados['fecha_procesamiento']}
Total de items procesados: {total_items}

ESTADÍSTICAS GENERALES
=====================
Items actualizados exitosamente: {items_exitosos} ({items_exitosos/total_items*100:.1f}%)
Items fallidos: {items_fallidos} ({items_fallidos/total_items*100:.1f}%)
Items ignorados: {items_ignorados}

ERRORES MÁS COMUNES
==================
"""
    
    for tipo_error, cantidad in sorted(errores_por_tipo.items(), key=lambda x: x[1], reverse=True):
        reporte += f"{tipo_error}: {cantidad} ocurrencias\n"
    
    reporte += f"""
DETALLE DE ITEMS FALLIDOS
=========================
"""
    
    for resultado in resultados['resultados']:
        if not resultado['exitoso']:
            reporte += f"\nID: {resultado['id']}\n"
            reporte += f"Error: {resultado.get('error', 'Error desconocido')}\n"
            reporte += f"Código de respuesta: {resultado.get('codigo_respuesta', 'N/A')}\n"
            if 'datos_enviados' in resultado:
                reporte += f"Datos enviados: {json.dumps(resultado['datos_enviados'], indent=2)}\n"
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
    
    parser = argparse.ArgumentParser(description='Actualizar datos de publicaciones en MercadoLibre')
    parser.add_argument('archivo_excel', help='Ruta al archivo Excel con los datos a actualizar')
    parser.add_argument('--tienda', default='CO', choices=list(TIENDAS_ML.keys()), 
                       help='Tienda a procesar (default: CO)')
    parser.add_argument('--salida', help='Archivo de salida para el reporte')
    parser.add_argument('--batch-size', type=int, default=10, 
                       help='Tamaño del lote para procesamiento (default: 10)')
    
    args = parser.parse_args()
    
    print("🎯 ACTUALIZADOR DE DATOS MERCADOLIBRE")
    print("=" * 50)
    print(f"📁 Archivo: {args.archivo_excel}")
    print(f"🏪 Tienda: {args.tienda}")
    print(f"📦 Tamaño de lote: {args.batch_size}")
    print(f"⏰ Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Verificar que el archivo existe
    if not os.path.exists(args.archivo_excel):
        print(f"❌ Error: El archivo {args.archivo_excel} no existe")
        return
    
    # Procesar actualización
    print("\n🚀 Iniciando proceso de actualización...")
    resultados = procesar_actualizacion(args.archivo_excel, args.tienda)
    
    if not resultados:
        print("❌ Error en el procesamiento")
        return
    
    # Generar reporte
    archivo_reporte = args.salida or f"reporte_actualizacion_{args.tienda}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    print(f"\n📋 Generando reporte: {archivo_reporte}")
    reporte = generar_reporte(resultados, archivo_reporte)
    
    # Mostrar resumen en consola
    print("\n" + "="*60)
    print("📊 RESUMEN EJECUTIVO")
    print("="*60)
    
    total_items = resultados['total_items']
    items_exitosos = resultados['items_exitosos']
    items_fallidos = resultados['items_fallidos']
    items_ignorados = resultados['items_ignorados']
    
    print(f"📈 Total items: {total_items}")
    print(f"✅ Items actualizados: {items_exitosos} ({items_exitosos/total_items*100:.1f}%)")
    print(f"❌ Items fallidos: {items_fallidos} ({items_fallidos/total_items*100:.1f}%)")
    print(f"⚠️  Items ignorados: {items_ignorados}")
    print(f"📄 Reporte completo: {archivo_reporte}")
    print(f"⏰ Finalizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print("🎉 ¡Proceso de actualización completado!")

if __name__ == "__main__":
    main()
