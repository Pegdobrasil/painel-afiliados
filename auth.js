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
async function api(url, method = "GET", body = null) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" }
    };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(url, opts);

    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || resp.statusText);
    }

    return resp.json();
}


// =====================
// CADASTRO
// =====================
async function salvarCadastro() {
    const data = {
        tipo_pessoa: document.getElementById("tipo_pessoa").value,
        cpf_cnpj: document.getElementById("cpf_cnpj").value,
        nome: document.getElementById("nome").value,
        email: document.getElementById("email").value,
        telefone: document.getElementById("telefone").value,
        cep: document.getElementById("cep").value,
        endereco: document.getElementById("endereco").value,
        numero: document.getElementById("numero").value,
        bairro: document.getElementById("bairro").value,
        cidade: document.getElementById("cidade").value,
        estado: document.getElementById("estado").value,
        senha: document.getElementById("senha").value
    };

    try {
        const r = await api(
            "https://painel-afiliados-production.up.railway.app/api/auth/register",
            "POST",
            data
        );

        if (r.status === "pending_first_access") {
            alert("Cadastro localizado na REIN! Enviamos um link para você definir sua senha.");
            window.location.href = "index.html";
            return;
        }

        if (r.status === "success") {
            alert("Cadastro criado com sucesso! Verifique seu e-mail.");
            window.location.href = "index.html";
        }

    } catch (e) {
        alert("Erro ao cadastrar: " + e.message);
    }
}


// =====================
// LOGIN
// =====================
async function realizarLogin() {
    const data = {
        email: document.getElementById("email_login").value,
        senha: document.getElementById("senha_login").value
    };

    try {
        const r = await api(
            "https://painel-afiliados-production.up.railway.app/api/auth/login",
            "POST",
            data
        );

        if (r.status === "change_password_required") {
            alert("Primeiro acesso! Verifique seu e-mail para criar sua senha.");
            return;
        }

        if (r.token) {
            localStorage.setItem("token", r.token);
            localStorage.setItem("user_id", r.user_id);

            window.location.href = "painel.html";
        }

    } catch (e) {
        alert("Erro ao fazer login: " + e.message);
    }
}


// =====================
// RECUPERAR SENHA
// =====================
async function recuperarSenha() {
    const email = document.getElementById("rec_email").value;

    try {
        const r = await api(
            "https://painel-afiliados-production.up.railway.app/api/auth/recover",
            "POST",
            { email }
        );

        alert("Nova senha enviada ao e-mail.");
        window.location.href = "index.html";

    } catch (e) {
        alert("Erro: " + e.message);
    }
}

function cadastrarPrompt() {
  window.location.href = "cadastro.html";
}
