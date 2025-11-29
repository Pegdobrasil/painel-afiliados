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

    if not usuario:
        # Usuário não existe
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos.")

    # Se tiver campo 'ativo' e estiver falso, reenvia o link de ativação
    if getattr(usuario, "ativo", True) is False:
        # Se não tiver token, ou se já estiver expirado, gera um novo
        expired = (
            getattr(usuario, "verification_token_expires_at", None)
            and usuario.verification_token_expires_at < datetime.utcnow()
        )

        if not getattr(usuario, "verification_token", None) or expired:
            usuario.verification_token = gerar_verification_token()
            usuario.verification_token_expires_at = datetime.utcnow() + timedelta(days=7)
            db.commit()
            db.refresh(usuario)

        # Tenta reenviar o e-mail de verificação
        try:
            enviar_email_verificacao(usuario)
        except Exception as e:
            print(f"[WARN] Falha ao reenviar e-mail de verificação no login: {e}")

        # Bloqueia o login com uma mensagem clara
        raise HTTPException(
            status_code=403,
            detail="Conta ainda não ativada. Reenviamos o link de ativação para o seu e-mail."
        )

    # Senha inválida
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

    token = secrets.token_hex(32)

    return {
        "status": "success",
        "token": token,
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "rein_pessoa_id": usuario.rein_pessoa_id,
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

@router.get("/test-email")
def test_email(to: str, db: Session = Depends(get_db)):
    """
    Rota simples para testar envio de e-mail.
    Exemplo:
    GET /api/auth/test-email?to=seuemail@dominio.com
    """
    html = f"""
    <h1>Teste de E-mail - Painel Afiliados</h1>
    <p>Este é um envio de teste para <strong>{to}</strong>.</p>
    """
    send_email(to_email=to, subject="Teste Painel Afiliados", html_body=html)
    return {"status": "ok", "message": f"E-mail de teste enviado para {to} (se tudo der certo)." }

