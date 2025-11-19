from pydantic import BaseModel, ConfigDict


class UsuarioCreate(BaseModel):
    tipo_pessoa: str
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


class PasswordReset(BaseModel):
    email: str
    nova_senha: str
