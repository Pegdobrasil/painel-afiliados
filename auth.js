// ===============================
// CONFIG API BACKEND
// ===============================

const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// ===============================
// HELPERS
// ===============================

function v(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

function notify(msg) {
  alert(msg);
}

function onlyDigits(str) {
  return (str || "").replace(/\D/g, "");
}

// ===============================
// BUSCA CEP VIACEP
// ===============================

async function buscarCep() {
  const cep = onlyDigits(v("cep"));
  if (cep.length !== 8) return;

  try {
    const res = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
    const data = await res.json();

    if (data.erro) {
      notify("CEP não encontrado.");
      return;
    }

    document.getElementById("logradouro").value = data.logradouro || "";
    document.getElementById("bairro").value = data.bairro || "";
    document.getElementById("cidade").value = data.localidade || "";
    document.getElementById("uf").value = (data.uf || "").toUpperCase();

  } catch (err) {
    console.error(err);
    notify("Não foi possível consultar o CEP.");
  }
}

// ===============================
// CADASTRO
// ===============================

async function registrar() {
  const payload = {
    tipo_pessoa: v("tipo_pessoa"),
    cpf_cnpj: onlyDigits(v("cpf_cnpj")),
    nome: v("nome"),
    email: v("email"),
    telefone: v("telefone"),
    cep: onlyDigits(v("cep")),
    endereco: (() => {
      const lg = v("logradouro");
      const cp = v("complemento");
      return cp ? `${lg} - ${cp}` : lg;
    })(),
    numero: v("numero"),
    bairro: v("bairro"),
    cidade: v("cidade"),
    estado: v("uf"),
    senha: v("senha"),
  };

  for (const k in payload) {
    if (!payload[k]) {
      notify("Preencha todos os campos obrigatórios.");
      return;
    }
  }

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      notify(err?.detail || "Erro ao cadastrar.");
      return;
    }

    notify("Cadastro realizado com sucesso!");
    window.location.href = "index.html";

  } catch (err) {
    console.error(err);
    notify("Erro ao enviar o cadastro.");
  }
}

// ===============================
// LOGIN
// ===============================

async function login() {
  const email = v("email");
  const senha = v("senha");

  if (!email || !senha) {
    notify("Informe email e senha.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      notify(err?.detail || "Erro ao fazer login.");
      return;
    }

    const data = await res.json();
    console.log("LOGIN OK:", data);

    // 🔥 Aqui está a parte nova, sem conflito:
    localStorage.setItem(
      "painel_afiliado_session",
      JSON.stringify({
        id: data.id,
        nome: data.nome,
        email: data.email,
        logged_at: new Date().toISOString(),
      })
    );

    window.location.href = "painel.html";

  } catch (err) {
    console.error(err);
    notify("Erro de conexão ao tentar login.");
  }
}

// ===============================
// PROTEGER PAINEL
// ===============================

function protegerPainel() {
  const session = JSON.parse(localStorage.getItem("painel_afiliado_session"));
  if (!session) {
    window.location.href = "index.html";
    return;
  }

  if (document.getElementById("nome")) {
    document.getElementById("nome").innerText = session.nome;
  }
  if (document.getElementById("email")) {
    document.getElementById("email").innerText = session.email;
  }
}

// Chamar automaticamente se estiver no painel
if (window.location.pathname.includes("painel.html")) {
  protegerPainel();
}

// ===============================
// LOGOUT
// ===============================

function sair() {
  localStorage.removeItem("painel_afiliado_session");
  window.location.href = "index.html";
}
