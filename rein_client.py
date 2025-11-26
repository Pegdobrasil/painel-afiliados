import requests
import re
from datetime import datetime
import hashlib
import hmac

BASE_URL = "https://api.rein.net.br/api/v1"
DATABASE = "pegdobrasil"
CLIENT_ID = "7e49-e62a-a2c6-cc84"
CLIENT_SECRET = "SUA_CHAVE_SECRETA_AQUI"  # coloque a sua chave

def gerar_assinatura(endpoint: str):
    timestamp = str(int((datetime.utcnow().timestamp() + 300)))
    data = f"{endpoint}.{DATABASE}.{timestamp}"

    assinatura = hmac.new(
        CLIENT_SECRET.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()

    return assinatura, timestamp


# ----------------------------------------------------------
# GERA MASCARA PARA CPF OU CNPJ AUTOMATICAMENTE
# ----------------------------------------------------------
def aplicar_mascara_documento(doc: str):
    doc = re.sub(r"\D", "", doc)

    if len(doc) == 11:
        return f"{doc[0:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:11]}"
    elif len(doc) == 14:
        return f"{doc[0:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:14]}"
    return doc


# ----------------------------------------------------------
# BUSCA PESSOA POR CPF/CNPJ
# ----------------------------------------------------------
def buscar_pessoa_por_documento(documento: str):
    documento = aplicar_mascara_documento(documento)
    endpoint = f"/pessoa"
    token, timestamp = gerar_assinatura(endpoint)

    params = {"page": 1, "termo": documento}

    headers = {
        "Content-Type": "application/json",
        "Token": token,
        "Database": DATABASE,
        "Timestamp": timestamp,
        "ClientId": CLIENT_ID
    }

    response = requests.get(BASE_URL + endpoint, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    itens = data.get("data", {}).get("items", [])
    if itens:
        return itens[0]["Id"]  # encontrou
    return None


# ----------------------------------------------------------
# CRIA CLIENTE NA REIN
# ----------------------------------------------------------
def criar_cliente_rein(usuario):
    cpf_cnpj = aplicar_mascara_documento(usuario.cpf)
    tipo_pessoa = "F" if len(re.sub(r"\D", "", usuario.cpf)) == 11 else "J"

    endpoint = "/pessoa"
    token, timestamp = gerar_assinatura(endpoint)

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
        "strCnpj": cpf_cnpj if tipo_pessoa == "J" else "",
        "strDataCadastro": "",
        "strDataFundacao": "",
        "strDataUltimaModificacao": "",
        "strDocumentoEstrangeiro": "",
        "strInscricaoMunicipal": "",
        "strSuframa": "",
        "strInscricaoEstadual": "",
        "strNome": usuario.nome,
        "strRazaoSocial": usuario.nome,
        "strObservacao": "",
        "strObservacaoFiscal": "",
        "strPerfilFornecedor": "",
        "strPrazoLimiteCredito": "",
        "strTipoPessoa": tipo_pessoa,
        "boolMei": False,
        "strSexo": "",
        "CadastroGeralEmail": [
            {
                "intId": 0,
                "intTipoCadastroId": 1,
                "boolPrincipal": True,
                "strEmail": usuario.email
            }
        ],
        "CadastroGeralEndereco": [
            {
                "intId": 0,
                "strMunicipio": usuario.cidade,
                "strEstado": usuario.uf,
                "intPaisId": 0,
                "strIdentificador": "",
                "strLogradouro": usuario.logradouro,
                "strNumero": usuario.numero,
                "strBairro": usuario.bairro,
                "strComplemento": usuario.complemento,
                "intCep": usuario.cep,
                "boolPrincipal": True,
                "boolEntrega": True,
                "boolRetirada": True,
                "boolCobranca": True,
                "strObservacao": "Endereço cadastrado automaticamente"
            }
        ],
        "CadastroGeralTelefone": [
            {
                "intId": 0,
                "intTipoCadastroId": 1,
                "strNome": "",
                "boolPrincipal": True,
                "strTelefone": usuario.telefone
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
            {
                "intId": 1,
                "strNome": ""
            }
        ],
        "UsoMercadoriaConstanteFiscal": {
            "intId": 0
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Token": token,
        "Database": DATABASE,
        "Timestamp": timestamp,
        "ClientId": CLIENT_ID
    }

    response = requests.put(BASE_URL + endpoint, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()
