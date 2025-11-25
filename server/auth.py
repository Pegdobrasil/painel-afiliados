from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import string

from . import models, schemas
from .database import get_db, SessionLocal
from .security import create_access_token, verify_password, get_password_hash
from .email_config import send_email
from .rein_client import get_or_create_pessoa_rein, buscar_pessoa_por_documento


# URL da tela de reset de senha no front
FRONT_RESET_URL = "https://pegdobrasil.github.io/painel-afiliados/reset_senha.html"

# Garante que as tabelas existam
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ----------------- HELPERS -----------------


def gerar_senha_aleatoria(tamanho: int = 10) -> str:
    """Gera uma senha aleatória com letras e números."""
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def enviar_email_boas_vindas(usuario: Usuario) -> None:
    """E-mail de boas-vindas após cadastro (cliente novo criado na Rein)."""
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


def enviar_email_senha_temporaria(usuario: Usuario, senha_plana: str) -> None:
    """E-mail com senha temporária (cliente que já existia no ERP)."""
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Identificamos que você já possuía cadastro como cliente em nosso sistema.</p>
        <p>Criamos seu acesso ao <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
        <p>Seus dados de acesso são:</p>
        <p><strong>Usuário:</strong> {usuario.email}<br>
        <strong>Senha temporária:</strong> {senha_plana}</p>
        <p>Por segurança, ao acessar o painel você será solicitado a alterar essa senha.</p>
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


def enviar_email_link_redefinicao(usuario: Usuario, token: str) -> None:
    """E-mail com link para redefinir senha (esqueci minha senha)."""
    try:
        link = f"{FRONT_RESET_URL}?token={token}"
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Você solicitou a redefinição de senha do seu acesso ao
        <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
        <p>Para criar uma nova senha, clique no link abaixo:</p>
        <p><a href="{link}" target="_blank">{link}</a></p>
        <p>Se você não fez essa solicitação, ignore este e-mail.</p>
        <p>Atenciosamente,<br>Equipe PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Redefinição de senha - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as exc:
        print(f"[WARN] Erro ao enviar e-mail de redefinição: {exc}")


# ----------------- CADASTRO (com Rein) -----------------


