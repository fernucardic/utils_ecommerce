# 🚀 Actualizador de Datos MercadoLibre

Script para actualizar publicaciones en MercadoLibre mediante la API PUT. Lee un archivo Excel y actualiza precios, cantidades, SKUs y status de las publicaciones.

## 🎯 Características

- ✅ Lee archivos Excel con columnas: ID, Precio, Cantidad disponible, SellerCustomSku, Status
- ✅ Construye payloads JSON válidos para la API de ML
- ✅ Hace requests PUT en lotes para optimizar el rendimiento
- ✅ Renovación automática de tokens de acceso
- ✅ Logs detallados de progreso con emojis
- ✅ Manejo robusto de errores y validaciones
- ✅ Reportes detallados con estadísticas

## 📋 Requisitos

- Python 3.7+
- Dependencias instaladas: `pip install -r requirements.txt`
- Variables de entorno configuradas para las tiendas de ML

## 🔧 Configuración

### Variables de Entorno

Crear archivo `.env` en `/Users/fernudev/Documents/Cardic/utils_ecommerce/`:

```env
# Tienda CO
CO_ACCESS_TOKEN=tu_token_aqui
CO_REFRESH_TOKEN=tu_refresh_token_aqui
CO_CLIENT_ID=tu_client_id_aqui
CO_CLIENT_SECRET=tu_client_secret_aqui
CO_SELLER_ID=tu_seller_id_aqui

# Repetir para DS, TE, TS, CA
DS_ACCESS_TOKEN=...
DS_REFRESH_TOKEN=...
# etc.
```

## 📊 Formato del Archivo Excel

El archivo Excel debe tener exactamente estas columnas:

| Columna | Tipo | Descripción | Requerido |
|---------|------|-------------|-----------|
| ID | Texto | ID del item en MercadoLibre | ✅ Sí |
| Precio | Número | Nuevo precio del item | ❌ No |
| Cantidad disponible | Número | Nueva cantidad en stock | ❌ No |
| SellerCustomSku | Texto | Nuevo SKU personalizado | ❌ No |
| Status | Texto | Nuevo estado (active/paused/closed) | ❌ No |

**Nota**: Al menos uno de los campos (Precio, Cantidad disponible, SellerCustomSku, Status) debe tener un valor válido.

## 🚀 Uso

### Uso Básico

```bash
# Activar entorno virtual
source venv/bin/activate

# Actualizar datos de la tienda CO
python scripts/actualizar_datos_ml.py mi_archivo.xlsx --tienda CO
```

### Parámetros Avanzados

```bash
# Actualizar con archivo de salida personalizado
python scripts/actualizar_datos_ml.py datos.xlsx --tienda DS --salida reporte_ds.txt

# Cambiar tamaño de lote (default: 10)
python scripts/actualizar_datos_ml.py datos.xlsx --tienda CO --batch-size 5

# Ver todas las opciones
python scripts/actualizar_datos_ml.py --help
```

### Demostración (Sin tokens reales)

```bash
# Ejecutar demostración
python scripts/test_actualizador_demo.py
```

## 📈 Logs de Progreso

El script proporciona logs detallados en tiempo real:

```
🎯 ACTUALIZADOR DE DATOS MERCADOLIBRE
==================================================
📁 Archivo: mi_archivo.xlsx
🏪 Tienda: CO
📦 Tamaño de lote: 10
⏰ Inicio: 2025-01-27 15:30:45
==================================================

🚀 Iniciando actualización para tienda: CO
============================================================
📁 Paso 1/4: Leyendo archivo Excel...
   📖 Leyendo archivo: mi_archivo.xlsx
   ✅ Archivo leído exitosamente: 100 filas encontradas
   🔍 Validando estructura del archivo...
   ✅ Estructura del archivo válida: todas las columnas requeridas presentes

🔧 Paso 2/4: Configurando actualizador...
✅ Actualizador configurado para tienda: CO

📊 Paso 3/4: Preparando datos para actualización...
✅ Preparados 95 items para actualización
⚠️  5 items ignorados (sin datos válidos)

🌐 Paso 4/4: Actualizando items en MercadoLibre...
📡 Iniciando actualizaciones: 95 items en 10 lotes de 10
🔄 Procesando lote 1/10 (10 items)
   🔄 Actualizando MLM3614653022...
   ✅ MLM3614653022 actualizado exitosamente
   ...
✅ Lote 1 completado: 9 exitosos, 1 fallidos
```

## 🔍 Validaciones Implementadas

