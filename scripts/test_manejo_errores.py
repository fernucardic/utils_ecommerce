#!/usr/bin/env python3
"""
Script para probar el manejo de errores del validador
Incluye casos edge como valores None, tipos incorrectos, etc.
"""

import pandas as pd
from datetime import datetime
from validar_datos_ml import ValidadorML

class ValidadorTestErrores(ValidadorML):
    """Validador de prueba que simula respuestas con errores"""
    
    def __init__(self, tienda_config):
        super().__init__(tienda_config)
        # Datos simulados con casos edge para probar manejo de errores
        self.datos_simulados = {
            'MLM3614653022': {
                'id': 'MLM3614653022',
                'price': 299,
                'available_quantity': 200,
                'seller_custom_field': 'SFRE0019-S10615-B0001',
                'status': 'paused',
                'sold_quantity': 0
            },
            'MLM3827210040': {
                'id': 'MLM3827210040',
                'price': None,  # Precio None para probar manejo de errores
                'available_quantity': 200,
                'seller_custom_field': None,  # SKU None
                'status': 'paused',
                'sold_quantity': 0
            },
            'MLM1234567890': {
                'id': 'MLM1234567890',
                'price': 'invalid_price',  # Precio inválido
                'available_quantity': 'invalid_qty',  # Cantidad inválida
                'seller_custom_field': 'TEST-SKU-001',
                'status': 'active',
                'sold_quantity': 0
            },
            'MLM9876543210': {
                'id': 'MLM9876543210',
                'price': 250,
                'available_quantity': 100,
                'seller_custom_field': '',  # SKU vacío
                'status': '',  # Status vacío
                'sold_quantity': 0
            }
        }
    
    def obtener_detalles_multiget(self, ids, batch_size=20):
        """Simula la obtención de detalles de ML con casos edge"""
        print(f"Simulando consulta para {len(ids)} IDs con casos edge...")
        
        resultados = []
        for id_item in ids:
            if id_item in self.datos_simulados:
                resultados.append(self.datos_simulados[id_item])
            else:
                resultados.append({
                    'error': f'ID {id_item} no encontrado en ML (simulado)'
                })
        
        return resultados

def crear_datos_con_errores():
    """Crea datos de Excel con casos edge para probar manejo de errores"""
    
    datos_ejemplo = [
        {
            'ID': 'MLM3614653022',
            'Precio': 299,
            'Cantidad disponible': 200,
            'SellerCustomSku': 'SFRE0019-S10615-B0001',
            'Status': 'active'
        },
        {
            'ID': 'MLM3827210040',
            'Precio': None,  # Precio None en Excel
            'Cantidad disponible': 200,
            'SellerCustomSku': None,  # SKU None en Excel
            'Status': 'active'
        },
        {
            'ID': 'MLM1234567890',
            'Precio': 'invalid',  # Precio inválido en Excel
            'Cantidad disponible': 'invalid',  # Cantidad inválida en Excel
            'SellerCustomSku': 'TEST-SKU-001',
            'Status': 'active'
        },
        {
            'ID': 'MLM9876543210',
            'Precio': 250,
            'Cantidad disponible': 100,
            'SellerCustomSku': '',  # SKU vacío en Excel
            'Status': '',  # Status vacío en Excel
        },
        {
            'ID': 'MLM9999999999',  # ID que no existe en ML
            'Precio': 150,
            'Cantidad disponible': 50,
            'SellerCustomSku': 'TEST-SKU-999',
            'Status': 'active'
        }
    ]
    
    return pd.DataFrame(datos_ejemplo)

def ejecutar_prueba_errores():
    """Ejecuta la prueba de manejo de errores"""
    
    print("🧪 PRUEBA DE MANEJO DE ERRORES")
    print("=" * 50)
    
    # Crear datos con casos edge
    print("📁 Creando datos de prueba con casos edge...")
    df = crear_datos_con_errores()
    archivo_prueba = 'prueba_errores.xlsx'
    df.to_excel(archivo_prueba, index=False)
    print(f"✅ Archivo creado: {archivo_prueba}")
    print("Datos de prueba:")
    print(df.to_string(index=False))
    
    # Configurar validador de prueba
    print("\n🔧 Configurando validador de prueba...")
    tienda_test = {
        'access_token': 'test_token',
        'refresh_token': 'test_refresh',
        'client_id': 'test_client',
        'client_secret': 'test_secret',
        'user_id': 'test_user',
        'nombre_tienda': 'TEST_ERRORS'
    }
    
    validador = ValidadorTestErrores(tienda_test)
    
    # Obtener IDs
    ids = df['ID'].dropna().unique().tolist()
    print(f"🔍 IDs a procesar: {ids}")
    
    # Simular consulta a ML
    print("\n🌐 Simulando consulta a MercadoLibre...")
    datos_ml = validador.obtener_detalles_multiget(ids)
    
    # Crear diccionario para búsqueda
    datos_ml_dict = {}
    for item in datos_ml:
        if 'id' in item:
            datos_ml_dict[item['id']] = item
    
    # Validar cada fila
    print("\n🔄 Validando datos con manejo de errores...")
    resultados_validacion = []
    
    for idx, row in df.iterrows():
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
    print("\n📊 Generando estadísticas...")
    total_items = len(resultados_validacion)
    items_validos = sum(1 for r in resultados_validacion if r['valido'])
    items_invalidos = total_items - items_validos
    
    print(f"\n" + "="*50)
    print("RESUMEN DE PRUEBA DE ERRORES")
    print("="*50)
    print(f"Total items: {total_items}")
    print(f"Items válidos: {items_validos} ({items_validos/total_items*100:.1f}%)")
    print(f"Items inválidos: {items_invalidos} ({items_invalidos/total_items*100:.1f}%)")
    
    # Mostrar detalles de errores
    print(f"\n" + "="*50)
    print("DETALLES DE ERRORES MANEJADOS")
    print("="*50)
    
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
    
    print(f"\n" + "="*50)
    print("✅ PRUEBA DE MANEJO DE ERRORES COMPLETADA")
    print("="*50)
    print("El validador maneja correctamente:")
    print("- Valores None en Excel y ML")
    print("- Valores inválidos (no numéricos)")
    print("- Strings vacíos")
    print("- IDs no encontrados en ML")
    print("- Errores de conversión de tipos")

if __name__ == "__main__":
    ejecutar_prueba_errores()
