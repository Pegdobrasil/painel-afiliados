# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
import math
import requests
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
    """
    Lê ProdutoMargem da grade e devolve um dicionário com:
    - ATACADO
    - VAREJO (preço recomendado)
    """
    out: Dict[str, float] = {}

    for m in (produto_grade.get("ProdutoMargem") or []):
        tab = ((m.get("TabelaPreco") or {}).get("Nome") or "").upper()
        # a REIN costuma mandar PrecoComDesconto
        preco = float(m.get("PrecoComDesconto") or m.get("Preco") or 0)
        if tab and tab not in out:
            out[tab] = preco

    return {
        "ATACADO": out.get("TABELA ATACADO") or out.get("ATACADO") or 0.0,
        "VAREJO": out.get("TABELA VAREJO") or out.get("VAREJO") or 0.0,
    }


def _imagem_capa(produto_grade: Dict[str, Any]) -> Optional[str]:
    """
    Pega a primeira imagem da grade (pela ordem de exibição)
    e devolve como data URL (pronta pra usar no <img src="...">).
    """
    imagens = produto_grade.get("ProdutoImagem") or []
    if not imagens:
        return None

    try:
        imagens = sorted(
            imagens,
            key=lambda im: int(im.get("intOrdemExibicao") or 0),
        )
    except Exception:
        pass

    img = imagens[0]
    binario = (img.get("BinarioArquivo") or "").strip()
    tipo = (img.get("strTipoArquivo") or "image/jpeg").strip().lower()

    if not binario:
        return None
    if not tipo.startswith("image/"):
        tipo = "image/jpeg"

    return f"data:{tipo};base64,{binario}"


def listar_produtos(termo: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Busca produtos na REIN com paginação por 'page'.
    Não envia 'limit': o per_page é usado só para calcular total_pages.
    Retorna: { items, total, page, per_page, total_pages }
    """
    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 10))

    url = f"{config.REIN_BASE}{EP_LIST}"
    r = requests.get(
        url,
        headers=config.rein_headers(EP_LIST),
        params={"page": page, "termo": termo},
        timeout=60,
    )
    r.raise_for_status()
    data = (r.json() or {}).get("data") or {}

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
    Flatteia os itens por grade e aplica filtros.
    Retorna linhas com:
    produto_id, grade_id, sku, nome, ncm, estoque, ativo,
    preco_atacado, preco_varejo, imagem_capa.
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
