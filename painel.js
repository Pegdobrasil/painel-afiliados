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

// ===============================
// BUSCA PRODUTOS REIN
// ===============================
async function buscarProdutosRein(page = 1) {
  const input = document.getElementById("buscaTermo");
  const tbody = document.getElementById("tabelaBuscaProdutos");
  if (!tbody) return;

  const termo = (input?.value || "").trim();

  // estado de carregando
  tbody.innerHTML =
  '<tr><td colspan="3" class="px-3 py-3 text-xs text-slate-400">Buscando produtos...</td></tr>';


  const params = new URLSearchParams();
  if (termo) params.set("termo", termo);
  params.set("page", String(page));
  params.set("per_page", "10");

  try {
    const res = await fetch(
      `${API_BASE}/rein/buscar_produtos?` + params.toString()
    );
    if (!res.ok) throw new Error("Erro HTTP na busca");

    const data = await res.json();
    const items = data.items || [];

    if (!items.length) {
      tbody.innerHTML =
        '<tr><td colspan="3" class="px-3 py-3 text-xs text-slate-400">Nenhum produto encontrado.</td></tr>';
      return;
    }

    tbody.innerHTML = "";

    for (const p of items) {
      const tr = document.createElement("tr");
      tr.className = "border-b border-slate-800";

      const estoque = p.estoque ?? 0;
      const precoAtacado = Number(p.preco_atacado || 0);
      const precoVarejo = Number(p.preco_varejo || 0);

      tr.innerHTML = `
        <td class="px-3 py-2 text-xs">${p.sku || ""}</td>
        <td class="px-3 py-2">
          <div class="text-xs font-medium">${p.nome || ""}</div>
          <div class="text-[10px] text-slate-400">
            NCM: ${p.ncm || "-"} • Estoque: ${estoque} • ${
        p.ativo ? "Ativo" : "Inativo"
      }
          </div>
          <div class="text-[10px] text-slate-400 mt-0.5">
            Atacado: R$ ${precoAtacado.toFixed(2)} • Varejo: R$ ${precoVarejo.toFixed(2)}
          </div>
        </td>
        <td class="px-3 py-2 text-right">
          <button
            type="button"
            class="btn-ver-detalhes inline-flex items-center px-3 py-1 rounded text-[11px] bg-sky-600 text-white hover:bg-sky-500"
            data-produto-id="${p.produto_id}"
            data-grade-id="${p.grade_id}"
          >
            Ver detalhes
          </button>
        </td>
      `;

      tbody.appendChild(tr);
    }
  } catch (err) {
    console.error(err);
    tbody.innerHTML =
      '<tr><td colspan="3" class="px-3 py-3 text-xs text-red-400">Erro ao buscar produtos.</td></tr>';
  }
}

// detalhes via REIN
async function verDetalhesRein(produtoId, botao) {
  if (!produtoId) return;
  const oldText = botao.textContent;
  botao.disabled = true;
  botao.textContent = "Carregando...";

  try {
    const res = await fetch(`${API_BASE}/rein/produto/${produtoId}`);
    const data = await res.json();
    if (!data.ok) {
      alert(data.msg || "Erro ao carregar detalhes.");
      return;
    }
    const det = data.data || {};

    alert(
      `Produto: ${det.Nome || ""}\n` +
        `NCM: ${det.Ncm || ""}\n` +
        `ID: ${det.Id || produtoId}`
    );
  } catch (err) {
    console.error(err);
    alert("Erro ao carregar detalhes do produto.");
  } finally {
    botao.disabled = false;
    botao.textContent = oldText;
  }
}

// delegação de eventos para o botão "Ver detalhes"
document.addEventListener("click", function (ev) {
  const btn = ev.target.closest(".btn-ver-detalhes");
  if (!btn) return;
  const produtoId = btn.getAttribute("data-produto-id");
  verDetalhesRein(produtoId, btn);
});

// ===============================
// API: SALDO E PEDIDOS
// ===============================
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

// ===============================
// UTM
// ===============================
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

// ===============================
// MINHA CONTA
// ===============================
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

// ===============================
// ALTERAR SENHA
// ===============================
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

// ===============================
// NAVEGAÇÃO E SESSÃO
// ===============================
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

// carrega o sub-html da busca de produtos
async function carregarSecaoBuscarProduto() {
  const wrapper = document.getElementById("sec_buscar_produto_wrapper");
  if (!wrapper) return;

  try {
    const res = await fetch("buscar_produto.html");
    if (!res.ok) {
      console.error("Erro ao carregar buscar_produto.html");
      return;
    }
    const html = await res.text();
    wrapper.innerHTML = html;
  } catch (err) {
    console.error(err);
    return;
  }

  const btnBuscar = document.getElementById("btnBuscarProduto");
  if (btnBuscar) {
    btnBuscar.addEventListener("click", function () {
      buscarProdutosRein(1);
    });
  }

  const inputBusca = document.getElementById("buscaTermo");
  if (inputBusca) {
    inputBusca.addEventListener("keyup", function (ev) {
      if (ev.key === "Enter") {
        buscarProdutosRein(1);
      }
    });
  }

  if (document.getElementById("tabelaBuscaProdutos")) {
    buscarProdutosRein(1);
  }
}

// protege o painel e carrega dados iniciais
async function protegerPainel() {
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

  await carregarSecaoBuscarProduto();
  carregarSaldo(session.id);
  carregarPedidos(session.id);
  carregarMinhaConta(session.id);
}

window.addEventListener("DOMContentLoaded", protegerPainel);
