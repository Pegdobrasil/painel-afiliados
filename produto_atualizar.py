# -*- coding: utf-8 -*-
"""
Funções de listagem de produtos da REIN para o painel.

Este módulo faz apenas chamadas GET para a API da REIN.
Foi escrito para não depender obrigatoriamente do pacote "requests":
- Se "requests" estiver instalado, ele é usado normalmente.
- Se não estiver, é usado urllib da biblioteca padrão.
"""
from typing import List, Dict, Any
import math
import json
from urllib import request as urlrequest, parse as urlparse

# "requests" é opcional
try:
    import requests as _requests
except ModuleNotFoundError:  # Railway sem requests instalado
    class _SimpleResponse:
        def __init__(self, resp):
            self._resp = resp

        def raise_for_status(self):
            code = self._resp.getcode()
            if code >= 400:
                raise Exception(f"HTTP {code}")

        def json(self):
            data = self._resp.read().decode("utf-8") or ""
            if not data.strip():
                return None
            return json.loads(data)

    class _SimpleRequests:
        def get(self, url, headers=None, params=None, timeout=None):
            if params:
                qs = urlparse.urlencode(params)
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}{qs}"
            req = urlrequest.Request(url, headers=headers or {}, method="GET")
            resp = urlrequest.urlopen(req, timeout=timeout or 60)
            return _SimpleResponse(resp)

    requests = _SimpleRequests()
else:
    requests = _requests

import config

EP_LIST = "/api/v1/produto"


def _sum_estoque(locais: List[Dict[str, Any]]) -> float:
    tot = 0.0
    for l in (locais or []):
        try:
            tot += float(l.get("EstoqueDisponivel") or 0)
        except Exception:
            pass
    return tot


def _precos_por_tabela(produto_grade: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for m in (produto_grade.get("ProdutoMargem") or []):
        tab = ((m.get("TabelaPreco") or {}).get("Nome") or "").upper()
        preco = float(m.get("Preco") or m.get("PrecoComDesconto") or 0)
        if tab and tab not in out:
            out[tab] = preco
    return {
        "ATACADO": out.get("TABELA ATACADO") or out.get("ATACADO") or 0.0,
        "VAREJO": out.get("TABELA VAREJO") or out.get("VAREJO") or 0.0,
    }


def listar_produtos(termo: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Busca produtos na REIN com paginação.
    Usa apenas GET /api/v1/produto.
    """
    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 10))

    url = f"{config.REIN_BASE}{EP_LIST}"
    resp = requests.get(
        url,
        headers=config.rein_headers(EP_LIST),
        params={"page": page, "termo": termo},
        timeout=60,
    )
    resp.raise_for_status()
    data = (resp.json() or {}).get("data") or {}

    items = data.get("items") or []

    pag = data.get("paginacao") or {}
    total = (
        pag.get("totalItems")
        or pag.get("total")
        or data.get("total")
        or len(items)
    )
    try:
        total = int(total)
    except Exception:
        total = len(items)

    total_pages = max(1, math.ceil(total / per_page))

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


def preparar_resultados(
    items: List[Dict[str, Any]],
    termo: str,
    sku_exato: bool = False,
    status: str = "ativos",  # "ativos" | "inativos" | "todos"
) -> List[Dict[str, Any]]:
    """
    Achata por grade (SKU) e monta linhas tratadas para o painel.
    """
    termo = (termo or "").strip()
    linhas: List[Dict[str, Any]] = []

    for p in items:
        ativo = p.get("DataInativado") in (None, "", "null")
        if status == "ativos" and not ativo:
            continue
        if status == "inativos" and ativo:
            continue

        for g in (p.get("ProdutoGrade") or []):
            sku = str(g.get("Sku") or "")
            if sku_exato and termo and sku != termo:
                continue

            estoque = _sum_estoque(g.get("ProdutoLocal") or [])
            precos = _precos_por_tabela(g)

            linhas.append(
                {
                    "produto_id": p.get("Id"),
                    "grade_id": g.get("Id"),
                    "sku": sku,
                    "nome": p.get("Nome") or "",
                    "ncm": p.get("Ncm"),
                    "estoque": estoque,
                    "ativo": bool(ativo),
                    "preco_atacado": precos.get("ATACADO", 0.0),
                    "preco_varejo": precos.get("VAREJO", 0.0),
                }
            )

    # ordena por: ativo desc, estoque desc, sku asc
    linhas.sort(key=lambda x: (-(x["ativo"]), -x["estoque"], x["sku"]))
    return linhas
