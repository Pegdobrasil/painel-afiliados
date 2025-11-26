from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas
from .email_config import send_email

import rein_client
import re
import secrets
import string

# Garante que as tabelas existam ao subir a aplicação
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# =========================
# Helpers de senha / e-mail
# =========================
def _hash_password(senha: str) -> str:
    return pwd_context.hash(senha)


def _verify_password(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)


def gerar_senha_aleatoria(tamanho: int = 8) -> str:
    caracteres = string.ascii_letters + string.digits
    return "".join(secrets.choice(caracteres) for _ in range(tamanho))


def enviar_email_boas_vindas(usuario: Usuario) -> None:
    """Envia e-mail de boas-vindas após cadastro de afiliado."""
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Seu cadastro no <strong>Painel de Afiliados PEG do Brasil</strong> foi realizado com sucesso.</p>
        <p>Você já pode acessar o painel usando este e-mail na tela de login.</p>
        <p>Se você não reconhece este cadastro, responda este e-mail para nossa equipe de suporte.</p>
        <p>Atenciosamente,<br>Equipe PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Cadastro realizado - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as exc:
        print(f"[WARN] Erro ao enviar e-mail de boas-vindas: {exc}")


def enviar_email_nova_senha(usuario: Usuario, senha_plana: str) -> None:
    """Envia e-mail com nova senha gerada na recuperação de conta."""
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Você solicitou a redefinição de senha do seu acesso ao
        <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
        <p>Sua nova senha é: <strong>{senha_plana}</strong></p>
        <p>Recomendamos que você altere essa senha após o login.</p>
        <p>Se você não fez esta solicitação, por favor desconsidere este e-mail.</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Nova senha de acesso - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as exc:
        print(f"[WARN] Erro ao enviar e-mail de nova senha: {exc}")


def enviar_email_senha_temporaria(usuario: Usuario, senha_plana: str) -> None:
    """E-mail usado quando o cliente já existia na REIN e ganhou acesso ao painel."""
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Identificamos que você já era cliente PEG do Brasil em nosso sistema interno.</p>
        <p>Criamos seu acesso ao <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
        <p>Senha temporária de acesso: <strong>{senha_plana}</strong></p>
        <p>No primeiro login, você será direcionado para criar uma nova senha definitiva.</p>
        <p>Se você não reconhece este acesso, responda este e-mail imediatamente.</p>
        <p>Atenciosamente,<br>Equipe PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Acesso ao Painel de Afiliados - senha temporária",
            html_body=html,
        )
    except Exception as exc:
        print(f"[WARN] Erro ao enviar e-mail de senha temporária: {exc}")


# ==============
# ROTAS: CADASTRO
# ==============


from datetime import datetime, timedelta
import secrets

FRONT_RESET_URL = "https://pegdobrasil.github.io/painel-afiliados/trocar_senha.html"

# ...

