# -*- coding: utf-8 -*-
"""
Utilitários de IMAGENS conforme manual da REIN.

- Reordenar: usar apenas intOrdemExibicao; imagens existentes devem ir com intId.
- Novas imagens: NÃO enviar intId; enviar strBinarioArquivo (base64), strNomeArquivo e strTipoArquivo.
- Campos de imagem sempre em str*/int*.
"""

from typing import List, Dict, Any, Optional
import base64
from .produto_detalhar import detalhar_produto
from .produto_atualizar import atualizar_produto

CDN_BASE = "https://cdn.rein.net.br/app/core/pegdobrasil/6.5.4/publico/imagem/produto/"

def _name_for(sku: str, pos: int) -> str:
    sku = str(sku).strip()
    return f"{sku}.jpg" if pos == 1 else f"{sku}-{pos}.jpg"

def _get(d: Dict[str, Any], keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def _normalize_from_get(imgs_get: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normaliza a lista vinda do detalhe para um shape interno homogêneo.
    """
    out: List[Dict[str, Any]] = []
    for it in (imgs_get or []):
        nome = _get(it, ["strNomeArquivo", "NomeImagem", "NomeArquivo"])
        ordem = int(_get(it, ["intOrdemExibicao", "OrdemExibicao"], 0) or 0)
        _id = _get(it, ["intId", "Id", "id"])
        if not nome:
            continue
        out.append({
            "id": _id,
            "nome": nome,
            "ordem": ordem if ordem > 0 else 0,
            "b64": "",  # existente não tem b64
        })
    out.sort(key=lambda x: x["ordem"])
    # força 1..n
    for i, it in enumerate(out, 1):
        it["ordem"] = i
    return out

def build_rein_image_payload(imgs_any: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Converte uma lista heterogênea (vinda do front/JS) no payload estrito da REIN.
    """
    norm: List[Dict[str, Any]] = []
    for it in (imgs_any or []):
        norm.append({
            "id": _get(it, ["intId","Id","id"]),
            "nome": _get(it, ["strNomeArquivo","NomeArquivo","NomeImagem","nome"]),
            "ordem": int(_get(it, ["intOrdemExibicao","ordem","OrdemExibicao"], 0) or 0),
            "b64": _get(it, ["strBinarioArquivo","BinarioArquivo","base64","b64"]),
        })
    # filtra vazios
    norm = [n for n in norm if n["nome"]]
    # força ordem 1..n
    norm.sort(key=lambda x: x["ordem"])
    for i, n in enumerate(norm, 1):
        n["ordem"] = i

    out: List[Dict[str, Any]] = []
    for n in norm:
        o: Dict[str, Any] = {
            "strNomeArquivo": n["nome"],
            "intOrdemExibicao": n["ordem"],
            "strTipoArquivo": "image/jpeg",
        }
        if n["id"]:
            o["intId"] = int(n["id"])
        if n["b64"]:
            o["strBinarioArquivo"] = n["b64"]
            if "intId" in o:
                del o["intId"]
        out.append(o)
    return out

def upload_b64(produto_id: int, grade_id: int, sku: str, file_storage) -> Dict[str, Any]:
    """
    Recebe .jpg, converte para Base64, adiciona na grade e renomeia tudo
    para SKU + posição. Envia o detalhe atualizado para a REIN.
    """
    if not file_storage:
        return {"ok": False, "msg": "Arquivo ausente."}, 400

    fn = (file_storage.filename or "").lower()
    if not (fn.endswith(".jpg") or fn.endswith(".jpeg")):
        return {"ok": False, "msg": "Apenas JPG é permitido."}, 400

    det = detalhar_produto(produto_id)
    grades = det.get("ProdutoGrade") or []
    g = next((x for x in grades if str(_get(x, ["Id","intId"])) == str(grade_id)), None)
    if not g:
        return {"ok": False, "msg": "Grade não encontrada."}, 400

    imgs = _normalize_from_get(g.get("ProdutoImagem") or [])

    # Base64 da nova imagem
    raw = file_storage.read()
    b64 = base64.b64encode(raw).decode("ascii")

    # adiciona nova no fim
    imgs.append({"id": None, "nome": "", "ordem": len(imgs) + 1, "b64": b64})

    # renomeia por SKU + posição (1..n) e monta payload REIN
    for i, it in enumerate(imgs, 1):
        it["ordem"] = i
        it["nome"] = _name_for(sku, i)
    g["ProdutoImagem"] = build_rein_image_payload(imgs)

    return atualizar_produto(produto_id, det)

def remove_image(produto_id: int, grade_id: int, sku: str, nome_arquivo: str) -> Dict[str, Any]:
    det = detalhar_produto(produto_id)
    grades = det.get("ProdutoGrade") or []
    g = next((x for x in grades if str(_get(x, ["Id","intId"])) == str(grade_id)), None)
    if not g:
        return {"ok": False, "msg": "Grade não encontrada."}, 400

    imgs = _normalize_from_get(g.get("ProdutoImagem") or [])
    imgs = [i for i in imgs if (i["nome"] or "").lower() != (nome_arquivo or "").lower()]

    # renomeia e aplica
    for i, it in enumerate(imgs, 1):
        it["ordem"] = i
        it["nome"] = _name_for(sku, i)
    g["ProdutoImagem"] = build_rein_image_payload(imgs)

    return atualizar_produto(produto_id, det)

def reorder_image(produto_id: int, grade_id: int, sku: str, nome_arquivo: str, direcao: str) -> Dict[str, Any]:
    det = detalhar_produto(produto_id)
    grades = det.get("ProdutoGrade") or []
    g = next((x for x in grades if str(_get(x, ["Id","intId"])) == str(grade_id)), None)
    if not g:
        return {"ok": False, "msg": "Grade não encontrada."}, 400

    imgs = _normalize_from_get(g.get("ProdutoImagem") or [])
    idx = next((i for i, x in enumerate(imgs) if (x["nome"] or "").lower() == (nome_arquivo or "").lower()), -1)
    if idx < 0:
        return {"ok": False, "msg": "Imagem não encontrada."}, 400

    if direcao == "up" and idx > 0:
        imgs[idx - 1], imgs[idx] = imgs[idx], imgs[idx - 1]
    elif direcao == "down" and idx < len(imgs) - 1:
        imgs[idx + 1], imgs[idx] = imgs[idx], imgs[idx + 1]
    else:
        return {"ok": False, "msg": "Movimento inválido."}, 400

    # renomeia e aplica
    for i, it in enumerate(imgs, 1):
        it["ordem"] = i
        it["nome"] = _name_for(sku, i)
    g["ProdutoImagem"] = build_rein_image_payload(imgs)

    return atualizar_produto(produto_id, det)