@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """
    Cadastro usado pelo cadastro.html.

    Regras:
    - Se CPF/CNPJ já existir COMO USUÁRIO do painel, bloqueia.
    - Se CPF/CNPJ existir na Rein e ainda não existir no painel:
        -> cria usuário com senha aleatória,
        -> manda por e-mail,
        -> marca first_login_must_change = True.
    - Se não existir Pessoa na Rein:
        -> cria Pessoa na Rein,
        -> usa a senha escolhida pelo afiliado normalmente.
    """

    # Normalizar CPF/CNPJ (só dígitos)
    documento = "".join(filter(str.isdigit, data.cpf_cnpj))
    tipo_pessoa = data.tipo_pessoa.upper()

    # 1) Já existe no painel (CPF/CNPJ ou e-mail)?
    usuario_existente = (
        db.query(Usuario)
        .filter(
            (Usuario.cpf_cnpj == documento) | (Usuario.email == data.email)
        )
        .first()
    )
    if usuario_existente:
        raise HTTPException(
            status_code=400,
            detail="Já existe um cadastro com este CPF/CNPJ ou e-mail.",
        )

    # 2) Ver se já existe Pessoa na Rein
    try:
        pessoa_existente = buscar_pessoa_por_documento(
            cpf_cnpj=documento,
            tipo_pessoa=tipo_pessoa,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao consultar cliente na Rein: {exc}",
        )

    # 2.1) Já tem cadastro no ERP, mas ainda não no painel
    if pessoa_existente:
        senha_temp = gerar_senha_aleatoria()
        try:
            senha_hash = pwd_context.hash(senha_temp)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Erro ao gerar hash: {exc}")

        pessoa_id = (
            pessoa_existente.get("Id")
            or pessoa_existente.get("intId")
            or pessoa_existente.get("id")
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
            rein_pessoa_id=int(pessoa_id) if pessoa_id else None,
            first_login_must_change=True,
            ativo=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        enviar_email_senha_temporaria(user, senha_temp)

        return {
            "status": "success",
            "message": "Cadastro vinculado ao cliente já existente na Rein. Senha temporária enviada por e-mail.",
            "id": user.id,
        }

    # 2.2) Não existe Pessoa na Rein -> cria Pessoa nova e usa a senha escolhida
    try:
        pessoa_id = get_or_create_pessoa_rein(
            {
                "tipo_pessoa": tipo_pessoa,
                "cpf_cnpj": documento,
                "nome": data.nome,
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar cliente na Rein: {exc}",
        )

    try:
        senha_hash = pwd_context.hash(data.senha)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar hash: {exc}")

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
        ativo=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    enviar_email_boas_vindas(user)

    return {
        "status": "success",
        "message": "Cadastro realizado com sucesso!",
        "id": user.id,
    }


# ----------------- LOGIN -----------------


@router.post("/login")
def login_user(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Login usado pelo index.html (/api/auth/login)."""
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="E-mail não encontrado")

    if not user.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo no painel.")

    if not pwd_context.verify(data.senha, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha inválida")

    return {
        "status": "success",
        "message": "Login realizado com sucesso!",
        "user": {
            "id": user.id,
            "nome": user.nome,
            "email": user.email,
            "rein_pessoa_id": user.rein_pessoa_id,
            "first_login_must_change": user.first_login_must_change,
        },
    }


# ----------------- LISTA / ADMIN -----------------


@router.get("/users", response_model=list[schemas.UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).all()


@router.get("/user/{user_id}", response_model=schemas.UsuarioOut)
def obter_usuario(user_id: int, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@router.put("/user/{user_id}", response_model=schemas.UsuarioOut)
def atualizar_usuario(
    user_id: int,
    data: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
):
    """
    Atualização de dados do afiliado.

    OBS: CPF/CNPJ e e-mail NÃO podem ser alterados aqui.
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Bloqueia alteração de e-mail
    if data.email and data.email != user.email:
        raise HTTPException(
            status_code=400,
            detail="E-mail não pode ser alterado pelo painel. Abra um ticket com o suporte.",
        )

    # Bloqueia alteração de CPF/CNPJ
    if data.cpf_cnpj and data.cpf_cnpj != user.cpf_cnpj:
        raise HTTPException(
            status_code=400,
            detail="CPF/CNPJ não pode ser alterado pelo painel. Abra um ticket com o suporte.",
        )

    if data.tipo_pessoa is not None:
        user.tipo_pessoa = data.tipo_pessoa
    if data.nome is not None:
        user.nome = data.nome
    if data.telefone is not None:
        user.telefone = data.telefone
    if data.cep is not None:
        user.cep = data.cep
    if data.endereco is not None:
        user.endereco = data.endereco
    if data.numero is not None:
        user.numero = data.numero
    if data.bairro is not None:
        user.bairro = data.bairro
    if data.cidade is not None:
        user.cidade = data.cidade
    if data.estado is not None:
        user.estado = data.estado

    db.commit()
    db.refresh(user)
    return user


# ----------------- ALTERAR SENHA (dentro do painel) -----------------


@router.post("/change-password/{user_id}")
def alterar_senha(
    user_id: int,
    data: schemas.PasswordChange,
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if not pwd_context.verify(data.senha_atual, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    user.senha_hash = pwd_context.hash(data.senha_nova)
    user.first_login_must_change = False  # se era primeiro acesso, libera de vez
    db.commit()
    return {"status": "success", "message": "Senha alterada com sucesso."}


# ----------------- RECUPERAR CONTA (tela de login) -----------------


@router.post("/recover")
def solicitar_recuperacao(data: schemas.PasswordRecover, db: Session = Depends(get_db)):
    """
    Etapa 1: 'Esqueci minha senha'
    - Recebe apenas o e-mail.
    - Gera um token temporário.
    - Salva no banco com validade.
    - Envia link por e-mail.
    """
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        # Opcional: devolver mensagem genérica para não revelar se o e-mail existe.
        raise HTTPException(status_code=404, detail="E-mail não encontrado")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    user.reset_token = token
    user.reset_token_expires_at = expires_at
    db.commit()

    enviar_email_link_redefinicao(user, token)

    return {
        "status": "success",
        "message": "Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha.",
    }


@router.post("/reset-password")
def reset_password(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    """
    Etapa 2: redefinir senha usando o token enviado por e-mail.
    - Recebe token + nova senha.
    - Valida token e expiração.
    - Atualiza a senha e limpa o token.
    """
    user = db.query(Usuario).filter(Usuario.reset_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Token inválido ou já utilizado.")

    if not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        # Limpa token expirado
        user.reset_token = None
        user.reset_token_expires_at = None
        db.commit()
        raise HTTPException(status_code=400, detail="Token expirado. Solicite uma nova redefinição.")

    user.senha_hash = pwd_context.hash(data.nova_senha)
    user.reset_token = None
    user.reset_token_expires_at = None
    user.first_login_must_change = False
    db.commit()

    return {"status": "success", "message": "Senha redefinida com sucesso."}


# ----------------- STUBS PARA PAINEL (pedidos/saldo) -----------------


@router.get("/pedidos/{afiliado_id}")
def listar_pedidos(afiliado_id: int):
    """
    Stub para, no futuro, integrar com /api/v1/pedido da Rein
    usando CodOrigem = 20, CodVendedor = 457 e a condição de pagamento do JSON.
    """
    return []


@router.get("/saldo/{afiliado_id}")
def saldo_afiliado(afiliado_id: int):
    """Stub para no futuro mostrar o saldo do afiliado."""
    return {"total": 0.0}