@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    # normaliza CPF/CNPJ
    documento = "".join(filter(str.isdigit, data.cpf_cnpj))

    # já existe usuário no painel?
    existente = (
        db.query(Usuario)
        .filter(
            (Usuario.cpf_cnpj == documento) | (Usuario.email == data.email)
        )
        .first()
    )
    if existente:
        raise HTTPException(status_code=400, detail="Já existe um cadastro com este CPF/CNPJ ou e-mail.")

    # 1) VER SE JÁ EXISTE PESSOA NA REIN
    pessoa_id = buscar_pessoa_por_documento(documento)

    # =================================================================
    # CASO A: JÁ É CLIENTE NA REIN → NÃO PODE LOGAR DIRETO
    # ENVIA LINK POR E-MAIL PARA DEFINIR A PRIMEIRA SENHA
    # =================================================================
    if pessoa_id:
        # senha “lixo” só pra ter algo no hash
        senha_hash_fake = pwd_context.hash(secrets.token_hex(16))

        # gera token de reset
        token = secrets.token_urlsafe(32)
        expires = datetime.utcnow() + timedelta(hours=24)

        user = Usuario(
            tipo_pessoa=data.tipo_pessoa.upper(),
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
            senha_hash=senha_hash_fake,
            rein_pessoa_id=pessoa_id,
            first_login_must_change=True,
            reset_token=token,
            reset_token_expires_at=expires,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # monta link de primeiro acesso
        reset_link = f"{FRONT_RESET_URL}?token={token}"

        html = f"""
        <p>Olá, {user.nome}!</p>
        <p>Identificamos que você já era cliente PEG do Brasil.</p>
        <p>Para ativar seu acesso ao <strong>Painel de Afiliados</strong>,
        clique no link abaixo e defina sua senha:</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>Este link é válido por 24 horas.</p>
        <p>Se você não solicitou este acesso, ignore este e-mail.</p>
        """

        try:
            send_email(
                to_email=user.email,
                subject="Ative seu acesso ao Painel de Afiliados PEG do Brasil",
                html_body=html,
            )
        except Exception as exc:
            print(f"[WARN] Erro ao enviar e-mail de primeiro acesso: {exc}")

        return {
            "status": "success",
            "message": "Cadastro localizado na Rein. Enviamos um link para seu e-mail para definir a senha.",
        }

    # =================================================================
    # CASO B: NÃO EXISTE NA REIN → cria cliente na Rein + senha escolhida
    # =================================================================
    try:
        rein_id = criar_cliente_rein({
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
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao criar cliente na Rein: {exc}")

    senha_hash = pwd_context.hash(data.senha)

    user = Usuario(
        tipo_pessoa=data.tipo_pessoa.upper(),
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
        rein_pessoa_id=rein_id,
        first_login_must_change=False,
        reset_token=None,
        reset_token_expires_at=None,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # opcional: e-mail de boas-vindas
    return {
        "status": "success",
        "message": "Cadastro criado na Rein e no Painel.",
        "id": user.id,
    }


# ==========
# ROTAS LOGIN
# ==========


@router.post("/login")
def login(data: schemas.Login, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos")

    if not pwd_context.verify(data.senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Usuário ou senha inválidos")

    # Se for primeiro login → OBRIGA troca de senha
    if usuario.first_login_must_change:
        return {
            "status": "change_password_required",
            "message": "É necessário criar uma nova senha antes de acessar.",
            "user_id": usuario.id,
        }

    # Login normal
    token = secrets.token_hex(32)

    return {
        "status": "success",
        "token": token,
        "user_id": usuario.id,
        "message": "Login realizado com sucesso",
    }


# =====================
# ROTAS: RECUPERAR SENHA
# =====================


@router.post("/recover")
def recuperar_senha(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    """Redefine a senha a partir do e-mail informado."""
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="E-mail não encontrado.")

    nova_hash = _hash_password(data.nova_senha)
    usuario.senha_hash = nova_hash
    db.commit()
    db.refresh(usuario)

    enviar_email_nova_senha(usuario, data.nova_senha)

    return {"status": "ok", "message": "Senha redefinida com sucesso."}


# =====================
# ROTAS: TROCA DE SENHA (primeiro acesso)
# =====================


@router.post("/change-password")
def change_password(data: schemas.ChangePassword, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == data.user_id).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    usuario.senha_hash = pwd_context.hash(data.nova_senha)
    usuario.first_login_must_change = False

    db.commit()
    db.refresh(usuario)

    return {
        "status": "success",
        "message": "Senha alterada com sucesso, agora você já pode acessar o painel.",
    }


# ========================
# ROTAS: SALDO E PEDIDOS (usando stub de pedidos por enquanto)
# ========================
@router.get("/saldo/{afiliado_id}")
def saldo_afiliado(afiliado_id: int, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == afiliado_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Afiliado não encontrado.")

    if not usuario.rein_pessoa_id:
        return {"total": 0.0}

    try:
        pedidos = rein_client.listar_pedidos_por_cliente(usuario.rein_pessoa_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar pedidos na REIN: {e}",
        )

    total = 0.0
    for p in pedidos or []:
        try:
            val = float(p.get("ValorTotal") or p.get("Valor") or 0)
        except Exception:
            val = 0.0
        total += val

    return {"total": total}


@router.get("/pedidos/{afiliado_id}")
def listar_pedidos(afiliado_id: int, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == afiliado_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Afiliado não encontrado.")

    if not usuario.rein_pessoa_id:
        return []

    try:
        pedidos = rein_client.listar_pedidos_por_cliente(usuario.rein_pessoa_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar pedidos na REIN: {e}",
        )

    saida = []
    for p in pedidos or []:
        cod = p.get("Codigo") or p.get("CodigoPedido") or p.get("Id") or p.get("intId")
        try:
            val = float(p.get("ValorTotal") or p.get("Valor") or 0)
        except Exception:
            val = 0.0

        data_criacao = (
            p.get("DataCriacao")
            or p.get("DataEmissao")
            or p.get("DataCadastro")
            or ""
        )

        saida.append(
            {
                "codigoPedido": cod,
                "valorTotal": val,
                "dataCriacao": data_criacao,
            }
        )

    return saida
