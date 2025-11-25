from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)

    # Dados cadastrais principais
    tipo_pessoa = Column(String, nullable=False)  # 'PF' ou 'PJ'
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
    ativo = Column(Boolean, default=True)

    # Integração com a Rein (Pessoa)
    rein_pessoa_id = Column(Integer, index=True, nullable=True)

    # Fluxo de segurança
    first_login_must_change = Column(Boolean, default=False)  # para quem já era cliente no ERP
    reset_token = Column(String, unique=True, index=True, nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    # Auditoria
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
