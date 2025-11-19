// =======================================
// CONFIG
// =======================================
const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// =======================================
// PROTEGER PAINEL
// =======================================
function carregarSessao() {
  const session = JSON.parse(localStorage.getItem("painel_afiliado_session"));

  if (!session) {
    window.location.href = "index.html";
    return;
  }

  document.getElementById("nome").innerText = session.nome;
  document.getElementById("email").innerText = session.email;
  document.getElementById("id").innerText = session.id;

  carregarSaldo(session.id);
  carregarPedidos(session.id);
}

carregarSessao();

// =======================================
// SAIR
// =======================================
function sair() {
  localStorage.removeItem("painel_afiliado_session");
  window.location.href = "index.html";
}

// =======================================
// RECUPERAR SENHA (placeholder)
// =======================================
function recuperarSenha() {
  alert(
    "A função 'Recuperar Senha' ainda será ativada.\n" +
    "Seu backend em FastAPI precisa da rota:\n\n" +
    "POST /api/auth/recover\n\n" +
    "Quando quiser posso te entregar ela pronta."
  );
}

// =======================================
// MINHA CONTA (placeholder)
// =======================================
function abrirConta() {
  alert(
    "A área 'Minha Conta' será ativada quando criarmos\n" +
    "a rota /api/auth/me com edição de cadastro.\n\n" +
    "Posso montar isso para você quando desejar."
  );
}

// =======================================
// GERAR LINK DE AFILIADO
// =======================================
async function gerarLink() {
  const url = document.getElementById("urlProduto").value;
  const session = JSON.parse(localStorage.getItem("painel_afiliado_session"));

  const res = await fetch(`${API_BASE}/utm/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      afiliado_id: session.id,
      url
    }),
  });

  const data = await res.json();
  document.getElementById("linkAfiliado").innerText = data.link || "Erro";
}

// =======================================
// CARREGAR PEDIDOS
// =======================================
async function carregarPedidos(id) {
  try {
    const res = await fetch(`${API_BASE}/auth/pedidos/${id}`);
    const pedidos = await res.json();

    document.getElementById("pedidos").innerText = pedidos.length;

    let tabela = document.getElementById("tabelaPedidos");
    tabela.innerHTML = "";

    pedidos.forEach(p => {
      tabela.innerHTML += `
        <tr>
          <td class="p-2 border">${p.codigoPedido}</td>
          <td class="p-2 border">R$ ${p.valorTotal.toFixed(2)}</td>
          <td class="p-2 border">${p.dataCriacao}</td>
        </tr>`;
    });

  } catch (err) {
    console.error("Erro ao carregar pedidos:", err);
  }
}

// =======================================
// CARREGAR SALDO
// =======================================
async function carregarSaldo(id) {
  try {
    const res = await fetch(`${API_BASE}/auth/saldo/${id}`);
    const data = await res.json();
    document.getElementById("saldo").innerText =
      "R$ " + (data.total || 0).toFixed(2);
  } catch (err) {
    console.error("Erro ao carregar saldo:", err);
  }
}
