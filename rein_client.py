# -*- coding: utf-8 -*-
import requests
from typing import Any, Dict, List, Optional, Tuple
import config

session = requests.Session()

EP_LIST = "/api/v1/produto"         # GET ?page=1&termo={sku}
# ============================================================
# PESSOA (CLIENTE / AFILIADO) NA REIN
# ============================================================
from typing import Any, Dict, List, Optional


def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Helper genérico para lidar com respostas paginadas da REIN."""
    if not data:
        return []
    d = data.get("data")
    if isinstance(d, dict) and "items" in d:
        return d.get("items") or []
    if isinstance(d, list):
        return d
    return []


def buscar_pessoa_por_documento(cpf_cnpj: str, tipo_pessoa: str) -> Optional[Dict[str, Any]]:
    """
    Busca uma pessoa na REIN pelo CPF/CNPJ.

    tipo_pessoa: 'PF' ou 'PJ'
    """
    params = {
        "tipoPessoa": (tipo_pessoa or "").upper(),  # PF ou PJ
        "status": "ativo",
        "tipoCliente": "cliente",
        "page": 1,
        "termo": cpf_cnpj,
    }
    resp = _get("/api/v1/pessoa", params=params)
    resp.raise_for_status()
    items = _extract_items(resp.json())
    return items[0] if items else None


def _put(path: str, json: Optional[Dict[str, Any]] = None, **kw):
    url = f"{config.REIN_BASE}{path}"
    return session.put(
        url,
        headers=config.rein_headers(path),
        json=json,
        timeout=60,
        **kw,
    )


def criar_pessoa_na_rein(payload: Dict[str, Any]) -> int:
    """Cria uma nova pessoa na REIN via PUT /api/v1/pessoa e retorna o ID."""
    resp = _put("/api/v1/pessoa", json=payload)
    resp.raise_for_status()
    data = resp.json() or {}
    pessoa_id = data.get("intId") or data.get("Id") or data.get("id")
    if not pessoa_id:
        raise RuntimeError(f"Não foi possível obter o ID da pessoa criada: {data}")
    return int(pessoa_id)


def montar_payload_pessoa_para_cadastro(usuario_data: Dict[str, Any]) -> Dict[str, Any]:
    """Monta o JSON mínimo para cadastrar Pessoa na Rein usando o cadastro de afiliado."""
    cpf_cnpj = usuario_data.get("cpf_cnpj")
    tipo_pessoa = (usuario_data.get("tipo_pessoa") or "").upper()
    nome = usuario_data.get("nome") or ""

    is_pf = tipo_pessoa == "PF"

    payload: Dict[str, Any] = {
        "TipoPessoa": tipo_pessoa,  # PF ou PJ
        "Nome": nome,
        "RazaoSocial": None if is_pf else nome,
        "Cpf": cpf_cnpj if is_pf else None,
        "Cnpj": cpf_cnpj if not is_pf else None,
        "TipoCliente": "cliente",
        "Status": 1,
        "CadastroGeralEmail": [],
        "CadastroGeralEndereco": [],
        "Observacao": "Cadastro criado automaticamente pelo painel de afiliados.",
    }

    return payload


def get_or_create_pessoa_rein(usuario_data: Dict[str, Any]) -> int:
    """Garante que exista uma Pessoa na REIN para este afiliado e retorna o ID."""
    tipo_pessoa = (usuario_data.get("tipo_pessoa") or "").upper()
    cpf_cnpj = usuario_data.get("cpf_cnpj") or ""

    existente = buscar_pessoa_por_documento(cpf_cnpj=cpf_cnpj, tipo_pessoa=tipo_pessoa)
    if existente:
        pessoa_id = existente.get("Id") or existente.get("intId") or existente.get("id")
        if not pessoa_id:
            raise RuntimeError(f"Pessoa encontrada na REIN sem ID claro: {existente}")
        return int(pessoa_id)

    payload = montar_payload_pessoa_para_cadastro(usuario_data)
    return criar_pessoa_na_rein(payload)


# ============================================================
# PEDIDOS NA REIN (LISTAGEM POR CLIENTE / AFILIADO)
# ============================================================

def listar_pedidos_por_cliente(rein_pessoa_id: int) -> List[Dict[str, Any]]:
    """Lista pedidos na REIN filtrando pelo IdCliente (Pessoa).

    Retorna a lista crua de pedidos vinda da API.
    """
    params = {
        "IdCliente": rein_pessoa_id,
        "page": 1,
    }
    resp = _get("/api/v1/pedido", params=params)
    resp.raise_for_status()
    data = resp.json() or {}
    return _extract_items(data)



def _get(path: str, **kw):
    url = f"{config.REIN_BASE}{path}"
    return session.get(url, headers=config.rein_headers(path), timeout=60, **kw)

def _parse_locais(grade: Dict[str, Any]) -> List[Dict[str, Any]]:
    locais = []
    for l in (grade.get("ProdutoLocal") or []):
        lobj = l.get("Local") or {}
        locais.append({
            "id": lobj.get("Id") or l.get("LocalId"),
            "nome": lobj.get("Nome") or "Sem nome",
            "saldo": float(l.get("EstoqueDisponivel") or l.get("Saldo") or 0),
            "margens": [
                {
                    "tabela": (m.get("TabelaPreco") or {}).get("Nome") or "",
                    "tabela_id": (m.get("TabelaPreco") or {}).get("Id"),
                    "preco_desc": float(m.get("PrecoComDesconto") or m.get("Preco") or 0),
                    "preco": float(m.get("Preco") or m.get("PrecoComDesconto") or 0),
                } for m in (l.get("ProdutoMargem") or [])
            ],
            "cadastro": (l.get("CadastroGeralEstoque") or {})
        })
    return locais

def _agregar_precos_por_tabela(locais: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolida um preço por tabela (primeiro encontrado).
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for l in locais:
        for m in l.get("margens", []):
            nome = m.get("tabela") or ""
            if nome and nome not in seen:
                seen[nome] = {"tabela": nome, "preco": m["preco"], "preco_desc": m["preco_desc"]}
    return list(seen.values())

def _match_grade_by_sku(items: List[Dict[str, Any]], sku: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Retorna (produto_item, grade) cujo ProdutoGrade.Sku == sku.
    """
    for it in items:
        for g in (it.get("ProdutoGrade") or []):
            if str(g.get("Sku")) == str(sku):
                return it, g
    return None

