import os
import time
import math
import random
import logging
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
from dotenv import load_dotenv

# ---------------- Config & Logging (archivo + consola selectiva) ----------------
TIENDA = "TE"
LOG_FILE = f"marcas_{TIENDA}.log"
PROCESSED_ITEMS_FILE = f"items_procesados_{TIENDA}.txt"  # Archivo para items procesados exitosamente

# Configurar logging solo para archivo
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler para archivo
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)

# Handler para consola (solo mensajes importantes)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(message)s")  # Sin timestamp para consola
console_handler.setFormatter(console_formatter)

# Agregar handlers
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

# Credenciales / archivo
EXCEL_PATH      = f"../Data/Cambio_Marca/{TIENDA}.xlsx"
ACCESS_TOKEN    = os.getenv(f"{TIENDA}_ACCESS_TOKEN", "").strip()
REFRESH_TOKEN   = os.getenv(f"{TIENDA}_REFRESH_TOKEN", "").strip()
CLIENT_ID       = os.getenv(f"{TIENDA}_CLIENT_ID", "").strip()
CLIENT_SECRET   = os.getenv(f"{TIENDA}_CLIENT_SECRET", "").strip()

# === Parámetros optimizados para estrategia de colas ===
# Objetivo: Máxima velocidad inicial, 429 van a cola, procesamiento gradual
# Usando PUT /items/{id} con sistema de colas inteligente
MAX_WORKERS     = 60       # hilos (máxima concurrencia inicial)
MAX_RETRIES     = 1        # reintentos mínimos (429 van a cola)
BASE_BACKOFF    = 0.1      # s (mínimo para errores de red)
MAX_BACKOFF     = 1.0      # s (mínimo para recuperación rápida)
JITTER_MAX      = 0.02     # s (mínima variabilidad)

# RPS ultra agresivo inicial, luego gradual
INIT_RPS        = 100      # RPS inicial (máximo agresivo)
MAX_RPS         = 100      # techo RPS inicial (~6000/min)
RPS_RAMP_UP     = 10       # incremento muy rápido inicial
RPS_PENALTY     = 0.1      # penalización mínima (429 van a cola)
MIN_RPS         = 5        # piso RPS muy bajo para colas

# Circuit breaker muy tolerante
CIRCUIT_BREAKER_THRESHOLD = 20  # muchos errores 429 para activar
CIRCUIT_BREAKER_TIMEOUT = 1     # pausa mínima

# Parámetros de colas
QUEUE_BATCH_SIZE = 1000    # procesar colas en lotes de 1000
QUEUE_REDUCTION_FACTOR = 0.8  # reducir RPS en 20% por iteración de cola

TOKEN_SAFETY_S  = 60       # refrescar si quedan < 60s

OAUTH_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

