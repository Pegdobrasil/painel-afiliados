import re
import requests

from config import REIN_BASE, rein_headers  # usa o MESMO header dos outros scripts


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
    Usa o mesmo esquema de token/headers do config.py.
    """
    endpoint_path = "/api/v1/pessoa"  # caminho completo para assinar e chamar
    headers = rein_headers(endpoint_path)

    termo = aplicar_mascara_documento(documento)
    params = {"page": 1, "termo": termo}

    url = f"{REIN_BASE}{endpoint_path}"
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()

    data = resp.json()
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

    endpoint_path = "/api/v1/pessoa"
    headers = rein_headers(endpoint_path)
    url = f"{REIN_BASE}{endpoint_path}"

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

    resp = requests.put(url, json=payload, headers=headers, timeout=20)
    resp.raise_for_status()

    data = resp.json()
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
