// CONFIG API
const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// ==========================
// Helpers
// ==========================
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

// ==========================
// CEP → ViaCEP
// ==========================
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

    const logEl = document.getElementById("logradouro");
    const bairroEl = document.getElementById("bairro");
    const cidadeEl = document.getElementById("cidade");
    const ufEl = document.getElementById("uf");

    if (logEl) logEl.value = data.logradouro || "";
    if (bairroEl) bairroEl.value = data.bairro || "";
    if (cidadeEl) cidadeEl.value = data.localidade || "";
    if (ufEl) ufEl.value = (data.uf || "").toUpperCase();
  } catch (err) {
    console.error(err);
    notify("Erro ao consultar CEP.");
  }
}

// ==========================
// CADASTRO
// ==========================
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

  // Validação simples: nada vazio
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
      notify(err?.detail || "Não foi possível concluir o cadastro.");
      return;
    }

    const data = await res.json().catch(() => null);
    notify((data && data.message) || "Cadastro realizado com sucesso!");
    // Após o aviso, redireciona para o login
    window.location.href = "index.html";
  } catch (err) {
    console.error(err);
    notify("Erro de conexão ao tentar cadastrar.");
  }
}

// ==========================
// LOGIN
// ==========================
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
      notify(err?.detail || "Não foi possível fazer login.");
      return;
    }

    const data = await res.json().catch(() => null);
    if (!data || data.status !== "success") {
      notify("Não foi possível fazer login.");
      return;
    }

    // Salva sessão simples no localStorage
    localStorage.setItem(
      "painel_afiliado_session",
      JSON.stringify({
        id: data.id,
        nome: data.nome,
        email: data.email,
        token: data.token,
        logged_at: new Date().toISOString(),
      })
    );

    window.location.href = "painel.html";
  } catch (err) {
    console.error(err);
    notify("Erro de conexão ao tentar logar.");
  }
}

// ==========================
// RECUPERAR CONTA (tela login)
// ==========================
async function recuperarConta() {
  const email = prompt("Informe o email cadastrado:");
  if (!email) return;

  const nova_senha = prompt("Digite a nova senha que deseja usar:");
  if (!nova_senha) return;

  try {
    const res = await fetch(`${API_BASE}/auth/recover`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, nova_senha }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      notify(err?.detail || "Erro ao recuperar conta.");
      return;
    }

    const data = await res.json().catch(() => null);
    notify(
      (data && data.message) ||
        "Senha redefinida. Agora faça login com a nova senha."
    );
  } catch (err) {
    console.error(err);
    notify("Erro de conexão ao recuperar conta.");
  }
}

function cadastrarPrompt() {
  window.location.href = "cadastro.html";
}
