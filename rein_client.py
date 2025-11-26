# -*- coding: utf-8 -*-
import requests
from typing import Any, Dict, List, Optional, Tuple
import config

session = requests.Session()

EP_LIST = "/api/v1/produto"  # GET ?page=1&termo={sku}


# ============================================================
# HELPERS BÁSICOS DE REQUISIÇÃO
# ============================================================

def _get(path: str, **kw):
    url = f"{config.REIN_BASE}{path}"
    return session.get(url, headers=config.rein_headers(path), timeout=60, **kw)


def _put(path: str, json: Optional[Dict[str, Any]] = None, **kw):
    url = f"{config.REIN_BASE}{path}"
    return session.put(
        url,
        headers=config.rein_headers(path),
        json=json,
        timeout=60,
        **kw,
    )


# ============================================================
# HELPERS DE DOCUMENTO (CPF / CNPJ)
# ============================================================

def somente_digitos(valor: str) -> str:
    return "".join(filter(str.isdigit, valor or ""))


def formatar_documento(cpf_cnpj: str) -> str:
    """
    Aplica máscara no documento para buscar na REIN.
    - 11 dígitos -> 000.000.000-00
    - 14 dígitos -> 00.000.000/0000-00
    """
    d = somente_digitos(cpf_cnpj)
    if len(d) == 11:
        return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"
    if len(d) == 14:
        return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    return cpf_cnpj  # se vier algo estranho, devolve como está


def detectar_tipo_pessoa_por_documento(cpf_cnpj: str) -> str:
    """
    Retorna 'F' para pessoa física, 'J' para jurídica.
    Baseado no número de dígitos do documento.
    """
    d = somente_digitos(cpf_cnpj)
    if len(d) == 11:
        return "F"
    if len(d) == 14:
        return "J"
    raise ValueError("CPF/CNPJ inválido.")


# ============================================================
# PRODUTOS / ESTOQUE
# ============================================================