### **Validación de Precios**
- Debe ser un número válido
- Se ignora si es `None` o vacío
- Se convierte a `float` automáticamente

### **Validación de Cantidades**
- Debe ser un número entero válido
- Se ignora si es `None` o vacío
- Se convierte a `int` automáticamente

### **Validación de SKUs**
- Se convierte a string y se eliminan espacios
- Se ignora si es `None` o vacío

### **Validación de Status**
- Debe ser uno de: `active`, `paused`, `closed`
- Se convierte a minúsculas automáticamente
- Se ignora si es inválido

## 📊 Reportes Generados

### **Estadísticas Generales**
- Total de items procesados
- Items actualizados exitosamente
- Items fallidos
- Items ignorados (sin datos válidos)

### **Análisis de Errores**
- Lista de errores más comunes
- Detalle de cada item fallido
- Códigos de respuesta HTTP
- Datos enviados en requests fallidos

### **Ejemplo de Reporte**

```
REPORTE DE ACTUALIZACIÓN MERCADOLIBRE
=====================================
Tienda: CO
Fecha: 2025-01-27T15:32:15
Total de items procesados: 100

ESTADÍSTICAS GENERALES
=====================
Items actualizados exitosamente: 85 (85.0%)
Items fallidos: 10 (10.0%)
Items ignorados: 5

ERRORES MÁS COMUNES
==================
Item not found: 5 ocurrencias
Invalid price: 3 ocurrencias
Invalid status: 2 ocurrencias
```

## 🛡️ Manejo de Errores

### **Errores de Token**
- Renovación automática cuando expira
- Reintento de requests fallidos
- Logs detallados del proceso

### **Errores de Validación**
- Items con datos inválidos se ignoran
- Logs de advertencia para cada caso
- Continuación del proceso sin interrupciones

### **Errores de Red**
- Manejo de timeouts y conexiones
- Logs de errores específicos
- Continuación con el siguiente item

## ⚡ Optimizaciones

### **Procesamiento en Lotes**
- Procesa items en lotes configurables (default: 10)
- Pausas entre lotes para no sobrecargar la API
- Pausas entre requests individuales

### **Rate Limiting**
- Pausa de 0.5 segundos entre requests
- Pausa de 2 segundos entre lotes
- Configurable según necesidades

## 🧪 Scripts de Prueba

### **test_actualizador_demo.py**
Script de demostración que simula actualizaciones sin tokens reales.

```bash
python test_actualizador_demo.py
```

### **Casos de Prueba Incluidos**
- ✅ Actualizaciones exitosas
- ❌ Items no encontrados (404)
- ❌ Errores de validación (400)
- ⚠️ Items con datos inválidos
- 📊 Estadísticas detalladas

## 🚨 Solución de Problemas

### **Error: "Token expirado"**
- El script intentará renovar automáticamente
- Si falla, verifica las credenciales en `.env`

### **Error: "Columnas faltantes"**
- Verifica que tu archivo Excel tenga las columnas exactas requeridas

### **Error: "No hay datos válidos"**
- Asegúrate de que al menos un campo tenga un valor válido
- Revisa que los datos no sean todos `None` o vacíos

### **Error: "Tienda no encontrada"**
- Usa una de las tiendas disponibles: CO, DS, TE, TS, CA

## 📁 Archivos Generados

- `reporte_actualizacion_[tienda]_[timestamp].txt`: Reporte detallado
- `demo_actualizacion.xlsx`: Archivo de ejemplo (generado por demo)

## 🔄 Flujo de Trabajo Recomendado

1. **Preparar datos**: Crear archivo Excel con las actualizaciones
2. **Validar estructura**: Verificar que tenga las columnas correctas
3. **Probar con demo**: Ejecutar `test_actualizador_demo.py`
4. **Configurar tokens**: Asegurar que las variables de entorno estén configuradas
5. **Ejecutar actualización**: `python actualizar_datos_ml.py datos.xlsx --tienda CO`
6. **Revisar reporte**: Analizar el reporte generado
7. **Corregir errores**: Revisar items fallidos y corregir datos

## 🎉 Resultado de la Demostración

La demostración mostró:
- ✅ Construcción correcta de payloads JSON
- ✅ Procesamiento en lotes
- ✅ Manejo de errores (404, 400)
- ✅ Logs detallados de progreso
- ✅ Estadísticas precisas
- ✅ Reportes comprensibles

El actualizador está listo para usar con datos reales una vez que configures las variables de entorno con los tokens de MercadoLibre.
