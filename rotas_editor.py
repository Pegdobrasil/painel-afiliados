# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, jsonify
from .produto_listar import listar_produtos, preparar_resultados
from .produto_detalhar import detalhar_produto
from .produto_atualizar import atualizar_produto
from .produto_imagem import (
    upload_b64,
    remove_image,
    reorder_image,
    build_rein_image_payload,  # para normalizar imagens no atualizar completo
)

# Nome do blueprint precisa bater com os templates (url_for('produto_editor_bp.produto_editor', ...))
bp_produto = Blueprint("produto_editor_bp", __name__, template_folder="templates")

# === Página principal ===
@bp_produto.route("/produto_editor")
def produto_editor():
    termo = (request.args.get("termo") or "").strip()
    sku_exato = request.args.get("exact", "0") in ("1", "true", "on", "True")
    status = (request.args.get("status") or "todos").lower()

    # paginação
    try:
        page = int(request.args.get("page", 1))
    except Exception:
        page = 1

    limit = request.args.get("limit", "10")
    limit_custom = (request.args.get("limit_custom") or "").strip()
    if limit == "custom" and limit_custom:
        try:
            per_page = max(1, int(limit_custom))
        except Exception:
            per_page = 10
    else:
        try:
            per_page = max(1, int(limit))
        except Exception:
            per_page = 10

    # controla apenas o autoload visual das imagens no front
    autoimg = request.args.get("autoimg", "1") in ("1", "true", "on", "True")

    linhas = []
    meta = {"total": 0, "page": page, "per_page": per_page, "total_pages": 1}

    if termo:
        # NÃO passar kwargs inesperados para listar_produtos (evita TypeError)
        res = listar_produtos(termo, page=page, per_page=per_page)
        itens = res.get("items") or res.get("data") or []
        # Filtros e modo exato feitos aqui para manter a compatibilidade antiga
        linhas = preparar_resultados(itens, termo, sku_exato=sku_exato, status=status)
        meta = {
            "total": int(res.get("total", len(itens))),
            "page": int(res.get("page", page)),
            "per_page": per_page,
            "total_pages": int(res.get("total_pages", 1)),
        }

    return render_template(
        "produto_editor.html",
        termo=termo,
        sku_exato=sku_exato,
        status=status,
        page=meta["page"],
        per_page=meta["per_page"],
        total=meta["total"],
        total_pages=meta["total_pages"],
        limit=str(limit),
        limit_custom=str(limit_custom or ""),
        autoimg=autoimg,
        linhas=linhas,
    )

# === GET Detalhe de produto ===
@bp_produto.route("/produto_editor/detalhe/<int:produto_id>")
def rota_detalhe(produto_id):
    try:
        return jsonify(detalhar_produto(produto_id))
    except Exception as e:
        return jsonify({"ok": False, "msg": f"erro ao detalhar: {e}"}), 500

# === POST Atualizar produto (envia o body completo de volta à REIN) ===
@bp_produto.route("/produto_editor/atualizar/<int:produto_id>", methods=["POST"])
def rota_atualizar(produto_id):
    """
    Recebe o corpo completo do produto (detalhe) e antes de enviar
    normaliza ProdutoGrade[].ProdutoImagem para o padrão str*/int* da REIN.
    """
    body = request.get_json(force=True, silent=True) or {}
    grades = body.get("ProdutoGrade") or []
    for g in grades:
        imgs = g.get("ProdutoImagem") or []
        g["ProdutoImagem"] = build_rein_image_payload(imgs)
    return jsonify(atualizar_produto(produto_id, body))

# === IMAGENS (upload Base64 direto) ===
@bp_produto.post("/produto_editor/grade/<int:produto_id>/<int:grade_id>/imagem_b64")
def rota_imagem_b64(produto_id, grade_id):
    sku = request.form.get("sku", "").strip() or request.args.get("sku", "").strip()
    f = request.files.get("file")
    return upload_b64(produto_id, grade_id, sku, f)

@bp_produto.delete("/produto_editor/grade/<int:produto_id>/<int:grade_id>/imagem")
def rota_imagem_delete(produto_id, grade_id):
    sku = request.args.get("sku", "").strip()
    nome = request.args.get("nome", "").strip()
    return remove_image(produto_id, grade_id, sku, nome)

@bp_produto.post("/produto_editor/grade/<int:produto_id>/<int:grade_id>/reordenar")
def rota_imagem_reordenar(produto_id, grade_id):
    data = request.get_json(force=True, silent=True) or {}
    sku = (data.get("sku") or "").strip()
    nome = (data.get("nome") or "").strip()
    direcao = data.get("direcao") or ""
    return reorder_image(produto_id, grade_id, sku, nome, direcao)

# === Atualizar dados rápidos (Nome + Frete) — preserva fluxo antigo ===
@bp_produto.post("/produto_editor/grade/<int:produto_id>/<int:grade_id>/dados")
def rota_dados_rapidos(produto_id, grade_id):
    body = request.get_json(force=True, silent=True) or {}
    det = detalhar_produto(produto_id)

    if "Nome" in body and body.get("Nome") is not None:
        det["Nome"] = body.get("Nome") or det.get("Nome")

    for g in (det.get("ProdutoGrade") or []):
        gid = g.get("Id") or g.get("intId")
        if str(gid) != str(grade_id):
            continue
        for k in ["PesoLiquido", "PesoBruto", "Largura", "Altura", "Comprimento"]:
            if k in body and body[k] is not None:
                try:
                    g[k] = float(body[k])
                except Exception:
                    pass
        break

    return atualizar_produto(produto_id, det)
