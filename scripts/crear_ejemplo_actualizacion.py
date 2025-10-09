#!/usr/bin/env python3
"""
Script para crear un archivo Excel de ejemplo para actualizaciones
Genera datos de prueba con diferentes escenarios
"""

import pandas as pd
import random
from datetime import datetime

def crear_archivo_ejemplo():
    """Crea un archivo Excel de ejemplo con datos de actualización"""
    
    # IDs de ejemplo (algunos reales, algunos simulados)
    ids_ejemplo = [
        'MLM3614653022', 'MLM3827210040', 'MLM1234567890', 'MLM9876543210',
        'MLM1111111111', 'MLM2222222222', 'MLM3333333333', 'MLM4444444444',
        'MLM5555555555', 'MLM6666666666', 'MLM7777777777', 'MLM8888888888',
        'MLM9999999999', 'MLM0000000000', 'MLM1111111112', 'MLM2222222223',
        'MLM3333333334', 'MLM4444444445', 'MLM5555555556', 'MLM6666666667'
    ]
    
    # Generar datos de ejemplo
    datos_ejemplo = []
    
    for i, id_item in enumerate(ids_ejemplo):
        # Generar precios variados
        precio_base = random.randint(100, 1000)
        precio_variacion = random.randint(-50, 100)
        precio_final = max(10, precio_base + precio_variacion)
        
        # Generar cantidades variadas
        cantidad_base = random.randint(10, 200)
        cantidad_variacion = random.randint(-20, 50)
        cantidad_final = max(1, cantidad_base + cantidad_variacion)
        
        # Generar SKUs variados
        sku_base = f"SKU-{i+1:03d}"
        sku_sufijo = random.choice(['-UPDATED', '-NEW', '-V2', '-REV'])
        sku_final = sku_base + sku_sufijo
        
        # Generar status variado
        status_opciones = ['active', 'paused', 'active', 'active', 'paused']  # Más active que paused
        status_final = random.choice(status_opciones)
        
        # Crear algunos casos especiales
        if i % 5 == 0:  # Cada 5to item
            # Item con solo precio
            datos_ejemplo.append({
                'ID': id_item,
                'Precio': precio_final,
                'Cantidad disponible': None,  # No actualizar cantidad
                'SellerCustomSku': None,  # No actualizar SKU
                'Status': None  # No actualizar status
            })
        elif i % 5 == 1:  # Cada 5to item + 1
            # Item con solo cantidad
            datos_ejemplo.append({
                'ID': id_item,
                'Precio': None,  # No actualizar precio
                'Cantidad disponible': cantidad_final,
                'SellerCustomSku': None,  # No actualizar SKU
                'Status': None  # No actualizar status
            })
        elif i % 5 == 2:  # Cada 5to item + 2
            # Item con solo SKU
            datos_ejemplo.append({
                'ID': id_item,
                'Precio': None,  # No actualizar precio
                'Cantidad disponible': None,  # No actualizar cantidad
                'SellerCustomSku': sku_final,
                'Status': None  # No actualizar status
            })
        elif i % 5 == 3:  # Cada 5to item + 3
            # Item con solo status
            datos_ejemplo.append({
                'ID': id_item,
                'Precio': None,  # No actualizar precio
                'Cantidad disponible': None,  # No actualizar cantidad
                'SellerCustomSku': None,  # No actualizar SKU
                'Status': status_final
            })
        else:  # Resto de items
            # Item con todos los campos
            datos_ejemplo.append({
                'ID': id_item,
                'Precio': precio_final,
                'Cantidad disponible': cantidad_final,
                'SellerCustomSku': sku_final,
                'Status': status_final
            })
    
    # Crear DataFrame
    df = pd.DataFrame(datos_ejemplo)
    
    # Guardar archivo Excel
    archivo_ejemplo = f'ejemplo_actualizacion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    df.to_excel(archivo_ejemplo, index=False)
    
    print(f"📁 Archivo de ejemplo creado: {archivo_ejemplo}")
    print(f"📊 Total de filas: {len(df)}")
    print(f"🔢 IDs únicos: {len(df['ID'].unique())}")
    
    # Mostrar estadísticas
    print(f"\n📈 Estadísticas del archivo:")
    print(f"   - Items con precio: {df['Precio'].notna().sum()}")
    print(f"   - Items con cantidad: {df['Cantidad disponible'].notna().sum()}")
    print(f"   - Items con SKU: {df['SellerCustomSku'].notna().sum()}")
    print(f"   - Items con status: {df['Status'].notna().sum()}")
    
    # Mostrar algunos ejemplos
    print(f"\n📋 Primeros 5 items del archivo:")
    print(df.head().to_string(index=False))
    
    return archivo_ejemplo

