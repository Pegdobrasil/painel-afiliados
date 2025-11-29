import os
import ssl
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 465  # SSL
SMTP_USER = "afiliados@pegdobrasil.com.br"
SMTP_PASSWORD = os.getenv("EMAIL_PASSWORD")

FROM_NAME = "Painel de Afiliados - PEG do Brasil"
FROM_EMAIL = SMTP_USER

# e-mail que sempre receberá cópia
COPIA_EMAIL = "contato@pegdobrasil.com.br"


def send_email(to_email: str, subject: str, html_body: str) -> None:
    """
    Envia e-mail via SMTP (Hostinger).

    - Para: to_email (usuário)
    - Cc:   contato@pegdobrasil.com.br
    """
    if not SMTP_PASSWORD:
        print(
            "[WARN] EMAIL_PASSWORD não definida. "
            "E-mail não será enviado, apenas logado."
        )
        print(f"[DEBUG] To={to_email} | Assunto={subject}")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    msg["To"] = to_email
    msg["Cc"] = COPIA_EMAIL  # cópia em todos os envios

    msg.set_content(html_body, subtype="html")

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[INFO] E-mail enviado para {to_email} (Cc: {COPIA_EMAIL}) - {subject}.")
    except Exception as e:
        print(f"[WARN] Falha ao enviar e-mail via SMTP: {e}")
        print(f"[DEBUG] To={to_email} | Assunto={subject}")
