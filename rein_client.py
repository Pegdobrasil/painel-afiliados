import requests
import re
from datetime import datetime
import hashlib
import hmac

BASE_URL = "https://api.rein.net.br/api/v1"
DATABASE = "pegdobrasil"
CLIENT_ID = "7e49-e62a-a2c6-cc84"
CLIENT_SECRET = "1a5a9c0e681c42a4944d911ee0c5b9be16274d38eb90986a33e3f4dc119f47c3"  # coloque a sua chave real aqui


def gerar_assinatura(endpoint: str):
    """
    Gera assinatura HMAC baseada no exemplo do Postman:
    endpoint.Database.Timestamp
    """
    timestamp = str(int(datetime.utcnow().timestamp()) + 300)
    data = f"{endpoint}.{DATABASE}.{timestamp}"

    assinatura = hmac.new(
        CLIENT_SECRET.encode(),
        data.encode(),
        hashlib.sha256,
    ).hexdigest()

    return assinatura, timestamp


def _default_headers(endpoint: str):
    token, timestamp = gerar_assinatura(endpoint)
    return {
        "Content-Type": "application/json",
        "Token": token,
        "Database": DATABASE,
        "Timestamp": timestamp,
        "ClientId": CLIENT_ID,
    }


# ----------------------------------------------------------
# GERA MÁSCARA PARA CPF OU CNPJ AUTOMATICAMENTE
# ----------------------------------------------------------
def aplicar_mascara_documento(doc: str) -> str:
    doc = re.sub(r"\D", "", doc or "")

    if len(doc) == 11:
        return f"{doc[0:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:11]}"
    elif len(doc) == 14:
        return f"{doc[0:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:14]}"
    return doc


# ----------------------------------------------------------
# BUSCA PESSOA POR CPF/CNPJ
# ----------------------------------------------------------
def buscar_pessoa_por_documento(documento: str):
    """
    Retorna o ID da pessoa na REIN, ou None se não encontrar.
    """
    endpoint = "/pessoa"
    headers = _default_headers(endpoint)

    termo = aplicar_mascara_documento(documento)
    params = {"page": 1, "termo": termo}

    response = requests.get(BASE_URL + endpoint, headers=headers, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    itens = data.get("data", {}).get("items") or []

    if not itens:
        return None

    pessoa = itens[0]
    return pessoa.get("Id") or pessoa.get("intId") or pessoa.get("id")


# ----------------------------------------------------------
# CRIA CLIENTE NA REIN
# ----------------------------------------------------------
def criar_cliente_rein(usuario_data: dict) -> int:
    """
    usuario_data deve conter:
    - cpf_cnpj
    - tipo_pessoa  ('PF' ou 'PJ')
    - nome
    - email
    - telefone
    - cep
    - endereco
    - numero
    - bairro
    - cidade
    - estado
    """
    doc_mascarado = aplicar_mascara_documento(usuario_data.get("cpf_cnpj", ""))
    doc_digits = re.sub(r"\D", "", doc_mascarado)
    tipo_rein = "F" if len(doc_digits) == 11 else "J"

    endpoint = "/pessoa"
    headers = _default_headers(endpoint)

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
        "strCnpj": doc_mascarado if tipo_rein == "J" else "",
        "strDataCadastro": "",
        "strDataFundacao": "",
        "strDataUltimaModificacao": "",
        "strDocumentoEstrangeiro": "",
        "strInscricaoMunicipal": "",
        "strSuframa": "",
        "strInscricaoEstadual": "",
        "strNome": usuario_data.get("nome", ""),
        "strRazaoSocial": usuario_data.get("nome", ""),
        "strObservacao": "",
        "strObservacaoFiscal": "",
        "strPerfilFornecedor": "",
        "strPrazoLimiteCredito": "",
        "strTipoPessoa": tipo_rein,
        "boolMei": False,
        "strSexo": "",
        "CadastroGeralEmail": [
            {
                "intId": 0,
                "intTipoCadastroId": 1,
                "boolPrincipal": True,
                "strEmail": usuario_data.get("email", ""),
            }
        ],
        "CadastroGeralEndereco": [
            {
                "intId": 0,
                "strMunicipio": usuario_data.get("cidade", ""),
                "strEstado": usuario_data.get("estado", ""),
                "intPaisId": 0,
                "strIdentificador": "",
                "strLogradouro": usuario_data.get("endereco", ""),
                "strNumero": usuario_data.get("numero", ""),
                "strBairro": usuario_data.get("bairro", ""),
                "strComplemento": "",
                "intCep": usuario_data.get("cep", ""),
                "boolPrincipal": True,
                "boolEntrega": True,
                "boolRetirada": True,
                "boolCobranca": True,
                "strObservacao": "Endereço cadastrado automaticamente",
            }
        ],
        "CadastroGeralTelefone": [
            {
                "intId": 0,
                "intTipoCadastroId": 1,
                "strNome": "",
                "boolPrincipal": True,
                "strTelefone": usuario_data.get("telefone", "") or "",
            }
        ],
        "TabelaPrecoPermissaoVinculo": [
            {
                "intId": 1,
                "strNome": "",
                "strIdentificador": "",
                "boolMostrarPrecoLojaVirtual": True,
                "boolPadrao": True,
            }
        ],
        "TabelaPrecoPrincipal": {},
        "CondicaoPagamentoBloqueado": [],
        "TipoCliente": [
            {
                "intId": 1,
                "strNome": "",
            }
        ],
        "UsoMercadoriaConstanteFiscal": {
            "intId": 0,
        },
    }

    response = requests.put(BASE_URL + endpoint, json=payload, headers=headers, timeout=20)
    response.raise_for_status()

    data = response.json()
    # Exemplo que você mostrou:
    # {"status": 200, "data": {"Id": 155816, "Nome": "...", "sucesso": True}}
    inner = data.get("data") or data
    pessoa_id = inner.get("Id") or inner.get("intId") or inner.get("id")

    if not pessoa_id:
        raise RuntimeError(f"Não foi possível obter o ID da pessoa criada na Rein: {data}")

    return int(pessoa_id)


# ----------------------------------------------------------
# LISTAR PEDIDOS POR CLIENTE (stub simples, pra não quebrar)
# ----------------------------------------------------------
def listar_pedidos_por_cliente(pessoa_id: int):
    """
    Por enquanto retorna lista vazia para não quebrar /saldo e /pedidos.
    Depois a gente liga no endpoint correto de pedidos da REIN.
    """
    return []
