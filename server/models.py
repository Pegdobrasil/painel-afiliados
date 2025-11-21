from sqlalchemy import Column, Integer, String
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    tipo_pessoa = Column(String, nullable=False)
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
    senha_hash = Column(String, nullable=False)
