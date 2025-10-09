#!/usr/bin/env python3
"""
Script de demostración del validador sin necesidad de tokens reales
Simula respuestas de la API de ML para mostrar el funcionamiento
"""

import pandas as pd
import json
from datetime import datetime
from validar_datos_ml import ValidadorML

class ValidadorDemo(ValidadorML):
    """Validador de demostración que simula respuestas de ML"""
    
    def __init__(self, tienda_config):
        super().__init__(tienda_config)
        # Datos simulados basados en los ejemplos proporcionados
        self.datos_simulados = {
            'MLM3614653022': {
                'id': 'MLM3614653022',
                'price': 299,
                'available_quantity': 200,
                'seller_custom_field': 'SFRE0019-S10615-B0001',
                'status': 'paused',  # Nota: en el ejemplo real está como 'paused', no 'active'
                'sold_quantity': 0
            },
            'MLM3827210040': {
                'id': 'MLM3827210040',
                'price': 299,
                'available_quantity': 200,
                'seller_custom_field': 'REAL0011-R20116-B0001',
                'status': 'paused',  # Nota: en el ejemplo real está como 'paused', no 'active'
                'sold_quantity': 0
            }
        }
    
    def obtener_detalles_multiget(self, ids, batch_size=20):
        """Simula la obtención de detalles de ML"""
        print(f"Simulando consulta para {len(ids)} IDs...")
        
        resultados = []
        for id_item in ids:
            if id_item in self.datos_simulados:
                resultados.append(self.datos_simulados[id_item])
            else:
                # Simular error para IDs no encontrados
                resultados.append({
                    'error': f'ID {id_item} no encontrado en ML (simulado)'
                })
        
        return resultados

def crear_datos_ejemplo():
    """Crea datos de ejemplo para la demostración"""
    
    datos_ejemplo = [
        {
            'ID': 'MLM3614653022',
            'Precio': 299,
            'Cantidad disponible': 200,
            'SellerCustomSku': 'SFRE0019-S10615-B0001',
            'Status': 'active'  # Intencionalmente diferente para mostrar validación
        },
        {
            'ID': 'MLM3827210040',
            'Precio': 299,
            'Cantidad disponible': 200,
            'SellerCustomSku': 'REAL0011-R20116-B0001',
            'Status': 'active'  # Intencionalmente diferente para mostrar validación
        },
        {
            'ID': 'MLM1234567890',
            'Precio': 150,
            'Cantidad disponible': 50,
            'SellerCustomSku': 'TEST-SKU-001',
            'Status': 'active'
        },
        {
            'ID': 'MLM9876543210',
            'Precio': 250,
            'Cantidad disponible': 100,
            'SellerCustomSku': 'TEST-SKU-002',
            'Status': 'paused'
        }
    ]
    
    return pd.DataFrame(datos_ejemplo)

def ejecutar_demo():
    """Ejecuta la demostración completa"""
    
    print("="*60)
    print("DEMOSTRACIÓN DEL VALIDADOR DE DATOS MERCADOLIBRE")
    print("="*60)
    
    # Crear datos de ejemplo
    print("\n1. Creando datos de ejemplo...")
    df = crear_datos_ejemplo()
    print("Datos de ejemplo:")
    print(df.to_string(index=False))
    
    # Crear archivo Excel
    archivo_ejemplo = 'demo_validacion.xlsx'
    df.to_excel(archivo_ejemplo, index=False)
    print(f"\nArchivo Excel creado: {archivo_ejemplo}")
    
    # Configurar validador demo
    print("\n2. Configurando validador de demostración...")
    tienda_demo = {
        'access_token': 'demo_token',
        'refresh_token': 'demo_refresh',
        'client_id': 'demo_client',
        'client_secret': 'demo_secret',
        'user_id': 'demo_user',
        'nombre_tienda': 'DEMO'
    }
    
    validador = ValidadorDemo(tienda_demo)
    
    # Obtener IDs
    ids = df['ID'].dropna().unique().tolist()
    print(f"IDs a procesar: {ids}")
    
    # Simular consulta a ML
    print("\n3. Simulando consulta a MercadoLibre...")
    datos_ml = validador.obtener_detalles_multiget(ids)
    
    # Crear diccionario para búsqueda
    datos_ml_dict = {}
    for item in datos_ml:
        if 'id' in item:
            datos_ml_dict[item['id']] = item
    
    # Validar cada fila
    print("\n4. Validando datos...")
    resultados_validacion = []
    for _, row in df.iterrows():
        id_item = row['ID']
        if pd.isna(id_item):
            continue
            
        datos_ml_item = datos_ml_dict.get(id_item, {'error': f'ID {id_item} no encontrado en ML'})
        resultado = validador.validar_item(row.to_dict(), datos_ml_item)
        resultados_validacion.append(resultado)
        
        # Mostrar resultado de validación
        status = "✅ VÁLIDO" if resultado['valido'] else "❌ INVÁLIDO"
        print(f"ID {id_item}: {status}")
        if not resultado['valido']:
            for error in resultado['errores']:
                print(f"  - {error}")
    
    # Generar estadísticas
    print("\n5. Generando estadísticas...")
    total_items = len(resultados_validacion)
    items_validos = sum(1 for r in resultados_validacion if r['valido'])
    items_invalidos = total_items - items_validos
    items_con_ventas = sum(1 for r in resultados_validacion if r.get('tiene_ventas', False))
    
    print(f"\n" + "="*40)
    print("RESUMEN DE VALIDACIÓN")
    print("="*40)
    print(f"Total items: {total_items}")
    print(f"Items válidos: {items_validos} ({items_validos/total_items*100:.1f}%)")
    print(f"Items inválidos: {items_invalidos} ({items_invalidos/total_items*100:.1f}%)")
    print(f"Items con ventas: {items_con_ventas} ({items_con_ventas/total_items*100:.1f}%)")
    
    # Mostrar detalles de errores
    print(f"\n" + "="*40)
    print("DETALLES DE ERRORES")
    print("="*40)
    
    for resultado in resultados_validacion:
        if not resultado['valido']:
            print(f"\nID: {resultado['id']}")
            print(f"Errores: {', '.join(resultado['errores'])}")
            print(f"Datos Excel: Precio={resultado['datos_excel'].get('Precio')}, "
                  f"Cantidad={resultado['datos_excel'].get('Cantidad disponible')}, "
                  f"SKU={resultado['datos_excel'].get('SellerCustomSku')}, "
                  f"Status={resultado['datos_excel'].get('Status')}")
            if resultado['datos_ml'] and 'error' not in resultado['datos_ml']:
                print(f"Datos ML: Precio={resultado['datos_ml'].get('price')}, "
                      f"Cantidad={resultado['datos_ml'].get('available_quantity')}, "
                      f"SKU={resultado['datos_ml'].get('seller_custom_field')}, "
                      f"Status={resultado['datos_ml'].get('status')}")
    
    print(f"\n" + "="*60)
    print("DEMOSTRACIÓN COMPLETADA")
    print("="*60)
    print("Este script demuestra cómo funciona el validador sin necesidad")
    print("de tokens reales de MercadoLibre. Para usar con datos reales,")
    print("ejecuta: python validar_datos_ml.py tu_archivo.xlsx --tienda CO")

if __name__ == "__main__":
    ejecutar_demo()