# ---------------- Token Manager (thread-safe) mejorado ----------------
class TokenManager:
    def __init__(self, access_token: str, refresh_token: str, client_id: str, client_secret: str):
        self._access_token = access_token or ""
        self._refresh_token = refresh_token or ""
        self._client_id = client_id or ""
        self._client_secret = client_secret or ""
        self._expires_at = 0.0  # epoch seconds; 0 = desconocido
        self._lock = threading.Lock()
        self._last_validation = 0.0  # timestamp de última validación
        self._validation_interval = 300  # validar cada 5 minutos
        self._is_valid = False  # estado de validez del token
        self._refresh_attempts = 0  # contador de intentos de refresh fallidos
        self._max_refresh_attempts = 3  # máximo intentos antes de fallar

    def _is_close_to_expiry(self) -> bool:
        if self._expires_at <= 0:
            return False
        return (self._expires_at - time.time()) < TOKEN_SAFETY_S

    def _needs_validation(self) -> bool:
        """Verifica si el token necesita validación"""
        now = time.time()
        return (now - self._last_validation) > self._validation_interval

    def _validate_credentials(self) -> bool:
        """Valida que las credenciales estén presentes y no vacías"""
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
            # Hacer una petición simple para validar el token
            headers = {"Authorization": f"Bearer {self._access_token}"}
            resp = requests.get(
                "https://api.mercadolibre.com/users/me", 
                headers=headers, 
                timeout=10
            )
            
            if resp.status_code == 200:
                self._is_valid = True
                self._last_validation = time.time()
                self._refresh_attempts = 0  # reset contador en caso de éxito
                user_data = resp.json()
                log_file_only("INFO", f"✅ Token validado correctamente para usuario: {user_data.get('nickname', 'N/A')}")
                return True
            elif resp.status_code == 401:
                self._is_valid = False
                log_file_only("WARNING", "⚠️ Token inválido (401) - necesita refresh")
                return False
            elif resp.status_code == 403:
                self._is_valid = False
                log_file_only("ERROR", f"❌ Token sin permisos (403): {resp.text[:200]}")
                return False
            else:
                log_file_only("WARNING", f"⚠️ Error validando token: {resp.status_code} - {resp.text[:200]}")
                return False
                
        except Exception as e:
            log_file_only("WARNING", f"⚠️ Error validando token: {e}")
            return False

    def get_token(self) -> str:
        """Obtiene el token, validando y refrescando si es necesario"""
        with self._lock:
            # Validar credenciales primero
            if not self._validate_credentials():
                log_file_only("ERROR", "❌ Credenciales incompletas o inválidas")
                return ""
            
            # Validar token si es necesario
            if self._needs_validation() or not self._is_valid:
                if not self.validate_token():
                    # Si la validación falla, intentar refresh
                    if self._refresh_attempts < self._max_refresh_attempts:
                        log_file_only("INFO", "🔄 Token inválido, intentando refresh...")
                        if self._refresh_locked():
                            return self._access_token
                        else:
                            self._refresh_attempts += 1
                    else:
                        log_file_only("ERROR", "❌ Máximo de intentos de refresh alcanzado")
                        return ""
            
            # Verificar si está cerca de expirar
            if self._is_close_to_expiry():
                self.try_refresh_async()
            
            return self._access_token

    def set_token_from_response(self, data: dict):
        at = data.get("access_token")
        if at:
            self._access_token = at
        rt = data.get("refresh_token")
        if rt:
            self._refresh_token = rt
        expires_in = int(data.get("expires_in", 0)) or 0
        if expires_in > 0:
            self._expires_at = time.time() + expires_in
            self._is_valid = True
            self._last_validation = time.time()
            self._refresh_attempts = 0  # reset contador en caso de éxito

    def try_refresh_async(self):
        if not self._validate_credentials():
            log_file_only("ERROR", "❌ Credenciales incompletas para refresh async")
            return
        if not self._lock.acquire(blocking=False):
            return
        try:
            self._refresh_locked()
        except Exception as e:
            log_file_only("WARNING", f"⚠️ Falló refresh async: {e}")
            self._refresh_attempts += 1
        finally:
            self._lock.release()

    def refresh_blocking(self) -> bool:
        if not self._validate_credentials():
            log_file_only("ERROR", "❌ No hay credenciales para refrescar token (faltan refresh_token/client_id/secret)")
            return False
        with self._lock:
            try:
                return self._refresh_locked()
            except Exception as e:
                log_file_only("ERROR", f"❌ Refresh token falló: {e}")
                self._refresh_attempts += 1
                return False

    def _refresh_locked(self) -> bool:
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
    token = token_manager.get_token()
    if not token:
        raise RuntimeError("No se pudo obtener token válido")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------- Rate Limiter adaptativo cooperativo mejorado ----------------
