from typing import List, Optional
from pydantic import BaseModel
from produto_listar import listar_produtos, preparar_resultados
from produto_detalhar import detalhar_produto
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from server.auth import router as auth_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas de cadastro/login/usuários ficam no módulo server.auth
# AGORA com prefixo /api/auth  → /api/auth/register, /api/auth/login, etc.
app.include_router(auth_router, prefix="/api/auth")


@app.get("/")
def root():
    return {"status": "online", "message": "Painel Afiliados funcionando!"}


# ---------------------------
# UTM – mantido simples aqui
# ---------------------------
class UTMCreateRequest(BaseModel):
    afiliado_id: int
    url: str


@app.post("/api/utm/create")
def create_utm(data: UTMCreateRequest):
    # Depois você pode criar lógica real de UTM aqui
    return {"link": data.url}


# Entry point pro Railway
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

