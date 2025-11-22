# -*- coding: utf-8 -*-
from typing import List, Dict, Any
import math
import requests
import config

EP_LIST = "/api/v1/produto"

# CDN base fixa para montar URL das imagens das grades
CDN_BASE = "https://cdn.rein.net.br/app/core/pegdobrasil/6.5.4/publico/imagem/produto/"


def _sum_estoque(locais: List[Dict[str, Any]]) -> float:
    """
    Soma EstoqueDisponivel de todos os locais da grade.
    """
    total = 0.0
    for local in locais or []:
        try:
            total += float(local.get("EstoqueDisponivel") or 0)
        except Exception:
            pass
    return total


def _precos_por_tabela(grade: Dict[str, Any]) -> Dict[str, float]:
    """
    Lê ProdutoMargem da grade e retorna:
      - ATACADO: preço da tabela atacado
      - VAREJO: preço da tabela varejo (preço recomendado)
    """
    out: Dict[str, float] = {}

    for margem in (grade.get("ProdutoMargem") or []):
        tabela = ((margem.get("TabelaPreco") or {}).get("Nome") or "").upper()
        preco = margem.get("PrecoComDesconto")
        if preco is None:
            preco = margem.get("Preco")
        try:
            preco = float(preco or 0)
        except Exception:
            continue

        if tabela and tabela not in out:
            out[tabela] = preco

    return {
        "ATACADO": out.get("TABELA ATACADO") or out.get("ATACADO") or 0.0,
        "VAREJO": out.get("TABELA VAREJO") or out.get("VAREJO") or 0.0,
    }


def _imagem_capa(grade: Dict[str, Any]) -> str | None:
    """
    Monta a URL da primeira imagem da grade usando ProdutoImagem.NomeImagem.
    """
    imagens = grade.get("ProdutoImagem") or []
    if not imagens:
        return None

    def _ordem(img: Dict[str, Any]) -> int:
        try:
            return int(
                img.get("intOrdemExibicao")
                or img.get("OrdemExibicao")
                or 0
            )
        except Exception:
            return 0

    imagens = sorted(imagens, key=_ordem)
    img0 = imagens[0]

    nome = (
        img0.get("NomeImagem")
        or img0.get("strNomeArquivo")
        or img0.get("NomeArquivo")
        or ""
    )
    nome = str(nome).strip().lstrip("/")
    if not nome:
        return None

    return f"{CDN_BASE}{nome}"


def listar_produtos(termo: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Consulta a REIN (endpoint de listagem de produtos) usando o termo informado.
    Retorna os dados crus da API + info de paginação.
    """
    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 10))

    url = f"{config.REIN_BASE}{EP_LIST}"
    params = {"page": page, "termo": termo}
    resp = requests.get(
        url,
        headers=config.rein_headers(EP_LIST),
        params=params,
        timeout=60,
    )
    resp.raise_for_status()

    payload = (resp.json() or {}).get("data") or {}
    items = payload.get("items") or []

    pag = payload.get("paginacao") or {}
    total = (
        pag.get("totalItems")
        or pag.get("total")
        or payload.get("total")
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
    Converte a resposta da REIN em linhas "achatadas" por grade,
    no formato esperado pelo painel.

    Cada linha contém:
      - produto_id
      - grade_id
      - sku
      - nome
      - ncm
      - estoque
      - ativo
      - preco_atacado
      - preco_varejo
      - imagem_capa
    """
    termo = (termo or "").strip()
    linhas: List[Dict[str, Any]] = []

    for p in items or []:
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
            imagem_capa = _imagem_capa(g)

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
                    "imagem_capa": imagem_capa,
                }
            )

    # ordena por: ativo desc, estoque desc, sku asc
    linhas.sort(key=lambda x: (-(x["ativo"]), -x["estoque"], x["sku"]))
    return linhas
