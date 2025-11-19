from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .database import get_db, Base, engine
from .models import Usuario
from . import schemas

Base.metadata.create_all(bind=engine)

router = APIRouter()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# -------- CADASTRO --------
@router.post("/register")
def register_user(data: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    if db.query(Usuario).filter(Usuario.cpf_cnpj == data.cpf_cnpj).first():
        raise HTTPException(status_code=400, detail="CPF/CNPJ já cadastrado")

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

    return {
        "status": "success",
        "message": "Cadastro realizado com sucesso!",
        "id": user.id,
    }


# -------- LOGIN --------
@router.post("/login")
def login_user(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="E-mail não encontrado")

    if not pwd_context.verify(data.senha, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha inválida")

    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
    }


# -------- LISTA / ADMIN --------
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
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if data.email and data.email != user.email:
        if db.query(Usuario).filter(Usuario.email == data.email).first():
            raise HTTPException(status_code=400, detail="E-mail já está em uso")
        user.email = data.email

    if data.cpf_cnpj and data.cpf_cnpj != user.cpf_cnpj:
        if db.query(Usuario).filter(Usuario.cpf_cnpj == data.cpf_cnpj).first():
            raise HTTPException(status_code=400, detail="CPF/CNPJ já está em uso")
        user.cpf_cnpj = data.cpf_cnpj

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


# -------- ALTERAR SENHA (dentro do painel) --------
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


# -------- RECUPERAR CONTA (tela de login) --------
@router.post("/recover")
def recuperar_conta(data: schemas.PasswordReset, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="E-mail não encontrado")

    user.senha_hash = pwd_context.hash(data.nova_senha)
    db.commit()
    return {"status": "success", "message": "Senha redefinida com sucesso."}


# -------- STUBS PARA PAINEL --------
@router.get("/pedidos/{afiliado_id}")
def listar_pedidos(afiliado_id: int):
    return []


@router.get("/saldo/{afiliado_id}")
def saldo_afiliado(afiliado_id: int):
    return {"total": 0.0}
