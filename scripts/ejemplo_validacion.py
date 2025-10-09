#!/usr/bin/env python3
"""
Script de ejemplo para demostrar el uso del validador de datos ML
Crea un archivo Excel de ejemplo y ejecuta la validación
"""

import pandas as pd
import os
from datetime import datetime

def crear_archivo_ejemplo():
    """Crea un archivo Excel de ejemplo con datos de prueba"""
    
    # Datos de ejemplo basados en los IDs proporcionados
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
            'Precio': 299,
            'Cantidad disponible': 200,
            'SellerCustomSku': 'REAL0011-R20116-B0001',
            'Status': 'active'
        },
        # Agregar algunos datos con errores intencionales para probar la validación
        {
            'ID': 'MLM1234567890',  # ID que probablemente no existe
            'Precio': 150,
            'Cantidad disponible': 50,
            'SellerCustomSku': 'TEST-SKU-001',
            'Status': 'active'
        },
        {
            'ID': 'MLM9876543210',  # ID que probablemente no existe
            'Precio': 250,
            'Cantidad disponible': 100,
            'SellerCustomSku': 'TEST-SKU-002',
            'Status': 'paused'
        }
    ]
    
    df = pd.DataFrame(datos_ejemplo)
    archivo_ejemplo = 'ejemplo_datos_validacion.xlsx'
    df.to_excel(archivo_ejemplo, index=False)
    
    print(f"Archivo de ejemplo creado: {archivo_ejemplo}")
    print("Datos del archivo:")
    print(df.to_string(index=False))
    
    return archivo_ejemplo

def ejecutar_validacion_ejemplo():
    """Ejecuta la validación con el archivo de ejemplo"""
    
    # Crear archivo de ejemplo
    archivo_ejemplo = crear_archivo_ejemplo()
    
    # Importar y ejecutar el validador
    from validar_datos_ml import procesar_validacion, generar_reporte
    
    print("\n" + "="*60)
    print("EJECUTANDO VALIDACIÓN DE EJEMPLO")
    print("="*60)
    
    # Procesar validación para tienda CO
    resultados = procesar_validacion(archivo_ejemplo, 'CO')
    
    if resultados:
        # Generar reporte
        archivo_reporte = f"reporte_ejemplo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        reporte = generar_reporte(resultados, archivo_reporte)
        
        print("\n" + "="*60)
        print("RESUMEN DE VALIDACIÓN")
        print("="*60)
        print(reporte)
    else:
        print("Error en la validación")

if __name__ == "__main__":
    ejecutar_validacion_ejemplo()
