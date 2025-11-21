# -*- coding: utf-8 -*-
"""
- Busca paginada na REIN (até a última página).
- Mantém cache local para atualização incremental.
- NÃO altera localizações: só espelha estoque total por SKU.
- Expõe:
    listar_cache() -> List[dict]
    atualizar_cache() -> dict {"items":[...], "diff": {...}}
"""
from __future__ import annotations
from typing import Any, Dict, List
import json
from datetime import datetime, timezone
import config
from pathlib import Path
from rein_client import listar_produtos_paginado

CACHE_FILE = config.DIR_CACHE / "rein_stock_cache.json"

def _json_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def _load_cache() -> Dict[str, Any]:
    if not Path(CACHE_FILE).exists():
        return {"generated_at": _json_now(), "items": {}}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"generated_at": _json_now(), "items": {}}

def _save_cache(payload: Dict[str, Any]) -> None:
    payload["generated_at"] = _json_now()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def _index_by_sku(lista: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for it in lista:
        sku = str(it.get("sku") or "").strip()
        if not sku:
            continue
        # Só mantemos os campos necessários para a página
        idx[sku] = {
            "sku": sku,
            "nome": it.get("nome"),
            "ncm": it.get("ncm"),
            "estoque_total": int(it.get("estoque_total") or 0),
            "imagem_url": it.get("imagem_url"),
            "produto_id": it.get("produto_id"),
            "grade_id": it.get("grade_id"),
            # Guardamos os locais crus – não alteramos
            "locais_rein": it.get("locais_rein") or [],
        }
    return idx

def atualizar_cache() -> Dict[str, Any]:
    """
    Baixa TODO o estoque da REIN (paginado), grava no cache e
    retorna:
      {
        "items": [lista final ordenada],
        "diff": {"new": X, "updated": Y, "removed": Z, "total_skus": N, "generated_at": "..."}
      }
    """
    full = listar_produtos_paginado()
    novo_idx = _index_by_sku(full)

    cache = _load_cache()
    old_idx = cache.get("items") or {}

    new, upd, rem = 0, 0, 0

    # novos/atualizados
    for sku, novo in novo_idx.items():
        antigo = old_idx.get(sku)
        if not antigo:
            new += 1
        elif (
            int(novo.get("estoque_total") or 0) != int(antigo.get("estoque_total") or 0)
            or (novo.get("nome") or "") != (antigo.get("nome") or "")
        ):
            upd += 1
        old_idx[sku] = novo

    # removidos
    for sku in list(old_idx.keys()):
        if sku not in novo_idx:
            rem += 1
            old_idx.pop(sku, None)

    # persistir
    _save_cache({"items": old_idx})

    # lista ordenada para devolver à página
    items = list(old_idx.values())
    items.sort(key=lambda x: (x.get("nome") or "", x.get("sku") or ""))

    return {
        "items": items,
        "diff": {
            "new": new,
            "updated": upd,
            "removed": rem,
            "total_skus": len(items),
            "generated_at": _json_now(),
        },
    }

def listar_cache() -> List[Dict[str, Any]]:
    """Retorna a lista atual do cache (sem chamar a REIN)."""
    cache = _load_cache()
    items = list((cache.get("items") or {}).values())
    items.sort(key=lambda x: (x.get("nome") or "", x.get("sku") or ""))
    return items
