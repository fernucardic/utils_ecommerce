#!/usr/bin/env python3
"""
Script de demostración del actualizador de datos ML
Simula actualizaciones sin necesidad de tokens reales
"""

import pandas as pd
import json
from datetime import datetime
from typing import Dict, Any
from actualizar_datos_ml import ActualizadorML

class ActualizadorDemo(ActualizadorML):
    """Actualizador de demostración que simula respuestas de ML"""
    
    def __init__(self, tienda_config):
        super().__init__(tienda_config)
        self.actualizaciones_realizadas = []
    
    def actualizar_item(self, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simula la actualización de un item en ML"""
        print(f"   🔄 Simulando actualización de {item_id}...")
        
        # Simular delay de red
        import time
        time.sleep(0.2)
        
        # Simular diferentes tipos de respuesta
        if item_id.startswith('MLM999'):
            # Simular error para IDs que empiecen con 999
            return {
                'id': item_id,
                'exitoso': False,
                'error': 'Item not found',
                'codigo_respuesta': 404,
                'datos_enviados': payload
            }
        elif item_id.startswith('MLM888'):
            # Simular error de validación
            return {
                'id': item_id,
                'exitoso': False,
                'error': 'Invalid price: Price must be greater than 0',
                'codigo_respuesta': 400,
                'datos_enviados': payload
            }
        else:
            # Simular éxito
            self.actualizaciones_realizadas.append({
                'id': item_id,
                'payload': payload,
                'timestamp': datetime.now().isoformat()
            })
            
            return {
                'id': item_id,
                'exitoso': True,
                'datos_actualizados': payload,
                'respuesta_ml': {
                    'id': item_id,
                    'price': payload.get('price'),
                    'available_quantity': payload.get('available_quantity'),
                    'seller_custom_field': payload.get('seller_custom_field'),
                    'status': payload.get('status'),
                    'last_updated': datetime.now().isoformat()
                },
                'codigo_respuesta': 200
            }

def crear_datos_actualizacion():
    """Crea datos de ejemplo para la demostración de actualización"""
    
    datos_ejemplo = [
        {
            'ID': 'MLM3614653022',
            'Precio': 350,  # Precio actualizado
            'Cantidad disponible': 150,  # Cantidad actualizada
            'SellerCustomSku': 'SFRE0019-S10615-B0001-UPDATED',
            'Status': 'active'
        },
        {
            'ID': 'MLM3827210040',
            'Precio': 320,
            'Cantidad disponible': 180,
            'SellerCustomSku': 'REAL0011-R20116-B0001-UPDATED',
            'Status': 'active'
        },
        {
            'ID': 'MLM1234567890',
            'Precio': 200,
            'Cantidad disponible': 75,
            'SellerCustomSku': 'TEST-SKU-001-UPDATED',
            'Status': 'paused'
        },
        {
            'ID': 'MLM9999999999',  # ID que simulará error
            'Precio': 150,
            'Cantidad disponible': 50,
            'SellerCustomSku': 'TEST-SKU-999',
            'Status': 'active'
        },
        {
            'ID': 'MLM8888888888',  # ID que simulará error de validación
            'Precio': -10,  # Precio inválido
            'Cantidad disponible': 25,
            'SellerCustomSku': 'TEST-SKU-888',
            'Status': 'active'
        },
        {
            'ID': 'MLM7777777777',
            'Precio': 280,
            'Cantidad disponible': 100,
            'SellerCustomSku': 'TEST-SKU-777-UPDATED',
            'Status': 'active'
        }
    ]
    
    return pd.DataFrame(datos_ejemplo)

def ejecutar_demo_actualizacion():
    """Ejecuta la demostración completa de actualización"""
    
    print("🧪 DEMOSTRACIÓN DEL ACTUALIZADOR DE DATOS MERCADOLIBRE")
    print("=" * 60)
    
    # Crear datos de ejemplo
    print("\n1. Creando datos de actualización...")
    df = crear_datos_actualizacion()
    print("Datos de actualización:")
    print(df.to_string(index=False))
    
    # Crear archivo Excel
    archivo_ejemplo = 'demo_actualizacion.xlsx'
    df.to_excel(archivo_ejemplo, index=False)
    print(f"\nArchivo Excel creado: {archivo_ejemplo}")
    
    # Configurar actualizador demo
    print("\n2. Configurando actualizador de demostración...")
    tienda_demo = {
        'access_token': 'demo_token',
        'refresh_token': 'demo_refresh',
        'client_id': 'demo_client',
        'client_secret': 'demo_secret',
        'user_id': 'demo_user',
        'nombre_tienda': 'DEMO'
    }
    
    actualizador = ActualizadorDemo(tienda_demo)
    
    # Obtener IDs
    ids = df['ID'].dropna().unique().tolist()
    print(f"IDs a actualizar: {ids}")
    
    # Preparar datos para actualización
    print("\n3. Preparando datos para actualización...")
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
        print(f"   ✅ {item_id}: {json.dumps(payload, indent=2)}")
    
    print(f"\nPreparados {len(items_data)} items para actualización")
    if items_ignorados > 0:
        print(f"⚠️  {items_ignorados} items ignorados (sin datos válidos)")
    
    # Simular actualizaciones
    print("\n4. Simulando actualizaciones en MercadoLibre...")
    resultados = actualizador.actualizar_items_lote(items_data, batch_size=3)
    
    # Generar estadísticas
    print("\n5. Generando estadísticas...")
    total_items = len(resultados)
    items_exitosos = sum(1 for r in resultados if r['exitoso'])
    items_fallidos = total_items - items_exitosos
    
    print(f"\n" + "="*50)
    print("RESUMEN DE ACTUALIZACIÓN")
    print("="*50)
    print(f"Total items: {total_items}")
    print(f"Items actualizados: {items_exitosos} ({items_exitosos/total_items*100:.1f}%)")
    print(f"Items fallidos: {items_fallidos} ({items_fallidos/total_items*100:.1f}%)")
    print(f"Items ignorados: {items_ignorados}")
    
    # Mostrar detalles de errores
    print(f"\n" + "="*50)
    print("DETALLES DE RESULTADOS")
    print("="*50)
    
    for resultado in resultados:
        if resultado['exitoso']:
            print(f"\n✅ ID: {resultado['id']}")
            print(f"   Datos actualizados: {json.dumps(resultado['datos_actualizados'], indent=2)}")
        else:
            print(f"\n❌ ID: {resultado['id']}")
            print(f"   Error: {resultado.get('error', 'Error desconocido')}")
            print(f"   Código: {resultado.get('codigo_respuesta', 'N/A')}")
    
    # Mostrar actualizaciones realizadas
    print(f"\n" + "="*50)
    print("ACTUALIZACIONES REALIZADAS (SIMULADAS)")
    print("="*50)
    for actualizacion in actualizador.actualizaciones_realizadas:
        print(f"ID: {actualizacion['id']}")
        print(f"Payload: {json.dumps(actualizacion['payload'], indent=2)}")
        print(f"Timestamp: {actualizacion['timestamp']}")
        print("-" * 30)
    
    print(f"\n" + "="*60)
    print("DEMOSTRACIÓN COMPLETADA")
    print("="*60)
    print("Este script demuestra cómo funciona el actualizador sin necesidad")
    print("de tokens reales de MercadoLibre. Para usar con datos reales,")
    print("ejecuta: python actualizar_datos_ml.py tu_archivo.xlsx --tienda CO")

if __name__ == "__main__":
    ejecutar_demo_actualizacion()
