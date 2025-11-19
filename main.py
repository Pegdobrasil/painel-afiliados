from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
import os

# ======================================
# APP FASTAPI
# ======================================
app = FastAPI()

# ======================================
# CORS
# ======================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================
# BANCO DE DADOS (SQLite)
# ======================================

# Corrigido para o Railway – cria o banco dentro do diretório correto
BASE_DIR = os.getcwd()
DB_PATH = os.path.join(BASE_DIR, "usuarios.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False}
)

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ======================================
# MODELO DO BANCO
# ======================================
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    tipo_pessoa = Column(String)
    cpf_cnpj = Column(String, unique=True)
    nome = Column(String)
    email = Column(String, unique=True)
    telefone = Column(String)
    cep = Column(String)
    endereco = Column(String)
    numero = Column(String)
    bairro = Column(String)
    cidade = Column(String)
    estado = Column(String)
    senha_hash = Column(String)


Base.metadata.create_all(bind=engine)

# ======================================
# MODELO DE REQUISIÇÃO
# ======================================
class UsuarioCreate(BaseModel):
    tipo_pessoa: str
    cpf_cnpj: str
    nome: str
    email: str
    telefone: str
    cep: str
    endereco: str
    numero: str
    bairro: str
    cidade: str
    estado: str
    senha: str


class LoginRequest(BaseModel):
    email: str
    senha: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ======================================
# ROTA DE TESTE
# ======================================
@app.get("/")
def root():
    return {"status": "online", "message": "Painel Afiliados API funcionando!"}

# ======================================
# ROTA CADASTRO
# ======================================
@app.post("/api/auth/register")
def register_user(data: UsuarioCreate):
    db = SessionLocal()

    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    user = Usuario(
        tipo_pessoa=data.tipo_pessoa,
        cpf_cnpj=data.cpf_cnpj,
        nome=data.nome,
        email=data.email,
        telefone=data.telefone,
        cep=data.cep,
        endereco=data.endereco,
        numero=data.numero,
        bairro=data.bairro,
        cidade=data.cidade,
        estado=data.estado,
        senha_hash=pwd_context.hash(data.senha),
    )

    db.add(user)
    db.commit()

    return {"status": "success", "message": "Cadastro realizado com sucesso!"}

# ======================================
# ROTA LOGIN
# ======================================
@app.post("/api/auth/login")
def login_user(data: LoginRequest):
    db = SessionLocal()

    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="E-mail não encontrado")

    if not pwd_context.verify(data.senha, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha incorreta")

    return {"status": "success", "message": "Login autorizado"}
@app.get("/")
def root():
    return {"status": "online", "message": "Painel Afiliados Rodando"}
