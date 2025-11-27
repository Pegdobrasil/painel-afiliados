# -*- coding: utf-8 -*-
"""
Integração central com a API REIN.

- Funções de PRODUTO (busca por SKU, paginação para estoque).
- Funções de PESSOA (buscar por CPF/CNPJ e criar cadastro).
- Usa sempre config.REIN_BASE e config.rein_headers(path) para montar
  as requisições com HMAC, seguindo o mesmo padrão do Postman.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import requests
import re
import time

import config

# Session global para reaproveitar conexões HTTP
session = requests.Session()

# Endpoints base
EP_PRODUTO = "/api/v1/produto"
EP_PESSOA = "/api/v1/pessoa"

# ----------------------------
# Helpers HTTP + debug
# ----------------------------

def _get(path: str, *, params: Dict[str, Any] | None = None) -> requests.Response:
    """
    Faz GET na REIN com headers HMAC corretos.
    Levanta erro em status != 2xx, com mensagem detalhada para debug.
    """
    url = f"{config.REIN_BASE}{path}"
    headers = config.rein_headers(path)
    try:
        resp = session.get(url, headers=headers, params=params or {}, timeout=60)
        resp.raise_for_status()
        return resp
    except requests.HTTPError as e:
        preview = ""
        try:
            preview = (resp.text or "")[:400]
        except Exception:
            pass
        raise RuntimeError(
            f"REIN GET {path} falhou "
            f"(status={getattr(resp, 'status_code', '?')}): {preview}"
        ) from e


def _put(path: str, *, json_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Faz PUT na REIN com headers HMAC corretos e retorna o JSON já desserializado.
    """
    url = f"{config.REIN_BASE}{path}"
    headers = config.rein_headers(path)
    try:
        resp = session.put(url, headers=headers, json=json_body, timeout=60)
        resp.raise_for_status()
        data = resp.json() or {}
    except requests.HTTPError as e:
        preview = ""
        try:
            preview = (resp.text or "")[:400]
        except Exception:
            pass
        raise RuntimeError(
            f"REIN PUT {path} falhou "
            f"(status={getattr(resp, 'status_code', '?')}): {preview}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar PUT {path} na REIN: {e}") from e

    # Muitos endpoints da REIN vêm embrulhados em {"data": {...}}
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data

# ============================================================
# PRODUTOS
# ============================================================

