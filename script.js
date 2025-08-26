const API_URL = "https://script.google.com/macros/s/AKfycbwVsxY7z92FqRlsgN0n1jrMk1qLBJn7DVFD1K3XhiWjWtIf4PWzh45nC3di7gJzEzUT/exec";

// Login
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

// Cadastro rápido
async function cadastrarPrompt() {
  let nome = prompt("Digite seu nome:");
  let email = prompt("Digite seu email:");
  let senha = prompt("Crie uma senha:");
  let source_id = email.split("@")[0]; // gera um source simples

  let res = await fetch(API_URL, {
    method: "POST",
    body: JSON.stringify({action: "cadastrar", nome, email, senha, source_id})
  });
  let data = await res.json();
  if (data.success) {
    alert("Cadastro realizado! Faça login.");
  }
}

// Painel
if (window.location.pathname.includes("painel.html")) {
  let afiliado = JSON.parse(localStorage.getItem("afiliado"));
  if (!afiliado) {
    window.location.href = "index.html";
  }

  document.getElementById("nome").innerText = afiliado.nome;
  document.getElementById("email").innerText = afiliado.email;
  document.getElementById("source").innerText = afiliado.source_id;

  // carregar pedidos reais (API Magazord)
  carregarPedidos(afiliado.source_id);
}

// Gerar link UTM
function gerarLink() {
  let url = document.getElementById("urlProduto").value;
  let afiliado = JSON.parse(localStorage.getItem("afiliado"));
  let link = url + "?utm_source=" + afiliado.source_id;
  document.getElementById("linkAfiliado").innerText = link;
}

// Buscar pedidos Magazord
async function carregarPedidos(source_id) {
  let res = await fetch("https://urlmagazord.com.br/api/v2/site/pedido", {
    headers: { "Authorization": "Bearer SEU_TOKEN_MAGAZORD" }
  });
  let pedidos = await res.json();

  let meusPedidos = pedidos.filter(p => p.utm_source === source_id);
  document.getElementById("pedidos").innerText = meusPedidos.length;

  let tabela = document.getElementById("tabelaPedidos");
  meusPedidos.forEach(p => {
    tabela.innerHTML += `<tr>
      <td class="border p-2">${p.codigoPedido}</td>
      <td class="border p-2">R$ ${p.valorTotal.toFixed(2)}</td>
      <td class="border p-2">${p.dataCriacao}</td>
    </tr>`;
  });
}
