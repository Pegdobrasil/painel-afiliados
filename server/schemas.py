from pydantic import BaseModel


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

    class Config:
        orm_mode = True


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
