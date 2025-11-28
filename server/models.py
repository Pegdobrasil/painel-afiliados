from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .database import Base
from datetime import datetime


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

    # Flag futura de segurança (primeiro acesso obrigatório trocar senha)
    first_login_must_change = Column(Boolean, default=False)

    # Novo: controle de ativação da conta (e-mail)
    ativo = Column(Boolean, default=False)

    # Token de verificação enviado por e-mail (primeiro acesso)
    verification_token = Column(String, nullable=True, index=True)
    verification_token_expires_at = Column(DateTime, nullable=True)

    # Opcional: token de sessão / API por usuário
    api_token = Column(String, nullable=True, index=True)
