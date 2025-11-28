from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

import secrets
import string
import re

from pydantic import BaseModel

from .database import get_db, Base, engine
from .models import Usuario, AccessToken
from . import schemas
from .email_config import send_email
import rein_client

# Garante que a tabela exista
Base.metadata.create_all(bind=engine)

router = APIRouter()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")



# =====================================================
# Helpers de senha
# =====================================================

def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def gerar_senha_aleatoria(tamanho: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(tamanho))


def gerar_reset_token() -> str:
    return secrets.token_urlsafe(32)


def criar_reset_para_usuario(usuario: Usuario, minutos: int = 60) -> None:
    usuario.reset_token = gerar_reset_token()
    usuario.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=minutos)


# =====================================================
# Helpers de token de acesso (ativação do painel)
# =====================================================

def gerar_token_acesso() -> str:
    # token longo, seguro, próprio para link de e-mail
    return secrets.token_urlsafe(32)


def criar_token_acesso(
    db: Session,
    usuario: Usuario,
    minutos: int = 60 * 24 * 7,  # 7 dias; se quiser sem expiração, passe minutos=None
) -> AccessToken:
    expires_at: Optional[datetime] = None
    if minutos:
        expires_at = datetime.utcnow() + timedelta(minutes=minutos)

    token = AccessToken(
        usuario_id=usuario.id,
        token=gerar_token_acesso(),
        is_active=False,  # só vira True quando clicar no link
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def usuario_tem_tokens(db: Session, usuario_id: int) -> bool:
    return (
        db.query(AccessToken.id)
        .filter(AccessToken.usuario_id == usuario_id)
        .first()
        is not None
    )


def obter_token_acesso_ativo(
    db: Session, usuario_id: int
) -> Optional[AccessToken]:
    """Retorna um token ativo e não expirado para o usuário, se houver."""
    agora = datetime.utcnow()
    return (
        db.query(AccessToken)
        .filter(
            AccessToken.usuario_id == usuario_id,
            AccessToken.is_active.is_(True),
            (
                (AccessToken.expires_at.is_(None))
                | (AccessToken.expires_at >= agora)
            ),
        )
        .order_by(AccessToken.id.desc())
        .first()
    )

# =====================================================
# Helpers de e-mail
# =====================================================

FRONT_RESET_URL = "https://pegdobrasil.github.io/painel-afiliados/trocar_senha.html"
FRONT_ACCESS_URL = "https://pegdobrasil.github.io/painel-afiliados/index.html"

def enviar_email_link_acesso(usuario: Usuario, token: str) -> None:
    link = f"{FRONT_ACCESS_URL}?token={token}"

    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Seu cadastro foi realizado no
    <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
    <p>Para liberar seu acesso ao painel, clique no link abaixo:</p>

    <p><a href="{link}">{link}</a></p>

    <p>Depois de ativar o acesso pelo link, você poderá entrar usando
    o seu e-mail e a senha cadastrada.</p>
    """

    try:
        send_email(
            to_email=usuario.email,
            subject="Ativar acesso – Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as e:
        print(f"[WARN] Falha ao enviar e-mail com link de acesso: {e}")

        
def enviar_email_link_reset(usuario: Usuario) -> None:
    if not getattr(usuario, "reset_token", None):
        criar_reset_para_usuario(usuario)

    link = f"{FRONT_RESET_URL}?token={usuario.reset_token}"

    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Para definir sua senha de acesso ao <strong>Painel de Afiliados PEG do Brasil</strong>,
    clique no link abaixo:</p>

    <p><a href="{link}">{link}</a></p>

    <p>Este link expira em 1 hora.</p>
    <p>Se você não pediu isto, ignore este e-mail.</p>
    """

    # Nunca deixar o erro de SMTP derrubar a API
    try:
        send_email(
            to_email=usuario.email,
            subject="Definir senha - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as e:
        print(f"[WARN] Falha ao enviar e-mail de link de senha: {e}")


def enviar_email_boas_vindas(usuario: Usuario) -> None:
    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Seu cadastro foi realizado com sucesso no
    <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
    <p>Agora você já pode acessar o painel utilizando o e-mail e senha cadastrados.</p>
    """

    try:
        send_email(
            to_email=usuario.email,
            subject="Cadastro realizado - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as e:
        print(f"[WARN] Falha ao enviar e-mail de boas-vindas: {e}")


def enviar_email_senha_alterada(usuario: Usuario) -> None:
    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>A senha de acesso ao seu Painel de Afiliados foi alterada.</p>
    <p>Se você não reconhece esta alteração, entre em contato com o suporte.</p>
    """
    try:
        send_email(
            to_email=usuario.email,
            subject="Senha alterada - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as e:
        print(f"[WARN] Falha ao enviar e-mail de confirmação de senha: {e}")

class AccessActivatePayload(BaseModel):
    token: str


@router.post("/access/activate")
def activate_access_link(
    payload: AccessActivatePayload, db: Session = Depends(get_db)
):
    token_str = (payload.token or "").strip()
    if not token_str:
        raise HTTPException(status_code=400, detail="Token inválido.")

    token_obj: Optional[AccessToken] = (
        db.query(AccessToken).filter(AccessToken.token == token_str).first()
    )

    if not token_obj:
        raise HTTPException(status_code=400, detail="Token inválido.")

    agora = datetime.utcnow()
    if token_obj.expires_at and token_obj.expires_at < agora:
        raise HTTPException(status_code=400, detail="Token expirado.")

    if not token_obj.is_active:
        token_obj.is_active = True
        db.commit()
        db.refresh(token_obj)

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == token_obj.usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=400, detail="Usuário não encontrado para este token."
        )

    return {
        "status": "ok",
        "message": "Seu acesso foi liberado. Agora você já pode fazer login no painel.",
    }

# =====================================================
# ROTA: CADASTRO
# =====================================================

@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    documento = re.sub(r"\D", "", data.cpf_cnpj)

    # Verifica duplicidade no painel
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado.")

    # 1) Verifica se já existe pessoa na Rein
    try:
        pessoa_existente_id = rein_client.buscar_pessoa_por_documento(documento)
    except Exception as e:
        # Erro de integração → devolve 500 amigável
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao consultar cliente na Rein: {e}",
        )

    rein_pessoa_id: int
    if pessoa_existente_id:
        # Cliente já existe na Rein → só vincula
        rein_pessoa_id = int(pessoa_existente_id)
    else:
        # Não existe → cria na Rein
        try:
            rein_pessoa_id = int(
                rein_client.criar_cliente_rein(
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
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao criar cliente na Rein: {e}",
            )

    # Cria usuário local usando a senha informada
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
        rein_pessoa_id=rein_pessoa_id,
        first_login_must_change=False,
    )

    # Campos opcionais (se existirem no modelo)
    if hasattr(usuario, "ativo"):
        usuario.ativo = True

        db.add(usuario)
    db.commit()
    db.refresh(usuario)

    # Gera token de acesso e envia link por e-mail
    try:
        token_acesso = criar_token_acesso(db, usuario)
        enviar_email_link_acesso(usuario, token_acesso.token)
    except Exception as e:
        # Não derruba o cadastro se der erro ao enviar e-mail
        print(f"[WARN] Falha ao criar token de acesso/enviar e-mail: {e}")

    return {
        "status": "success",
        "message": "Cadastro realizado com sucesso! Verifique seu e-mail para ativar o acesso.",
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
    }



# =====================================================
# ROTA: LOGIN
# =====================================================

@router.post("/login")
def login(data: schemas.Login, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos.")

    # Se tiver flag 'ativo' e estiver falso, bloqueia sempre
    if getattr(usuario, "ativo", True) is False:
        raise HTTPException(status_code=403, detail="Usuário inativo.")

    if not verificar_senha(data.senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos.")

    # =====================================================
    # Checagem de token de acesso (ativação por e-mail)
    # =====================================================
    # Regra:
    # - Se o usuário NÃO tiver nenhum token cadastrado → não bloqueia (cadastros antigos).
    # - Se tiver token cadastrado e NENHUM ativo → bloqueia.
    tem_token = usuario_tem_tokens(db, usuario.id)
    if tem_token:
        token_ativo = obter_token_acesso_ativo(db, usuario.id)
        if not token_ativo:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Seu acesso ainda não foi liberado. "
                    "Use o link enviado por e-mail para ativar o painel."
                ),
            )

    # ========================================
    # Sincroniza / valida vínculo com pessoa na Rein
    # ========================================
    try:
        documento = usuario.cpf_cnpj  # está salvo só com dígitos no banco
        pessoa_id = rein_client.buscar_pessoa_por_documento(documento)

        if pessoa_id:
            # Já existe na Rein → garante que o vínculo está correto
            if usuario.rein_pessoa_id != int(pessoa_id):
                usuario.rein_pessoa_id = int(pessoa_id)
                db.commit()
                db.refresh(usuario)
        else:
            # Não existe na Rein -> cria agora usando os dados do usuário do painel
            novo_id = rein_client.criar_cliente_rein(
                {
                    "cpf_cnpj": documento,
                    "tipo_pessoa": usuario.tipo_pessoa,
                    "nome": usuario.nome,
                    "email": usuario.email,
                    "telefone": usuario.telefone,
                    "cep": usuario.cep,
                    "endereco": usuario.endereco,
                    "numero": usuario.numero,
                    "bairro": usuario.bairro,
                    "cidade": usuario.cidade,
                    "estado": usuario.estado,
                }
            )
            usuario.rein_pessoa_id = int(novo_id)
            db.commit()
            db.refresh(usuario)
    except Exception as e:
        # Nunca derruba o login por causa de problema de integração
        print(
            f"[WARN] Falha ao sincronizar usuário {usuario.email} com Rein no login: {e}"
        )

    # token de sessão simples (se quiser usar futuramente no backend)
    token = secrets.token_hex(32)

    return {
        "status": "success",
        "token": token,
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "rein_pessoa_id": usuario.rein_pessoa_id,
    }



# =====================================================
# ROTA: TROCAR SENHA VIA TOKEN (tela trocar_senha.html)
# =====================================================

@router.post("/change-password-token")
def change_password_token(
    data: schemas.ChangePasswordToken, db: Session = Depends(get_db)
):
    usuario = (
        db.query(Usuario)
        .filter(Usuario.reset_token == data.token)
        .first()
    )

    if not usuario:
        raise HTTPException(status_code=400, detail="Token inválido.")

    if (
        not getattr(usuario, "reset_token_expires_at", None)
        or usuario.reset_token_expires_at < datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="Token expirado.")

    usuario.senha_hash = hash_senha(data.nova_senha)
    usuario.reset_token = None
    usuario.reset_token_expires_at = None
    usuario.first_login_must_change = False

    db.commit()
    db.refresh(usuario)

    enviar_email_senha_alterada(usuario)

    return {"status": "success", "message": "Senha atualizada com sucesso!"}


# =====================================================
# ROTA: RECUPERAR CONTA (fluxo do botão na tela de login)
# =====================================================

@router.post("/recover")
def recover(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="E-mail não encontrado.")

    usuario.senha_hash = hash_senha(data.nova_senha)
    usuario.first_login_must_change = False
    usuario.reset_token = None
    if hasattr(usuario, "reset_token_expires_at"):
        usuario.reset_token_expires_at = None

    db.commit()
    db.refresh(usuario)

    enviar_email_senha_alterada(usuario)

    return {
        "status": "ok",
        "message": "Senha redefinida. Agora faça login com a nova senha.",
    }
