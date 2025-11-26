from pydantic import BaseModel, ConfigDict


# ===========================
#  MODELOS DE USUÁRIO
# ===========================
class UsuarioCreate(BaseModel):
    tipo_pessoa: str
    cpf_cnpj: str
    nome: str
    email: str
    telefone: str | None = None  # agora opcional
    cep: str
    endereco: str
    numero: str
    bairro: str
    cidade: str
    estado: str
    senha: str

class ChangePasswordToken(BaseModel):
    token: str
    nova_senha: str

class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_pessoa: str
    cpf_cnpj: str
    nome: str
    email: str
    telefone: str | None = None
    cep: str | None = None
    endereco: str | None = None
    numero: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None


class UsuarioUpdate(BaseModel):
    tipo_pessoa: str | None = None
    cpf_cnpj: str | None = None
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    cep: str | None = None
    endereco: str | None = None
    numero: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None


# ===========================
# LOGIN
# ===========================
class Login(BaseModel):
    email: str
    senha: str


# ===========================
# PRIMEIRO ACESSO (TROCA DE SENHA)
# ===========================
class ChangePassword(BaseModel):
    user_id: int
    nova_senha: str


# ===========================
# RESET DE SENHA (OPCIONAL)
# ===========================
class PasswordReset(BaseModel):
    email: str
    nova_senha: str
