import pandas as pd
import re

# Rutas de archivo
EXCEL_PATH = "../Data/Eliminar/Eliminar_CO.xlsx"
LOG_PATH = "../logs/CO_eliminados.log"

# 1. Leer archivo Excel
df = pd.read_excel(EXCEL_PATH)

# 2. Leer el log y extraer los IDs eliminados
with open(LOG_PATH, "r") as f:
    lines = f.readlines()

# Extraer solo el número del ID (sin "MLM")
eliminados = set()
for line in lines:
    match = re.search(r"MLM(\d+)", line)
    if match:
        eliminados.add(match.group(1))  # solo el número

# 3. Filtrar el DataFrame eliminando los IDs encontrados
def id_sin_mlm(valor):
    try:
        return str(valor).replace("MLM", "").strip()
    except:
        return ""

df["ID_sin_MLM"] = df["ID"].apply(id_sin_mlm)
df_filtrado = df[~df["ID_sin_MLM"].isin(eliminados)]

# 4. Eliminar columna auxiliar y sobrescribir el Excel
df_filtrado.drop(columns=["ID_sin_MLM"], inplace=True)
df_filtrado.to_excel(EXCEL_PATH, index=False)

print(f"✅ Se eliminaron {len(df) - len(df_filtrado)} filas del archivo.")
