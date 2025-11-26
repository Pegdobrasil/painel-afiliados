import requests
import re
from config import REIN_BASE, rein_headers


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
