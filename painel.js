const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

function getSession() {
  const raw = localStorage.getItem("painel_afiliado_session");
  return raw ? JSON.parse(raw) : null;
}

function msgConta(text, tipo = "info") {
  const el = document.getElementById("msg_conta");
  if (!el) return;
  el.textContent = text || "";
  el.className =
    "text-xs mt-2 " + (tipo === "erro" ? "text-red-600" : "text-gray-500");
}

function msgSenha(text, tipo = "info") {
  const el = document.getElementById("msg_senha");
  if (!el) return;
  el.textContent = text || "";
  el.className =
    "text-xs mt-2 " + (tipo === "erro" ? "text-red-600" : "text-gray-500");
}

function protegerPainel() {
  const session = getSession();
  if (!session) {
    window.location.href = "index.html";
    return;
  }

  if (document.getElementById("nome"))
    document.getElementById("nome").textContent = session.nome || "";
  if (document.getElementById("email"))
    document.getElementById("email").textContent = session.email || "";
  if (document.getElementById("id"))
    document.getElementById("id").textContent = session.id || "";

  carregarSaldo(session.id);
  carregarPedidos(session.id);
  carregarMinhaConta(session.id);
}

async function carregarSaldo(id) {
  try {
    const res = await fetch(`${API_BASE}/auth/saldo/${id}`);
    const data = await res.json();
    const val = data?.total || 0;
    document.getElementById("saldo").textContent = "R$ " + val.toFixed(2);
  } catch (err) {
    console.error(err);
  }
}

async function carregarPedidos(id) {
  try {
    const res = await fetch(`${API_BASE}/auth/pedidos/${id}`);
    const pedidos = await res.json();
    document.getElementById("pedidos").textContent = pedidos.length || 0;

    const tbody = document.getElementById("tabelaPedidos");
    if (!tbody) return;
    tbody.innerHTML = "";
    pedidos.forEach((p) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="p-2 border">${p.codigoPedido}</td>
        <td class="p-2 border">R$ ${p.valorTotal.toFixed(2)}</td>
        <td class="p-2 border">${p.dataCriacao}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

// gerar UTM
async function gerarLink() {
  const url = document.getElementById("urlProduto").value.trim();
  const session = getSession();
  if (!url) {
    document.getElementById("linkAfiliado").textContent = "Informe a URL.";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/utm/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ afiliado_id: session.id, url }),
    });

    const data = await res.json();
    document.getElementById("linkAfiliado").textContent = data.link || "Erro";
  } catch (err) {
    console.error(err);
    document.getElementById("linkAfiliado").textContent = "Erro";
  }
}

// Minha Conta
async function carregarMinhaConta(id) {
  msgConta("Carregando dados...");
  try {
    const res = await fetch(`${API_BASE}/auth/user/${id}`);
    if (!res.ok) {
      msgConta("Não foi possível carregar seus dados.", "erro");
      return;
    }
    const u = await res.json();

    document.getElementById("conta_tipo_pessoa").value = u.tipo_pessoa || "PF";
    document.getElementById("conta_cpf_cnpj").value = u.cpf_cnpj || "";
    document.getElementById("conta_nome").value = u.nome || "";
    document.getElementById("conta_email").value = u.email || "";
    document.getElementById("conta_telefone").value = u.telefone || "";
    document.getElementById("conta_cep").value = u.cep || "";
    document.getElementById("conta_endereco").value = u.endereco || "";
    document.getElementById("conta_numero").value = u.numero || "";
    document.getElementById("conta_bairro").value = u.bairro || "";
    document.getElementById("conta_cidade").value = u.cidade || "";
    document.getElementById("conta_estado").value = u.estado || "";

    msgConta("Dados carregados.");
  } catch (err) {
    console.error(err);
    msgConta("Erro ao carregar dados.", "erro");
  }
}

async function salvarMinhaConta() {
  const session = getSession();
  if (!session) return;

  const payload = {
    tipo_pessoa: document.getElementById("conta_tipo_pessoa").value || null,
    cpf_cnpj: document.getElementById("conta_cpf_cnpj").value || null,
    nome: document.getElementById("conta_nome").value || null,
    email: document.getElementById("conta_email").value || null,
    telefone: document.getElementById("conta_telefone").value || null,
    cep: document.getElementById("conta_cep").value || null,
    endereco: document.getElementById("conta_endereco").value || null,
    numero: document.getElementById("conta_numero").value || null,
    bairro: document.getElementById("conta_bairro").value || null,
    cidade: document.getElementById("conta_cidade").value || null,
    estado: document.getElementById("conta_estado").value || null,
  };

  msgConta("Salvando dados...");
  try {
    const res = await fetch(`${API_BASE}/auth/user/${session.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      msgConta(err?.detail || "Erro ao salvar dados.", "erro");
      return;
    }

    const atualizado = await res.json();
    // atualiza também na sessão (nome/email)
    localStorage.setItem(
      "painel_afiliado_session",
      JSON.stringify({
        ...session,
        nome: atualizado.nome,
        email: atualizado.email,
      })
    );
    document.getElementById("nome").textContent = atualizado.nome;
    document.getElementById("email").textContent = atualizado.email;

    msgConta("Dados atualizados com sucesso.");
  } catch (err) {
    console.error(err);
    msgConta("Erro de conexão ao salvar dados.", "erro");
  }
}

// Alterar senha
async function alterarSenha() {
  const session = getSession();
  if (!session) return;

  const senha_atual = document.getElementById("senha_atual").value;
  const senha_nova = document.getElementById("senha_nova").value;
  const senha_nova2 = document.getElementById("senha_nova2").value;

  if (!senha_atual || !senha_nova || !senha_nova2) {
    msgSenha("Preencha todos os campos.", "erro");
    return;
  }
  if (senha_nova !== senha_nova2) {
    msgSenha("A nova senha e a confirmação não conferem.", "erro");
    return;
  }

  msgSenha("Alterando senha...");
  try {
    const res = await fetch(`${API_BASE}/auth/change-password/${session.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ senha_atual, senha_nova }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      msgSenha(err?.detail || "Erro ao alterar senha.", "erro");
      return;
    }

    msgSenha("Senha alterada com sucesso.");
    document.getElementById("senha_atual").value = "";
    document.getElementById("senha_nova").value = "";
    document.getElementById("senha_nova2").value = "";
  } catch (err) {
    console.error(err);
    msgSenha("Erro de conexão ao alterar senha.", "erro");
  }
}

// navegação
function scrollMinhaConta() {
  const sec = document.getElementById("sec_minhaconta");
  if (sec) sec.scrollIntoView({ behavior: "smooth" });
}

function scrollAlterarSenha() {
  const sec = document.getElementById("sec_alterarsenha");
  if (sec) sec.scrollIntoView({ behavior: "smooth" });
}

function sair() {
  localStorage.removeItem("painel_afiliado_session");
  window.location.href = "index.html";
}

window.addEventListener("DOMContentLoaded", protegerPainel);
