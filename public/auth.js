// ===============================
// CONFIG: URL base da sua API backend
// (depois vamos subir isso em Render / Railway / etc.)
const API_BASE = "https://SEU_BACKEND_URL/api";
// ===============================

const SESSION_KEY = "painel_afiliado_token";

// -------------------------------
// Helper: pegar valor de input
// -------------------------------
function v(id) {
  return document.getElementById(id).value.trim();
}

// -------------------------------
// CADASTRO
// -------------------------------
async function registrar() {
  const payload = {
    tipo_pessoa: v("tipo_pessoa"),
    cpf_cnpj: v("cpf_cnpj").replace(/\D/g, ""),
    nome: v("nome"),
    email: v("email"),
    senha: v("senha"),
    telefone: v("telefone"),
    cep: v("cep").replace(/\D/g, ""),
    logradouro: v("logradouro"),
    numero: v("numero"),
    complemento: v("complemento"),
    bairro: v("bairro"),
    cidade: v("cidade"),
    uf: v("uf").toUpperCase()
  };

  // validações básicas
  if (!payload.nome || !payload.email || !payload.senha) {
    alert("Preencha nome, email e senha.");
    return;
  }

  if (payload.cpf_cnpj.length !== 11 && payload.cpf_cnpj.length !== 14) {
    alert("CPF/CNPJ deve ter 11 ou 14 dígitos.");
    return;
  }

  if (payload.cep.length !== 8) {
    alert("CEP deve ter 8 dígitos.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || "Erro ao cadastrar.");
      return;
    }

    alert("Cadastro realizado com sucesso! Faça login para entrar.");
    window.location.href = "index.html";

  } catch (e) {
    console.error(e);
    alert("Falha na comunicação com o servidor.");
  }
}

// -------------------------------
// LOGIN
// -------------------------------
async function login() {
  const email = v("email");
  const senha = v("senha");

  if (!email || !senha) {
    alert("Informe email e senha.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({email, senha})
    });

    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || "Login inválido.");
      return;
    }

    // salva token JWT
    localStorage.setItem(SESSION_KEY, data.access_token);
    window.location.href = "painel.html";

  } catch (e) {
    console.error(e);
    alert("Erro ao conectar com o servidor.");
  }
}

// -------------------------------
// LOGOUT
// -------------------------------
function logout() {
  localStorage.removeItem(SESSION_KEY);
  window.location.href = "index.html";
}

// -------------------------------
// PROTEGE PÁGINAS INTERNAS
// (chamar em painel.html, settings.html etc.)
// -------------------------------
function requerLogin() {
  const token = localStorage.getItem(SESSION_KEY);
  if (!token) {
    window.location.href = "index.html";
  }
  return token;
}

// -------------------------------
// CEP -> ViaCEP
// -------------------------------
async function buscarCep() {
  let cep = v("cep").replace(/\D/g, "");
  if (cep.length !== 8) {
    return;
  }

  try {
    const res = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
    const data = await res.json();

    if (data.erro) {
      alert("CEP não encontrado.");
      return;
    }

    document.getElementById("logradouro").value = data.logradouro || "";
    document.getElementById("bairro").value = data.bairro || "";
    document.getElementById("cidade").value = data.localidade || "";
    document.getElementById("uf").value = data.uf || "";

  } catch (e) {
    console.error(e);
    alert("Erro ao consultar CEP.");
  }
}
