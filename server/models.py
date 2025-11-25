from sqlalchemy import Column, Integer, String, Boolean
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)

    # Dados
    tipo_pessoa = Column(String, nullable=False)
    cpf_cnpj = Column(String, nullable=False, unique=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)

    telefone = Column(String, nullable=True)
    cep = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    numero = Column(String, nullable=True)
    bairro = Column(String, nullable=True)
    cidade = Column(String, nullable=True)
    estado = Column(String, nullable=True)

    # Login
    senha_hash = Column(String, nullable=False)

    # Integração Rein
    rein_pessoa_id = Column(Integer, nullable=True, index=True)

    # Primeiro acesso
    first_login_must_change = Column(Boolean, default=False)
