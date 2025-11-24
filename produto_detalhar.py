# -*- coding: utf-8 -*-
from typing import Dict, Any
import requests
import config

CDN_BASE = "https://cdn.rein.net.br/app/core/pegdobrasil/6.5.4/publico/imagem/produto/"

def detalhar_produto(produto_id: int) -> Dict[str, Any]:
    """
    Busca detalhe completo do produto e retorna:
    - SKU
    - Nome
    - Categoria
    - Descrição
    - Imagens da grade
    - Preços
    - Peso e dimensões
    """

    url = f"{config.REIN_BASE}/api/v1/produto/{produto_id}"
    resp = requests.get(url, headers=config.rein_headers("/api/v1/produto"), timeout=60)

    try:
        resp.raise_for_status()
    except:
        return {"erro": True}

    data = resp.json() or {}

    # produto raiz
    nome_produto = data.get("Nome", "")
    descricao = data.get("Descricao", "")
    categoria = (data.get("Categoria") or {}).get("Nome", "")

    produto_grades = data.get("ProdutoGrade") or []

    imagens_final = []
    primeira_imagem = None

    # percorre grades
    for g in produto_grades:
        sku = g.get("Sku")
        peso = g.get("PesoLiquido") or "-"
        altura = g.get("Altura") or "-"
        largura = g.get("Largura") or "-"
        comprimento = g.get("Comprimento") or "-"
        ncm = g.get("Ncm") or "-"

        imgs = g.get("ProdutoImagem") or []
        if imgs:
            # ordem correta
            imgs_sorted = sorted(imgs, key=lambda x: int(
                x.get("OrdemExibicao") or x.get("intOrdemExibicao") or 0
            ))

            # adiciona todas as imagens dessa grade
            for im in imgs_sorted:
                nome_arq = im.get("NomeImagem") or im.get("strNomeArquivo")
                if nome_arq:
                    url_img = CDN_BASE + nome_arq
                    imagens_final.append(url_img)
                    if not primeira_imagem:
                        primeira_imagem = url_img

        # pega preços
        preco_atacado = 0
        preco_varejo = 0
        margens = g.get("ProdutoMargem") or []
        for m in margens:
            tabela = ((m.get("TabelaPreco") or {}).get("Nome") or "").upper()
            preco = m.get("PrecoComDesconto") or m.get("Preco") or 0
            try:
                preco = float(preco)
            except:
                preco = 0

            if "ATACADO" in tabela:
                preco_atacado = preco
            if "VAREJO" in tabela:
                preco_varejo = preco

        # dados completos para o modal
        return {
            "erro": False,
            "sku": sku,
            "nome": nome_produto,
            "categoria": categoria,
            "descricao": descricao,
            "ncm": ncm,
            "peso": peso,
            "altura": altura,
            "largura": largura,
            "comprimento": comprimento,
            "preco_atacado": preco_atacado,
            "preco_varejo": preco_varejo,
            "imagem_principal": primeira_imagem,
            "imagens": imagens_final,
        }

    return {"erro": True}
