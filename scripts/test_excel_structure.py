#!/usr/bin/env python3
"""
Script de prueba para verificar la estructura del Excel de marcas
"""
import pandas as pd
import os

def test_excel_structure():
    excel_path = "../Data/Cambio_Marca/TS.xlsx"
    
    if not os.path.exists(excel_path):
        print(f"❌ Archivo no encontrado: {excel_path}")
        return False
    
    try:
        df = pd.read_excel(excel_path)
        print(f"✅ Archivo cargado exitosamente: {excel_path}")
        print(f"📊 Total de filas: {len(df)}")
        print(f"📋 Columnas disponibles: {list(df.columns)}")
        
        # Verificar columnas requeridas
        required_columns = ["ID", "Marca"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ Columnas faltantes: {missing_columns}")
            return False
        
        print(f"✅ Columnas requeridas presentes: {required_columns}")
        
        # Mostrar algunas filas de ejemplo
        print("\n📝 Primeras 5 filas:")
        print(df[["ID", "Marca"]].head())
        
        # Verificar valores nulos
        null_ids = df["ID"].isnull().sum()
        null_marcas = df["Marca"].isnull().sum()
        
        print(f"\n📊 Valores nulos:")
        print(f"   ID: {null_ids}")
        print(f"   Marca: {null_marcas}")
        
        # Mostrar marcas únicas
        marcas_unicas = df["Marca"].dropna().unique()
        print(f"\n🏷️ Marcas únicas encontradas ({len(marcas_unicas)}):")
        for marca in sorted(marcas_unicas)[:10]:  # Mostrar solo las primeras 10
            print(f"   - {marca}")
        
        if len(marcas_unicas) > 10:
            print(f"   ... y {len(marcas_unicas) - 10} más")
        
        return True
        
    except Exception as e:
        print(f"❌ Error leyendo Excel: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Verificando estructura del Excel de marcas...")
    test_excel_structure()