class AdaptiveRateLimiter:
    """
    Token bucket cooperativo mejorado con:
      - RPS dinámico (warm-up + penalidad ante 429)
      - Pausa global coordinada (Retry-After)
      - Detección de headers de rate limiting
      - Circuit breaker para patrones de fallos
    """
    def __init__(self, init_rps: float, max_rps: float):
        self.max_rps = float(max_rps)
        self.current_rps = max(float(init_rps), 1.0)
        self.capacity = max(1, int(math.floor(self.current_rps)))
        self.tokens = self.capacity
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        self.last_refill = time.monotonic()
        self.pause_until = 0.0
        self.last_429_at = 0.0
        
        # Circuit breaker
        self.consecutive_429s = 0
        self.circuit_breaker_until = 0.0
        
        # Headers de rate limiting detectados
        self.detected_rate_limit = None
        self.detected_reset_time = None
        
        # Boost para rendimiento sostenido
        self.last_success_at = 0.0
        self.boost_factor = 1.0

    def _refill_and_adjust(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        if elapsed >= 1.0:
            # Estrategia de recuperación ultra agresiva para alta velocidad
            if now > self.circuit_breaker_until:
                if self.consecutive_429s == 0:
                    # Sin errores 429 recientes: incrementar muy agresivamente
                    self.current_rps = min(self.max_rps, self.current_rps + RPS_RAMP_UP)
                    
                    # Boost adicional si hay muchos éxitos recientes
                    if now - self.last_success_at < 5.0:  # Últimos 5 segundos
                        self.boost_factor = min(1.6, self.boost_factor + 0.1)
                    else:
                        self.boost_factor = max(1.0, self.boost_factor - 0.05)
                    
                    # Aplicar boost
                    self.current_rps = min(self.max_rps, self.current_rps * self.boost_factor)
                    
                elif now - self.last_429_at > 1.0:
                    # Han pasado 1+ segundos desde el último 429: recuperar muy rápidamente
                    recovery_factor = min(2.2, 1.0 + (now - self.last_429_at) / 2.0)
                    self.current_rps = min(self.max_rps, self.current_rps * recovery_factor)
                elif now - self.last_429_at > 0.2:
                    # Han pasado 0.2+ segundos: recuperar gradualmente
                    recovery_factor = min(1.4, 1.0 + (now - self.last_429_at) / 5.0)
                    self.current_rps = min(self.max_rps, self.current_rps * recovery_factor)
                # Si hay 429 muy recientes, mantener RPS actual
            
            # Asegurar que nunca baje del mínimo
            self.current_rps = max(MIN_RPS, self.current_rps)
            self.capacity = max(1, int(math.floor(self.current_rps)))
            self.tokens = self.capacity
            self.last_refill = now

    def pause_for(self, seconds: float):
        with self.lock:
            cooldown = max(1.0, float(seconds))
            self.pause_until = max(self.pause_until, time.monotonic() + cooldown)
            self.cv.notify_all()

    def penalize(self, factor: float):
        with self.lock:
            self.last_429_at = time.monotonic()
            self.consecutive_429s += 1
            
            # Activar circuit breaker si hay muchos 429 consecutivos
            if self.consecutive_429s >= CIRCUIT_BREAKER_THRESHOLD:
                self.circuit_breaker_until = time.monotonic() + CIRCUIT_BREAKER_TIMEOUT
                log_file_only("WARNING", f"🚨 Circuit breaker activado por {self.consecutive_429s} errores 429 consecutivos. Pausa de {CIRCUIT_BREAKER_TIMEOUT}s")
            
            # Penalización mínima para mantener alta velocidad
            if self.consecutive_429s <= 5:
                # Primeros 5 errores: penalización mínima
                penalty_factor = max(factor, 0.9)
            elif self.consecutive_429s <= 10:
                # Errores 6-10: penalización moderada
                penalty_factor = max(factor, 0.8)
            else:
                # Más de 10 errores: penalización severa pero no extrema
                penalty_factor = max(factor, 0.7)
            
            self.current_rps = max(MIN_RPS, self.current_rps * penalty_factor)
            self.capacity = max(1, int(math.floor(self.current_rps)))
            self.tokens = 0
            self.cv.notify_all()

    def update_rate_limits_from_headers(self, headers: dict):
        """Actualiza límites basado en headers de la API"""
        with self.lock:
            # Headers comunes de rate limiting
            rate_limit = headers.get('X-RateLimit-Limit')
            remaining = headers.get('X-RateLimit-Remaining')
            reset_time = headers.get('X-RateLimit-Reset')
            
            if rate_limit:
                try:
                    detected_limit = int(rate_limit)
                    if detected_limit > 0 and detected_limit < self.max_rps:
                        self.detected_rate_limit = detected_limit
                        self.max_rps = min(self.max_rps, detected_limit)
                        log_file_only("INFO", f"📊 Límite de API detectado: {detected_limit} req/min")
                except ValueError:
                    pass
            
            if remaining:
                try:
                    remaining_count = int(remaining)
                    if remaining_count < 5:  # Si quedan pocas requests
                        self.pause_for(10)  # Pausa preventiva
                except ValueError:
                    pass

    def reset_consecutive_429s(self):
        """Resetea contador de 429 consecutivos en caso de éxito"""
        with self.lock:
            if self.consecutive_429s > 0:
                self.consecutive_429s = 0
                self.last_success_at = time.monotonic()  # Actualizar timestamp de éxito
                log_file_only("INFO", "✅ Contador de 429 consecutivos reseteado")

    def acquire(self):
        with self.lock:
            while True:
                now = time.monotonic()
                
                # Verificar circuit breaker
                if now < self.circuit_breaker_until:
                    wait_time = self.circuit_breaker_until - now
                    self.cv.wait(timeout=wait_time)
                    continue
                
                # Verificar pausa global
                if now < self.pause_until:
                    self.cv.wait(timeout=self.pause_until - now)
                    continue
                
                self._refill_and_adjust()
                if self.tokens > 0:
                    self.tokens -= 1
                    return
                self.cv.wait(timeout=0.01)

    def debug_snapshot(self) -> tuple[float, int, int]:
        with self.lock:
            return (self.current_rps, self.tokens, self.capacity)

limiter = AdaptiveRateLimiter(INIT_RPS, MAX_RPS)

# ---------------- HTTP session ----------------
_session = None
_session_lock = threading.Lock()

def get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            # Pool de conexiones ultra optimizado para rendimiento sostenido
            adapter = HTTPAdapter(
                pool_connections=MAX_WORKERS,  # Número de pools de conexión
                pool_maxsize=MAX_WORKERS * 3,  # Máximo de conexiones por pool (ultra agresivo)
                max_retries=Retry(total=0, backoff_factor=0.0, raise_on_status=False),
                pool_block=False,  # No bloquear si no hay conexiones disponibles
            )
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            s.request = _wrap_request_with_timeout(s.request, timeout=10)  # Timeout reducido
            _session = s
        return _session

def _wrap_request_with_timeout(orig_request, timeout=15):
    def wrapped(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return orig_request(method, url, **kwargs)
    return wrapped

# ---------------- utilidades ----------------
def parse_retry_after(ra_header: str | None) -> float | None:
    if not ra_header:
        return None
    try:
        return float(ra_header)
    except Exception:
        pass
    try:
        dt = parsedate_to_datetime(ra_header)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - now).total_seconds()
        return max(1.0, delta)
    except Exception:
        return None

def calculate_adaptive_backoff(attempt: int, status_code: int, base_backoff: float = BASE_BACKOFF) -> float:
    """Calcula backoff adaptativo basado en el tipo de error y número de intento"""
    if status_code == 429:
        # Backoff mínimo para 429 (recuperación ultra rápida)
        if attempt == 1:
            return 0.5  # Primer intento: 0.5s
        elif attempt == 2:
            return 1.0  # Segundo intento: 1s
        elif attempt == 3:
            return 2.0  # Tercer intento: 2s
        else:
            return min(MAX_BACKOFF, base_backoff * (1.2 ** (attempt - 1)))
    elif 500 <= status_code < 600:
        # Backoff estándar para errores de servidor
        return min(MAX_BACKOFF, base_backoff * (1.5 ** (attempt - 1)))
    else:
        # Backoff mínimo para otros errores
        return min(3.0, base_backoff * (1.5 ** (attempt - 1)))

def safe_item_id(v: str) -> str:
    v = str(v).strip()
    return v if v.startswith("ML") else ("MLM" + v)

def jitter():
    return (random.random() - 0.5) * 2 * JITTER_MAX  # [-JITTER_MAX, +JITTER_MAX]

# ---------------- Gestión de items procesados ----------------
def load_processed_items() -> set:
    """Carga los items ya procesados exitosamente desde el archivo"""
    processed_items = set()
    try:
        if os.path.exists(PROCESSED_ITEMS_FILE):
            with open(PROCESSED_ITEMS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    item_id = line.strip()
                    if item_id:
                        processed_items.add(item_id)
            log_file_only("INFO", f"📋 Cargados {len(processed_items)} items ya procesados exitosamente")
    except Exception as e:
        log_file_only("WARNING", f"⚠️ Error cargando items procesados: {e}")
    return processed_items

def save_processed_items_batch(processed_items: list):
    """Guarda un lote de items procesados exitosamente al archivo"""
    try:
        with open(PROCESSED_ITEMS_FILE, 'a', encoding='utf-8') as f:
            for item_id in processed_items:
                f.write(f"{item_id}\n")
        log_file_only("INFO", f"💾 Guardados {len(processed_items)} items procesados exitosamente")
    except Exception as e:
        log_file_only("ERROR", f"❌ Error guardando items procesados: {e}")

def remove_processed_items_from_excel(processed_items: set, excel_path: str) -> bool:
    """Elimina los items procesados del archivo Excel y guarda una copia de respaldo"""
    try:
        # Leer el Excel actual
        df = pd.read_excel(excel_path)
        original_count = len(df)
        
        # Filtrar items no procesados
        df_filtered = df[~df['ID'].isin(processed_items)]
        remaining_count = len(df_filtered)
        removed_count = original_count - remaining_count
        
        if removed_count > 0:
            # Crear respaldo del archivo original
            backup_path = excel_path.replace('.xlsx', f'_backup_{time.strftime("%Y%m%d_%H%M%S")}.xlsx')
            df.to_excel(backup_path, index=False)
            log_file_only("INFO", f"💾 Respaldo creado: {backup_path}")
            
            # Guardar archivo filtrado
            df_filtered.to_excel(excel_path, index=False)
            log_file_only("INFO", f"🗑️ Eliminados {removed_count} items procesados del Excel")
            log_file_only("INFO", f"📊 Items restantes: {remaining_count} (de {original_count})")
            return True
        else:
            log_file_only("INFO", f"ℹ️ No hay items procesados para eliminar del Excel")
            return False
            
    except Exception as e:
        log_file_only("ERROR", f"❌ Error procesando Excel: {e}")
        return False

# ---------------- Procesamiento de colas ----------------
def process_queue_batch(queue_items: list, current_rps: float) -> tuple[int, int, list]:
    """
    Procesa un lote de items de la cola con RPS reducido
    Retorna: (éxitos, errores, nueva_cola)
    """
    if not queue_items:
        return 0, 0, []
    
    # Reducir RPS para procesamiento de cola
    reduced_rps = max(MIN_RPS, current_rps * QUEUE_REDUCTION_FACTOR)
    limiter.current_rps = reduced_rps
    limiter.capacity = max(1, int(math.floor(reduced_rps)))
    limiter.tokens = limiter.capacity
    
    log_file_only("INFO", f"🔄 Procesando cola: {len(queue_items)} items con RPS={reduced_rps:.1f}")
    
    successes = 0
    errors = 0
    new_queue = []
    
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(queue_items))) as ex:
        futures = [ex.submit(aplicar_cambio, item_id, marca) for item_id, marca in queue_items]
        
        for fut in tqdm(as_completed(futures), total=len(queue_items), desc="Procesando cola", unit="it"):
            ok, err, should_queue, item_id, marca = fut.result()
            if ok:
                successes += 1
                log_file_only("INFO", f"✅ Cola éxito {item_id}: Marca actualizada a '{marca}'")
            else:
                if should_queue and "429_RATE_LIMIT" in str(err):
                    # Solo 429 van a nueva cola
                    new_queue.append((item_id, marca))
                    log_file_only("WARNING", f"⚠️ Cola 429 {item_id} → nueva cola")
                else:
                    errors += 1
                    log_file_only("WARNING", f"❌ Cola error final {item_id}: {err}")
    
    return successes, errors, new_queue

