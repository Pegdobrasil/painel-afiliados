// CONFIG API
const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// helpers
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

// CEP
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
    if (document.getElementById("logradouro"))
      document.getElementById("logradouro").value = data.logradouro || "";
    if (document.getElementById("bairro"))
      document.getElementById("bairro").value = data.bairro || "";
    if (document.getElementById("cidade"))
      document.getElementById("cidade").value = data.localidade || "";
    if (document.getElementById("uf"))
      document.getElementById("uf").value = (data.uf || "").toUpperCase();
  } catch (err) {
    console.error(err);
    notify("Não foi possível consultar o CEP.");
  }
}

// CADASTRO
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

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      notify(data?.detail || "Erro ao cadastrar.");
      return;
    }

    notify("Cadastro realizado com sucesso!");
    window.location.href = "index.html";
  } catch (err) {
    console.error(err);
    notify("Erro ao enviar o cadastro.");
  }
}

// LOGIN — ★ CORRIGIDO ★
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

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      notify(data?.detail || "Não foi possível fazer login.");
      return;
    }

    // Primeiro acesso — força troca de senha
    if (data.status === "change_password_required") {
      localStorage.setItem("pending_user_id", data.user_id);
      window.location.href = "trocar_senha.html";
      return;
    }

    if (data.status !== "success") {
      notify(data.message || "Erro ao fazer login.");
      return;
    }

    // LOGIN NORMAL
    localStorage.setItem(
      "painel_afiliado_session",
      JSON.stringify({
        id: data.user_id,
        token: data.token,
        email: email,
        logged_at: new Date().toISOString(),
      })
    );

    window.location.href = "painel.html";
  } catch (err) {
    console.error(err);
    notify("Erro de conexão ao tentar login.");
  }
}

// TELA DE TROCA DE SENHA — ★ CORRIGIDO ★
async function trocarSenha() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");

  if (!token) {
    alert("Link inválido. Abra o link diretamente do seu e-mail.");
    window.location.href = "index.html";
    return;
  }

  const nova_senha = document.getElementById("senha_nova").value.trim();
  const confirma = document.getElementById("senha_confirma").value.trim();

  if (!nova_senha || !confirma) {
    alert("Preencha os dois campos de senha.");
    return;
  }

  if (nova_senha !== confirma) {
    alert("As senhas digitadas não conferem.");
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/auth/change-password-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, nova_senha }),
    });

    const data = await resp.json();

    if (!resp.ok || data.status !== "success") {
      alert(data.detail || data.message || "Erro ao trocar senha.");
      return;
    }

    alert("Senha alterada com sucesso! Agora você já pode fazer login.");
    window.location.href = "index.html";
  } catch (err) {
    console.error(err);
    alert("Erro de conexão ao tentar trocar a senha.");
  }
}


// RECUPERAR CONTA
async function recuperarConta() {
  const email = prompt("Informe o email cadastrado:");
  if (!email) return;

  const nova_senha = prompt("Digite a nova senha:");
  if (!nova_senha) return;

  try {
    const res = await fetch(`${API_BASE}/auth/recover`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, nova_senha }),
    });

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      notify(data?.detail || "Erro ao recuperar conta.");
      return;
    }

    notify("Senha redefinida. Agora faça login.");
  } catch (err) {
    console.error(err);
    notify("Erro de conexão ao recuperar conta.");
  }
}

function cadastrarPrompt() {
  window.location.href = "cadastro.html";
}