def _parse_locais(grade: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrai os locais de estoque de uma grade da REIN.
    """
    locais: List[Dict[str, Any]] = []
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
    items: List[Dict[str, Any]], sku: str
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
    sku = str(sku).strip()
    if not sku:
        return None

    # Etapa 1: listar
    r1 = _get(EP_LIST, params={"page": 1, "termo": sku})
    r1.raise_for_status()
    data1 = r1.json() or {}
    items = (data1.get("data") or {}).get("items", []) or []

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


def listar_produtos_paginado() -> List[Dict[str, Any]]:
    """
    Wrapper para manter compatibilidade com scripts antigos.
    Delega para rein_estoque_paginado.listar_produtos_paginado().
    """
    try:
        from rein_estoque_paginado import listar_produtos_paginado as _inner
    except ImportError:
        return []
    return _inner()


# ============================================================
# PESSOAS (CLIENTES / AFILIADOS) NA REIN
# ============================================================

def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Helper genérico para extrair lista de itens da resposta padrão da REIN."""
    if not data:
        return []
    d = data.get("data")
    if isinstance(d, dict):
        items = d.get("items")
        if isinstance(items, list):
            return items
    if isinstance(d, list):
        return d
    return []


def buscar_pessoa_por_documento(cpf_cnpj: str, tipo_pessoa: str) -> Optional[Dict[str, Any]]:
    """
    Busca uma pessoa na REIN filtrando por CPF/CNPJ e tipo (F/J).

    A Rein está esperando o termo COM máscara:
    - Ex.: 102.524.679-90 (não 10252467990)
    """
    documento_mascarado = formatar_documento(cpf_cnpj)
    # TipoPessoa da API: 'F' ou 'J'
    try:
        tipo_auto = detectar_tipo_pessoa_por_documento(cpf_cnpj)
    except ValueError:
        tipo_auto = None

    tipo_param = tipo_auto or (tipo_pessoa or "").strip().upper()

    params = {
        "tipoPessoa": tipo_param,       # F ou J
        "status": "ativo",
        "tipoCliente": "cliente",
        "page": 1,
        "termo": documento_mascarado,   # << com máscara
    }

    resp = _get("/api/v1/pessoa", params=params)
    resp.raise_for_status()
    items = _extract_items(resp.json() or {})
    return items[0] if items else None


def montar_payload_pessoa_para_cadastro(usuario_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monta o JSON mínimo para cadastro de Pessoa na REIN a partir dos dados do afiliado.
    - 11 dígitos = pessoa física (TipoPessoa = 'F', campo Cpf)
    - 14 dígitos = pessoa jurídica (TipoPessoa = 'J', campo Cnpj)
    """
    cpf_cnpj_raw = usuario_data.get("cpf_cnpj") or ""
    d = somente_digitos(cpf_cnpj_raw)
    nome = usuario_data.get("nome") or ""

    if len(d) == 11:
        tipo_pessoa_api = "F"
        cpf_formatado = formatar_documento(d)
        cpf_field = cpf_formatado
        cnpj_field = None
    elif len(d) == 14:
        tipo_pessoa_api = "J"
        cnpj_formatado = formatar_documento(d)
        cpf_field = None
        cnpj_field = cnpj_formatado
    else:
        raise ValueError("CPF/CNPJ inválido para cadastro da Pessoa na Rein.")

    payload: Dict[str, Any] = {
        "TipoPessoa": tipo_pessoa_api,  # F ou J (padrão da Rein)
        "Nome": nome,
        "RazaoSocial": nome if tipo_pessoa_api == "J" else None,
        "Cpf": cpf_field,
        "Cnpj": cnpj_field,
        "TipoCliente": "cliente",
        "Status": 1,
        "CadastroGeralEmail": [],
        "CadastroGeralEndereco": [],
        "Observacao": "Cadastro criado automaticamente pelo painel de afiliados.",
    }
    return payload


def criar_pessoa_na_rein(payload: Dict[str, Any]) -> int:
    """
    Cria uma pessoa na REIN via PUT /api/v1/pessoa e retorna o ID criado.
    """
    resp = _put("/api/v1/pessoa", json=payload)
    resp.raise_for_status()
    data = resp.json() or {}
    pessoa_id = data.get("intId") or data.get("Id") or data.get("id")
    if not pessoa_id:
        raise RuntimeError(
            f"Não foi possível obter o ID da pessoa criada na Rein: {data}"
        )
    return int(pessoa_id)


def montar_payload_pessoa_para_cadastro(usuario_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monta o JSON completo para cadastro de Pessoa na REIN a partir dos dados do afiliado.

    Regra:
    - 11 dígitos = pessoa física (TipoPessoa = 'F', campo Cpf com máscara)
    - 14 dígitos = pessoa jurídica (TipoPessoa = 'J', campo Cnpj com máscara)
    - Todos os campos do exemplo da REIN são enviados, mesmo que vazios.
    """

    cpf_cnpj_raw = usuario_data.get("cpf_cnpj") or ""
    d = somente_digitos(cpf_cnpj_raw)

    nome = usuario_data.get("nome") or ""
    email = usuario_data.get("email") or ""
    telefone = usuario_data.get("telefone") or ""
    cep = usuario_data.get("cep") or ""
    endereco = usuario_data.get("endereco") or ""
    numero = usuario_data.get("numero") or ""
    bairro = usuario_data.get("bairro") or ""
    cidade = usuario_data.get("cidade") or ""
    estado = usuario_data.get("estado") or ""

    if len(d) == 11:
        tipo_pessoa_api = "F"
        doc_formatado = formatar_documento(d)  # 000.000.000-00
        cpf_field = doc_formatado
        cnpj_field = ""
    elif len(d) == 14:
        tipo_pessoa_api = "J"
        doc_formatado = formatar_documento(d)  # 00.000.000/0000-00
        cpf_field = ""
        cnpj_field = doc_formatado
    else:
        raise ValueError("CPF/CNPJ inválido para cadastro da Pessoa na Rein.")

    # Bloco de e-mails (se tiver e-mail, cria um registro principal)
    cadastro_emails: List[Dict[str, Any]] = []
    if email:
        cadastro_emails.append(
            {
                "Id": 0,
                "TipoCadastroId": 0,
                "Principal": True,
                "Email": email,
            }
        )

    # Bloco de endereços (se tiver CEP/logradouro, manda 1 principal)
    cadastro_enderecos: List[Dict[str, Any]] = []
    if any([cep, endereco, cidade, estado]):
        cadastro_enderecos.append(
            {
                "Id": 0,
                "Municipio": cidade or "",
                "Estado": estado or "",
                "PaisId": 0,  # pode ajustar depois se a REIN exigir o ID do Brasil
                "Identificador": "Endereço principal",
                "Logradouro": endereco or "",
                "Numero": numero or "",
                "Bairro": bairro or "",
                "strComplemento": "",
                "Cep": cep or "",
                "Principal": True,
                "Entrega": True,
                "Retirada": True,
                "Cobranca": True,
                "strObservacao": "",
            }
        )

    # Bloco de telefones (opcional)
    cadastro_telefones: List[Dict[str, Any]] = []
    if telefone:
        cadastro_telefones.append(
            {
                "Id": 5,
                "TipoCadastroId": 0,
                "Nome": "Principal",
                "Principal": True,
                "Telefone": telefone,
            }
        )

    payload: Dict[str, Any] = {
        "CanalVendaId": 0,
        "UsuarioTecnicoId": 0,
        "UsuarioVendedorId": 0,
        "EnviarEcf": True,
        "CreditoDevolucao": 0,
        "LimiteDeCredito": 0,
        "Crt": 0,
        "IndicadorInscricaoEstadual": 0,
        "Cnae": "",
        "Cnpj": cnpj_field,
        "DataCadao": "",
        "DataFundacao": "",
        "DataUltimaModificacao": "",
        "DocumentoEangeiro": "",
        "InscricaoMunicipal": "",
        "Suframa": "",
        "InscricaoEstadual": "",
        "Nome": nome,
        "RazaoSocial": nome if tipo_pessoa_api == "J" else "",
        "Observacao": "Cadastro criado automaticamente pelo painel de afiliados.",
        "ObservacaoFiscal": "",
        "PerfilFornecedor": "",
        "PrazoLimiteCredito": "",
        "TipoPessoa": tipo_pessoa_api,  # 'F' ou 'J' (padrão da REIN)
        "Mei": False,
        "Sexo": "",
        "CadastroGeralEmail": cadastro_emails,
        "CadastroGeralEndereco": cadastro_enderecos,
        "CadastroGeralTelefone": cadastro_telefones,
        "TabelaPrecoPermissaoVinculo": [],
        "TabelaPrecoPrincipal": {
            "Id": 0,
            "Nome": "",
            "Identificador": "",
            "MostrarPrecoLojaVirtual": True,
        },
        "CondicaoPagamentoBloqueado": [],
        "TipoCliente": [],  # se sua base exigir, depois dá para mandar o Id real aqui
        "UsoMercadoriaConstanteFiscal": {
            "Id": 0
        },
        # Campos equivalentes ao CPF (PF)
        "Cpf": cpf_field,
    }

    return payload



# ============================================================
# PEDIDOS NA REIN (LISTAGEM POR CLIENTE / AFILIADO)
# ============================================================

def listar_pedidos_por_cliente(rein_pessoa_id: int) -> List[Dict[str, Any]]:
    """
    Lista pedidos na REIN filtrando pelo IdCliente (Pessoa / Afiliado).
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

