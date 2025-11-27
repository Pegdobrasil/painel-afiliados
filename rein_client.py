import requests
import re
from config import REIN_BASE, rein_headers

EP_LIST = "/api/v1/produto"         # GET ?page=1&termo={sku}
# detalhe usa /api/v1/produto/{id}

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

def aplicar_mascara_documento(doc: str) -> str:
    doc = re.sub(r"\D", "", doc or "")
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    return doc


def buscar_pessoa_por_documento(documento: str):
    endpoint = "/api/v1/pessoa"
    headers = rein_headers(endpoint)

    termo = aplicar_mascara_documento(documento)
    params = {"page": 1, "termo": termo}

    resp = requests.get(REIN_BASE + endpoint, headers=headers, params=params, timeout=20)
    resp.raise_for_status()

    data = resp.json()
    items = data.get("data", {}).get("items") or []

    if not items:
        return None

    pessoa = items[0]
    return pessoa.get("Id") or pessoa.get("intId") or pessoa.get("id")


def criar_cliente_rein(usuario_data: dict) -> int:
    endpoint = "/api/v1/pessoa"
    headers = rein_headers(endpoint)
    url = REIN_BASE + endpoint

    cpf = aplicar_mascara_documento(usuario_data["cpf_cnpj"])
    digits = re.sub(r"\D", "", cpf)
    tipo = "F" if len(digits) == 11 else "J"

    payload = {
        "intCanalVendaId": 4,
        "intUsuarioTecnicoId": 1,
        "intUsuarioVendedorId": 1,
        "boolEnviarEcf": True,
        "floatCreditoDevolucao": 0,
        "floatLimiteDeCredito": 0,
        "intCrt": 0,
        "intIndicadorInscricaoEstadual": 0,
        "strCnae": "",
        "strCnpj": cpf if tipo == "J" else "",
        "strDataCadastro": "",
        "strDataFundacao": "",
        "strDataUltimaModificacao": "",
        "strDocumentoEstrangeiro": "",
        "strInscricaoMunicipal": "",
        "strSuframa": "",
        "strInscricaoEstadual": "",
        "strNome": usuario_data["nome"],
        "strRazaoSocial": usuario_data["nome"],
        "strObservacao": "",
        "strObservacaoFiscal": "",
        "strPerfilFornecedor": "",
        "strPrazoLimiteCredito": "",
        "strTipoPessoa": tipo,
        "boolMei": False,
        "strSexo": "",
        "CadastroGeralEmail": [
            {
                "intId": 0,
                "intTipoCadastroId": 1,
                "boolPrincipal": True,
                "strEmail": usuario_data["email"]
            }
        ],
        "CadastroGeralEndereco": [
            {
                "intId": 0,
                "strMunicipio": usuario_data["cidade"],
                "strEstado": usuario_data["estado"],
                "intPaisId": 0,
                "strIdentificador": "",
                "strLogradouro": usuario_data["endereco"],
                "strNumero": usuario_data["numero"],
                "strBairro": usuario_data["bairro"],
                "strComplemento": "",
                "intCep": usuario_data["cep"],
                "boolPrincipal": True,
                "boolEntrega": True,
                "boolRetirada": True,
                "boolCobranca": True,
                "strObservacao": "Cadastro automático"
            }
        ],
        "CadastroGeralTelefone": [
            {
                "intId": 0,
                "intTipoCadastroId": 1,
                "strNome": "",
                "boolPrincipal": True,
                "strTelefone": usuario_data["telefone"] or "",
            }
        ],
        "TabelaPrecoPermissaoVinculo": [
            {
                "intId": 1,
                "strNome": "",
                "strIdentificador": "",
                "boolMostrarPrecoLojaVirtual": True,
                "boolPadrao": True
            }
        ],
        "TabelaPrecoPrincipal": {},
        "CondicaoPagamentoBloqueado": [],
        "TipoCliente": [
            {"intId": 1, "strNome": ""}
        ],
        "UsoMercadoriaConstanteFiscal": {"intId": 0},
    }

    resp = requests.put(url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()

    data = resp.json()
    inner = data.get("data") or data
    pessoa_id = inner.get("Id") or inner.get("intId") or inner.get("id")

    if not pessoa_id:
        raise RuntimeError(f"Falha ao obter ID: {data}")

    return int(pessoa_id)


def listar_pedidos_por_cliente(pessoa_id: int):
    return []

