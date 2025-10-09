#!/usr/bin/env python3
"""
Script para probar los logs de progreso del validador
Crea un archivo Excel de prueba y ejecuta la validación mostrando todos los logs
"""

import pandas as pd
import os
from datetime import datetime

def crear_archivo_prueba():
    """Crea un archivo Excel de prueba con más datos para mostrar logs de progreso"""
    
    # Crear datos de prueba con más filas para mostrar progreso
    datos_prueba = []
    
    # IDs reales de ejemplo (que probablemente existan en ML)
    ids_reales = [
        'MLM3614653022', 'MLM3827210040', 'MLM1234567890', 'MLM9876543210',
        'MLM1111111111', 'MLM2222222222', 'MLM3333333333', 'MLM4444444444',
        'MLM5555555555', 'MLM6666666666', 'MLM7777777777', 'MLM8888888888',
        'MLM9999999999', 'MLM0000000000', 'MLM1111111112', 'MLM2222222223',
        'MLM3333333334', 'MLM4444444445', 'MLM5555555556', 'MLM6666666667',
        'MLM7777777778', 'MLM8888888889', 'MLM9999999990', 'MLM0000000001',
        'MLM1111111113', 'MLM2222222224', 'MLM3333333335', 'MLM4444444446',
        'MLM5555555557', 'MLM6666666668', 'MLM7777777779', 'MLM8888888890',
        'MLM9999999991', 'MLM0000000002', 'MLM1111111114', 'MLM2222222225',
        'MLM3333333336', 'MLM4444444447', 'MLM5555555558', 'MLM6666666669',
        'MLM7777777780', 'MLM8888888891', 'MLM9999999992', 'MLM0000000003',
        'MLM1111111115', 'MLM2222222226', 'MLM3333333337', 'MLM4444444448',
        'MLM5555555559', 'MLM6666666670', 'MLM7777777781', 'MLM8888888892'
    ]
    
    for i, id_item in enumerate(ids_reales):
        datos_prueba.append({
            'ID': id_item,
            'Precio': 299 + (i % 10) * 50,  # Precios variados
            'Cantidad disponible': 200 - (i % 5) * 20,  # Cantidades variadas
            'SellerCustomSku': f'TEST-SKU-{i+1:03d}',
            'Status': 'active' if i % 3 != 0 else 'paused'  # Status variado
        })
    
    df = pd.DataFrame(datos_prueba)
    archivo_prueba = 'prueba_logs_progreso.xlsx'
    df.to_excel(archivo_prueba, index=False)
    
    print(f"📁 Archivo de prueba creado: {archivo_prueba}")
    print(f"📊 Total de filas: {len(df)}")
    print(f"🔢 IDs únicos: {len(df['ID'].unique())}")
    
    return archivo_prueba

def ejecutar_prueba_logs():
    """Ejecuta la prueba de logs de progreso"""
    
    print("🧪 PRUEBA DE LOGS DE PROGRESO")
    print("=" * 50)
    
    # Crear archivo de prueba
    archivo_prueba = crear_archivo_prueba()
    
    # Importar y ejecutar el validador
    from validar_datos_ml import procesar_validacion, generar_reporte
    
    print(f"\n🚀 Ejecutando validación con logs detallados...")
    print("=" * 50)
    
    # Procesar validación para tienda CO (usando datos simulados)
    resultados = procesar_validacion(archivo_prueba, 'CO')
    
    if resultados:
        # Generar reporte
        archivo_reporte = f"reporte_prueba_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        print(f"\n📋 Generando reporte: {archivo_reporte}")
        reporte = generar_reporte(resultados, archivo_reporte)
        
        print("\n" + "=" * 50)
        print("✅ PRUEBA DE LOGS COMPLETADA")
        print("=" * 50)
        print("Los logs de progreso se mostraron durante la ejecución.")
        print("Revisa la salida anterior para ver todos los mensajes de progreso.")
    else:
        print("❌ Error en la validación")

if __name__ == "__main__":
    ejecutar_prueba_logs()
