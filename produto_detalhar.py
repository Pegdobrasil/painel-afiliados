# -*- coding: utf-8 -*-
import requests, config

def detalhar_produto(produto_id: int) -> dict:
    """Retorna o detalhe completo de um produto pelo ID."""
    ep = f"/api/v1/produto/{produto_id}"
    url = f"{config.REIN_BASE}{ep}"
    r = requests.get(url, headers=config.rein_headers(ep), timeout=60)
    r.raise_for_status()
    return (r.json() or {}).get("data") or {}
