// admin.js

const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// memória local da lista carregada
let afiliadosCache = [];

// utilidades
function msg(texto, tipo = "info") {
  const el = document.getElementById("admin_msg");
  if (!el) return;
  el.textContent = texto || "";
  el.className = "text-xs mt-3 " + (tipo === "erro" ? "text-red-600" : "text-gray-500");
}

function limparFormulario() {
  document.getElementById("form_id").textContent = "nenhum";

  const campos = [
    "form_tipo_pessoa",
    "form_cpf_cnpj",
    "form_nome",
    "form_email",
    "form_telefone",
    "form_cep",
    "form_endereco",
    "form_numero",
    "form_bairro",
    "form_cidade",
    "form_estado",
  ];

  campos.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      if (el.tagName === "SELECT") el.value = "PF";
      else el.value = "";
    }
  });

  msg("");
}
async function login() {
    const email = document.getElementById("email").value;
    const senha = document.getElementById("senha").value;

    const resp = await fetch(API_BASE + "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, senha })
    });

    const data = await resp.json();

    if (data.status === "change_password_required") {
        localStorage.setItem("pending_user_id", data.user_id);
        window.location.href = "trocar_senha.html";
        return;
    }

    if (data.status !== "success") {
        alert(data.message || "Erro ao fazer login");
        return;
    }

    // Login normal
    localStorage.setItem("session_token", data.token);
    localStorage.setItem("user_id", data.user_id);

    window.location.href = "painel.html";
}

// voltar para login (ou outra página)
function voltarLogin() {
  window.location.href = "index.html";
}

// carregar lista de afiliados
async function carregarAfiliados() {
  msg("Carregando afiliados...");
  try {
    const res = await fetch(`${API_BASE}/auth/users`);
    if (!res.ok) {
      msg("Erro ao buscar afiliados.", "erro");
      return;
    }

    const data = await res.json();
    afiliadosCache = data || [];
    renderTabelaAfiliados();
    msg(`Foram carregados ${afiliadosCache.length} afiliados.`);
  } catch (err) {
    console.error(err);
    msg("Falha de conexão ao carregar afiliados.", "erro");
  }
}

function renderTabelaAfiliados(filtro = "") {
  const tbody = document.getElementById("tabelaAfiliados");
  if (!tbody) return;
  tbody.innerHTML = "";

  const termo = filtro.toLowerCase();

  afiliadosCache
    .filter((a) => {
      if (!termo) return true;
      return (
        a.nome.toLowerCase().includes(termo) ||
        a.email.toLowerCase().includes(termo) ||
        a.cpf_cnpj.toLowerCase().includes(termo)
      );
    })
    .forEach((a) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-gray-100 cursor-pointer";
      tr.onclick = () => carregarAfiliadoNoForm(a.id);

      tr.innerHTML = `
        <td class="p-2 border">${a.id}</td>
        <td class="p-2 border">${a.nome}</td>
        <td class="p-2 border">${a.email}</td>
        <td class="p-2 border">${a.cpf_cnpj}</td>
      `;
      tbody.appendChild(tr);
    });
}

function filtrarTabela() {
  const filtro = document.getElementById("filtroBusca").value || "";
  renderTabelaAfiliados(filtro);
}

// carrega um afiliado específico no formulário
async function carregarAfiliadoNoForm(id) {
  msg("Carregando dados do afiliado...");
  try {
    const res = await fetch(`${API_BASE}/auth/user/${id}`);
    if (!res.ok) {
      msg("Erro ao buscar dados do afiliado.", "erro");
      return;
    }

    const a = await res.json();
    document.getElementById("form_id").textContent = a.id;

    document.getElementById("form_tipo_pessoa").value = a.tipo_pessoa || "PF";
    document.getElementById("form_cpf_cnpj").value = a.cpf_cnpj || "";
    document.getElementById("form_nome").value = a.nome || "";
    document.getElementById("form_email").value = a.email || "";
    document.getElementById("form_telefone").value = a.telefone || "";
    document.getElementById("form_cep").value = a.cep || "";
    document.getElementById("form_endereco").value = a.endereco || "";
    document.getElementById("form_numero").value = a.numero || "";
    document.getElementById("form_bairro").value = a.bairro || "";
    document.getElementById("form_cidade").value = a.cidade || "";
    document.getElementById("form_estado").value = a.estado || "";

    msg("Dados carregados. Edite e clique em salvar.");
  } catch (err) {
    console.error(err);
    msg("Falha de conexão ao carregar afiliado.", "erro");
  }
}

// salvar alterações de um afiliado
async function salvarAfiliado() {
  const idText = document.getElementById("form_id").textContent;
  const id = parseInt(idText, 10);

  if (!id || isNaN(id)) {
    msg("Nenhum afiliado selecionado.", "erro");
    return;
  }

  const payload = {
    tipo_pessoa: document.getElementById("form_tipo_pessoa").value || null,
    cpf_cnpj: document.getElementById("form_cpf_cnpj").value || null,
    nome: document.getElementById("form_nome").value || null,
    email: document.getElementById("form_email").value || null,
    telefone: document.getElementById("form_telefone").value || null,
    cep: document.getElementById("form_cep").value || null,
    endereco: document.getElementById("form_endereco").value || null,
    numero: document.getElementById("form_numero").value || null,
    bairro: document.getElementById("form_bairro").value || null,
    cidade: document.getElementById("form_cidade").value || null,
    estado: document.getElementById("form_estado").value || null,
  };

  msg("Salvando alterações...");
  try {
    const res = await fetch(`${API_BASE}/auth/user/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      msg(err?.detail || "Erro ao salvar afiliado.", "erro");
      return;
    }

    const atualizado = await res.json();
    msg("Afiliado atualizado com sucesso.");

    // atualiza cache local e tabela
    const idx = afiliadosCache.findIndex((a) => a.id === atualizado.id);
    if (idx !== -1) {
      afiliadosCache[idx] = atualizado;
      renderTabelaAfiliados(document.getElementById("filtroBusca").value || "");
    }
  } catch (err) {
    console.error(err);
    msg("Falha de conexão ao salvar afiliado.", "erro");
  }
}

// carrega lista na abertura da página
window.addEventListener("DOMContentLoaded", () => {
  carregarAfiliados();
  limparFormulario();
});
