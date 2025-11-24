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
  const container = document.getElementById("listaBuscaProdutos");
  if (!container) return;

  const termo = (input?.value || "").trim();

  container.innerHTML =
    '<div class="col-span-full px-3 py-3 text-xs text-slate-400">Buscando produtos...</div>';

  const params = new URLSearchParams();
  if (termo) params.set("termo", termo);
  params.set("page", String(page));
  params.set("per_page", "9");

  try {
    const res = await fetch(
      `${API_BASE}/rein/buscar_produtos?` + params.toString()
    );
    if (!res.ok) throw new Error("Erro HTTP na busca");

    const data = await res.json();
    const items = data.items || [];

    if (!items.length) {
      container.innerHTML =
        '<div class="col-span-full px-3 py-3 text-xs text-slate-400">Nenhum produto encontrado.</div>';
      return;
    }

    container.innerHTML = "";

    for (const p of items) {
      const estoque = Number(p.estoque ?? 0);
      const precoAtacado = Number(p.preco_atacado || 0);
      const precoVarejo = Number(p.preco_varejo || 0);
      const capa = p.imagem_capa || "";

      const card = document.createElement("button");
      card.type = "button";
      card.className =
        "card-produto w-full text-left bg-slate-950 border border-slate-800 rounded-xl overflow-hidden flex flex-col hover:border-sky-500/70 hover:shadow-lg transition cursor-pointer";
      card.setAttribute("data-produto-id", p.produto_id);

      card.innerHTML = `
        <div class="relative aspect-video bg-slate-900 flex items-center justify-center overflow-hidden">
          ${
            capa
              ? `<img src="${capa}" alt="${(p.nome || "")
                  .replace(/"/g, "&quot;")}" class="w-full h-full object-cover" />`
              : `<div class="text-[11px] text-slate-500">Sem imagem</div>`
          }
        </div>
        <div class="p-3 flex-1 flex flex-col gap-1">
          <div class="flex items-center justify-between mb-1">
            <span class="text-[11px] text-slate-400">SKU: ${p.sku}</span>
            <span class="text-[10px] px-2 py-0.5 rounded-full border ${
              p.ativo
                ? "border-emerald-500/60 text-emerald-300 bg-emerald-500/5"
                : "border-slate-600 text-slate-300 bg-slate-800/60"
            }">
              ${p.ativo ? "Ativo" : "Inativo"}
            </span>
          </div>
          <div class="text-xs font-semibold text-slate-50 line-clamp-2">
            ${p.nome || ""}
          </div>
          <div class="text-[11px] text-slate-400 mt-1">
            Estoque: ${estoque}
          </div>
          <div class="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div>
              <div class="text-[10px] text-slate-500">Atacado</div>
              <div class="font-semibold text-emerald-400">
                R$ ${precoAtacado.toFixed(2)}
              </div>
            </div>
            <div>
              <div class="text-[10px] text-slate-500">Varejo recomendado</div>
              <div class="font-semibold text-sky-400">
                R$ ${precoVarejo.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      `;

      card.addEventListener("click", () => {
        abrirModalProduto(p.produto_id);
      });

      container.appendChild(card);
    }
  } catch (err) {
    console.error(err);
    container.innerHTML =
      '<div class="col-span-full px-3 py-3 text-xs text-red-500">Erro ao buscar produtos.</div>';
  }
}

