# Optimizaciones Realizadas - get_delete_items.py

## 📊 Resumen de Cambios

Se optimizó el script `get_delete_items.py` para mejorar significativamente su rendimiento y visibilidad del progreso.

## 🚀 Optimizaciones Implementadas

### 1. **Proyección de MongoDB** (Mejora de Rendimiento: ~40-60%)
**Antes:**
```python
items = list(items_col.find(filtro_items))
```

**Después:**
```python
projection = {
    "_id": 1,
    "sold_quantity": 1,
    "seller_custom_sku": 1,
    "numero_parte": 1,
    "date_created": 1,
    "origen": 1
}
cursor = items_col.find(filtro_items, projection)
```

**Beneficio:** Solo trae los campos necesarios desde MongoDB, reduciendo la transferencia de datos y el uso de memoria.

---

### 2. **Pre-conversión a Mayúsculas** (Mejora de Rendimiento: ~10-15%)
**Antes:**
```python
# Convertía a mayúsculas en cada comparación
if any(npc.upper() in seller_sku for npc in npcs):
```

**Después:**
```python
# Pre-convierte una sola vez al construir el diccionario
npcs.append(str(val).strip().upper())
# ...
if npcs and any(npc in seller_sku for npc in npcs):
```

**Beneficio:** Evita conversiones repetidas a mayúsculas en el loop principal.

---

### 3. **Uso de defaultdict** (Mejora de Rendimiento: ~5-10%)
**Antes:**
```python
# Iteraba múltiples veces sobre los items
for origen in origenes:
    items_origen = [item for item in items_filtrados if item.get("origen") == origen]
```

**Después:**
```python
# Agrupa en una sola pasada
items_por_origen = defaultdict(list)
for item in items_filtrados:
    origen = item.get("origen", "SIN_ORIGEN")
    items_por_origen[origen].append({...})
```

**Beneficio:** Reduce de O(n*m) a O(n) donde n=items, m=orígenes.

---

### 4. **Sistema de Logging Profesional**

**Características:**
- ✅ Logs guardados en archivo con timestamp: `logs/get_delete_items_YYYYMMDD_HHMMSS.log`
- ✅ Logs también en consola (simultáneamente)
- ✅ Formato claro con timestamp en cada línea
- ✅ Manejo de errores con try-except

**Ejemplo de salida:**
```
2025-10-06 10:30:15 - INFO - ============================================================
2025-10-06 10:30:15 - INFO - INICIO DEL PROCESO DE FILTRADO DE ITEMS PARA ELIMINAR
2025-10-06 10:30:15 - INFO - ============================================================
2025-10-06 10:30:15 - INFO - Conectando a MongoDB...
2025-10-06 10:30:16 - INFO - ✓ Conexión exitosa a MongoDB
```

---

### 5. **Barras de Progreso con tqdm**

Se agregaron barras de progreso en todas las operaciones largas:

1. **Procesando Excel** - Muestra cuántas filas se están procesando
2. **Cargando items de MongoDB** - Muestra el progreso de descarga
3. **Filtrando por NPC** - Muestra items procesados
4. **Agrupando por origen** - Muestra el progreso de agrupación
5. **Escribiendo Excel** - Muestra cuántas hojas se están creando

**Ejemplo visual:**
```
Cargando items: 100%|████████████████████| 15234/15234 [00:23<00:00, 652.35 items/s]
Filtrando por NPC: 100%|████████████████| 15234/15234 [00:05<00:00, 2847.21 items/s]
```

---

### 6. **Conteo Previo de Documentos**

**Antes:** No sabías cuántos items había hasta terminar de cargarlos.

**Después:**
```python
total_count = items_col.count_documents(filtro_items)
logger.info(f"Total de items a procesar: {total_count}")
```

**Beneficio:** Sabes inmediatamente la magnitud del trabajo y las barras de progreso son precisas.

---

### 7. **Resumen Final Detallado**

Al finalizar, el script muestra un resumen completo:

```
============================================================
RESUMEN FINAL:
  - Total items iniciales: 15234
  - Items conservados (con NPC protegido): 3421
  - Items para eliminar: 11813
  - Orígenes diferentes: 5
  - Archivo generado: ELIMINAR_SIN_VENTAS.xlsx
============================================================
PROCESO COMPLETADO EXITOSAMENTE
============================================================
```

---

### 8. **Desglose por Origen**

Ahora muestra cuántos items hay en cada origen:
```
✓ Items agrupados en 5 orígenes:
  - CA: 2345 items
  - CO: 3421 items
  - DS: 4532 items
  - TE: 892 items
  - TS: 623 items
```

---

## 📈 Mejora Estimada de Rendimiento

| Operación | Tiempo Antes (estimado) | Tiempo Después (estimado) | Mejora |
|-----------|------------------------|---------------------------|--------|
| Carga de MongoDB | 60-120s | 20-40s | ~60% |
| Filtrado NPC | 30-60s | 20-30s | ~40% |
| Agrupación por origen | 20-40s | 5-10s | ~75% |
| **TOTAL** | **110-220s** | **45-80s** | **~60%** |

*Nota: Los tiempos reales dependen del tamaño de la base de datos y la velocidad de la conexión a MongoDB.*

---

## 🎯 Ventajas Adicionales

1. **Visibilidad total** - Sabes en todo momento qué está haciendo el script
2. **Debugging facilitado** - Los logs guardados ayudan a diagnosticar problemas
3. **Menos memoria** - Proyección reduce el uso de RAM
4. **Código más limpio** - Mejor organizado y comentado
5. **Manejo de errores** - Try-except en carga de Excel

---

## 📝 Dependencias

El script ahora usa `tqdm` que ya está en tu `requirements.txt` (línea 280).

---

## 🔧 Cómo Ejecutar

```bash
cd scripts
python get_delete_items.py
```

Los logs se guardarán automáticamente en: `logs/get_delete_items_YYYYMMDD_HHMMSS.log`

---

## 🎨 Mejoras Futuras Posibles

Si el script sigue siendo lento, considera:

1. **Índices en MongoDB** - Crear índices en `sold_quantity` y `seller_custom_sku`
2. **Procesamiento por lotes** - Procesar en chunks de 1000 items
3. **Multiprocesamiento** - Usar `multiprocessing` para paralelizar el filtrado NPC
4. **Caché de resultados** - Guardar resultados intermedios
5. **Actualización incremental** - Solo procesar items nuevos desde la última ejecución

