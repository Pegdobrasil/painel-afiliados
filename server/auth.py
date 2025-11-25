from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import secrets
import string

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas
from .email_config import send_email
from .rein_client import buscar_pessoa_por_documento, get_or_create_pessoa_rein

# Garante que as tabelas existam
Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ----------------- HELPERS -----------------


def gerar_senha_aleatoria(tamanho: int = 10) -> str:
    """Gera uma senha aleatória com letras e números."""
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def enviar_email_boas_vindas(usuario: Usuario, mensagem_extra: str | None = None) -> None:
    """E-mail de boas-vindas após cadastro de afiliado."""
    try:
        extra = mensagem_extra or ""
        html = f"""
        <p>Olá, {usuario.nome}!</p>
        <p>Seu cadastro no <strong>Painel de Afiliados PEG do Brasil</strong> foi realizado com sucesso.</p>
        <p>Você já pode acessar o painel usando este e-mail na tela de login.</p>
        {extra}
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
        <p>Conforme solicitado, geramos uma nova senha para o seu acesso ao
        <strong>Painel de Afiliados PEG do Brasil</strong>.</p>
        <p><strong>Nova senha:</strong> {senha_plana}</p>
        <p>Por segurança, recomendamos que você altere essa senha após o primeiro acesso.</p>
        <p>Se você não fez essa solicitação, responda este e-mail imediatamente.</p>
        <p>Atenciosamente,<br>Equipe PEG do Brasil</p>
        """
        send_email(
            to_email=usuario.email,
            subject="Nova senha - Painel de Afiliados PEG do Brasil",
            html_body=html,
        )
    except Exception as exc:
        print(f"[WARN] Erro ao enviar e-mail de nova senha: {exc}")


# ----------------- CADASTRO (REGISTER) -----------------


@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    """
    Cadastro do afiliado.

    Lógica:
    1. Normaliza CPF/CNPJ.
    2. Verifica se já existe usuário no painel (CPF ou e-mail).
    3. Faz GET na Rein por CPF/CNPJ:
       - Se achar Pessoa:
           - Se ainda não existir usuário no painel, cria usuário vinculado
             à Pessoa da Rein e usa a senha informada.
             Marca first_login_must_change = True.
       - Se não achar Pessoa:
           - Cria Pessoa na Rein e depois cria usuário no painel
             com a senha informada e first_login_must_change = False.
    """

    # Normaliza CPF/CNPJ
    documento = "".join(filter(str.isdigit, data.cpf_cnpj))
    tipo_pessoa = (data.tipo_pessoa or "").upper()

    # 1) Já existe usuário no painel (e-mail)?
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado.",
        )

    # 2) Já existe usuário no painel (CPF/CNPJ)?
    if db.query(Usuario).filter(Usuario.cpf_cnpj == documento).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF/CNPJ já cadastrado.",
        )

    # 3) Gera hash da senha escolhida
    try:
        senha_hash = pwd_context.hash(data.senha)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar hash da senha: {exc}",
        )

    # 4) Consulta Pessoa na Rein pelo documento
    try:
        pessoa_existente = buscar_pessoa_por_documento(
            cpf_cnpj=documento,
            tipo_pessoa=tipo_pessoa,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar cliente na Rein: {exc}",
        )

    # 4A) Pessoa já existe na Rein → cria usuário vinculado, marcando first_login_must_change
    if pessoa_existente:
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
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        enviar_email_boas_vindas(
            user,
            mensagem_extra="<p>Identificamos que você já possuía cadastro como cliente em nossa loja e vinculamos seu acesso ao Painel de Afiliados.</p>",
        )

        return {
            "status": "success",
            "message": "Cadastro vinculado ao cliente já existente na Rein.",
            "id": user.id,
        }

    # 4B) Pessoa NÃO existe na Rein → cria Pessoa nova e depois o usuário
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar cliente na Rein: {exc}",
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


# ----------------- LOGIN -----------------


@router.post("/login")
def login_user(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    """
    Login usado pelo index.html.

    Resposta já no formato que o auth.js espera:
    {
      "id": ...,
      "nome": "...",
      "email": "...",
      "first_login_must_change": false
    }
    """
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="E-mail não encontrado")

    if not pwd_context.verify(data.senha, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha inválida")

    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "first_login_must_change": getattr(user, "first_login_must_change", False),
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
    Atualização de dados cadastrais (exceto e-mail e CPF/CNPJ).
    """
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Bloqueia alteração de e-mail
    if data.email and data.email != user.email:
        raise HTTPException(
            status_code=400,
            detail="E-mail não pode ser alterado pelo painel.",
        )

    # Bloqueia alteração de CPF/CNPJ
    if data.cpf_cnpj and data.cpf_cnpj != user.cpf_cnpj:
        raise HTTPException(
            status_code=400,
            detail="CPF/CNPJ não pode ser alterado pelo painel.",
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
    user.first_login_must_change = False
    db.commit()

    return {"status": "success", "message": "Senha alterada com sucesso."}


# ----------------- RECUPERAR CONTA (tela de login) -----------------


@router.post("/recover")
def recuperar_conta(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    """
    Fluxo simplificado de 'Esqueci minha senha':
    - Recebe e-mail e nova senha (como está hoje no auth.js).
    - Atualiza a senha e envia um e-mail avisando.
    """
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="E-mail não encontrado")

    user.senha_hash = pwd_context.hash(data.nova_senha)
    user.first_login_must_change = False
    db.commit()

    enviar_email_nova_senha(user, data.nova_senha)

    return {
        "status": "success",
        "message": "Senha redefinida com sucesso.",
    }


# ----------------- STUBS PARA PAINEL -----------------


@router.get("/pedidos/{afiliado_id}")
def listar_pedidos(afiliado_id: int):
    """Stub para, no futuro, listar pedidos da Rein para o afiliado."""
    return []


@router.get("/saldo/{afiliado_id}")
def saldo_afiliado(afiliado_id: int):
    """Stub para, no futuro, mostrar o saldo do afiliado."""
    return {"total": 0.0}