def _parse_locais(grade: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Normaliza os dados de ProdutoLocal de uma grade em uma lista simples.
    Cada item contém:
      - id / nome do local
      - saldo (EstoqueDisponivel / Saldo)
      - margens por tabela de preço
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
                        "preco_desc": float(m.get("PrecoComDesconto") or m.get("Preco") or 0),
                        "preco": float(m.get("Preco") or m.get("PrecoComDesconto") or 0),
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
    Retorno: [{"tabela": "ATACADO", "preco": 10.0, "preco_desc": 9.5}, ...]
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


def _match_grade_by_sku(items: List[Dict[str, Any]], sku: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Dentro de uma lista de produtos vinda de /api/v1/produto,
    encontra (produto, grade) em que ProdutoGrade.Sku == sku.
    """
    sku = str(sku)
    for it in (items or []):
        for g in (it.get("ProdutoGrade") or []):
            if str(g.get("Sku")) == sku:
                return it, g
    return None


def buscar_por_sku_duas_etapas(sku: str) -> Optional[Dict[str, Any]]:
    """
    Busca produto/grade na REIN em DUAS ETAPAS:

      1) GET /api/v1/produto?termo={sku}&page=1
         - filtra exatamente pela grade com ProdutoGrade.Sku == sku
      2) GET /api/v1/produto/{id}
         - detalha o produto e tenta achar a mesma grade
    """
    # -------- Etapa 1: listar por termo --------
    r1 = _get(EP_PRODUTO, params={"page": 1, "termo": sku})
    data1 = r1.json() or {}
    items = (data1.get("data") or {}).get("items") or []

    hit = _match_grade_by_sku(items, sku)
    if not hit:
        return None

    item, grade = hit
    prod_id = item.get("Id")
    nome = item.get("Nome") or "Sem nome"
    ncm = item.get("Ncm")
    locais_snapshot = _parse_locais(grade)

    # -------- Etapa 2: detalhe por ID --------
    ep_id = f"{EP_PRODUTO}/{prod_id}"
    r2 = _get(ep_id)
    data2 = r2.json() or {}
    det = (data2.get("data") or data2) or {}

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

    # tenta montar URL de imagem pela NomeImagem da grade
    nome_imagem = None
    grade_img = grade2 or grade
    for img in (grade_img.get("ProdutoImagem") or []):
        nome_imagem = img.get("NomeImagem") or img.get("NomeArquivo")
        if nome_imagem:
            break

    imagem_url = None
    if hasattr(config, "rein_image_url"):
        try:
            imagem_url = config.rein_image_url(nome_imagem)
        except Exception:
            imagem_url = None

    return {
        "produto_id": prod_id,
        "sku": str(sku),
        "grade_id": grade_img.get("Id"),
        "nome": nome,
        "ncm": ncm,
        "imagem_url": imagem_url,
        "locais_rein": locais,
        "precos_tabela": precos_por_tabela,
        "produto_raw": det or item,  # prioriza o detalhe
        "grade_raw": grade_img,
    }


def listar_produtos_paginado() -> List[Dict[str, Any]]:
    """
    Faz a paginação completa em /api/v1/produto?page=N
    e devolve uma lista achatada por grade.
    Usado por rein_estoque.py para espelhar o estoque.
    """
    page = 1
    out: List[Dict[str, Any]] = []
    PAGE_SIZE = 100

    while True:
        r = _get(EP_PRODUTO, params={"page": page})
        data = r.json() or {}
        items = (data.get("data") or {}).get("items") or []

        if not items:
            break

        for prod in items:
            nome = prod.get("Nome") or ""
            ncm = prod.get("Ncm")
            prod_id = prod.get("Id")
            for g in (prod.get("ProdutoGrade") or []):
                sku = str(g.get("Sku") or g.get("Id") or "").strip()
                if not sku:
                    continue

                # soma estoque nos locais da grade
                estoque_total = 0
                for pl in (g.get("ProdutoLocal") or []):
                    try:
                        estoque_total += int(pl.get("EstoqueDisponivel") or 0)
                    except Exception:
                        pass

                # imagem por NomeImagem, se disponível
                nome_imagem = None
                for img in (g.get("ProdutoImagem") or []):
                    nome_imagem = img.get("NomeImagem") or img.get("NomeArquivo")
                    if nome_imagem:
                        break
                imagem_url = None
                if hasattr(config, "rein_image_url"):
                    try:
                        imagem_url = config.rein_image_url(nome_imagem)
                    except Exception:
                        imagem_url = None

                out.append(
                    {
                        "sku": sku,
                        "nome": nome,
                        "ncm": ncm,
                        "estoque_total": estoque_total,
                        "imagem_url": imagem_url,
                        "produto_id": prod_id,
                        "grade_id": g.get("Id"),
                        "locais_rein": g.get("ProdutoLocal") or [],
                    }
                )

        if len(items) < PAGE_SIZE:
            break
        page += 1
        # pequena pausa para não estourar 60 req/min da API
        time.sleep(1.05)

    return out

# ============================================================
# PESSOAS (vínculo afiliado x cliente REIN)
# ============================================================

def aplicar_mascara_documento(doc: str) -> str:
    doc = re.sub(r"\D", "", doc or "")
    if len(doc) == 11:
        return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    if len(doc) == 14:
        return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
    return doc


def buscar_pessoa_por_documento(documento: str):
    """
    Consulta /api/v1/pessoa?termo={documento} (com máscara de CPF/CNPJ)
    e retorna o ID da primeira pessoa encontrada, ou None.
    """
    endpoint = EP_PESSOA
    termo = aplicar_mascara_documento(documento)

    resp = _get(endpoint, params={"page": 1, "termo": termo})
    data = resp.json() or {}
    items = (data.get("data") or {}).get("items") or []

    if not items:
        return None

    pessoa = items[0]
    # A API às vezes usa "Id", às vezes "id" / "intId"
    return pessoa.get("Id") or pessoa.get("intId") or pessoa.get("id")


def criar_cliente_rein(usuario_data: Dict[str, Any]) -> int:
    """
    Cria um cliente na REIN utilizando o endpoint /api/v1/pessoa (PUT),
    seguindo a estrutura base do exemplo do Postman, montando
    os campos a partir dos dados do afiliado.
    """
    endpoint = EP_PESSOA

    cpf_cnpj = aplicar_mascara_documento(usuario_data.get("cpf_cnpj", ""))
    digits = re.sub(r"\D", "", cpf_cnpj)
    if len(digits) == 11:
        tipo = "F"
    else:
        tipo = "J"

    payload: Dict[str, Any] = {
        "CanalVendaId": 4,          # canal de venda que você informou
        "UsuarioTecnicoId": 1,
        "UsuarioVendedorId": 1,
        "EnviarEcf": True,
        "CreditoDevolucao": 0,
        "LimiteDeCredito": 0,
        "Crt": 0,
        "IndicadorInscricaoEstadual": 0,
        "Cnae": "",
        "Cnpj": cpf_cnpj if tipo == "J" else "",
        "Cpf": cpf_cnpj if tipo == "F" else "",
        "DataCadastro": "",
        "DataFundacao": "",
        "DataUltimaModificacao": "",
        "DocumentoEstrangeiro": "",
        "InscricaoMunicipal": "",
        "Suframa": "",
        "InscricaoEstadual": "",
        "Nome": usuario_data.get("nome"),
        "RazaoSocial": usuario_data.get("nome"),
        "Observacao": "",
        "ObservacaoFiscal": "",
        "PerfilFornecedor": "",
        "PrazoLimiteCredito": "",
        "TipoPessoa": tipo,
        "Mei": False,
        "Sexo": "",
        "CadastroGeralEmail": [
            {
                "Id": 0,
                "TipoCadastroId": 1,
                "Principal": True,
                "Email": usuario_data.get("email"),
            }
        ],
        "CadastroGeralEndereco": [
            {
                "Id": 0,
                "Municipio": usuario_data.get("cidade"),
                "Estado": usuario_data.get("estado"),
                "PaisId": 0,
                "Identificador": "",
                "Logradouro": usuario_data.get("endereco"),
                "Numero": usuario_data.get("numero"),
                "Bairro": usuario_data.get("bairro"),
                "Complemento": "",
                "Cep": usuario_data.get("cep"),
                "Principal": True,
                "Entrega": True,
                "Retirada": True,
                "Cobranca": True,
                "Observacao": "Cadastro automático Painel Afiliados",
            }
        ],
        "CadastroGeralTelefone": [
            {
                "Id": 0,
                "TipoCadastroId": 1,
                "Nome": "",
                "Principal": True,
                "Telefone": usuario_data.get("telefone") or "",
            }
        ],
        "TabelaPrecoPermissaoVinculo": [
            {
                "Id": 1,
                "Nome": "",
                "Identificador": "",
                "MostrarPrecoLojaVirtual": True,
                "Padrao": True,
            }
        ],
        "TabelaPrecoPrincipal": {},
        "CondicaoPagamentoBloqueado": [],
        "TipoCliente": [
            {
                "Id": 1,
                "Nome": "",
            }
        ],
        "UsoMercadoriaConstanteFiscal": {"Id": 0},
    }

    data = _put(endpoint, json_body=payload)
    pessoa_id = data.get("Id") or data.get("intId") or data.get("id")
    if not pessoa_id:
        raise RuntimeError(f"Não foi possível obter o ID da pessoa criada: {data}")

    return int(pessoa_id)


def listar_pedidos_por_cliente(pessoa_id: int):
    """
    Placeholder para futuras integrações de pedidos por cliente.
    Mantido aqui só para compatibilidade com imports antigos.
    """
    return []
