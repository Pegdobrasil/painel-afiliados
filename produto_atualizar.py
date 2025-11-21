# -*- coding: utf-8 -*-
import requests, config

def atualizar_produto(produto_id: int, body: dict) -> dict:
    """Atualiza dados de um produto na REIN."""
    ep = f"/api/v1/produto/{produto_id}"
    url = f"{config.REIN_BASE}{ep}"
    r = requests.post(url, json=body, headers=config.rein_headers(ep), timeout=90)
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text}