// Normaliza o detalhe vindo da API da REIN (produto cru) para o formato usado no modal
function normalizarDetalheRein(raw) {
  if (!raw) return null;

  // Algumas rotas podem devolver { status, data: { ... } }.
  // Neste caso, usamos sempre o conteúdo de "data".
  const data =
    raw && raw.data && (raw.data.ProdutoGrade || raw.data.ProdutoDescricao)
      ? raw.data
      : raw;

  // Se já vier no formato esperado (nome + imagens), só retorna
  if (data.nome && Array.isArray(data.imagens)) {
    return data;
  }

  const det = {};

  // nome, descrição e NCM
  det.nome = data.Nome || data.nome || "";
  det.descricao = data.Descricao || data.descricao || "";

  // pega a primeira grade do produto (padrão)
  const grades = data.ProdutoGrade || data.produtoGrade || [];
  const grade = grades[0] || {};

  det.sku = grade.Sku || grade.sku || "";
  det.ncm = grade.Ncm || data.Ncm || data.ncm || "";

  // pesos
  const pesoLiq = Number(
    grade.PesoLiquido ?? data.PesoLiquido ?? data.peso_liquido ?? 0
  );
  const pesoBru = Number(
    grade.PesoBruto ?? data.PesoBruto ?? data.peso_bruto ?? pesoLiq
  );
  det.peso_liquido = Number.isFinite(pesoLiq) ? pesoLiq : 0;
  det.peso_bruto = Number.isFinite(pesoBru) ? pesoBru : det.peso_liquido;

  // dimensões (em cm)
  const largura = Number(
    grade.Largura ?? data.Largura ?? data.largura_cm ?? 0
  );
  const altura = Number(
    grade.Altura ?? data.Altura ?? data.altura_cm ?? 0
  );
  const comp = Number(
    grade.Comprimento ?? data.Comprimento ?? data.comprimento_cm ?? 0
  );

  det.largura_cm = Number.isFinite(largura) ? largura : 0;
  det.altura_cm = Number.isFinite(altura) ? altura : 0;
  det.comprimento_cm = Number.isFinite(comp) ? comp : 0;

  if (det.largura_cm && det.altura_cm && det.comprimento_cm) {
    det.cubagem =
      (det.largura_cm * det.altura_cm * det.comprimento_cm) / 1_000_000;
  } else {
    det.cubagem = 0;
  }

  // preços (ProdutoMargem da grade)
  let precoAt = 0;
  let precoVar = 0;
  for (const m of grade.ProdutoMargem || []) {
    const nomeTabela = ((m.TabelaPreco || {}).Nome || "").toUpperCase();
    let preco = Number(m.PrecoComDesconto ?? m.Preco ?? 0);
    if (!Number.isFinite(preco)) preco = 0;

    if (nomeTabela.includes("ATACADO")) precoAt = preco;
    if (nomeTabela.includes("VAREJO")) precoVar = preco;
  }
  det.preco_atacado = precoAt;
  det.preco_varejo = precoVar;

  // imagens da grade
  const cdnBase =
    "https://cdn.rein.net.br/app/core/pegdobrasil/6.5.4/publico/imagem/produto/";
  const imagens = [];
  for (const img of grade.ProdutoImagem || []) {
    const nome =
      img.NomeImagem || img.strNomeArquivo || img.NomeArquivo || img.nome;
    if (!nome) continue;
    const nomeLimpo = String(nome).trim().replace(/^\/+/, "");
    imagens.push({ conteudo: cdnBase + nomeLimpo });
  }
  det.imagens = imagens;

  // categorias em texto (para exibir no modal)
  const categorias = [];
  for (const pc of data.ProdutoCategoria || []) {
    const cat = pc.Categoria || {};
    const pai = cat.CategoriaPai || {};
    if (pai.Nome && cat.Nome) categorias.push(`${pai.Nome} > ${cat.Nome}`);
    else if (cat.Nome) categorias.push(cat.Nome);
  }
  det.categorias = categorias;

  return det;
}

