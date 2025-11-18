from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta

# ==== CONFIG GERAL ====
DATABASE_URL = "sqlite:///./afiliados.db"
SECRET_KEY = "PEGDOBRASIL@8102ECOMMERCE"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 dia

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

app = FastAPI(title="API Afiliados")

# CORS: libera seu painel em GitHub Pages
origins = [
    "https://pegdobrasil.github.io",  # ajuste para sua URL real
    "http://localhost:8000",
    "*",  # enquanto desenvolve; depois deixar mais restrito
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== MODELO BANCO ====
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    tipo_pessoa = Column(String, nullable=False)
    cpf_cnpj = Column(String, unique=True, index=True, nullable=False)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    telefone = Column(String, nullable=True)
    cep = Column(String, nullable=False)
    logradouro = Column(String, nullable=False)
    numero = Column(String, nullable=False)
    complemento = Column(String, nullable=True)
    bairro = Column(String, nullable=False)
    cidade = Column(String, nullable=False)
    uf = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)

# ==== SCHEMAS Pydantic ====
class UsuarioCreate(BaseModel):
    tipo_pessoa: str
    cpf_cnpj: str
    nome: str
    email: EmailStr
    senha: str
    telefone: str | None = None
    cep: str
    logradouro: str
    numero: str
    complemento: str | None = None
    bairro: str
    cidade: str
    uf: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginData(BaseModel):
    email: EmailStr
    senha: str


# ==== DEPENDÊNCIA DE SESSÃO DB ====
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==== FUNÇÕES AUXILIARES ====
def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    return pwd_context.verify(senha, hash_armazenado)


def criar_token(dados: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = dados.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ==== ROTAS ====

@app.post("/api/auth/register", status_code=201)
def register(user: UsuarioCreate, db: Session = Depends(get_db)):
    # valida CPF/CNPJ básico
    digits = "".join(filter(str.isdigit, user.cpf_cnpj))
    if len(digits) not in (11, 14):
        raise HTTPException(status_code=400, detail="CPF/CNPJ inválido.")

    # checa duplicidade
    if db.query(Usuario).filter(Usuario.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email já cadastrado.")
    if db.query(Usuario).filter(Usuario.cpf_cnpj == digits).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado.")

    novo = Usuario(
        tipo_pessoa=user.tipo_pessoa,
        cpf_cnpj=digits,
        nome=user.nome,
        email=user.email,
        senha_hash=hash_senha(user.senha),
        telefone=user.telefone,
        cep=user.cep,
        logradouro=user.logradouro,
        numero=user.numero,
        complemento=user.complemento,
        bairro=user.bairro,
        cidade=user.cidade,
        uf=user.uf.upper(),
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {"id": novo.id, "email": novo.email}


@app.post("/api/auth/login", response_model=Token)
def login(data: LoginData, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user or not verificar_senha(data.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    token = criar_token({"sub": str(user.id), "email": user.email})
    return Token(access_token=token)

