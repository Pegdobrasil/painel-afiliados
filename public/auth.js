// ===============================
// CONFIG API BACKEND
// ===============================

// URL base da sua API no Railway
const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// ===============================
// HELPERS
// ===============================

// Pega valor de um input por id
function v(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

// Mostra alerta simples (pode trocar por toast depois)
function notify(msg) {
  alert(msg);
}

// Remove tudo que não for número
function onlyDigits(str) {
  return (str || "").replace(/\D/g, "");
}

// ===============================
// BUSCA CEP (ViaCEP)
// ===============================

async function buscarCep() {
  const cep = onlyDigits(v("cep"));

  if (cep.length !== 8) {
    // CEP inválido ou incompleto
    return;
  }

  try {
    const res = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
    const data = await res.json();

    if (data.erro) {
      notify("CEP não encontrado. Verifique os números informados.");
      return;
    }

    // Preenche campos
    const logradouro = document.getElementById("logradouro");
    const bairro = document.getElementById("bairro");
    const cidade = document.getElementById("cidade");
    const uf = document.getElementById("uf");

    if (logradouro) logradouro.value = data.logradouro || "";
    if (bairro) bairro.value = data.bairro || "";
    if (cidade) cidade.value = data.localidade || "";
    if (uf) uf.value = (data.uf || "").toUpperCase();
  } catch (err) {
    console.error("Erro ao buscar CEP:", err);
    notify("Não foi possível consultar o CEP no momento.");
  }
}

// ===============================
// CADASTRO DE USUÁRIO
// ===============================

async function registrar() {
  // Coleta de dados do formulário
  const payload = {
    tipo_pessoa: v("tipo_pessoa"),
    cpf_cnpj: onlyDigits(v("cpf_cnpj")),
    nome: v("nome"),
    email: v("email"),
    telefone: v("telefone"),
    cep: onlyDigits(v("cep")),
    // Endereço = logradouro + complemento (quando houver)
    endereco: (() => {
      const logradouro = v("logradouro");
      const complemento = v("complemento");
      return complemento ? `${logradouro} - ${complemento}` : logradouro;
    })(),
    numero: v("numero"),
    bairro: v("bairro"),
    cidade: v("cidade"),
    estado: v("uf"),
    senha: v("senha"),
  };

  // Validação básica
  if (
    !payload.tipo_pessoa ||
    !payload.cpf_cnpj ||
    !payload.nome ||
    !payload.email ||
    !payload.senha ||
    !payload.cep ||
    !payload.endereco ||
    !payload.numero ||
    !payload.bairro ||
    !payload.cidade ||
    !payload.estado
  ) {
    notify("Preencha todos os campos obrigatórios antes de salvar.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => null);
      const msg = errorData?.detail || "Erro ao salvar o cadastro.";
      notify(msg);
      return;
    }

    const data = await res.json();
    console.log("Cadastro OK:", data);

    notify("Cadastro realizado com sucesso!");

    // Depois do cadastro, envia para o login
    window.location.href = "index.html";
  } catch (err) {
    console.error("Erro no cadastro:", err);
    notify("Não foi possível concluir o cadastro. Tente novamente em instantes.");
  }
}

// ===============================
// LOGIN (caso queira usar o mesmo arquivo no index.html)
// ===============================

async function login() {
  const email = v("email");
  const senha = v("senha");

  if (!email || !senha) {
    notify("Informe email e senha para entrar.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => null);
      const msg = errorData?.detail || "Não foi possível fazer login.";
      notify(msg);
      return;
    }

    const data = await res.json();
    console.log("Login OK:", data);

    // Aqui futuramente podemos guardar token / dados do usuário
    // Exemplo simples:
    localStorage.setItem(
      "painel_afiliado_session",
      JSON.stringify({ email, logged_at: new Date().toISOString() })
    );

    notify("Login realizado com sucesso!");
    window.location.href = "painel.html";
  } catch (err) {
    console.error("Erro no login:", err);
    notify("Erro de conexão ao tentar fazer login.");
  }
}

// ===============================
// UTILIDADE OPCIONAL: ir para tela de cadastro
// (caso queira usar no link "Cadastrar" do index.html)
// ===============================
function cadastrarPrompt() {
  window.location.href = "cadastro.html";
}