def crear_archivo_con_errores():
    """Crea un archivo Excel con casos edge para probar manejo de errores"""
    
    datos_con_errores = [
        {
            'ID': 'MLM3614653022',
            'Precio': 350,
            'Cantidad disponible': 150,
            'SellerCustomSku': 'SKU-VALIDO-001',
            'Status': 'active'
        },
        {
            'ID': 'MLM3827210040',
            'Precio': 'invalid_price',  # Precio inválido
            'Cantidad disponible': 180,
            'SellerCustomSku': 'SKU-VALIDO-002',
            'Status': 'active'
        },
        {
            'ID': 'MLM1234567890',
            'Precio': 200,
            'Cantidad disponible': 'invalid_qty',  # Cantidad inválida
            'SellerCustomSku': 'SKU-VALIDO-003',
            'Status': 'active'
        },
        {
            'ID': 'MLM9876543210',
            'Precio': 250,
            'Cantidad disponible': 100,
            'SellerCustomSku': 'SKU-VALIDO-004',
            'Status': 'invalid_status'  # Status inválido
        },
        {
            'ID': 'MLM9999999999',  # ID que probablemente no existe
            'Precio': 150,
            'Cantidad disponible': 50,
            'SellerCustomSku': 'SKU-VALIDO-005',
            'Status': 'active'
        },
        {
            'ID': 'MLM8888888888',
            'Precio': -10,  # Precio negativo (inválido)
            'Cantidad disponible': 25,
            'SellerCustomSku': 'SKU-VALIDO-006',
            'Status': 'active'
        },
        {
            'ID': 'MLM7777777777',
            'Precio': 280,
            'Cantidad disponible': 100,
            'SellerCustomSku': '',  # SKU vacío
            'Status': 'active'
        },
        {
            'ID': 'MLM6666666666',
            'Precio': None,  # Todos los campos None
            'Cantidad disponible': None,
            'SellerCustomSku': None,
            'Status': None
        }
    ]
    
    df = pd.DataFrame(datos_con_errores)
    archivo_errores = f'ejemplo_errores_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    df.to_excel(archivo_errores, index=False)
    
    print(f"📁 Archivo con errores creado: {archivo_errores}")
    print(f"📊 Total de filas: {len(df)}")
    
    return archivo_errores

def main():
    """Función principal"""
    print("🎯 GENERADOR DE ARCHIVOS DE EJEMPLO PARA ACTUALIZACIONES")
    print("=" * 60)
    
    print("\n1. Creando archivo de ejemplo normal...")
    archivo_normal = crear_archivo_ejemplo()
    
    print("\n2. Creando archivo con casos edge...")
    archivo_errores = crear_archivo_con_errores()
    
    print(f"\n" + "="*60)
    print("✅ ARCHIVOS CREADOS EXITOSAMENTE")
    print("="*60)
    print(f"📁 Archivo normal: {archivo_normal}")
    print(f"📁 Archivo con errores: {archivo_errores}")
    print(f"\n🚀 Para probar el actualizador:")
    print(f"   python actualizar_datos_ml.py {archivo_normal} --tienda CO")
    print(f"   python actualizar_datos_ml.py {archivo_errores} --tienda CO")
    print(f"\n🧪 Para ver la demostración:")
    print(f"   python test_actualizador_demo.py")

if __name__ == "__main__":
    main()