def process_all_queues(initial_queue: list) -> tuple[int, int, list]:
    """
    Procesa todas las colas iterativamente hasta que no queden 429
    Retorna: (total_éxitos, total_errores, cola_final)
    """
    if not initial_queue:
        return 0, 0, []
    
    current_queue = initial_queue.copy()
    total_successes = 0
    total_errors = 0
    iteration = 0
    
    log_console_and_file("INFO", f"🔄 Iniciando procesamiento de colas: {len(current_queue)} items")
    
    while current_queue and iteration < 10:  # Máximo 10 iteraciones
        iteration += 1
        log_console_and_file("INFO", f"🔄 Iteración {iteration}: {len(current_queue)} items en cola")
        
        # Procesar lote de la cola
        successes, errors, new_queue = process_queue_batch(current_queue, limiter.current_rps)
        
        total_successes += successes
        total_errors += errors
        current_queue = new_queue
        
        log_console_and_file("INFO", f"✅ Iteración {iteration} completada: {successes} éxitos, {errors} errores, {len(current_queue)} en nueva cola")
        
        if current_queue:
            # Esperar un poco antes de la siguiente iteración
            time.sleep(2)
    
    if current_queue:
        log_console_and_file("WARNING", f"⚠️ Cola final con {len(current_queue)} items (máximo de iteraciones alcanzado)")
    
    return total_successes, total_errors, current_queue

