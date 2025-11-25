from pydantic import BaseModel, ConfigDict


class UsuarioCreate(BaseModel):
    tipo_pessoa: str          # "PF" ou "PJ"
    cpf_cnpj: str
    nome: str
    email: str
    telefone: str
    cep: str
    endereco: str
    numero: str
    bairro: str
    cidade: str
    estado: str
    senha: str


class LoginRequest(BaseModel):
    email: str
    senha: str


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

    # Integração / segurança
    rein_pessoa_id: int | None = None
    first_login_must_change: bool = False
    ativo: bool = True


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


class PasswordChange(BaseModel):
    senha_atual: str
    senha_nova: str


# 2-etapas de recuperação:
# 1) /recover -> recebe só e-mail
class PasswordRecover(BaseModel):
    email: str


# 2) /reset-password -> recebe token + nova senha
class PasswordReset(BaseModel):
    token: str
    nova_senha: str
