# email_config.py
import os
import ssl
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 465  # SSL
SMTP_USER = "afiliados@pegdobrasil.com.br"
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD")  # defina no Railway

FROM_NAME = "Painel de Afiliados - PEG do Brasil"
FROM_EMAIL = SMTP_USER  # remetente padrão


def send_email(to_email: str, subject: str, html_body: str) -> None:
    """
    Envia um e-mail HTML usando o SMTP da Hostinger.
    Lança exceção se algo der errado.
    """
    if not SMTP_PASSWORD:
        raise RuntimeError(
            "Variável de ambiente EMAIL_PASSWORD não definida no servidor."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg.set_content(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
