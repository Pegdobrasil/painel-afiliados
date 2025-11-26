from typing import Optional
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
    telefone: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None
    rein_pessoa_id: Optional[int] = None
    first_login_must_change: bool = False


class UsuarioUpdate(BaseModel):
    tipo_pessoa: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    bairro: Optional[str] = None
    cidade: Optional[str] = None
    estado: Optional[str] = None


class PasswordChange(BaseModel):
    senha_atual: str
    senha_nova: str


class PasswordReset(BaseModel):
    email: str
    nova_senha: str
    class ChangePassword(BaseModel):
    user_id: int
    nova_senha: str

class Login(BaseModel):
    email: str
    senha: str

