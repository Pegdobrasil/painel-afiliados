from sqlalchemy import Column, Integer, String, Boolean
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)

    # Dados cadastrais
    tipo_pessoa = Column(String, nullable=False)  # "PF" ou "PJ"
    cpf_cnpj = Column(String, unique=True, nullable=False, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    telefone = Column(String)
    cep = Column(String)
    endereco = Column(String)
    numero = Column(String)
    bairro = Column(String)
    cidade = Column(String)
    estado = Column(String)

    # Autenticação
    senha_hash = Column(String, nullable=False)

    # Integração com a Rein
    rein_pessoa_id = Column(Integer, index=True, nullable=True)

    # Fluxo de segurança
    first_login_must_change = Column(Boolean, default=False)
