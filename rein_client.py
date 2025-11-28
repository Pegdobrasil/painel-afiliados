# -*- coding: utf-8 -*-
import requests
from typing import Any, Dict, List, Optional, Tuple
import re as _re

import config

session = requests.Session()

EP_LIST = "/api/v1/produto"   # GET ?page=1&termo={sku}
EP_PESSOA = "/api/v1/pessoa"  # PUT /api/v1/pessoa  | GET ?termo=...&page=1


# ============================================================
# HELPERS HTTP (REIN)
# ============================================================

def _get(path: str, **kw) -> requests.Response:
    """
    GET na REIN usando o esquema de HMAC do config.rein_headers(endpoint_path).
    """
    url = f"{config.REIN_BASE}{path}"
    resp = session.get(url, headers=config.rein_headers(path), timeout=60, **kw)
    resp.raise_for_status()
    return resp


def _put_json(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    PUT na REIN com JSON, retornando o JSON já desserializado.
    Em erro HTTP, levanta RuntimeError com status + trecho da resposta
    para facilitar debug.
    """
    url = f"{config.REIN_BASE}{path}"
    headers = config.rein_headers(path)
    headers["Content-Type"] = "application/json"

    resp = session.put(url, headers=headers, json=body, timeout=60)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        preview = ""
        try:
            preview = (resp.text or "")[:400]
        except Exception:
            pass
        raise RuntimeError(
            f"Erro ao fazer PUT {path} na REIN "
            f"(status={resp.status_code}): {preview}"
        ) from e

    data = resp.json() or {}
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data


# ============================================================
# PRODUTO – já existentes no seu projeto
# ============================================================

def _parse_locais(grade: Dict[str, Any]) -> List[Dict[str, Any]]:
    locais = []
    for l in (grade.get("ProdutoLocal") or []):
        lobj = l.get("Local") or {}
        locais.append(
            {
                "id": lobj.get("Id") or l.get("LocalId"),
                "nome": lobj.get("Nome") or "Sem nome",
                "saldo": float(l.get("EstoqueDisponivel") or l.get("Saldo") or 0),
                "margens": [
                    {
                        "tabela": (m.get("TabelaPreco") or {}).get("Nome") or "",
                        "tabela_id": (m.get("TabelaPreco") or {}).get("Id"),
                        "preco_desc": float(
                            m.get("PrecoComDesconto") or m.get("Preco") or 0
                        ),
                        "preco": float(
                            m.get("Preco") or m.get("PrecoComDesconto") or 0
                        ),
                    }
                    for m in (l.get("ProdutoMargem") or [])
                ],
                "cadastro": (l.get("CadastroGeralEstoque") or {}),
            }
        )
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
                seen[nome] = {
                    "tabela": nome,
                    "preco": m["preco"],
                    "preco_desc": m["preco_desc"],
                }
    return list(seen.values())


def _match_grade_by_sku(
    items: List[Dict[str, Any]],
    sku: str,
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
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
        "grade_raw": grade2 or grade,
    }


# ============================================================
# PESSOA – integração para cadastro/vínculo de afiliado
# ============================================================

def _format_documento(doc: str) -> str:
    """
    Normaliza CPF/CNPJ (só dígitos) e aplica a máscara
    que a Rein está usando:

      - CPF:  000.000.000-00
      - CNPJ: 00.000.000/0000-00
    """
    digits = _re.sub(r"\D", "", doc or "")
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits



def buscar_pessoa_por_documento(documento: str):
    """
    Consulta /api/v1/pessoa?termo={documento}&page=1
    e retorna o ID da primeira pessoa encontrada na Rein
    (ou None se não achar).
    """
    termo = _format_documento(documento)

    params = {
        "page": 1,
        "termo": termo,
        # replica os filtros que funcionaram no seu curl
        "tipoPessoa": "PF ou PJ",
        "status": "ativo, excluido ou inativo",
        "tipoCliente": "empresa, cliente, fornecedor, funcionario ou transportadora",
    }

    resp = _get(EP_PESSOA, params=params)
    data = resp.json() or {}
    items = (data.get("data") or {}).get("items") or []

    if not items:
        return None

    pessoa = items[0]
    return pessoa.get("Id") or pessoa.get("id") or pessoa.get("intId")


def criar_cliente_rein(usuario_data: dict) -> int:
    """
    Cria um cliente na REIN usando PUT /api/v1/pessoa.

    Espera em usuario_data:
      - cpf_cnpj
      - tipo_pessoa ('PF' ou 'PJ')
      - nome
      - email
      - telefone
      - cep, endereco, numero, bairro, cidade, estado
    """

    endpoint = "/api/v1/pessoa"
    url = config.REIN_BASE + endpoint
    headers = config.rein_headers(endpoint)

    # documento vem só com dígitos no painel; aqui aplicamos máscara
    raw_doc = usuario_data["cpf_cnpj"]
    digits = re.sub(r"\D", "", raw_doc or "")

    if len(digits) == 11:
        # CPF
        doc_masked = f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
        tipo_pessoa = "F"
    else:
        # CNPJ
        doc_masked = f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
        tipo_pessoa = "J"

    payload = {
        # cabeçalho da pessoa (segue o modelo funcional / Postman)
        "CanalVendaId": 1001,          # você comentou que o canal de venda, por enquanto, é 4
        "UsuarioTecnicoId": 1,
        "UsuarioVendedorId": 457,   # mesmo vendedor que aparece nos cadastros gerados pela Magazord
        "EnviarEcf": True,
        "CreditoDevolucao": 0,
        "LimiteDeCredito": 0,
        "Crt": 0,
        "IndicadorInscricaoEstadual": 0,
        "Cnae": "",
        # A Rein usa SEMPRE o campo Cnpj, mesmo para pessoa física
        "Cnpj": doc,
        "DataCadastro": "",
        "DataFundacao": "",
        "DataUltimaModificacao": "",
        "DocumentoEstrangeiro": "",
        "InscricaoMunicipal": "",
        "Suframa": "",
        "InscricaoEstadual": "",
        "Nome": usuario_data["nome"],
        "RazaoSocial": usuario_data["nome"],
        "Observacao": "Cliente Gerado Automáticamente - Afiliado",
        "ObservacaoFiscal": "",
        "PerfilFornecedor": "",
        "PrazoLimiteCredito": "",
        "TipoPessoa": tipo,         # "F" ou "J"
        "Mei": False,
        "Sexo": "",

        # E-mails
        "CadastroGeralEmail": [
            {
                "Id": 8,
                "TipoCadastroId": 8,
                "Principal": True,
                "Email": usuario_data["email"]
            }
        ],

        # Endereço
        "CadastroGeralEndereco": [
            {
                "Id": 0,
                "Municipio": usuario_data["cidade"],
                "Estado": usuario_data["estado"],
                "PaisId": 0,
                "Identificador": "",
                "Logradouro": usuario_data["endereco"],
                "Numero": usuario_data["numero"],
                "Bairro": usuario_data["bairro"],
                "Complemento": "",
                "Cep": usuario_data["cep"],
                "Principal": True,
                "Entrega": True,
                "Retirada": True,
                "Cobranca": True,
                "Observacao": "Cadastro automático"
            }
        ],

        # Telefone
        "CadastroGeralTelefone": [
            {
                "Id": 8,
                "TipoCadastroId": 8,
                "Nome": "",
                "Principal": True,
                "Telefone": usuario_data.get("telefone") or ""
            }
        ],

        # Tabela de preços (permissão / principal)
        "TabelaPrecoPermissaoVinculo": [
            {
                "Id": 1,
                "Nome": "",
                "Identificador": "",
                "MostrarPrecoLojaVirtual": True,
                "Padrao": True
            }
        ],
        "TabelaPrecoPrincipal": {},

        # Condições de pagamento bloqueadas (nenhuma, por enquanto)
        "CondicaoPagamentoBloqueado": [
            {
                "Id": 1,
                "Nome": "string"
            }
          ],
        # Tipo de cliente
        "TipoCliente": [
            {
                "Id": 1,
                "Nome": "Cliente"
            }
        ],

        # Uso da mercadoria
        "UsoMercadoriaConstanteFiscal": {
            "Id": 0
        }
    }

    resp = requests.put(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()

    body = resp.json() or {}
    data = body.get("data") or body

    # exemplo: { "status": 200, "data": { "Id": 156026, "Nome": "...", "sucesso": true } }
    pessoa_id = data.get("Id") or data.get("id") or data.get("intId")

    if not pessoa_id:
        raise RuntimeError(f"Resposta da REIN não retornou Id ao criar pessoa: {body}")

    return int(pessoa_id)






