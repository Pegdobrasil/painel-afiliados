# -*- coding: utf-8 -*-
"""
rein_estoque_paginado.py
- NÃO altera config.py nem rein_client.py (apenas os utiliza).
- Pagina /api/v1/produto?page=N até a última (quando vier < 100 itens).
- Respeita ~60 req/min.
- Mantém cache local e faz atualização incremental (diff).
"""

from __future__ import annotations
from typing import Dict, List, Any, Tuple
import json, time, os
from datetime import datetime, timezone
import requests

import config  # usa REIN_BASE e rein_headers(path)

# --- parâmetros de paginação/limite ---
PAGE_SIZE = 100
RATE_WAIT = 1.05  # ~1 req/s para respeitar 60 rpm

# --- caminhos de cache (usa sua pasta Cache já existente em config) ---
try:
    CACHE_DIR = config.DIR_CACHE
except Exception:
    CACHE_DIR = os.path.join(os.getcwd(), "Cache")
    os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_FILE = os.path.join(CACHE_DIR, "rein_stock_cache.json")

SESSION = requests.Session()
EP_LIST = "/api/v1/produto"


# -------- helpers --------
def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _get(path: str, params: Dict[str, Any] | None = None) -> requests.Response:
    url = f"{config.REIN_BASE}{path}"
    r = SESSION.get(url, headers=config.rein_headers(path), params=params or {}, timeout=90)
    r.raise_for_status()
    return r


def _sum_local_stock(grade: Dict[str, Any]) -> int:
    tot = 0
    for pl in (grade.get("ProdutoLocal") or []):
        try:
            tot += int(pl.get("EstoqueDisponivel") or 0)
        except Exception:
            pass
    return tot


def _extract_page(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for prod in (items or []):
        nome = prod.get("Nome") or ""
        prod_id = prod.get("Id")
        for g in (prod.get("ProdutoGrade") or []):
            sku = str(g.get("Sku") or g.get("Id") or "").strip()
            if not sku:
                continue
            estoque_total = _sum_local_stock(g)
            out.append({
                "sku": sku,
                "nome": nome,
                "estoque_total": estoque_total,
                "imagem_url": getattr(config, "rein_image_url", lambda s: f"")[sku] if False else (
                    getattr(config, "rein_image_url")(sku) if hasattr(config, "rein_image_url") else ""
                ),
                "produto_id": prod_id,
                "grade_id": g.get("Id"),
                "locais_rein": g.get("ProdutoLocal") or [],
            })
    return out


def _fetch_page(page: int) -> Tuple[List[Dict[str, Any]], int]:
    t0 = time.perf_counter()
    try:
        # seu tenant aceita "page=1" (vide print que você mandou)
        resp = _get(EP_LIST, params={"page": page})
        data = resp.json() or {}
        items = (data.get("data") or {}).get("items") or []
        rows = _extract_page(items)
        return rows, len(items)
    except requests.HTTPError as e:
        preview = ""
        try:
            preview = (resp.text or "")[:400]
        except Exception:
            pass
        raise RuntimeError(f"REIN HTTP {getattr(resp,'status_code', '?')} na página {page}: {preview}") from e
    except Exception as e:
        raise RuntimeError(f"Erro ao obter página {page} do REIN: {e}") from e
    finally:
        elapsed = time.perf_counter() - t0
        if elapsed < RATE_WAIT:
            time.sleep(RATE_WAIT - elapsed)


def _index_by_sku(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sku = r["sku"]
        if sku in idx:
            idx[sku]["estoque_total"] += int(r.get("estoque_total") or 0)
        else:
            idx[sku] = {
                "sku": sku,
                "nome": r.get("nome"),
                "estoque_total": int(r.get("estoque_total") or 0),
                "imagem_url": r.get("imagem_url"),
                "produto_id": r.get("produto_id"),
                "grade_id": r.get("grade_id"),
                "locais_rein": r.get("locais_rein") or [],
            }
    return idx


def _load_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_FILE):
        return {"generated_at": _now_iso(), "items": {}}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"generated_at": _now_iso(), "items": {}}


def _save_cache(items_by_sku: Dict[str, Dict[str, Any]]) -> None:
    payload = {"generated_at": _now_iso(), "items": items_by_sku}
    tmp = CACHE_FILE + "._tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CACHE_FILE)


# -------- APIs públicas (usar no app.py) --------
def atualizar_cache(mode: str = "diff") -> Dict[str, Any]:
    """
    mode:
      - "full": reescreve o cache com um snapshot completo.
      - "diff" (default): calcula diferenças vs cache anterior e salva novo snapshot.
    Retorna {"items":[...], "summary":{...}}
    """
    page = 1
    all_rows: List[Dict[str, Any]] = []

    while True:
        rows, count = _fetch_page(page)
        all_rows.extend(rows)
        if count < PAGE_SIZE:
            break
        page += 1

    new_snapshot = _index_by_sku(all_rows)

    old = _load_cache().get("items") or {}
    new_count = sum(1 for s in new_snapshot.keys() if s not in old)
    removed_count = sum(1 for s in old.keys() if s not in new_snapshot)
    updated_count = 0
    for s, r in new_snapshot.items():
        if s in old:
            if int(old[s].get("estoque_total") or 0) != int(r.get("estoque_total") or 0) \
               or (old[s].get("nome") or "") != (r.get("nome") or ""):
                updated_count += 1

    # salva (tanto no full quanto no diff)
    _save_cache(new_snapshot)

    items = list(new_snapshot.values())
    items.sort(key=lambda x: (x.get("nome") or "", x.get("sku") or ""))

    return {
        "items": items,
        "summary": {
            "mode": mode,
            "new": new_count,
            "updated": updated_count,
            "removed": removed_count,
            "total_skus": len(items),
            "generated_at": _now_iso()
        }
    }


def listar_cache() -> List[Dict[str, Any]]:
    c = _load_cache()
    items = list((c.get("items") or {}).values())
    items.sort(key=lambda x: (x.get("nome") or "", x.get("sku") or ""))
    return items
