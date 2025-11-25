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


@router.post("/register", response_model=schemas.UsuarioOut)
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """Cadastro de afiliado.

    Fluxo:
    - Normaliza CPF/CNPJ
    - Verifica se já existe usuário com mesmo e-mail ou documento
    - Consulta Pessoa na REIN
        - se existir, reaproveita e vincula rein_pessoa_id
        - se não existir, cria Pessoa na REIN
    - Cria usuário local com senha escolhida no formulário
    """
    documento = "".join(filter(str.isdigit, data.cpf_cnpj or ""))
    tipo_pessoa = (data.tipo_pessoa or "").upper()

    if not documento:
        raise HTTPException(status_code=400, detail="CPF/CNPJ inválido.")

    # E-mail duplicado
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    # CPF / CNPJ duplicado
    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado.")

    # Consulta Pessoa na REIN
    try:
        pessoa = rein_client.buscar_pessoa_por_documento(
            cpf_cnpj=documento,
            tipo_pessoa=tipo_pessoa,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao consultar cliente na REIN: {e}",
        )

    if pessoa:
        # Já existe cliente na REIN → reaproveita
        pessoa_id = pessoa.get("Id") or pessoa.get("intId") or pessoa.get("id")
        if not pessoa_id:
            raise HTTPException(
                status_code=500,
                detail="Cliente encontrado na REIN sem ID válido.",
            )
        rein_pessoa_id = int(pessoa_id)
    else:
        # Não existe → cria novo cliente na REIN
        try:
            rein_pessoa_id = rein_client.get_or_create_pessoa_rein(
                {
                    "tipo_pessoa": tipo_pessoa,
                    "cpf_cnpj": documento,
                    "nome": data.nome,
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao criar cliente na REIN: {e}",
            )

    # Cria usuário local
    senha_hash = _hash_password(data.senha)

    novo = Usuario(
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
        rein_pessoa_id=rein_pessoa_id,
        first_login_must_change=False,
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    enviar_email_boas_vindas(novo)

    return novo


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