# ---------------- worker optimizado para actualización de marca ----------------
def aplicar_cambio(item_id: str, marca: str) -> tuple[bool, str | None, bool, str, str]:
    """
    Actualiza el atributo de marca usando la API de atributos de MercadoLibre:
    - 429 van directamente a cola sin reintentos
    - Máxima velocidad inicial
    - Procesamiento gradual de colas
    """
    # Primero obtener los atributos actuales del item
    get_url = f"https://api.mercadolibre.com/items/{item_id}"
    update_url = f"https://api.mercadolibre.com/items/{item_id}"
    s = get_session()
    tried_refresh = False

    # Solo un intento inicial - 429 van a cola
    limiter.acquire()
    try:
        # Obtener atributos actuales
        resp = s.get(get_url, headers=build_headers())
        
        if resp.status_code == 200:
            attributes = resp.json()
            
            # Buscar el atributo BRAND existente
            brand_attr = None
            for attr in attributes:
                if attr.get("id") == "BRAND":
                    brand_attr = attr
                    break
            
            if brand_attr:
                # Actualizar el atributo BRAND existente
                brand_attr["value_name"] = marca
                brand_attr["values"] = [{"id": brand_attr.get("value_id", ""), "name": marca, "struct": None}]
            else:
                # Crear nuevo atributo BRAND si no existe
                brand_attr = {
                    "id": "BRAND",
                    "name": "Marca",
                    "value_id": "24591625",  # ID por defecto para Cardic
                    "value_name": marca,
                    "values": [{"id": "24591625", "name": marca, "struct": None}],
                    "value_type": "string"
                }
                attributes.append(brand_attr)
            
            # Actualizar atributos
            update_resp = s.put(update_url, headers=build_headers(), json=attributes)
            
            if 200 <= update_resp.status_code < 300:
                limiter.update_rate_limits_from_headers(update_resp.headers)
                limiter.reset_consecutive_429s()
                return True, None, False, item_id, marca
            else:
                status = update_resp.status_code
        else:
            status = resp.status_code
            
    except Exception as e:
        log_file_only("WARNING", f"⚠️ NET [{item_id}]: {e} → va a cola")
        return False, f"NET_ERROR: {e}", True, item_id, marca

    if status == 401:
        if not tried_refresh:
            log_file_only("INFO", f"🔐 401 en {item_id} → intentando refresh de token...")
            if token_manager.refresh_blocking():
                tried_refresh = True
                log_file_only("INFO", f"✅ Token refrescado, reintentando {item_id}")
                # Un reintento después del refresh
                try:
                    resp = s.get(get_url, headers=build_headers())
                    if resp.status_code == 200:
                        attributes = resp.json()
                        brand_attr = None
                        for attr in attributes:
                            if attr.get("id") == "BRAND":
                                brand_attr = attr
                                break
                        
                        if brand_attr:
                            brand_attr["value_name"] = marca
                            brand_attr["values"] = [{"id": brand_attr.get("value_id", ""), "name": marca, "struct": None}]
                        else:
                            brand_attr = {
                                "id": "BRAND",
                                "name": "Marca",
                                "value_id": "24591625",
                                "value_name": marca,
                                "values": [{"id": "24591625", "name": marca, "struct": None}],
                                "value_type": "string"
                            }
                            attributes.append(brand_attr)
                        
                        update_resp = s.put(update_url, headers=build_headers(), json=attributes)
                        if 200 <= update_resp.status_code < 300:
                            return True, None, False, item_id, marca
                except Exception as e:
                    pass
            else:
                log_file_only("ERROR", f"❌ No se pudo refrescar token para {item_id}")
        return False, f"401 {resp.text[:300]}", False, item_id, marca

    if status == 403:
        # Error 403: Va a cola para reintento posterior
        error_detail = resp.text[:300] if resp.text else "Sin detalles"
        log_file_only("WARNING", f"⚠️ [403] {item_id} → va a cola: {error_detail}")
        return False, f"403 {error_detail}", True, item_id, marca

    if status == 429:
        # 429: Va directamente a cola sin reintentos
        ra = parse_retry_after(resp.headers.get("Retry-After"))
        pause_s = ra if ra is not None else 1.0
        
        limiter.update_rate_limits_from_headers(resp.headers)
        limiter.penalize(RPS_PENALTY)
        limiter.pause_for(pause_s)
        
        log_file_only("WARNING", f"⚠️ [429] {item_id} → va a cola (Retry-After: {pause_s:.1f}s)")
        return False, f"429_RATE_LIMIT", True, item_id, marca

    if 500 <= status < 600:
        # 5xx: Va a cola para reintento posterior
        log_file_only("WARNING", f"⚠️ [{status}] {item_id} → va a cola: {resp.text[:200]}")
        return False, f"{status} {resp.text[:300]}", True, item_id, marca

    # 4xx "duros": no reintentar
    return False, f"{status} {resp.text[:300]}", False, item_id, marca

