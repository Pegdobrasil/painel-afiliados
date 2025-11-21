# -*- coding: utf-8 -*-
from pathlib import Path
import time, hmac, hashlib, requests, shutil

# ===== MAGAZORD (compat com seu app.py) =====
BASE_URL = "https://pegdobrasil.painel.magazord.com.br/api/v2/site"
USERNAME = "MZDKe88bdab8de6a3e2dd6a0d245e79ac01bed40f875c356b5bc675d6524a701"
PASSWORD = "I%w$CEf2Rya0"
AUTH = requests.auth.HTTPBasicAuth(USERNAME, PASSWORD)
HEADERS_MAGAZORD = {"Content-Type": "application/json"}

# ===== Estrutura de pastas =====
BASE_DIR = Path(__file__).resolve().parent
DIR_CACHE      = BASE_DIR / "Cache"
DIR_ETIQUETAS  = BASE_DIR / "Etiquetas"
DIR_MOVIMENTOS = BASE_DIR / "Movimentos"
DIR_STATIC     = BASE_DIR / "static"
DIR_TEMPLATES  = BASE_DIR / "templates"
for d in [DIR_CACHE, DIR_ETIQUETAS, DIR_MOVIMENTOS, DIR_STATIC, DIR_TEMPLATES]:
    d.mkdir(parents=True, exist_ok=True)

def file_path(kind: str, name: str) -> Path:
    m = {"cache":DIR_CACHE, "etiqueta":DIR_ETIQUETAS, "mov":DIR_MOVIMENTOS,
         "static":DIR_STATIC, "templates":DIR_TEMPLATES, "root":BASE_DIR}
    base = m.get(kind)
    if not base: raise ValueError(f"kind inválido: {kind}")
    p = base / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

# arquivos esperados por scripts antigos no raiz (mantém espelho)
CRITICOS = {
    "pedidos.json":                 DIR_CACHE / "pedidos.json",
    "pedidos_movimento.json":       DIR_MOVIMENTOS / "pedidos_movimento.json",
    "motoboy_pedidos.json":         DIR_MOVIMENTOS / "motoboy_pedidos.json",
    "cache_detalhes_pedidos.json":  DIR_CACHE / "cache_detalhes_pedidos.json",
    "log_historico.csv":            DIR_MOVIMENTOS / "log_historico.csv",
}
def compat_write(name: str) -> Path:
    dst = CRITICOS.get(name, BASE_DIR / name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    return dst
def compat_mirror_to_root(name: str):
    if name in CRITICOS and CRITICOS[name].exists():
        try: shutil.copy2(CRITICOS[name], BASE_DIR / name)
        except Exception: pass

# ===== REIN (HMAC) =====
REIN_BASE = "https://api.rein.net.br"
REIN_CLIENT_ID = "7e49-e62a-a2c6-cc84"
REIN_CLIENT_SECRET = "1a5a9c0e681c42a4944d911ee0c5b9be16274d38eb90986a33e3f4dc119f47c3"
REIN_DATABASE = "pegdobrasil"

def rein_headers(endpoint_path: str) -> dict:
    """
    endpoint_path deve ser EXATAMENTE o caminho do serviço:
      - "/api/v1/produto"               (lista)
      - f"/api/v1/produto/{id}"         (detalhe)
    """
    ts = int(time.time()) + 300
    payload = f"{endpoint_path}.{REIN_DATABASE}.{ts}"
    token = hmac.new(REIN_CLIENT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return {
        "Token": token, "Database": REIN_DATABASE,
        "Timestamp": str(ts), "ClientId": REIN_CLIENT_ID,
        "Accept": "application/json"
    }

# Imagem por SKU
REIN_CDN_VERSION = "6.5.3"
def rein_image_url(sku: str) -> str:
    sku = str(sku).strip()
    return f"https://cdn.rein.net.br/app/core/{REIN_DATABASE}/{REIN_CDN_VERSION}/publico/imagem/produto/{sku}.jpg"

# === Usuários & Uploads ===
from pathlib import Path
DIR_USUARIOS = BASE_DIR / "Usuarios"
DIR_USUARIOS.mkdir(parents=True, exist_ok=True)
DIR_UPLOADS = DIR_USUARIOS / "_uploads"
DIR_UPLOADS.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTS = {"png","jpg","jpeg","webp","gif"}
def allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_IMAGE_EXTS
