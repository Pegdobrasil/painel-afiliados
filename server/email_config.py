# server/email_config.py -- Brevo API (100% funcional no Railway)

import os
import requests

# Pegamos a key do Railway
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

# Remetente do e-mail
FROM_EMAIL = "afiliados@pegdobrasil.com.br"
FROM_NAME = "Painel de Afiliados - PEG do Brasil"

# Cópia automática
COPIA_EMAIL = "contato@pegdobrasil.com.br"


def send_email(to_email: str, subject: str, html_body: str) -> None:
    """
    Envia e-mail usando a API HTTP da Brevo.
    Totalmente compatível com Railway (não usa SMTP).
    """
    if not BREVO_API_KEY:
        print("[BREVO] ERRO: BREVO_API_KEY não configurado no Railway.")
        return

    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {
            "name": FROM_NAME,
            "email": FROM_EMAIL
        },
        "to": [
            {"email": to_email}
        ],
        "cc": [
            {"email": COPIA_EMAIL}
        ],
        "subject": subject,
        "htmlContent": html_body
    }

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"[BREVO] status={resp.status_code} envio_para={to_email}")
        print(resp.text[:500])
    except Exception as e:
        print(f"[BREVO] ERRO ao enviar e-mail: {e}")
