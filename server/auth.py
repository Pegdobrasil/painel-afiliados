from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import string
import re

from server.database import get_db, Base, engine
from server.models import Usuario
from server import schemas
from server.email_config import send_email
import rein_client

# Cria tabelas se não existirem
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ============================================================
# TOKEN HELPERS
# ============================================================

def gerar_verification_token() -> str:
    return secrets.token_urlsafe(32)

def gerar_reset_token() -> str:
    return secrets.token_urlsafe(32)

def gerar_api_token() -> str:
    return secrets.token_hex(32)

def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)

# ============================================================
# EMAIL
# ============================================================

FRONT_RESET_URL = "https://pegdobrasil.github.io/painel-afiliados/trocar_senha.html"
FRONT_VERIFY_URL = "https://pegdobrasil.github.io/painel-afiliados/validar.html"


def enviar_email_verificacao(usuario: Usuario):
    if not usuario.verification_token:
        usuario.verification_token = gerar_verification_token()
        usuario.verification_token_expires_at = datetime.utcnow() + timedelta(days=7)

    link = f"{FRONT_VERIFY_URL}?id={usuario.id}&token={usuario.verification_token}"

    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Clique para ativar seu acesso ao painel:</p>
    <p><a href="{link}">{link}</a></p>
    """

    try:
        send_email(
            to_email=usuario.email,
            subject="Ative seu acesso ao Painel Afiliados",
            html_body=html,
        )
    except:
        pass


def enviar_email_senha_alterada(usuario: Usuario):
    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Sua senha foi alterada com sucesso.</p>
    """

    try:
        send_email(
            to_email=usuario.email,
            subject="Senha alterada",
            html_body=html,
        )
    except:
        pass

# ============================================================
# ROTA: REGISTRO
# ============================================================

@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    documento = re.sub(r"\D", "", data.cpf_cnpj)

    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado.")

    try:
        pessoa_id = rein_client.buscar_pessoa_por_documento(documento)
        if not pessoa_id:
            pessoa_id = rein_client.criar_cliente_rein(
                {
                    "cpf_cnpj": documento,
                    "tipo_pessoa": data.tipo_pessoa,
                    "nome": data.nome,
                    "email": data.email,
                    "telefone": data.telefone,
                    "cep": data.cep,
                    "endereco": data.endereco,
                    "numero": data.numero,
                    "bairro": data.bairro,
                    "cidade": data.cidade,
                    "estado": data.estado,
                }
            )
    except Exception as e:
        raise HTTPException(500, f"Erro na integração com a Rein: {e}")

    usuario = Usuario(
        tipo_pessoa=data.tipo_pessoa,
        cpf_cnpj=documento,
        nome=data.nome,
        email=data.email,
        telefone=data.telefone,
        cep=data.cep,
        endereco=data.endereco,
        numero=data.numero,
        bairro=data.bairro,
        cidade=data.cidade,
        estado=data.estado,
        senha_hash=hash_senha(data.senha),
        rein_pessoa_id=int(pessoa_id),
        ativo=False,
        verification_token=gerar_verification_token(),
        verification_token_expires_at=datetime.utcnow() + timedelta(days=7),
        api_token=gerar_api_token(),
    )

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    enviar_email_verificacao(usuario)

    return {
        "status": "success",
        "message": "Cadastro realizado. Verifique seu e-mail para ativar a conta.",
    }

# ============================================================
# ROTA: LOGIN
# ============================================================

@router.post("/login")
def login(data: schemas.Login, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario or not verificar_senha(data.senha, usuario.senha_hash):
        raise HTTPException(400, "Usuário ou senha inválidos.")

    if not usuario.ativo:
        raise HTTPException(403, "Usuário ainda não ativado. Verifique seu e-mail.")

    return {
        "status": "success",
        "token": usuario.api_token,
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
    }

# ============================================================
# ROTA: VERIFICAR EMAIL
# ============================================================

@router.get("/verify-email")
def verify_email(id: int, token: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()
    if not usuario:
        raise HTTPException(400, "Usuário não encontrado.")

    if usuario.verification_token != token:
        raise HTTPException(400, "Token inválido.")

    if usuario.verification_token_expires_at < datetime.utcnow():
        raise HTTPException(400, "Token expirado.")

    usuario.ativo = True
    usuario.verification_token = None
    usuario.verification_token_expires_at = None
    db.commit()

    return {"status": "success", "message": "Conta ativada com sucesso!"}

# ============================================================
# ROTA: ALTERAR SENHA VIA TOKEN
# ============================================================

@router.post("/change-password-token")
def change_password_token(data: schemas.ChangePasswordToken, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.reset_token == data.token).first()
    if not usuario:
        raise HTTPException(400, "Token inválido.")

    if usuario.reset_token_expires_at < datetime.utcnow():
        raise HTTPException(400, "Token expirado.")

    usuario.senha_hash = hash_senha(data.nova_senha)
    usuario.reset_token = None
    usuario.reset_token_expires_at = None

    db.commit()
    enviar_email_senha_alterada(usuario)

    return {"status": "success", "message": "Senha alterada."}

# ============================================================
# ROTA: RECUPERAÇÃO DE SENHA
# ============================================================

@router.post("/recover")
def recover(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not usuario:
        raise HTTPException(400, "E-mail não encontrado.")

    usuario.senha_hash = hash_senha(data.nova_senha)
    usuario.reset_token = None
    usuario.reset_token_expires_at = None

    db.commit()
    enviar_email_senha_alterada(usuario)

    return {"status": "success", "message": "Senha redefinida."}
