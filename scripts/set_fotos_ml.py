import os
import time
import logging
import threading
import tempfile
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# 🔽 IMPORTS PARA MANEJO DE URLs
from urllib.parse import urlparse, urljoin
import json

# ==================== CONFIGURACIÓN ====================

# Configurar tienda (cambiar según necesidad: CA, CO, DS, TE, TS)
TIENDA = "CA"  # CAMBIAR SEGÚN LA TIENDA QUE SE PROCESE

LOG_FILE = f"fotos_{TIENDA}.log"
PROCESSED_ITEMS_FILE = f"items_fotos_procesados_{TIENDA}.txt"
CSV_FOLDER = "../Data/Fotos/"

# 🔧 User-Agent para las peticiones HTTP
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0.0.0 Safari/537.36")

# Configurar logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler para archivo
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)

# Función para log solo en archivo
def log_file_only(level, message):
    """Log que solo va al archivo, no a la consola"""
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)

# Función para log en consola y archivo
def log_console_and_file(level, message):
    """Log que va tanto a consola como a archivo"""
    logger.addHandler(console_handler)
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    logger.removeHandler(console_handler)

load_dotenv()

# Credenciales de la tienda
ACCESS_TOKEN = os.getenv(f"{TIENDA}_ACCESS_TOKEN", "").strip()
REFRESH_TOKEN = os.getenv(f"{TIENDA}_REFRESH_TOKEN", "").strip()
CLIENT_ID = os.getenv(f"{TIENDA}_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv(f"{TIENDA}_CLIENT_SECRET", "").strip()

# Parámetros de procesamiento
MAX_WORKERS = 5  # Reducido porque subir imágenes es más pesado
TIMEOUT_DOWNLOAD = 30  # Timeout para descargar imágenes
TIMEOUT_UPLOAD = 60  # Timeout para subir imágenes
TIMEOUT_UPDATE = 30  # Timeout para actualizar item

OAUTH_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
UPLOAD_PICTURE_URL = "https://api.mercadolibre.com/pictures"

# ==================== TOKEN MANAGER ====================

class TokenManager:
    def __init__(self, access_token: str, refresh_token: str, client_id: str, client_secret: str):
        self._access_token = access_token or ""
        self._refresh_token = refresh_token or ""
        self._client_id = client_id or ""
        self._client_secret = client_secret or ""
        self._lock = threading.Lock()

    def _validate_credentials(self) -> bool:
        """Valida que las credenciales estén presentes"""
        return bool(
            self._access_token and 
            self._refresh_token and 
            self._client_id and 
            self._client_secret and
            len(self._access_token.strip()) > 0 and
            len(self._refresh_token.strip()) > 0 and
            len(self._client_id.strip()) > 0 and
            len(self._client_secret.strip()) > 0
        )

    def validate_token(self) -> bool:
        """Valida el token actual haciendo una petición de prueba"""
        if not self._access_token:
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            resp = requests.get(
                "https://api.mercadolibre.com/users/me", 
                headers=headers, 
                timeout=10
            )
            
            if resp.status_code == 200:
                user_data = resp.json()
                log_file_only("INFO", f"✅ Token validado correctamente para usuario: {user_data.get('nickname', 'N/A')}")
                return True
            elif resp.status_code == 401:
                log_file_only("WARNING", "⚠️ Token inválido (401) - necesita refresh")
                return False
            else:
                log_file_only("WARNING", f"⚠️ Error validando token: {resp.status_code}")
                return False
                
        except Exception as e:
            log_file_only("WARNING", f"⚠️ Error validando token: {e}")
            return False

    def get_token(self) -> str:
        """Obtiene el token actual"""
        with self._lock:
            if not self._validate_credentials():
                log_file_only("ERROR", "❌ Credenciales incompletas o inválidas")
                return ""
            return self._access_token

    def set_token_from_response(self, data: dict):
        """Actualiza tokens desde respuesta OAuth"""
        at = data.get("access_token")
        if at:
            self._access_token = at
        rt = data.get("refresh_token")
        if rt:
            self._refresh_token = rt

    def refresh_blocking(self) -> bool:
        """Refresca el token de forma bloqueante"""
        if not self._validate_credentials():
            log_file_only("ERROR", "❌ No hay credenciales para refrescar token")
            return False
        
        with self._lock:
            try:
                return self._refresh_locked()
            except Exception as e:
                log_file_only("ERROR", f"❌ Refresh token falló: {e}")
                return False

    def _refresh_locked(self) -> bool:
        """Lógica interna de refresh (asume lock tomado)"""
        payload = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        }
        
        try:
            r = requests.post(OAUTH_TOKEN_URL, data=payload, timeout=15)
            if r.status_code != 200:
                error_msg = f"OAuth {r.status_code}: {r.text[:300]}"
                log_file_only("ERROR", f"❌ Error en refresh: {error_msg}")
                raise RuntimeError(error_msg)
            
            data = r.json()
            self.set_token_from_response(data)
            log_file_only("INFO", "🔄 Access token refrescado correctamente.")
            return True
            
        except requests.exceptions.RequestException as e:
            log_file_only("ERROR", f"❌ Error de red en refresh: {e}")
            raise
        except Exception as e:
            log_file_only("ERROR", f"❌ Error inesperado en refresh: {e}")
            raise

