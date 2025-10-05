import os
import time
import math
import json
import asyncio
import random
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd
import aiohttp
from aiohttp.client_exceptions import ClientError
from dotenv import load_dotenv

import ssl, certifi
from tqdm import tqdm

load_dotenv()

# ======== CONFIG =========
INPUT_FILE = "Data/Cambio_Precio/CO.xlsx"   # columnas: ID, Precio
OUTPUT_DIR = os.path.join("Output", "Updates_Prices")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Límite sostenido y comportamiento
RATE_RPM = 900                 # tokens por minuto (ajusta 900–1200; sube si 0×429 por minutos)
MAX_CONC = 8                   # nº de workers concurrentes (5–10 recomendado)
READ_BATCH = 80                # tamaño de multiget para lectura (50–100 recomendado)
CSV_FLUSH_EVERY = 500          # guardar resultados cada N

TIENDAS: Dict[str, Dict[str, Optional[str]]] = {
    code: {
        "access_token": os.getenv(f"{code}_ACCESS_TOKEN"),
        "refresh_token": os.getenv(f"{code}_REFRESH_TOKEN"),
        "client_id": os.getenv(f"{code}_CLIENT_ID"),
        "client_secret": os.getenv(f"{code}_CLIENT_SECRET"),
        "user_id": os.getenv(f"{code}_SELLER_ID"),
        "name": code
    }
    for code in ["CO"]
}
# =========================


# =========== Utilidades ===========

def _now() -> float:
    return time.monotonic()

def _to_float_price(x) -> float:
    if isinstance(x, str):
        x = x.strip().replace(",", "")
    return float(x)

