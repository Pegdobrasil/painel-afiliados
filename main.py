from typing import List, Optional, Dict, Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.auth import router as auth_router

# =====================================================
# IMPORT / FALLBACK PARA FUNÇÕES DE LISTAGEM DA REIN
# =====================================================
# Tenta importar de produto_listar.py (nome padrão).
# Se não achar, tenta painel_listar.py.
# Se ainda assim não achar, define as funções inline.
try:
    from produto_listar import listar_produtos, preparar_resultados
except ModuleNotFoundError:
    try:
        from painel_listar import listar_produtos, preparar_resultados
    except ModuleNotFoundError:
        import math
        import requests
        import config

        EP_LIST = "/api/v1/produto"

        def _sum_estoque(locais: List[Dict[str, Any]]) -> float:
            tot = 0.0
            for l in (locais or []):
                try:
                    tot += float(l.get("EstoqueDisponivel") or 0)
                except Exception:
                    pass
            return tot

        def _precos_por_tabela(produto_grade: Dict[str, Any]) -> Dict[str, float]:
            out: Dict[str, float] = {}
            for m in (produto_grade.get("ProdutoMargem") or []):
                tab = ((m.get("TabelaPreco") or {}).get("Nome") or "").upper()
                preco = float(m.get("Preco") or m.get("PrecoComDesconto") or 0)
                if tab and tab not in out:
                    out[tab] = preco
            return {
                "ATACADO": out.get("TABELA ATACADO") or out.get("ATACADO") or 0.0,
                "VAREJO": out.get("TABELA VAREJO") or out.get("VAREJO") or 0.0,
            }

        def listar_produtos(
            termo: str, page: int = 1, per_page: int = 10
        ) -> Dict[str, Any]:
            """
            Busca produtos na REIN com paginação por 'page'.
            Usa apenas GET /api/v1/produto.
            """
            page = max(1, int(page or 1))
            per_page = max(1, int(per_page or 10))

            url = f"{config.REIN_BASE}{EP_LIST}"
            r = requests.get(
                url,
                headers=config.rein_headers(EP_LIST),
                params={"page": page, "termo": termo},
                timeout=60,
            )
            r.raise_for_status()
            data = (r.json() or {}).get("data") or {}

            items = data.get("items") or []

            pag = data.get("paginacao") or {}
            total = (
                pag.get("totalItems")
                or pag.get("total")
                or data.get("total")
                or len(items)
            )
            try:
                total = int(total)
            except Exception:
                total = len(items)

            total_pages = max(1, math.ceil(total / per_page))

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            }

        def preparar_resultados(
            items: List[Dict[str, Any]],
            termo: str,
            sku_exato: bool = False,
            status: str = "ativos",  # "ativos" | "inativos" | "todos"
        ) -> List[Dict[str, Any]]:
            """
            Achata por grade (SKU) e monta linhas já tratadas para o painel.
            """
            termo = (termo or "").strip()
            linhas: List[Dict[str, Any]] = []

            for p in items:
                ativo = p.get("DataInativado") in (None, "", "null")
                if status == "ativos" and not ativo:
                    continue
                if status == "inativos" and ativo:
                    continue

                for g in (p.get("ProdutoGrade") or []):
                    sku = str(g.get("Sku") or "")
                    if sku_exato and termo and sku != termo:
                        continue

                    estoque = _sum_estoque(g.get("ProdutoLocal") or [])
                    precos = _precos_por_tabela(g)

                    linhas.append(
                        {
                            "produto_id": p.get("Id"),
                            "grade_id": g.get("Id"),
                            "sku": sku,
                            "nome": p.get("Nome") or "",
                            "ncm": p.get("Ncm"),
                            "estoque": estoque,
                            "ativo": bool(ativo),
                            "preco_atacado": precos.get("ATACADO", 0.0),
                            "preco_varejo": precos.get("VAREJO", 0.0),
                        }
                    )

            linhas.sort(key=lambda x: (-(x["ativo"]), -x["estoque"], x["sku"]))
            return linhas

# Detalhe de produto – se o módulo não existir, tratamos na rota
try:
    from produto_detalhar import detalhar_produto
except ModuleNotFoundError:
    detalhar_produto = None


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas de cadastro/login/usuários ficam no módulo server.auth
# Prefixo /api/auth → /api/auth/register, /api/auth/login, etc.
app.include_router(auth_router, prefix="/api/auth")


@app.get("/")
def root():
    return {"status": "online", "message": "Painel Afiliados funcionando!"}


# ---------------------------
# UTM – simples por enquanto
# ---------------------------
class UTMCreateRequest(BaseModel):
    afiliado_id: int
    url: str


class ReinProdutoLinha(BaseModel):
    produto_id: int
    grade_id: int
    sku: str
    nome: str
    ncm: Optional[str] = None
    estoque: float
    ativo: bool
    preco_atacado: float
    preco_varejo: float


class ReinBuscaResponse(BaseModel):
    items: List[ReinProdutoLinha]
    total: int
    page: int
    per_page: int
    total_pages: int


@app.post("/api/utm/create")
def create_utm(data: UTMCreateRequest):
    # Depois você pode criar lógica real de UTM aqui
    return {"link": data.url}


# =====================================================
# ROTAS REIN – APENAS GET (LISTA + DETALHE)
# =====================================================
@app.get("/api/rein/buscar_produtos", response_model=ReinBuscaResponse)
def rein_buscar_produtos(termo: str = "", page: int = 1, per_page: int = 10):
    """
    Endpoint consumido pelo painel (Buscar Produto).
    Usa só GET na API da REIN via listar_produtos + preparar_resultados.
    Não altera nenhum cadastro na REIN.
    """
    try:
        res = listar_produtos(termo, page=page, per_page=per_page)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar produtos na REIN: {e}",
        )

    items_raw = res.get("items") or res.get("data") or []
    linhas = preparar_resultados(items_raw, termo, sku_exato=False, status="ativos")

    total = int(res.get("total", len(linhas)))
    total_pages = int(res.get("total_pages", 1))

    return ReinBuscaResponse(
        items=[ReinProdutoLinha(**linha) for linha in linhas],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@app.get("/api/rein/produto/{produto_id}")
def rein_detalhe_produto(produto_id: int):
    """
    Detalhe de produto na REIN.
    Também usa somente GET. Usado quando o painel clica em "Ver detalhes".
    """
    if detalhar_produto is None:
        raise HTTPException(
            status_code=500,
            detail="Função detalhar_produto não disponível no servidor.",
        )

    try:
        data = detalhar_produto(produto_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar detalhe do produto na REIN: {e}",
        )


# Entry point pro Railway
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
