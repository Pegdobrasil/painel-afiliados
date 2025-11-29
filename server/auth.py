from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import string
import re

from server.database import get_db, Base, engine
from server.models import Usuario
from . import server.schemas
from .email_config import send_email
import rein_client

# Garante que a tabela exista
Base.metadata.create_all(bind=engine)

router = APIRouter()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def gerar_reset_token() -> str:
    return secrets.token_urlsafe(32)


def gerar_verification_token() -> str:
    return secrets.token_urlsafe(32)


def gerar_api_token() -> str:
    return secrets.token_hex(32)

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
# Helpers de e-mail
# =====================================================
FRONT_RESET_URL = "https://pegdobrasil.github.io/painel-afiliados/trocar_senha.html"
FRONT_VERIFY_URL = "https://pegdobrasil.github.io/painel-afiliados/validar.html"

def enviar_email_verificacao(usuario: Usuario) -> None:
    """
    Manda o link para validar o cadastro (primeiro acesso).
    Usa o campo verification_token do usuário.
    """
    if not getattr(usuario, "verification_token", None):
        usuario.verification_token = gerar_verification_token()
        usuario.verification_token_expires_at = datetime.utcnow() + timedelta(days=7)

    link = f"{FRONT_VERIFY_URL}?id={usuario.id}&token={usuario.verification_token}"

    html = f"""
    <p>Olá, {usuario.nome}!</p>
    <p>Para ativar seu acesso ao <strong>Painel de Afiliados PEG do Brasil</strong>,
    clique no link abaixo:</p>

    <p><a href="{link}">{link}</a></p>

    <p>Este link é válido por 7 dias.</p>
    <p>Se você não solicitou este cadastro, ignore esta mensagem.</p>
    """

    try:
        send_email(
            to_email=usuario.email,
            subject="Ative seu acesso - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as e:
        print(f"[WARN] Falha ao enviar e-mail de verificação: {e}")

from fastapi import Query

@router.get("/verify-email")
def verify_email(
    id: int = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuário não encontrado.")

    if not getattr(usuario, "verification_token", None):
        raise HTTPException(status_code=400, detail="Conta já verificada ou token inválido.")

    if usuario.verification_token != token:
        raise HTTPException(status_code=400, detail="Token de verificação inválido.")

    if getattr(usuario, "verification_token_expires_at", None) and \
       usuario.verification_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token de verificação expirado.")

    # Marca como ativo e limpa o token de verificação
    usuario.ativo = True
    usuario.verification_token = None
    usuario.verification_token_expires_at = None

    # Garante que possui api_token (se não tiver por algum motivo)
    if hasattr(usuario, "api_token") and not usuario.api_token:
        usuario.api_token = gerar_api_token()

    db.commit()
    db.refresh(usuario)

    return {
        "status": "success",
        "message": "Conta verificada com sucesso. Agora você já pode acessar o painel.",
        "id": usuario.id,
        "email": usuario.email,
        "api_token": getattr(usuario, "api_token", None),
    }
        
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

    # Cria usuário local
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
        usuario.ativo = False  # só ativa após validar o link

    # Gera token de verificação e (opcional) token de navegação
    if hasattr(usuario, "verification_token"):
        usuario.verification_token = gerar_verification_token()
        usuario.verification_token_expires_at = datetime.utcnow() + timedelta(days=7)

    if hasattr(usuario, "api_token"):
        usuario.api_token = gerar_api_token()

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    # Manda e-mail com link de verificação
    enviar_email_verificacao(usuario)

    return {
        "status": "success",
        "message": "Cadastro realizado. Enviamos um link para ativação no seu e-mail.",
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

    # Se tiver campo 'ativo' e estiver falso, bloqueia
    if getattr(usuario, "ativo", True) is False:
        raise HTTPException(status_code=403, detail="Usuário inativo.")

    if not verificar_senha(data.senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos.")

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

if hasattr(usuario, "api_token") and not usuario.api_token:
    usuario.api_token = gerar_api_token()
    db.commit()
    db.refresh(usuario)

return {
    "status": "success",
    "token": getattr(usuario, "api_token", None),
    "id": usuario.id,
    "nome": usuario.nome,
    "email": usuario.email,
    "rein_pessoa_id": usuario.rein_pessoa_id,
}

from fastapi import Query

@router.get("/verify-email")
def verify_email(
    id: int = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.id == id).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuário não encontrado.")

    if not getattr(usuario, "verification_token", None):
        raise HTTPException(status_code=400, detail="Conta já verificada ou token inválido.")

    if usuario.verification_token != token:
        raise HTTPException(status_code=400, detail="Token de verificação inválido.")

    if getattr(usuario, "verification_token_expires_at", None) and \
       usuario.verification_token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token de verificação expirado.")

    # Marca como ativo e limpa o token de verificação
    usuario.ativo = True
    usuario.verification_token = None
    usuario.verification_token_expires_at = None

    # Garante que possui api_token (se não tiver por algum motivo)
    if hasattr(usuario, "api_token") and not usuario.api_token:
        usuario.api_token = gerar_api_token()

    db.commit()
    db.refresh(usuario)

    return {
        "status": "success",
        "message": "Conta verificada com sucesso. Agora você já pode acessar o painel.",
        "id": usuario.id,
        "email": usuario.email,
        "api_token": getattr(usuario, "api_token", None),
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
