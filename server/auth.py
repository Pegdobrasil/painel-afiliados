from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import string
import re

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas
from .email_config import send_email
import rein_client


# Garante tabelas
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ======================================
# Helpers de Senha
# ======================================

def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)

def gerar_senha_aleatoria(tamanho: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(tamanho))

def gerar_reset_token():
    return secrets.token_urlsafe(32)

def criar_reset_para_usuario(usuario: Usuario, minutos: int = 60):
    usuario.reset_token = gerar_reset_token()
    usuario.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=minutos)


# ======================================
# Helpers de E-mail
# ======================================

FRONT_RESET_URL = "https://pegdobrasil.github.io/painel-afiliados/trocar_senha.html"

def enviar_email_link_reset(usuario: Usuario):
    link = f"{FRONT_RESET_URL}?token={usuario.reset_token}"

    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Para definir sua senha de acesso ao <strong>Painel de Afiliados PEG do Brasil</strong>,
    clique no link abaixo:</p>

    <p><a href="{link}">{link}</a></p>

    <p>Este link expira em 1 hora.</p>
    <p>Se você não pediu isto, ignore este e-mail.</p>
    """

    send_email(
        to_email=usuario.email,
        subject="Definir senha - Painel de Afiliados PEG do Brasil",
        html_body=html
    )


def enviar_email_boas_vindas(usuario: Usuario):
    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Seu cadastro foi realizado com sucesso.</p>
    <p>Seus dados já foram vinculados ao nosso ERP.</p>
    """

    send_email(
        to_email=usuario.email,
        subject="Cadastro realizado - Painel de Afiliados PEG do Brasil",
        html_body=html
    )


def enviar_email_nova_senha(usuario: Usuario, senha: str):
    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Sua nova senha é: <strong>{senha}</strong></p>
    <p>Você pode alterá-la a qualquer momento no painel.</p>
    """

    send_email(
        to_email=usuario.email,
        subject="Nova senha - Painel de Afiliados",
        html_body=html
    )


# ======================================
# ROTA: CADASTRO DE USUÁRIO
# ======================================

@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):

    documento = re.sub(r"\D", "", data.cpf_cnpj)

    # Verifica duplicidade no PAINEL
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado.")


    # 1) VERIFICA SE CLIENTE EXISTE NA REIN
    pessoa_existente_id = rein_client.buscar_pessoa_por_documento(documento)


    # ======================================
    # A) CLIENTE JÁ EXISTE NA REIN
    # ======================================
    if pessoa_existente_id:

        senha_inicial = gerar_senha_aleatoria()
        senha_hash = hash_senha(senha_inicial)

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
            senha_hash=senha_hash,
            rein_pessoa_id=pessoa_existente_id,
            first_login_must_change=True
        )

        # Gera token de primeiro acesso
        criar_reset_para_usuario(usuario)

        db.add(usuario)
        db.commit()
        db.refresh(usuario)

        # Envia link por e-mail
        enviar_email_link_reset(usuario)

        return {
            "status": "pending_first_access",
            "message": "Cliente já existe no ERP. Enviamos um link para definir sua senha."
        }


    # ======================================
    # B) CLIENTE NÃO EXISTE → CRIA NA REIN
    # ======================================
    try:
        rein_id = rein_client.criar_cliente_rein({
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
            "estado": data.estado
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar cliente na Rein: {e}")


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
        rein_pessoa_id=rein_id,
        first_login_must_change=False
    )

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    enviar_email_boas_vindas(usuario)

    return {
        "status": "success",
        "message": "Cadastro criado na REIN e vinculado com sucesso!"
    }


# ======================================
# ROTA: LOGIN
# ======================================

@router.post("/login")
def login(data: schemas.Login, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos.")

    if not verificar_senha(data.senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos.")

    # Primeiro acesso → precisa usar token enviado por e-mail
    if usuario.first_login_must_change:
        return {
            "status": "change_password_required",
            "message": "Primeiro acesso: verifique seu e-mail para criar sua senha."
        }

    token = secrets.token_hex(32)
    return {
        "status": "success",
        "token": token,
        "user_id": usuario.id
    }


# ======================================
# ROTA: REDEFINIR SENHA (TOKEN VIA E-MAIL)
# ======================================

@router.post("/change-password-token")
def change_password_token(data: schemas.ChangePasswordToken, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(
        Usuario.reset_token == data.token
    ).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Token inválido.")

    if not usuario.reset_token_expires_at or usuario.reset_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expirado.")

    usuario.senha_hash = hash_senha(data.nova_senha)
    usuario.reset_token = None
    usuario.reset_token_expires_at = None
    usuario.first_login_must_change = False

    db.commit()
    db.refresh(usuario)

    return {"status": "success", "message": "Senha atualizada com sucesso!"}


# ======================================
# ROTA: RECUPERAR SENHA (SEM TOKEN)
# ======================================

@router.post("/recover")
def recover(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="E-mail não encontrado.")

    nova = gerar_senha_aleatoria()
    usuario.senha_hash = hash_senha(nova)

    db.commit()
    db.refresh(usuario)

    enviar_email_nova_senha(usuario, nova)

    return {"status": "ok", "message": "Uma nova senha foi enviada ao seu e-mail."}