def _deduplicate_rows(rows: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """Último precio prevalece por ID."""
    seen = {}
    for _id, price in rows:
        seen[_id] = price
    return list(seen.items())

def _valid_item_id(item_id: str) -> bool:
    return isinstance(item_id, str) and len(item_id) >= 8 and item_id[:3].isalpha()

def build_ssl_connector(limit=64):
    """TLS con certifi (evita errores de certificado)."""
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    return aiohttp.TCPConnector(limit=limit, ttl_dns_cache=300, ssl=ssl_ctx)


# =========== Rate Limiter (Token Bucket real) ===========

class TokenBucket:
    """
    Token bucket simple:
      - capacity = rpm (como 'burst' razonable)
      - refill continuo: rate = rpm / 60 tokens/seg
      - acquire() bloquea hasta haber >=1 token
    """
    def __init__(self, rpm: float, capacity: Optional[float] = None):
        self.rate = rpm / 60.0
        self.capacity = capacity if capacity is not None else float(rpm)
        self.tokens = self.capacity
        self.last = _now()
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = _now()
                elapsed = now - self.last
                if elapsed > 0:
                    self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                    self.last = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # tokens que faltan y tiempo necesario
                need = 1.0 - self.tokens
                wait = need / self.rate if self.rate > 0 else 0.5
            await asyncio.sleep(min(0.5, max(0.01, wait)))


# =========== Token Manager ===========

class TokenManager:
    def __init__(self, store: Dict[str, Any]):
        self.store = store
        self._lock = asyncio.Lock()

    async def refresh(self, session: aiohttp.ClientSession) -> bool:
        url = "https://api.mercadolibre.com/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.store["client_id"],
            "client_secret": self.store["client_secret"],
            "refresh_token": self.store["refresh_token"],
        }
        async with self._lock:
            try:
                async with session.post(url, data=payload, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status != 200:
                        return False
                    data = await r.json()
                    self.store["access_token"] = data.get("access_token", self.store["access_token"])
                    if data.get("refresh_token"):
                        self.store["refresh_token"] = data["refresh_token"]
                    return True
            except ClientError:
                return False


# =========== I/O Helpers ===========

def dump_append(path: str, rows: List[Dict[str, Any]]):
    if not rows:
        return
    df = pd.DataFrame(rows)
    if not os.path.exists(path):
        df.to_csv(path, index=False, encoding="utf-8")
    else:
        df.to_csv(path, mode="a", index=False, header=False, encoding="utf-8")

def merge_csv_preserving(path: str):
    df = pd.read_csv(path)
    df = df.sort_index().drop_duplicates(subset=["ID"], keep="last")
    df.to_csv(path, index=False, encoding="utf-8")


# =========== API Calls ===========

async def safe_text(resp: aiohttp.ClientResponse) -> str:
    try:
        return await resp.text()
    except Exception:
        return "<no-body>"

async def ml_multiget_items(http: aiohttp.ClientSession, ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    GET /items?ids=ID1,ID2,...
    Devuelve dict {id: body_dict} sólo para los 200 OK; los no 200 no aparecen.
    """
    if not ids:
        return {}
    url = "https://api.mercadolibre.com/items"
    params = {"ids": ",".join(ids)}
    out: Dict[str, Dict[str, Any]] = {}
    try:
        async with http.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return out
            data = await r.json(content_type=None)
            # formato típico: [{"code":200,"body":{...}}, {"code":404,"body":{...}}]
            for entry in data:
                code = entry.get("code")
                body = entry.get("body") or {}
                _id = body.get("id") or (entry.get("id") if isinstance(entry.get("id"), str) else None)
                if code == 200 and _id:
                    out[_id] = body
            return out
    except ClientError:
        return out

async def actualizar_item(
    http: aiohttp.ClientSession,
    bucket: TokenBucket,
    token_mgr: TokenManager,
    store: Dict[str, Any],
    item_id: str,
    precio: float,
    counters: Dict[str, int],
    max_retries: int = 6
) -> Dict[str, Any]:
    """
    PUT /items/{id} con backoff, Retry-After y refresh 401.
    Silencia 429 (no imprime).
    """
    url = f"https://api.mercadolibre.com/items/{item_id}"
    payload = {"price": precio}
    attempt = 0
    while True:
        attempt += 1
        # respeta el bucket antes de disparar
        await bucket.acquire()
        try:
            async with http.put(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status in (200, 202):
                    return {"ID": item_id, "Precio": precio, "status": "OK", "msg": "OK"}

                if resp.status == 401:
                    counters["401"] += 1
                    ok = await token_mgr.refresh(http)
                    if not ok:
                        return {"ID": item_id, "Precio": precio, "status": "FAIL",
                                "msg": f"401_refresh_failed:{await safe_text(resp)}"}
                    http.headers["Authorization"] = f"Bearer {store['access_token']}"
                    await asyncio.sleep(0.15 + random.uniform(0, 0.15))
                    continue

                if resp.status == 429:
                    counters["429"] += 1
                    ra = resp.headers.get("Retry-After")
                    try:
                        retry_after = float(ra) if ra is not None else 0.6
                    except ValueError:
                        retry_after = 0.6
                    await asyncio.sleep(retry_after)
                    if attempt <= max_retries:
                        # pequeño backoff adicional
                        await asyncio.sleep(min(2.0, (2 ** attempt) * 0.05) + random.uniform(0, 0.1))
                        continue
                    return {"ID": item_id, "Precio": precio, "status": "FAIL",
                            "msg": f"429_max_retries:{await safe_text(resp)}"}

                if 500 <= resp.status < 600:
                    counters["5xx"] += 1
                    if attempt <= max_retries:
                        delay = min(5.0, (2 ** attempt) * 0.15) + random.uniform(0, 0.2)
                        await asyncio.sleep(delay)
                        continue
                    return {"ID": item_id, "Precio": precio, "status": "FAIL",
                            "msg": f"{resp.status}_max_retries:{await safe_text(resp)}"}

                text = await safe_text(resp)
                return {"ID": item_id, "Precio": precio, "status": "FAIL", "msg": f"{resp.status}:{text[:500]}"}

        except (asyncio.TimeoutError, ClientError):
            counters["timeout"] += 1
            if attempt <= max_retries:
                delay = min(4.0, (2 ** attempt) * 0.12) + random.uniform(0, 0.15)
                await asyncio.sleep(delay)
                continue
            return {"ID": item_id, "Precio": precio, "status": "FAIL", "msg": "exception_max_retries"}


# =========== Pipeline por tienda (multiget + updates con bucket) ===========

async def procesar_tienda(code: str, store: Dict[str, Any]) -> Tuple[str, int]:
    print(f"\n[{code}] Iniciando actualizaciones…")

    # 1) Leer archivo
    if INPUT_FILE.endswith(".xlsx"):
        df = pd.read_excel(INPUT_FILE)
    else:
        df = pd.read_csv(INPUT_FILE)
    df = df.dropna(subset=["ID", "Precio"])

    # 2) Normalizar + deduplicar
    items: List[Tuple[str, float]] = []
    for _, row in df.iterrows():
        item_id = str(row["ID"]).strip()
        if not _valid_item_id(item_id):
            continue
        try:
            price = _to_float_price(row["Precio"])
        except Exception:
            continue
        items.append((item_id, price))
    items = _deduplicate_rows(items)

    out_file = os.path.join(OUTPUT_DIR, f"{code}_resultados.csv")

    # 3) Reanudación
    done_ok = set()
    if os.path.exists(out_file):
        prev = pd.read_csv(out_file)
        ok_prev = prev[prev["status"] == "OK"]["ID"].astype(str).tolist()
        done_ok.update(ok_prev)

    # 4) Multiget lectura para saltar PUT innecesarios
    #    - primero, excluir los ya OK de runs previas
    base_todo = [(i, p) for (i, p) in items if i not in done_ok]
    if not base_todo:
        print(f"[{code}] Todo ya procesado previamente ({len(done_ok)} OK).")
        return code, len(done_ok)

    timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=20)
    connector = build_ssl_connector(limit=max(64, MAX_CONC * 4))
    headers = {
        "Authorization": f"Bearer {store['access_token']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Connection": "keep-alive",
    }
    token_mgr = TokenManager(store)

    # Sesión para todo
    async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers, trust_env=True) as http:

        # 4a) (opcional) refresh al inicio por seguridad
        await token_mgr.refresh(http)

        # 4b) multiget en lotes
        #     Construye mapa {id -> precio_actual}
        id_to_target = dict(base_todo)
        ids = [i for (i, _) in base_todo]
        current_prices: Dict[str, float] = {}
        for start in tqdm(range(0, len(ids), READ_BATCH), desc=f"[{code}] Leyendo (multiget)", unit="lote", dynamic_ncols=True):
            chunk = ids[start:start+READ_BATCH]
            data = await ml_multiget_items(http, chunk)
            for _id, body in data.items():
                try:
                    # precio “simple”. Si tu caso usa variaciones, aquí tendrías que mapear variaciones.
                    current_prices[_id] = float(body.get("price")) if body.get("price") is not None else None
                except Exception:
                    current_prices[_id] = None

        # 4c) filtra los que ya tienen el precio deseado (tolerancia centavos)
        def _same_price(a: Optional[float], b: Optional[float], tol=0.01) -> bool:
            if a is None or b is None:
                return False
            return abs(float(a) - float(b)) <= tol

        todo_updates = [(i, p) for (i, p) in base_todo if not _same_price(current_prices.get(i), p)]
        skipped = len(base_todo) - len(todo_updates)
        if skipped > 0:
            print(f"[{code}] Saltados {skipped} por ya tener el precio objetivo.")

        if not todo_updates:
            # nada por hacer, pero guardamos merge final
            if os.path.exists(out_file):
                merge_csv_preserving(out_file)
            print(f"[{code}] No hay pendientes de actualización.")
            return code, len(done_ok)

        # 5) Token bucket + workers
        bucket = TokenBucket(rpm=RATE_RPM, capacity=RATE_RPM)  # burst = rpm (razonable)
        results_batch: List[Dict[str, Any]] = []
        ok_count = 0
        fail_count = 0
        counters = {"401": 0, "429": 0, "5xx": 0, "timeout": 0}

        # Cola de trabajo
        queue: asyncio.Queue[Tuple[str, float]] = asyncio.Queue()
        for pair in todo_updates:
            queue.put_nowait(pair)

        # Worker secuencial (por item) que usa el bucket antes de cada PUT
        async def worker():
            nonlocal ok_count, fail_count, results_batch
            while True:
                try:
                    item_id, price = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                res = await actualizar_item(http, bucket, token_mgr, store, item_id, price, counters)
                results_batch.append(res)
                if res["status"] == "OK": ok_count += 1
                else: fail_count += 1
                # Flush periódico
                if len(results_batch) >= CSV_FLUSH_EVERY:
                    dump_append(out_file, results_batch)
                    results_batch.clear()
                queue.task_done()

        # Barra de progreso sobre el total de updates verdaderamente necesarios
        pbar = tqdm(
            total=len(todo_updates),
            desc=f"[{code}] Actualizando",
            unit="it",
            dynamic_ncols=True,
            smoothing=0.0,
            mininterval=0.5,
            miniters=100,
            leave=True
        )

        # Interceptor para actualizar pbar cuando el queue avanza
        async def progress_updater():
            done_local = 0
            while True:
                await asyncio.sleep(0.5)
                processed_now = ok_count + fail_count
                delta = processed_now - done_local
                if delta > 0:
                    pbar.update(delta)
                    done_local = processed_now
                    # actualizar postfix cada ~200
                    if processed_now % 200 == 0 or processed_now == len(todo_updates):
                        pbar.set_postfix_str(
                            f"OK:{ok_count} FAIL:{fail_count} 401:{counters['401']} 429:{counters['429']} 5xx:{counters['5xx']} TO:{counters['timeout']}",
                            refresh=False
                        )
                if processed_now >= len(todo_updates):
                    break

        # Lanza workers + updater
        workers = [asyncio.create_task(worker()) for _ in range(MAX_CONC)]
        updater = asyncio.create_task(progress_updater())

        await asyncio.gather(*workers)
        await updater
        pbar.close()

        # flush final
        dump_append(out_file, results_batch)
        results_batch.clear()

    # merge final y resumen
    merge_csv_preserving(out_file)
    print(f"[{code}] Guardado resultados en {out_file}")
    return code, len(done_ok) + len(todo_updates)


# =========== Main ===========

async def main():
    print("Renovando tokens iniciales (mejor práctica)…")
    connector = build_ssl_connector()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25), connector=connector, trust_env=True) as http:
        for code, store in TIENDAS.items():
            tm = TokenManager(store)
            ok = await tm.refresh(http)
            if not ok:
                await asyncio.sleep(0.6)
                await tm.refresh(http)
            await asyncio.sleep(0.25 + random.uniform(0, 0.25))

    results = []
    for code, store in TIENDAS.items():
        res = await procesar_tienda(code, store)
        results.append(res)

    print("\n=== RESUMEN ===")
    total = 0
    for code, count in results:
        print(f"{code}: {count} publicaciones procesadas (incluye saltadas por precio igual)")
        total += count
    print(f"Total: {total}")

if __name__ == "__main__":
    asyncio.run(main())