token_manager = TokenManager(ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET)

def build_headers() -> dict:
    """Construye headers con token de autorización"""
    token = token_manager.get_token()
    if not token:
        raise RuntimeError("No se pudo obtener token válido")
    return {
        "Authorization": f"Bearer {token}",
    }

# ==================== HTTP SESSION ====================

_session = None
_session_lock = threading.Lock()

def get_session() -> requests.Session:
    """Obtiene sesión HTTP compartida con retry strategy + headers tipo navegador."""
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=0.6,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]),
                raise_on_status=False
            )
            adapter = HTTPAdapter(
                pool_connections=MAX_WORKERS,
                pool_maxsize=MAX_WORKERS * 2,
                max_retries=retry,
            )
            s.mount("https://", adapter)
            s.mount("http://", adapter)

                    # Headers tipo navegador completos (cookies persistentes en la Session)
            s.headers.update({
                        "User-Agent": USER_AGENT,
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "DNT": "1",
                    })
            _session = s
        return _session


# ==================== FUNCIONES DE PROCESAMIENTO ====================

def load_processed_items() -> set:
    """Carga los items ya procesados exitosamente"""
    processed_items = set()
    try:
        if os.path.exists(PROCESSED_ITEMS_FILE):
            with open(PROCESSED_ITEMS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    item_id = line.strip()
                    if item_id:
                        processed_items.add(item_id)
            log_file_only("INFO", f"📋 Cargados {len(processed_items)} items ya procesados")
    except Exception as e:
        log_file_only("WARNING", f"⚠️ Error cargando items procesados: {e}")
    return processed_items

def save_processed_item(item_id: str):
    """Guarda un item procesado exitosamente"""
    try:
        with open(PROCESSED_ITEMS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{item_id}\n")
    except Exception as e:
        log_file_only("ERROR", f"❌ Error guardando item procesado: {e}")

def download_image(url: str, item_id: str, image_num: int) -> tuple[bool, str, str]:
    """
    Descarga una imagen desde URL con peticiones simples.
    Hace hasta 3 intentos con backoff exponencial.
    Retorna: (éxito, ruta_archivo, mensaje_error)
    """
    if not url or pd.isna(url) or str(url).strip() == "":
        error_msg = "URL vacía o inválida"
        log_file_only("WARNING", f"⚠️ Imagen {image_num} para {item_id}: {error_msg}")
        return False, "", error_msg
    
    url = str(url).strip()
    MAX_ATTEMPTS = 3

    try:
        log_console_and_file("INFO", f"📥 [{item_id}] Imagen {image_num}: Iniciando descarga desde {url[:100]}...")
        session = get_session()
        
        attempts = 0
        last_resp = None

        while attempts < MAX_ATTEMPTS:
            attempts += 1
            log_file_only("INFO", f"   └─ Intento {attempts}/{MAX_ATTEMPTS}")
            
            resp = session.get(url, timeout=TIMEOUT_DOWNLOAD, stream=True)
            last_resp = resp

            # Log detallado del response HTTP
            log_file_only("INFO", f"      └─ Response HTTP: {resp.status_code} {resp.reason}")
            log_file_only("INFO", f"      └─ Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
            log_file_only("INFO", f"      └─ Content-Length: {resp.headers.get('Content-Length', 'N/A')} bytes")

            content_type = (resp.headers.get('Content-Type') or '').lower()

            # Errores HTTP estándar
            if resp.status_code != 200:
                resp.close()
                error_msg = f"HTTP {resp.status_code} - {resp.reason}"
                
                if resp.status_code == 404:
                    error_msg += " (Imagen no encontrada en el servidor)"
                elif resp.status_code == 403:
                    error_msg += " (Acceso prohibido - verificar permisos)"
                elif resp.status_code == 401:
                    error_msg += " (No autorizado - verificar credenciales)"
                elif resp.status_code >= 500:
                    error_msg += " (Error del servidor de origen)"
                elif resp.status_code == 400:
                    error_msg += " (Petición incorrecta)"

                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
                log_file_only("ERROR", f"   └─ URL completa: {url}")

                # Reintentar en errores recuperables
                if resp.status_code in (429, 500, 502, 503, 504) and attempts < MAX_ATTEMPTS:
                    backoff = 0.8 * attempts
                    log_file_only("INFO", f"      └─ Error recuperable, esperando {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue
                return False, "", error_msg

            # VALIDACIÓN: Solo aceptar Content-Type que empiece con "image/"
            if not content_type.startswith("image/"):
                resp.close()
                error_msg = f"Content-Type no es imagen: '{content_type or 'N/A'}' (se esperaba image/*)"
                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
                log_file_only("ERROR", f"   └─ URL completa: {url}")
                log_file_only("ERROR", f"   └─ Posible HTML/texto en lugar de imagen")
                
                # Reintentar si quedan intentos
                if attempts < MAX_ATTEMPTS:
                    backoff = 0.5 * attempts
                    log_file_only("INFO", f"      └─ Reintentando en {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue
                return False, "", error_msg

            # Determinar extensión por Content-Type
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            elif 'webp' in content_type:
                ext = '.webp'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'svg' in content_type:
                ext = '.svg'
            else:
                ext = '.jpg'  # fallback

            log_file_only("INFO", f"      └─ Tipo de archivo detectado: {ext} (de {content_type})")

            # Descargar a archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                bytes_downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    tmp_file.write(chunk)
                    bytes_downloaded += len(chunk)
                tmp_path = tmp_file.name

            file_size = os.path.getsize(tmp_path)
            
            # Validar que el archivo descargado tenga contenido
            if file_size == 0:
                os.remove(tmp_path)
                error_msg = "Archivo descargado está vacío (0 bytes)"
                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
                if attempts < MAX_ATTEMPTS:
                    time.sleep(0.5 * attempts)
                    continue
                return False, "", error_msg
            
            log_console_and_file("INFO", f"✅ [{item_id}] Imagen {image_num}: Descargada exitosamente ({file_size:,} bytes)")
            log_file_only("INFO", f"   └─ Archivo temporal: {tmp_path}")
            
            return True, tmp_path, ""

        # Si agotamos todos los intentos
        if last_resp is not None:
            ct = last_resp.headers.get('Content-Type') or 'N/A'
            msg = f"No se pudo obtener imagen después de {MAX_ATTEMPTS} intentos (último: status={last_resp.status_code}, Content-Type={ct})"
        else:
            msg = f"No se pudo obtener imagen después de {MAX_ATTEMPTS} intentos (sin respuesta)"
        
        log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {msg}")
        return False, "", msg

    except requests.Timeout:
        error_msg = f"Timeout después de {TIMEOUT_DOWNLOAD}s (servidor no responde)"
        log_console_and_file("ERROR", f"⏱️ [{item_id}] Imagen {image_num}: {error_msg}")
        log_file_only("ERROR", f"   └─ URL: {url}")
        return False, "", error_msg
    except requests.ConnectionError as e:
        error_msg = f"Error de conexión: {str(e)}"
        log_console_and_file("ERROR", f"🔌 [{item_id}] Imagen {image_num}: {error_msg}")
        log_file_only("ERROR", f"   └─ URL: {url}")
        return False, "", error_msg
    except Exception as e:
        error_msg = f"Excepción inesperada: {type(e).__name__} - {str(e)}"
        log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
        log_file_only("ERROR", f"   └─ URL: {url}")
        log_file_only("ERROR", f"   └─ Stack trace: {str(e)}")
        return False, "", error_msg

def upload_image_to_ml(image_path: str, item_id: str, image_num: int) -> tuple[bool, str, str]:
    """
    Sube imagen a MercadoLibre y obtiene el picture_id
    Retorna: (éxito, picture_id, mensaje_error)
    """
    try:
        file_size = os.path.getsize(image_path)
        log_console_and_file("INFO", f"📤 [{item_id}] Imagen {image_num}: Subiendo a MercadoLibre ({file_size:,} bytes)...")
        log_file_only("INFO", f"   └─ Archivo local: {image_path}")
        
        session = get_session()
        headers = build_headers()
        
        with open(image_path, 'rb') as f:
            files = {'file': f}
            resp = session.post(
                UPLOAD_PICTURE_URL,
                headers=headers,
                files=files,
                timeout=TIMEOUT_UPLOAD
            )
        
        log_file_only("INFO", f"   └─ Response HTTP: {resp.status_code}")
        
        if resp.status_code == 201:
            data = resp.json()
            picture_id = data.get('id')
            
            if picture_id:
                log_console_and_file("INFO", f"✅ [{item_id}] Imagen {image_num}: Subida exitosamente (ID: {picture_id})")
                log_file_only("INFO", f"   └─ Picture ID: {picture_id}")
                
                # Validar que la imagen esté disponible
                if 'variations' in data and len(data['variations']) > 0:
                    log_file_only("INFO", f"   └─ Validación ML: OK ({len(data['variations'])} variaciones generadas)")
                    log_console_and_file("INFO", f"✅ [{item_id}] Imagen {image_num}: Validada por ML ({len(data['variations'])} variaciones)")
                else:
                    log_file_only("INFO", f"   └─ Validación ML: Imagen aceptada (sin variaciones)")
                
                return True, picture_id, ""
            else:
                error_msg = "No se recibió picture_id en la respuesta de ML"
                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
                log_file_only("ERROR", f"   └─ Respuesta completa: {data}")
                return False, "", error_msg
                
        elif resp.status_code == 401:
            # Token expirado, intentar refresh
            log_console_and_file("WARNING", f"🔐 [{item_id}] Imagen {image_num}: Token expirado (401), refrescando...")
            if token_manager.refresh_blocking():
                log_console_and_file("INFO", f"🔄 [{item_id}] Imagen {image_num}: Token refrescado, reintentando...")
                # Reintentar con nuevo token
                return upload_image_to_ml(image_path, item_id, image_num)
            else:
                error_msg = "HTTP 401 - No se pudo refrescar token"
                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
                return False, "", error_msg
        else:
            error_msg = f"HTTP {resp.status_code}"
            try:
                error_detail = resp.json()
                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg} - {error_detail.get('message', 'Sin mensaje')}")
                log_file_only("ERROR", f"   └─ Detalle de error ML: {error_detail}")
            except:
                log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg} - {resp.text[:200]}")
                log_file_only("ERROR", f"   └─ Respuesta completa: {resp.text[:500]}")
            
            return False, "", error_msg
            
    except requests.Timeout:
        error_msg = f"Timeout después de {TIMEOUT_UPLOAD}s subiendo a ML"
        log_console_and_file("ERROR", f"⏱️ [{item_id}] Imagen {image_num}: {error_msg}")
        return False, "", error_msg
    except Exception as e:
        error_msg = f"Excepción: {type(e).__name__} - {str(e)}"
        log_console_and_file("ERROR", f"❌ [{item_id}] Imagen {image_num}: {error_msg}")
        log_file_only("ERROR", f"   └─ Stack trace: {str(e)}")
        return False, "", error_msg

def update_item_pictures(item_id: str, picture_ids: list) -> tuple[bool, str]:
    """
    Actualiza el item en ML con los nuevos picture_ids
    Retorna: (éxito, mensaje_error)
    """
    try:
        log_console_and_file("INFO", f"🔄 [{item_id}] Actualizando item con {len(picture_ids)} imágenes...")
        log_file_only("INFO", f"   └─ Picture IDs: {picture_ids}")
        
        session = get_session()
        headers = build_headers()
        headers["Content-Type"] = "application/json"
        
        url = f"https://api.mercadolibre.com/items/{item_id}"
        
        # Construir payload con array de pictures
        pictures = [{"id": pic_id} for pic_id in picture_ids]
        payload = {"pictures": pictures}
        
        log_file_only("INFO", f"   └─ Payload: {payload}")
        
        resp = session.put(url, headers=headers, json=payload, timeout=TIMEOUT_UPDATE)
        
        log_file_only("INFO", f"   └─ Response HTTP: {resp.status_code}")
        
        if resp.status_code == 200:
            log_console_and_file("INFO", f"✅ [{item_id}] Item actualizado exitosamente con {len(picture_ids)} imágenes")
            data = resp.json()
            log_file_only("INFO", f"   └─ Permalink: {data.get('permalink', 'N/A')}")
            return True, ""
            
        elif resp.status_code == 401:
            # Token expirado, intentar refresh
            log_console_and_file("WARNING", f"🔐 [{item_id}] Token expirado (401) al actualizar, refrescando...")
            if token_manager.refresh_blocking():
                log_console_and_file("INFO", f"🔄 [{item_id}] Token refrescado, reintentando actualización...")
                # Reintentar con nuevo token
                return update_item_pictures(item_id, picture_ids)
            else:
                error_msg = "HTTP 401 - No se pudo refrescar token"
                log_console_and_file("ERROR", f"❌ [{item_id}] {error_msg}")
                return False, error_msg
        else:
            error_msg = f"HTTP {resp.status_code}"
            try:
                error_detail = resp.json()
                log_console_and_file("ERROR", f"❌ [{item_id}] Error actualizando: {error_msg} - {error_detail.get('message', 'Sin mensaje')}")
                log_file_only("ERROR", f"   └─ Detalle de error ML: {error_detail}")
            except:
                log_console_and_file("ERROR", f"❌ [{item_id}] Error actualizando: {error_msg} - {resp.text[:200]}")
                log_file_only("ERROR", f"   └─ Respuesta completa: {resp.text[:500]}")
            
            return False, error_msg
            
    except requests.Timeout:
        error_msg = f"Timeout después de {TIMEOUT_UPDATE}s actualizando item"
        log_console_and_file("ERROR", f"⏱️ [{item_id}] {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Excepción: {type(e).__name__} - {str(e)}"
        log_console_and_file("ERROR", f"❌ [{item_id}] Error actualizando: {error_msg}")
        log_file_only("ERROR", f"   └─ Stack trace: {str(e)}")
        return False, error_msg

def process_item(row: pd.Series, item_num: int, total_items: int) -> dict:
    """
    Procesa un item completo: valida URLs, descarga imágenes, sube a ML y actualiza item
    Retorna: dict con estado del procesamiento y estadísticas
    """
    item_id = str(row['ID']).strip()
    
    log_console_and_file("INFO", f"\n{'='*70}")
    log_console_and_file("INFO", f"🎯 PROCESANDO ITEM {item_num}/{total_items}: {item_id}")
    log_console_and_file("INFO", f"{'='*70}")
    
    # Recolectar URLs de imágenes (columnas que empiezan con "Imagen")
    image_urls = []
    for col in row.index:
        if col.startswith('Imagen'):
            url = row[col]
            # Validar que la URL no sea vacía, NaN, o valores inválidos
            if url and url not in ['', 'nan', 'None', 'NaN', 'null'] and not pd.isna(url):
                u = str(url).strip()
                if u and (u.startswith("http://") or u.startswith("https://")):
                    image_urls.append((col, u))
    
    if not image_urls:
        error_msg = "No hay URLs de imágenes válidas en el CSV"
        log_console_and_file("WARNING", f"🟡 [{item_id}] {error_msg}, se omite")
        return {
            "success": False,
            "item_id": item_id,
            "error": error_msg,
            "omitted": True,
            "images_found": 0,
            "images_uploaded": 0,
            "images_failed": 0
        }
    
    log_console_and_file("INFO", f"📸 [{item_id}] Total de imágenes encontradas: {len(image_urls)}")
    log_file_only("INFO", f"   └─ Columnas con imágenes: {[col for col, _ in image_urls]}")
    
    # PASO 1: Validar URLs de imágenes (accesibilidad)
    log_console_and_file("INFO", f"\n📋 [{item_id}] Paso 1: Validando accesibilidad de {len(image_urls)} URLs...")
    log_console_and_file("INFO", f"📋 [{item_id}] Formato: Imagen # - Link - Status Code - Content Type")
    validated_urls = []
    for idx, (col_name, url) in enumerate(image_urls, start=1):
        try:
            # Intentar HEAD request primero (más rápido)
            resp = requests.head(url, timeout=10, allow_redirects=True)
            content_type = resp.headers.get('Content-Type', 'N/A')
            
            # Si HEAD da 405 (Method Not Allowed), intentar GET con rango limitado
            if resp.status_code == 405:
                log_file_only("INFO", f"      └─ HEAD no permitido (405), intentando GET con rango...")
                # GET request con rango de solo los primeros 1024 bytes para verificar
                headers = {'Range': 'bytes=0-1023'}
                resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True, stream=True)
                content_type = resp.headers.get('Content-Type', 'N/A')
                resp.close()  # Cerrar inmediatamente ya que solo queremos validar
            
            # Log con formato solicitado
            log_console_and_file("INFO", f"📋 [{item_id}] Imagen {idx} - {url} - {resp.status_code} - {content_type}")
            
            # Aceptar códigos de éxito (200, 206 para partial content)
            if resp.status_code in (200, 206):
                validated_urls.append((col_name, url))
                log_file_only("INFO", f"      └─ ✅ URL válida")
            else:
                log_file_only("INFO", f"      └─ ⚠️ URL inaccesible")
        except Exception as e:
            log_console_and_file("WARNING", f"📋 [{item_id}] Imagen {idx} - {url} - ERROR - {str(e)}")
            log_file_only("WARNING", f"      └─ ⚠️ Error validando URL: {e}")
    
    if not validated_urls:
        error_msg = f"Ninguna de las {len(image_urls)} URLs es accesible"
        log_console_and_file("WARNING", f"🟡 [{item_id}] {error_msg}, se omite")
        return {
            "success": False,
            "item_id": item_id,
            "error": error_msg,
            "omitted": True,
            "images_found": len(image_urls),
            "images_uploaded": 0,
            "images_failed": len(image_urls)
        }
    
    if len(validated_urls) < len(image_urls):
        log_console_and_file("WARNING", f"⚠️ [{item_id}] Solo {len(validated_urls)}/{len(image_urls)} URLs son válidas")
    else:
        log_console_and_file("INFO", f"✅ [{item_id}] Todas las URLs son válidas")
    
    # PASO 2: Procesar cada imagen SECUENCIALMENTE
    log_console_and_file("INFO", f"\n📥 [{item_id}] Paso 2: Descargando y subiendo {len(validated_urls)} imágenes...")
    picture_ids = []
    temp_files = []
    images_failed = 0
    
    for idx, (col_name, url) in enumerate(validated_urls, start=1):
        log_console_and_file("INFO", f"\n--- [{item_id}] Imagen {idx}/{len(validated_urls)} ---")
        
        # Descargar imagen
        success, temp_path, error = download_image(url, item_id, idx)
        if not success:
            images_failed += 1
            log_console_and_file("WARNING", f"⚠️ [{item_id}] Imagen {idx} no descargada: {error}")
            log_console_and_file("WARNING", f"⏭️ [{item_id}] Continuando con siguiente imagen...")
            continue
        
        temp_files.append(temp_path)
        
        # Subir a ML
        success, picture_id, error = upload_image_to_ml(temp_path, item_id, idx)
        if not success:
            images_failed += 1
            log_console_and_file("WARNING", f"⚠️ [{item_id}] Imagen {idx} no subida a ML: {error}")
            log_console_and_file("WARNING", f"⏭️ [{item_id}] Continuando con siguiente imagen...")
            continue
        
        picture_ids.append(picture_id)
        log_console_and_file("INFO", f"✅ [{item_id}] Imagen {idx}/{len(validated_urls)} procesada correctamente")
        
        # Pequeña pausa entre uploads para no saturar
        if idx < len(validated_urls):
            time.sleep(0.5)
    
    # Limpiar archivos temporales
    log_file_only("INFO", f"\n🗑️ [{item_id}] Limpiando {len(temp_files)} archivos temporales...")
    for temp_path in temp_files:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                log_file_only("INFO", f"   └─ Eliminado: {temp_path}")
        except Exception as e:
            log_file_only("WARNING", f"   └─ No se pudo eliminar {temp_path}: {e}")
    
    # Verificar que se subieron imágenes
    if not picture_ids:
        error_msg = f"No se pudo subir ninguna imagen ({len(validated_urls)} intentadas, {images_failed} fallaron)"
        log_console_and_file("ERROR", f"❌ [{item_id}] {error_msg}")
        return {
            "success": False,
            "item_id": item_id,
            "error": error_msg,
            "omitted": False,
            "images_found": len(image_urls),
            "images_uploaded": 0,
            "images_failed": images_failed
        }
    
    log_console_and_file("INFO", f"\n📊 [{item_id}] Resumen de imágenes:")
    log_console_and_file("INFO", f"   ✅ Subidas exitosamente: {len(picture_ids)}")
    log_console_and_file("INFO", f"   ❌ Fallidas: {images_failed}")
    log_console_and_file("INFO", f"   📋 Total procesadas: {len(validated_urls)}")
    
    # PASO 3: Actualizar item con nuevas imágenes
    log_console_and_file("INFO", f"\n🔄 [{item_id}] Paso 3: Actualizando item en MercadoLibre...")
    success, error = update_item_pictures(item_id, picture_ids)
    if not success:
        error_msg = f"Error actualizando item: {error}"
        log_console_and_file("ERROR", f"❌ [{item_id}] {error_msg}")
        return {
            "success": False,
            "item_id": item_id,
            "error": error_msg,
            "omitted": False,
            "images_found": len(image_urls),
            "images_uploaded": len(picture_ids),
            "images_failed": images_failed
        }
    
    log_console_and_file("INFO", f"\n🎉 [{item_id}] ¡ITEM PROCESADO EXITOSAMENTE!")
    log_console_and_file("INFO", f"{'='*70}\n")
    
    return {
        "success": True,
        "item_id": item_id,
        "error": None,
        "omitted": False,
        "images_found": len(image_urls),
        "images_uploaded": len(picture_ids),
        "images_failed": images_failed
    }

# ==================== MAIN ====================

def main():
    log_console_and_file("INFO", f"{'='*70}")
    log_console_and_file("INFO", f"🚀 SCRIPT DE ACTUALIZACIÓN DE FOTOS - TIENDA: {TIENDA}")
    log_console_and_file("INFO", f"{'='*70}")
    
    # Validar credenciales
    log_console_and_file("INFO", "🔍 Validando credenciales...")
    if not token_manager._validate_credentials():
        log_console_and_file("ERROR", "❌ Credenciales incompletas. Verifica tu archivo .env:")
        log_console_and_file("ERROR", f"   {TIENDA}_ACCESS_TOKEN: {'✓' if ACCESS_TOKEN else '✗'}")
        log_console_and_file("ERROR", f"   {TIENDA}_REFRESH_TOKEN: {'✓' if REFRESH_TOKEN else '✗'}")
        log_console_and_file("ERROR", f"   {TIENDA}_CLIENT_ID: {'✓' if CLIENT_ID else '✗'}")
        log_console_and_file("ERROR", f"   {TIENDA}_CLIENT_SECRET: {'✓' if CLIENT_SECRET else '✗'}")
        return
    
    # Refrescar token
    log_console_and_file("INFO", "🔄 Refrescando token de acceso...")
    if not token_manager.refresh_blocking():
        log_console_and_file("ERROR", "❌ No se pudo refrescar token. Abortando.")
        return
    log_console_and_file("INFO", "✅ Token refrescado exitosamente")
    
    # Validar token
    if not token_manager.validate_token():
        log_console_and_file("ERROR", "❌ Token inválido después del refresh. Abortando.")
        return
    
    # Buscar archivo CSV de la tienda
    csv_files = [f for f in os.listdir(CSV_FOLDER) if f.startswith(TIENDA.lower()) and f.endswith('.csv')]
    
    if not csv_files:
        log_console_and_file("ERROR", f"❌ No se encontró archivo CSV para tienda {TIENDA} en {CSV_FOLDER}")
        return
    
    csv_file = os.path.join(CSV_FOLDER, csv_files[0])
    log_console_and_file("INFO", f"📄 Leyendo archivo: {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        total_items = len(df)
        log_console_and_file("INFO", f"📊 Total de items en CSV: {total_items}")
        
        # Cargar items ya procesados
        processed_items = load_processed_items()
        
        # Filtrar items ya procesados
        df = df[~df['ID'].isin(processed_items)]
        pending_items = len(df)
        
        if processed_items:
            skipped = total_items - pending_items
            log_console_and_file("INFO", f"⏭️ Saltando {skipped} items ya procesados")
        
        if pending_items == 0:
            log_console_and_file("INFO", "✅ Todos los items ya fueron procesados")
            return
        
        log_console_and_file("INFO", f"📊 Items pendientes: {pending_items}")
        log_console_and_file("INFO", f"⚙️ Modo de procesamiento: SECUENCIAL (item por item, foto por foto)")
        log_console_and_file("INFO", f"🔄 Modo secuencial: validación + descarga + subida de imágenes una por una")
        log_console_and_file("INFO", "")
        log_console_and_file("INFO", "🚀 Iniciando procesamiento secuencial...")
        log_console_and_file("INFO", "")
        
        # Contadores detallados
        items_exitosos = 0
        items_con_errores = 0
        items_omitidos = 0
        total_imagenes_encontradas = 0
        total_imagenes_subidas = 0
        total_imagenes_fallidas = 0
        errors_list = []
        
        # Procesar items SECUENCIALMENTE (uno por uno)
        for item_num, (idx, row) in enumerate(df.iterrows(), start=1):
            log_console_and_file("INFO", f"\n{'#'*70}")
            log_console_and_file("INFO", f"📦 ITEM {item_num}/{pending_items}")
            log_console_and_file("INFO", f"{'#'*70}")
            
            # Procesar el item
            result = process_item(row, item_num, pending_items)
            
            # Actualizar estadísticas
            total_imagenes_encontradas += result["images_found"]
            total_imagenes_subidas += result["images_uploaded"]
            total_imagenes_fallidas += result["images_failed"]
            
            if result["success"]:
                items_exitosos += 1
                save_processed_item(result["item_id"])
                log_console_and_file("INFO", f"\n✅ Item {item_num}/{pending_items} completado exitosamente")
            elif result["omitted"]:
                items_omitidos += 1
                log_console_and_file("WARNING", f"\n🟡 Item {item_num}/{pending_items} omitido: {result['error']}")
            else:
                items_con_errores += 1
                errors_list.append({"ID": result["item_id"], "Error": result["error"]})
                log_console_and_file("ERROR", f"\n❌ Item {item_num}/{pending_items} falló: {result['error']}")
            
            # Mostrar progreso general
            items_procesados = items_exitosos + items_con_errores
            log_console_and_file("INFO", f"\n📊 Progreso General: {item_num}/{pending_items} items")
            log_console_and_file("INFO", f"   ✅ Exitosos: {items_exitosos}")
            log_console_and_file("INFO", f"   ❌ Con errores: {items_con_errores}")
            log_console_and_file("INFO", f"   🟡 Omitidos: {items_omitidos}")
            
            # Log de progreso periódico cada 10 items
            if item_num % 10 == 0 and item_num > 0:
                log_console_and_file("INFO", f"\n📈 Checkpoint - Procesados {item_num}/{pending_items} items...")
                log_console_and_file("INFO", f"   🖼️ Imágenes: {total_imagenes_subidas} subidas, {total_imagenes_fallidas} fallidas")
                log_file_only("INFO", f"   └─ Checkpoint en item {item_num}: memoria OK")
            
            # Pausa breve entre items para no saturar (excepto en el último)
            if item_num < pending_items:
                log_file_only("INFO", "\n⏸️ Pausa breve antes del siguiente item...")
                time.sleep(1)
        
        # Resumen final detallado
        log_console_and_file("INFO", "")
        log_console_and_file("INFO", f"{'='*70}")
        log_console_and_file("INFO", "📊 RESUMEN FINAL DE PROCESAMIENTO")
        log_console_and_file("INFO", f"{'='*70}")
        log_console_and_file("INFO", "")
        log_console_and_file("INFO", "📦 ITEMS:")
        log_console_and_file("INFO", f"   📋 Total en archivo: {total_items}")
        log_console_and_file("INFO", f"   ⏭️ Ya procesados (saltados): {total_items - pending_items}")
        log_console_and_file("INFO", f"   🔄 Procesados en esta ejecución: {pending_items}")
        log_console_and_file("INFO", f"   ✅ Exitosos: {items_exitosos}")
        log_console_and_file("INFO", f"   ❌ Con errores: {items_con_errores}")
        log_console_and_file("INFO", f"   🟡 Omitidos: {items_omitidos}")
        log_console_and_file("INFO", "")
        log_console_and_file("INFO", "🖼️ IMÁGENES:")
        log_console_and_file("INFO", f"   📸 Total encontradas: {total_imagenes_encontradas}")
        log_console_and_file("INFO", f"   ✅ Subidas a ML: {total_imagenes_subidas}")
        log_console_and_file("INFO", f"   ❌ Fallidas: {total_imagenes_fallidas}")
        if total_imagenes_encontradas > 0:
            tasa_exito = (total_imagenes_subidas / total_imagenes_encontradas) * 100
            log_console_and_file("INFO", f"   📊 Tasa de éxito: {tasa_exito:.1f}%")
        log_console_and_file("INFO", "")
        
        # Guardar errores si los hay
        if errors_list:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_file = f"errores_fotos_{TIENDA}_{timestamp}.xlsx"
            pd.DataFrame(errors_list).to_excel(error_file, index=False)
            log_console_and_file("WARNING", f"⚠️ Archivo de errores guardado: {error_file}")
            log_console_and_file("WARNING", f"   Total de errores: {len(errors_list)}")
        
        log_console_and_file("INFO", "")
        log_console_and_file("INFO", f"📝 Log completo guardado en: {LOG_FILE}")
        log_console_and_file("INFO", f"📁 Items procesados guardados en: {PROCESSED_ITEMS_FILE}")
        log_console_and_file("INFO", f"{'='*70}")
        
        # Log de finalización
        if items_exitosos == pending_items:
            log_console_and_file("INFO", f"🎉 ¡PROCESAMIENTO COMPLETADO CON ÉXITO!")
        elif items_con_errores > 0:
            log_console_and_file("WARNING", f"⚠️ PROCESAMIENTO COMPLETADO CON ALGUNOS ERRORES")
        else:
            log_console_and_file("INFO", f"✅ PROCESAMIENTO COMPLETADO")
        
    except FileNotFoundError:
        log_console_and_file("ERROR", f"❌ Archivo no encontrado: {csv_file}")
    except Exception as e:
        log_console_and_file("ERROR", f"❌ Error general: {e}")
        import traceback
        log_file_only("ERROR", traceback.format_exc())

if __name__ == "__main__":
    main()