function fecharModalProduto() {
  const modal = document.getElementById("modalProduto");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

async function abrirModalProduto(produtoId) {
  const modal = document.getElementById("modalProduto");
  if (!modal) return;

  const titulo = document.getElementById("modalProdutoTitulo");
  const skuEl = document.getElementById("modalProdutoSku");
  const catEl = document.getElementById("modalProdutoCategoria");
  const descEl = document.getElementById("modalProdutoDescricao");
  const pesoEl = document.getElementById("modalProdutoPeso");
  const dimEl = document.getElementById("modalProdutoDimensoes");
  const precoAEl = document.getElementById("modalProdutoPrecoAtacado");
  const precoVEl = document.getElementById("modalProdutoPrecoVarejo");
  const imagensEl = document.getElementById("modalProdutoImagens");
  const thumbsEl = document.getElementById("modalProdutoThumbs");

  modal.classList.remove("hidden");
  modal.classList.add("flex");

  titulo.textContent = "Carregando...";
  skuEl.textContent = "";
  catEl.textContent = "-";
  descEl.textContent = "";
  pesoEl.textContent = "-";
  dimEl.textContent = "-";
  precoAEl.textContent = "R$ 0,00";
  precoVEl.textContent = "R$ 0,00";
  imagensEl.innerHTML =
    '<div class="text-[11px] text-slate-400">Carregando imagens...</div>';
  thumbsEl.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/rein/produto/${produtoId}`);
    if (!res.ok) throw new Error("Erro HTTP no detalhe");

    const payload = await res.json();

    // aceita tanto { ok, data } quanto objeto cru da REIN ou {status, data}
    let det = null;
    if (payload && payload.ok && payload.data) {
      det = payload.data;
    } else {
      det = normalizarDetalheRein(payload);
    }

    if (!det) throw new Error("Detalhe vazio");

    // TÍTULO, SKU, NCM
    titulo.textContent = det.nome || "Produto";
    skuEl.textContent = `SKU: ${det.sku || "-"} • NCM: ${det.ncm || "-"}`;

    // CATEGORIA
    if (Array.isArray(det.categorias) && det.categorias.length) {
      catEl.textContent = det.categorias.join(" | ");
    } else {
      catEl.textContent = "-";
    }

    // DESCRIÇÃO
    descEl.textContent = det.descricao || "Sem descrição cadastrada.";

    // PESOS
    const pesoLiq = Number(det.peso_liquido ?? 0);
    const pesoBru = Number(det.peso_bruto ?? 0);
    if (pesoLiq || pesoBru) {
      const liq = Number.isFinite(pesoLiq) ? pesoLiq : 0;
      const bru = Number.isFinite(pesoBru) ? pesoBru : liq;
      pesoEl.textContent = `Líquido: ${liq.toFixed(
        3
      )} kg • Bruto: ${bru.toFixed(3)} kg`;
    } else {
      pesoEl.textContent = "-";
    }

    // DIMENSÕES
    const largura = Number(det.largura_cm ?? 0);
    const altura = Number(det.altura_cm ?? 0);
    const comp = Number(det.comprimento_cm ?? 0);
    const cubagem = Number(det.cubagem ?? 0);

    if (largura || altura || comp) {
      let textoDim = `${largura.toFixed(1)} x ${altura.toFixed(
        1
      )} x ${comp.toFixed(1)} cm`;
      if (cubagem) {
        textoDim += ` (Cubagem: ${cubagem.toFixed(4)})`;
      }
      dimEl.textContent = textoDim;
    } else {
      dimEl.textContent = "-";
    }

    // PREÇOS
    precoAEl.textContent = `R$ ${Number(
      det.preco_atacado || 0
    ).toFixed(2)}`;
    precoVEl.textContent = `R$ ${Number(
      det.preco_varejo || 0
    ).toFixed(2)}`;

    // IMAGENS
    const imagens = det.imagens || [];

    if (!imagens.length) {
      imagensEl.innerHTML =
        '<div class="text-[11px] text-slate-400">Sem imagens cadastradas.</div>';
      return;
    }

    function renderImagemPrincipal(src) {
      imagensEl.innerHTML = `
        <img src="${src}" alt="${(det.nome || "")
          .replace(/"/g, "&quot;")}" class="w-full h-full object-contain" />
      `;
    }

    renderImagemPrincipal(imagens[0].conteudo || imagens[0]);

    thumbsEl.innerHTML = "";
    for (const img of imagens) {
      const src = img.conteudo || img;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "border border-slate-700 rounded-md overflow-hidden w-16 h-16 flex-shrink-0 hover:border-sky-500";
      btn.innerHTML = `<img src="${src}" class="w-full h-full object-cover" />`;
      btn.addEventListener("click", () => renderImagemPrincipal(src));
      thumbsEl.appendChild(btn);
    }
  } catch (err) {
    console.error(err);
    titulo.textContent = "Erro ao carregar detalhes";
    imagensEl.innerHTML =
      '<div class="text-[11px] text-red-500">Não foi possível carregar o produto.</div>';
  }
}

// eventos de fechar modal
document.addEventListener("click", (ev) => {
  const closeBtn = ev.target.closest("#modalProdutoFechar");
  if (closeBtn) {
    fecharModalProduto();
  }

  const modal = document.getElementById("modalProduto");
  if (!modal || modal.classList.contains("hidden")) return;

  if (ev.target === modal) {
    fecharModalProduto();
  }
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") {
    fecharModalProduto();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const btnBuscar = document.getElementById("btnBuscarProduto");
  const inputBuscar = document.getElementById("buscaTermo");

  if (btnBuscar) {
    btnBuscar.addEventListener("click", () => buscarProdutosRein(1));
  }
  if (inputBuscar) {
    inputBuscar.addEventListener("keyup", (ev) => {
      if (ev.key === "Enter") {
        buscarProdutosRein(1);
      }
    });
  }

  // pode disparar uma busca inicial vazia se quiser
  // buscarProdutosRein(1);
});

// detalhes via REIN (alert simples, opcional)
async function verDetalhesRein(produtoId, botao) {
  if (!produtoId) return;
  const oldText = botao.textContent;
  botao.disabled = true;
  botao.textContent = "Carregando...";

  try {
    const res = await fetch(`${API_BASE}/rein/produto/${produtoId}`);
    const payload = await res.json();

    // aceita tanto { ok, data } quanto { status, data } ou objeto cru
    let det;
    if (payload && payload.ok && payload.data) {
      det = payload.data;
    } else if (
      payload &&
      payload.data &&
      (payload.data.Nome || payload.data.ProdutoGrade)
    ) {
      det = payload.data;
    } else {
      det = payload;
    }

    alert(
      `Produto: ${det.Nome || det.nome || ""}\n` +
        `NCM: ${det.Ncm || det.ncm || ""}\n` +
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
