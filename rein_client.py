# -*- coding: utf-8 -*-
import requests
from typing import Any, Dict, List, Optional, Tuple
import config

session = requests.Session()

EP_LIST = "/api/v1/produto"         # GET ?page=1&termo={sku}
EP_PESSOA = "/api/v1/pessoa"

def _put(path: str, **kw) -> requests.Response:
    """
    Wrapper para PUT na Rein usando o mesmo esquema de headers dos produtos.
    """
    url = f"{config.REIN_BASE}{path}"
    return session.put(url, headers=config.rein_headers(path), timeout=60, **kw)


def buscar_pessoa_por_documento(cpf_cnpj: str, tipo_pessoa: str) -> Optional[Dict[str, Any]]:
    """
    Consulta /api/v1/pessoa filtrando pelo CPF/CNPJ.
    tipo_pessoa: 'PF' ou 'PJ'
    Retorna o primeiro registro encontrado ou None.
    """
    path = "/api/v1/pessoa"
    params = {
        "page": 1,
        "termo": cpf_cnpj,
        # se no seu ERP precisar filtrar mais, pode ativar:
        # "tipoPessoa": tipo_pessoa,  # PF / PJ
        # "status": "ativo",
        # "tipoCliente": "cliente",
    }

    resp = _get(path, params=params)
    resp.raise_for_status()
    data = resp.json()

    # Segue a mesma lógica que você já usa em produtos: data -> items
    items = None
    if isinstance(data.get("data"), dict) and "items" in data["data"]:
        items = data["data"]["items"]
    else:
        items = data.get("data")

    if not items:
        return None

    return items[0]


def montar_payload_pessoa_para_cadastro(usuario_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monta o JSON mínimo para cadastrar Pessoa na Rein usando o que vem do form de afiliado.
    Aqui estamos mandando só o básico – dá pra enriquecer depois.
    """
    cpf_cnpj = usuario_data["cpf_cnpj"]
    tipo_pessoa = usuario_data["tipo_pessoa"].upper()  # 'PF' ou 'PJ'
    nome = usuario_data["nome"]

    is_pf = tipo_pessoa == "PF"

    payload: Dict[str, Any] = {
        "TipoPessoa": tipo_pessoa,          # PF ou PJ
        "Nome": nome,
        "RazaoSocial": None if is_pf else nome,
        "Cpf": cpf_cnpj if is_pf else None,
        "Cnpj": cpf_cnpj if not is_pf else None,
        "TipoCliente": "cliente",           # ajuste se no ERP for outro valor
        "Status": 1,                        # ativo
        "Observacao": "Cadastro criado automaticamente pelo painel de afiliados.",
    }

    # Se quiser já mandar e-mail e endereço depois, a gente ajusta aqui:
    # payload["CadastroGeralEmail"] = [...]
    # payload["CadastroGeralEndereco"] = [...]

    return payload


def criar_pessoa_na_rein(dados: Dict[str, Any]) -> int:
    """
    Cria uma nova pessoa na Rein via PUT /api/v1/pessoa.
    'dados' precisa seguir a estrutura básica do Example Value do PDF.
    Retorna o ID da pessoa criada.
    """
    path = "/api/v1/pessoa"
    resp = _put(path, json=dados)
    resp.raise_for_status()
    data = resp.json()

    pessoa_id = data.get("intId") or data.get("Id") or data.get("id")
    if not pessoa_id:
        raise RuntimeError(f"Não foi possível identificar o ID da pessoa criada na Rein: {data}")

    return int(pessoa_id)


def get_or_create_pessoa_rein(usuario_data: Dict[str, Any]) -> int:
    """
    Garante que exista uma Pessoa na Rein e devolve o ID.

    - Se já existir (busca pelo CPF/CNPJ), retorna o ID existente.
    - Se não existir, cria uma nova Pessoa e retorna o novo ID.
    """
    tipo_pessoa = usuario_data["tipo_pessoa"].upper()
    cpf_cnpj = usuario_data["cpf_cnpj"]

    existente = buscar_pessoa_por_documento(cpf_cnpj=cpf_cnpj, tipo_pessoa=tipo_pessoa)
    if existente:
        pessoa_id = (
            existente.get("Id")
            or existente.get("intId")
            or existente.get("id")
        )
        if not pessoa_id:
            raise RuntimeError(f"Pessoa encontrada na Rein, mas sem ID claro: {existente}")
        return int(pessoa_id)

    # Não achou: cria nova Pessoa
    payload = montar_payload_pessoa_para_cadastro(usuario_data)
    return criar_pessoa_na_rein(payload)

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


