from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import secrets
import string

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas

from .rein_client import (
    buscar_pessoa_por_documento,
    get_or_create_pessoa_rein,
)

from .email_config import send_email

# Garante que a tabela exista
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ---------------- HELPERS ----------------


def gerar_senha_aleatoria(tamanho: int = 10):
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(tamanho))


def enviar_email_boas_vindas(usuario: Usuario):
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Seu acesso ao <strong>Painel de Afiliados</strong> foi criado com sucesso.</p>
        <p>Use este e-mail e a senha cadastrada para entrar no painel.</p>
        <p>PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Cadastro confirmado - Painel Afiliados",
            html_body=html,
        )
    except:
        pass


def enviar_email_primeiro_acesso(usuario: Usuario):
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Identificamos que você já era cliente da PEG do Brasil.</p>
        <p>Seu cadastro foi vinculado ao ERP automaticamente.</p>
        <p>No primeiro login será necessário criar uma nova senha.</p>
        <p>PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Acesso ao Painel Afiliados vinculado ao ERP",
            html_body=html,
        )
    except:
        pass


# ---------------- REGISTER ----------------


@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    documento = "".join(filter(str.isdigit, data.cpf_cnpj))
    tipo_pessoa = data.tipo_pessoa.upper()

    # 1 — usuário já existe no painel?
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(400, "E-mail já cadastrado.")

    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(400, "CPF/CNPJ já cadastrado.")

    # 2 — consulta REIN
    try:
        pessoa = buscar_pessoa_por_documento(documento, tipo_pessoa)
    except Exception as e:
        raise HTTPException(500, f"Erro ao consultar ERP: {e}")

    # Hash da senha escolhida pelo afiliado
    try:
        senha_hash = pwd_context.hash(data.senha)
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar hash da senha: {e}")

    # 2A — se pessoa já existe na Rein → cadastra usuário usando essa pessoa
    if pessoa:
        pessoa_id = (
            pessoa.get("Id")
            or pessoa.get("intId")
            or pessoa.get("id")
        )

        user = Usuario(
            tipo_pessoa=tipo_pessoa,
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
            rein_pessoa_id=int(pessoa_id),
            first_login_must_change=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        enviar_email_primeiro_acesso(user)

        return {
            "status": "success",
            "message": "Cadastro vinculado ao cliente existente no ERP.",
            "id": user.id,
        }

    # 2B — não existe pessoa na Rein → cria e depois cria usuário
    try:
        pessoa_id = get_or_create_pessoa_rein({
            "tipo_pessoa": tipo_pessoa,
            "cpf_cnpj": documento,
            "nome": data.nome,
        })
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar pessoa na Rein: {e}")

    user = Usuario(
        tipo_pessoa=tipo_pessoa,
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
        rein_pessoa_id=pessoa_id,
        first_login_must_change=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    enviar_email_boas_vindas(user)

    return {
        "status": "success",
        "message": "Cadastro realizado com sucesso.",
        "id": user.id,
    }


# ---------------- LOGIN ----------------


@router.post("/login")
def login_user(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(400, "E-mail não encontrado.")

    if not pwd_context.verify(data.senha, user.senha_hash):
        raise HTTPException(400, "Senha incorreta.")

    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "first_login_must_change": user.first_login_must_change,
        "rein_pessoa_id": user.rein_pessoa_id,
    }
