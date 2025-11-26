from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas
from .email_config import send_email

import rein_client

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
        # Não vamos quebrar o cadastro por erro de e-mail
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


# ==============
# ROTAS: CADASTRO
# ==============


@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """
    Cadastro com integração à REIN.
    FLUXOS:
    
    A) Se CPF/CNPJ já existir na REIN → NÃO cria na Rein
       - Cria somente o usuário local
       - Gera senha temporária
       - Marca first_login_must_change = True
       - Envia senha temporária por e-mail

    B) Se CPF/CNPJ NÃO existir na REIN → cria pessoa na Rein
       - Usa a senha digitada pelo afiliado
       - Marca first_login_must_change = False
       - Envia e-mail normal de boas-vindas
    """

    # ---- Normalização do documento ----
    documento = re.sub(r"\D", "", data.cpf_cnpj)

    # ---- Verificar duplicidade no PAINEL ----
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado")

    # ---- 1) CONSULTAR NA REIN ----
    pessoa_existente_id = buscar_pessoa_por_documento(documento)

    # ----------------------------------------------------------------
    # CASO A: Cliente já existe no ERP → cria usuário local + senha provisória
    # ----------------------------------------------------------------
    if pessoa_existente_id:
        senha_temp = gerar_senha_aleatoria()
        senha_hash = pwd_context.hash(senha_temp)

        user = Usuario(
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
            first_login_must_change=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Envia senha temporária
        enviar_email_senha_temporaria(user, senha_temp)

        return {
            "status": "success",
            "message": "Cadastro realizado (cliente já existia no ERP). Senha temporária enviada.",
            "id": user.id,
        }

    # ----------------------------------------------------------------
    # CASO B: Cliente NÃO existe no ERP → cria na REIN
    # ----------------------------------------------------------------
    try:
        rein_id = get_or_create_pessoa_rein({
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
        raise HTTPException(status_code=500, detail=f"Erro ao criar cliente na REIN: {exc}")

    # Hash da senha normal escolhida pelo afiliado
    senha_hash = pwd_context.hash(data.senha)

    # Cria o usuário local vinculado
    user = Usuario(
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
        rein_pessoa_id=rein_id,
        first_login_must_change=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    enviar_email_boas_vindas(user)

    return {
        "status": "success",
        "message": "Cadastro criado com sucesso na REIN e vinculado ao afiliado!",
        "id": user.id,
    }

# ==========
# ROTAS LOGIN
# ==========


@router.post("/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Login simples usando e-mail + senha.

    Usado pelo auth.js na tela de login.
    """
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="E-mail não encontrado.")

    if not _verify_password(data.senha, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha incorreta.")

    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "rein_pessoa_id": usuario.rein_pessoa_id,
    }


# =====================
# ROTAS: RECUPERAR SENHA
# =====================


@router.post("/recover")
def recuperar_senha(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    """Redefine a senha a partir do e-mail informado.

    Usado pelo auth.js (recuperarConta).
    """
    usuario = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="E-mail não encontrado.")

    nova_hash = _hash_password(data.nova_senha)
    usuario.senha_hash = nova_hash
    db.commit()
    db.refresh(usuario)

    enviar_email_nova_senha(usuario, data.nova_senha)

    return {"status": "ok", "message": "Senha redefinida com sucesso."}


# ========================
# ROTAS: SALDO E PEDIDOS
# ========================


@router.get("/saldo/{afiliado_id}")
def saldo_afiliado(afiliado_id: int, db: Session = Depends(get_db)):
    """Retorna o 'saldo' do afiliado.

    Por enquanto, usamos a soma dos valores dos pedidos na REIN
    como total movimentado. Depois dá para trocar para carteira real.
    """
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
    """Lista pedidos do afiliado (cliente) na REIN.

    Retorna em formato simplificado, já no padrão esperado pelo painel.js:
    - codigoPedido
    - valorTotal
    - dataCriacao
    """
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
        cod = (
            p.get("Codigo")
            or p.get("CodigoPedido")
            or p.get("Id")
            or p.get("intId")
        )
        try:
            val = float(p.get("ValorTotal") or p.get("Valor") or 0)
        except Exception:
            val = 0.0

        data = (
            p.get("DataCriacao")
            or p.get("DataEmissao")
            or p.get("DataCadastro")
            or ""
        )

        saida.append(
            {
                "codigoPedido": cod,
                "valorTotal": val,
                "dataCriacao": data,
            }
        )

    return saida
