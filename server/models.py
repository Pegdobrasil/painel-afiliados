# server/models.py
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)

    # Dados cadastrais principais
    tipo_pessoa = Column(String, nullable=False)  # 'PF' ou 'PJ'
    cpf_cnpj = Column(String, unique=True, nullable=False, index=True)

    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    telefone = Column(String, nullable=True)

    cep = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    numero = Column(String, nullable=True)
    bairro = Column(String, nullable=True)
    cidade = Column(String, nullable=True)
    estado = Column(String, nullable=True)

    # Autenticação
    senha_hash = Column(String, nullable=False)

    # Integração com a Rein (Pessoa / Cliente)
    rein_pessoa_id = Column(Integer, nullable=True, index=True)

    # Primeiro acesso obrigatório trocar senha (se quiser usar no futuro)
    first_login_must_change = Column(Boolean, default=False)

    # Flag manual de bloqueio de usuário (já é usada no login, se existir)
    ativo = Column(Boolean, default=True)

    # Token de reset de senha (já referenciado no auth.py)
    reset_token = Column(String, nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    # Timestamps básicos (opcional)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AccessToken(Base):
    """
    Token de acesso do afiliado, enviado por e-mail.

    Regras:
    - Um usuário pode ter vários tokens (ex.: reenvio de link).
    - Só navega no painel se tiver pelo menos UM token ativo e não expirado.
    """

    __tablename__ = "usuario_access_tokens"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), index=True, nullable=False)

    token = Column(String, unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=False)  # vira True quando o link é clicado
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # pode ser None para não expirar

    usuario = relationship("Usuario", backref="access_tokens")
