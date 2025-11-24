from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import secrets
import string

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas
from .email_config import send_email  # novo módulo de e-mail

# Garante que as tabelas existam tanto no SQLite quanto no Postgres
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ----------------- HELPERS -----------------


def gerar_senha_aleatoria(tamanho: int = 10) -> str:
    """Gera uma senha aleatória com letras e números."""
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


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
        # Não vamos quebrar o cadastro por erro de e-mail, apenas logar no console
        print(f"[WARN] Erro ao enviar e-mail de boas-vindas: {exc}")


def enviar_email_nova_senha(usuario: Usuario, senha_plana: str) -> None:
    """Envia e-mail com nova senha gerada na recuperação de conta."""
    try:
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Você solicitou a redefinição de senha do seu acesso ao
        <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
        <p>Sua nova senha é:</p>
        <p><strong>{senha_plana}</strong></p>
        <p>Por segurança, após acessar o painel, recomendamos alterar essa senha na área
        <strong>Meus Dados &gt; Alterar Senha</strong>.</p>
        <p>Se você não fez essa solicitação, entre em contato com nossa equipe imediatamente.</p>
        <p>Atenciosamente,<br>Equipe PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Nova senha de acesso - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as exc:
        print(f"[WARN] Erro ao enviar e-mail de recuperação: {exc}")


# ----------------- CADASTRO -----------------


@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """Cadastro de usuário usado pelo cadastro.html.

    URL final: /api/auth/register
    """
    # E-mail duplicado
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    # CPF / CNPJ duplicado
    if db.query(Usuario).filter(Usuario.cpf_cnpj == data.cpf_cnpj).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado")

    # Gera hash da senha informada (cliente novo define a própria senha)
    try:
        senha_hash = pwd_context.hash(data.senha)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar hash: {exc}")

    user = Usuario(
        tipo_pessoa=data.tipo_pessoa,
        cpf_cnpj=data.cpf_cnpj,
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
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # E-mail de boas-vindas (não bloqueia o fluxo se falhar)
    enviar_email_boas_vindas(user)

    return {
        "status": "success",
        "message": "Cadastro realizado com sucesso!",
        "id": user.id,
    }


# ----------------- LOGIN -----------------


@router.post("/login")
def login_user(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Login usado pelo index.html.

    URL final: /api/auth/login
    """
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="E-mail não encontrado")

    if not pwd_context.verify(data.senha, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha inválida")

    # Front só precisa saber que deu certo. Aqui já devolvemos dados básicos.
    return {
        "status": "success",
        "message": "Login realizado com sucesso!",
        "user": {
            "id": user.id,
            "nome": user.nome,
            "email": user.email,
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
    Qualquer tentativa de alteração desses campos deve ser feita via ticket/suporte.
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
    db.commit()
    return {"status": "success", "message": "Senha alterada com sucesso."}


# ----------------- RECUPERAR CONTA (tela de login) -----------------


@router.post("/recover")
def recuperar_conta(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    """
    Fluxo de 'Esqueci minha senha':
    - Recebe apenas o e-mail.
    - Gera uma nova senha aleatória.
    - Atualiza o hash no banco.
    - Envia a nova senha por e-mail.
    """
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        # Para não dar dica se o e-mail existe ou não, pode devolver a mesma mensagem.
        raise HTTPException(status_code=404, detail="E-mail não encontrado")

    nova_senha_plana = gerar_senha_aleatoria()
    user.senha_hash = pwd_context.hash(nova_senha_plana)
    db.commit()

    enviar_email_nova_senha(user, nova_senha_plana)

    return {
        "status": "success",
        "message": "Se o e-mail estiver cadastrado, uma nova senha foi enviada.",
    }


# ----------------- STUBS PARA PAINEL (placeholders) -----------------


@router.get("/pedidos/{afiliado_id}")
def listar_pedidos(afiliado_id: int):
    """Stub para no futuro listar pedidos de um afiliado."""
    return []


@router.get("/saldo/{afiliado_id}")
def saldo_afiliado(afiliado_id: int):
    """Stub para no futuro mostrar o saldo do afiliado."""
    return {"total": 0.0}