# ---------------- main ----------------
def main():
    # 1) Validar credenciales y token al inicio
    log_console_and_file("INFO", "🔍 Validando credenciales y token...")
    
    if not token_manager._validate_credentials():
        log_console_and_file("ERROR", "❌ Credenciales incompletas. Verifica tu archivo .env:")
        log_console_and_file("ERROR", f"   DS_ACCESS_TOKEN: {'✓' if ACCESS_TOKEN else '✗'}")
        log_console_and_file("ERROR", f"   DS_REFRESH_TOKEN: {'✓' if REFRESH_TOKEN else '✗'}")
        log_console_and_file("ERROR", f"   DS_SELLER_ID: {'✓' if CLIENT_ID else '✗'}")
        log_console_and_file("ERROR", f"   DS_CLIENT_SECRET: {'✓' if CLIENT_SECRET else '✗'}")
        return
    
    # 2) Validar token actual o refrescar si es necesario
    if not token_manager.validate_token():
        log_console_and_file("INFO", "🔄 Token inválido, intentando refresh...")
        if not token_manager.refresh_blocking():
            log_console_and_file("ERROR", "❌ No se pudo obtener token válido. Abortando.")
            return
        log_console_and_file("INFO", "✅ Token obtenido correctamente")
    else:
        log_console_and_file("INFO", "✅ Token válido, continuando...")
    
    # 3) Verificar que el token funcione con una petición de prueba
    try:
        test_headers = build_headers()
        log_console_and_file("INFO", "🔍 Verificando conectividad con la API...")
    except RuntimeError as e:
        log_console_and_file("ERROR", f"❌ Error obteniendo headers: {e}")
        return
    
    # 4) Cargar items ya procesados y filtrar
    log_console_and_file("INFO", "🚀 Iniciando procesamiento de items...")
    
    # Cargar items ya procesados exitosamente
    processed_items = load_processed_items()
    
    try:
        df = pd.read_excel(EXCEL_PATH)
        original_count = len(df)
        
        # Filtrar items ya procesados
        if processed_items:
            df = df[~df['ID'].isin(processed_items)]
            filtered_count = len(df)
            skipped_count = original_count - filtered_count
            log_console_and_file("INFO", f"⏭️ Saltando {skipped_count} items ya procesados exitosamente")
            log_console_and_file("INFO", f"📊 Items pendientes: {filtered_count} (de {original_count})")
        else:
            log_console_and_file("INFO", f"📊 Procesando todos los {original_count} items")
        
        items = [
            (safe_item_id(row["ID"]), str(row["Marca"]).strip())
            for _, row in df.iterrows()
            if pd.notna(row.get("ID")) and pd.notna(row.get("Marca"))
        ]

        random.shuffle(items)

        total = len(items)
        log_console_and_file("INFO", 
            f"🚀 Iniciando actualización de marcas para {total} items | workers={MAX_WORKERS} | "
            f"rps_init={INIT_RPS} rps_max={MAX_RPS} (estrategia de colas) | "
            f"circuit_breaker_threshold={CIRCUIT_BREAKER_THRESHOLD} | "
            f"usando API de atributos /items/{id}/attributes con sistema de colas inteligente"
        )

        ok_count, err_count = 0, 0
        fallidos_finales = []  # -> para el Excel de salida (errores que no se pudieron resolver)
        queue_items = []  # -> para items que van a cola (429, 403, 5xx)
        
        # Lista para items procesados exitosamente (guardar en lotes de 1000)
        successful_items = []
        BATCH_SIZE = 1000  # Guardar cada 1000 items procesados

        # FASE 1: Procesamiento inicial ultra rápido (429 van a cola)
        log_console_and_file("INFO", "🚀 FASE 1: Actualización de marcas - velocidad máxima")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [ex.submit(aplicar_cambio, item_id, marca) for item_id, marca in items]
            
            # Monitoreo en tiempo real
            start_time = time.time()
            last_report_time = start_time
            
            for fut in tqdm(as_completed(futures), total=total, desc="Fase 1 - Actualizando marcas", unit="it"):
                ok, err, should_queue, item_id, marca = fut.result()
                if ok:
                    ok_count += 1
                    successful_items.append(item_id)  # Agregar a la lista de exitosos
                    log_file_only("INFO", f"✅ Éxito item {item_id}: Marca actualizada a '{marca}'")
                    
                    # Guardar lote cuando alcance 1000 items exitosos
                    if len(successful_items) >= BATCH_SIZE:
                        save_processed_items_batch(successful_items)
                        successful_items = []  # Limpiar la lista
                        
                else:
                    if should_queue:
                        # Va a cola para procesamiento posterior
                        queue_items.append((item_id, marca))
                        log_file_only("WARNING", f"⚠️ Item {item_id} → cola: {err}")
                    else:
                        # Error final (no va a cola)
                        err_count += 1
                        fallidos_finales.append({"ID": item_id, "Marca": marca, "Error": err})
                        log_file_only("WARNING", f"❌ Error final item {item_id}: {err}")
                
                # Reporte de rendimiento cada 30 segundos
                current_time = time.time()
                if current_time - last_report_time >= 30:
                    elapsed = current_time - start_time
                    processed = ok_count + err_count + len(queue_items)
                    current_rps = processed / elapsed if elapsed > 0 else 0
                    rps_limiter, tokens, cap = limiter.debug_snapshot()
                    
                    log_file_only("INFO", f"📊 Fase 1: {processed}/{total} | "
                               f"RPS actual: {current_rps:.1f} | "
                               f"RPS limiter: {rps_limiter:.1f} | "
                               f"Éxitos: {ok_count} | Cola: {len(queue_items)} | Finales: {len(fallidos_finales)}")
                    last_report_time = current_time

        # FASE 2: Procesamiento de colas con RPS reducido
        if queue_items:
            log_console_and_file("INFO", f"🔄 FASE 2: Procesando {len(queue_items)} items de cola")
            queue_successes, queue_errors, final_queue = process_all_queues(queue_items)
            
            ok_count += queue_successes
            err_count += queue_errors
            
            # Agregar items exitosos de cola a la lista
            for item_id, _ in queue_items:
                if (item_id, _) not in [(item_id, _) for item_id, _ in final_queue]:
                    successful_items.append(item_id)
            
            # Agregar items restantes de cola a errores finales
            for item_id, marca in final_queue:
                fallidos_finales.append({"ID": item_id, "Marca": marca, "Error": "429_RATE_LIMIT_PERSISTENT"})
                err_count += 1

        # Guardar items exitosos restantes (menos de 1000)
        if successful_items:
            save_processed_items_batch(successful_items)
        
        rps, tokens, cap = limiter.debug_snapshot()
        log_console_and_file("INFO", f"🎉 Actualización de marcas completada: ok={ok_count} err={err_count} | rps_final≈{rps:.1f} cap={cap}")
        
        # Log de resumen final
        if ok_count > 0:
            log_console_and_file("INFO", f"✅ {ok_count} marcas actualizadas exitosamente")
        if err_count > 0:
            log_console_and_file("WARNING", f"⚠️ {err_count} items con errores")
        if len(fallidos_finales) > 0:
            log_console_and_file("WARNING", f"⚠️ {len(fallidos_finales)} items fallaron definitivamente")
        
        # Resumen de estrategia de colas
        if queue_items:
            log_console_and_file("INFO", f"🔄 Estrategia de colas: {len(queue_items)} items procesados en cola")
        else:
            log_console_and_file("INFO", f"🚀 Estrategia de colas: Todas las marcas procesadas en fase inicial")
        
        # Actualizar Excel eliminando items procesados exitosamente en esta ejecución
        if ok_count > 0:
            log_console_and_file("INFO", "🔄 Actualizando archivo Excel...")
            # Crear set con items procesados en esta ejecución
            current_session_processed = set(successful_items)
            
            # Agregar items procesados en esta sesión a la lista total
            all_processed_items = processed_items.union(current_session_processed)
            
            if remove_processed_items_from_excel(all_processed_items, EXCEL_PATH):
                log_console_and_file("INFO", "✅ Archivo Excel actualizado exitosamente")
            else:
                log_console_and_file("WARNING", "⚠️ No se pudo actualizar el archivo Excel")

        # ---- Generar Excel con fallidos ----
        ts = time.strftime("%Y%m%d_%H%M%S")
        
        if fallidos_finales:
            out_name_finales = f"errores_finales_{ts}.xlsx"
            pd.DataFrame(fallidos_finales).to_excel(out_name_finales, index=False)
            log_console_and_file("INFO", f"📄 Archivo de errores finales generado: {out_name_finales} "
                         f"({len(fallidos_finales)} filas)")
            
            if len(fallidos_finales) > 10:
                log_console_and_file("WARNING", "⚠️ Muchos errores finales detectados. Revisa el archivo de errores para más detalles.")
        
        # Log de éxito final
        log_console_and_file("INFO", f"🎯 Script de actualización de marcas completado exitosamente. Log guardado en: {LOG_FILE}")

    except FileNotFoundError:
        log_console_and_file("ERROR", f"❌ Archivo no encontrado: {EXCEL_PATH}")
    except Exception as e:
        log_console_and_file("ERROR", f"⚠️ Error general: {e}")

if __name__ == "__main__":
    main()
