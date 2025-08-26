const API_URL = "https://script.google.com/macros/s/SEU_SCRIPT_ID/exec"; // troque pelo seu Apps Script

// ===== LOGIN =====
async function login() {
  let email = document.getElementById("email").value;
  let senha = document.getElementById("senha").value;

  let res = await fetch(API_URL, {
    method: "POST",
    body: JSON.stringify({action: "login", email, senha})
  });
  let data = await res.json();

  if (data.success) {
    localStorage.setItem("afiliado", JSON.stringify(data));
    window.location.href = "painel.html";
  } else {
    alert("Login inválido!");
  }
}

// ===== CADASTRO (via grupo WhatsApp) =====
function cadastrarPrompt() {
  let url = "https://chat.whatsapp.com/JKC9c71I98x7jbfoQBPQEX?mode=ems_copy_c";
  window.open(url, "_blank");
}

// ===== PAINEL =====
if (window.location.pathname.includes("painel.html")) {
  let afiliado = JSON.parse(localStorage.getItem("afiliado"));
  if (!afiliado) {
    window.location.href = "index.html";
  }

  document.getElementById("nome").innerText = afiliado.nome;
  document.getElementById("email").innerText = afiliado.email;
  document.getElementById("source").innerText = afiliado.source_id;

  carregarPedidos(afiliado.source_id);
  carregarSaldo(afiliado.source_id);
  carregarGraficos(afiliado.source_id);
}

// ===== GERAR LINK UTM =====
async function gerarLink() {
  let url = document.getElementById("urlProduto").value;
  let afiliado = JSON.parse(localStorage.getItem("afiliado"));

  let res = await fetch(API_URL, {
    method: "POST",
    body: JSON.stringify({action: "gerarLink", url, source_id: afiliado.source_id})
  });
  let data = await res.json();

  document.getElementById("linkAfiliado").innerText = data.link;
}

// ===== BUSCAR PEDIDOS =====
async function carregarPedidos(source_id) {
  let res = await fetch(API_URL, {
    method: "POST",
    body: JSON.stringify({action: "pedidos", source_id})
  });
  let pedidos = await res.json();

  document.getElementById("pedidos").innerText = pedidos.length;

  let tabela = document.getElementById("tabelaPedidos");
  tabela.innerHTML = "";
  pedidos.forEach(p => {
    tabela.innerHTML += `<tr>
      <td class="border p-2">${p.codigoPedido}</td>
      <td class="border p-2">R$ ${p.valorTotal.toFixed(2)}</td>
      <td class="border p-2">${p.dataCriacao}</td>
    </tr>`;
  });
}

// ===== SALDO (total vendido) =====
async function carregarSaldo(source_id) {
  let res = await fetch(API_URL, {
    method: "POST",
    body: JSON.stringify({action: "saldo", source_id})
  });
  let data = await res.json();

  document.getElementById("saldo").innerText = "R$ " + data.total_vendido.toFixed(2);
}

// ===== GRÁFICOS (exemplo: evolução vendas) =====
async function carregarGraficos(source_id) {
  let res = await fetch(API_URL, {
    method: "POST",
    body: JSON.stringify({action: "graficos", source_id})
  });
  let dados = await res.json();

  console.log("Dados para gráficos:", dados);
  // aqui você pode usar Chart.js ou Google Charts para exibir no painel
}