def buscar_por_sku_duas_etapas(sku: str) -> Optional[Dict[str, Any]]:
    """
    1) Lista por termo (token do /api/v1/produto)
    2) Detalha por ID (token do /api/v1/produto/{id})
    Sempre filtra exatamente pelo ProdutoGrade.Sku == sku.
    """
    # Etapa 1: listar
    r1 = _get(EP_LIST, params={"page": 1, "termo": sku})
    r1.raise_for_status()
    items = (r1.json().get("data") or {}).get("items", [])
    hit = _match_grade_by_sku(items, sku)
    if not hit:
        return None
    item, grade = hit
    prod_id = item.get("Id")
    nome = item.get("Nome") or "Sem nome"
    ncm = item.get("Ncm")
    locais_snapshot = _parse_locais(grade)

    # Etapa 2: detalhe por ID
    ep_id = f"/api/v1/produto/{prod_id}"
    r2 = _get(ep_id)
    r2.raise_for_status()
    det = (r2.json() or {}).get("data") or {}

    # tenta achar a mesma grade dentro do detalhe (para pegar locais/preços atualizados)
    grade2 = None
    for g in (det.get("ProdutoGrade") or []):
        if str(g.get("Sku")) == str(sku):
            grade2 = g
            break
    if grade2:
        locais = _parse_locais(grade2)
    else:
        locais = locais_snapshot

    precos_por_tabela = _agregar_precos_por_tabela(locais)
    img = config.rein_image_url(sku)

    return {
        "produto_id": prod_id,
        "sku": str(sku),
        "grade_id": (grade2 or grade).get("Id"),
        "nome": nome,
        "ncm": ncm,
        "imagem_url": img,
        "locais_rein": locais,
        "precos_tabela": precos_por_tabela,
        "produto_raw": det or item,  # prioriza o detalhe
        "grade_raw": grade2 or grade
    }




