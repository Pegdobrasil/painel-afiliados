# -*- coding: utf-8 -*-
from typing import Any, Dict

import requests
import config


def detalhar_produto(produto_id: int) -> Dict[str, Any]:
    """
    Busca o detalhe do produto na REIN e retorna o JSON CRU,
    mantendo a estrutura original com ProdutoGrade, ProdutoImagem etc.

    Isso é importante porque:
      - produto_listar.py usa ProdutoGrade/ProdutoImagem para montar imagem_capa
      - o frontend (painel.js) usa normalizarDetalheRein() para achatar os dados
    """
    endpoint = f"/api/v1/produto/{produto_id}"
    url = f"{config.REIN_BASE}{endpoint}"

    resp = requests.get(
        url,
        headers=config.rein_headers(endpoint),
        timeout=60,
    )
    resp.raise_for_status()

    data = resp.json() or {}

    # Alguns endpoints da REIN retornam {"data": {...}}
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]

    return data
