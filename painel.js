const API_BASE = "https://painel-afiliados-production.up.railway.app/api";

// ===============================
// SESSÃO E MENSAGENS
// ===============================
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
// BUSCAR PRODUTOS (LISTAGEM)
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

      // Dataset com TUDO que o modal precisa reaproveitar
      card.dataset.produtoId = p.produto_id || "";
      card.dataset.sku = p.sku || "";
      card.dataset.nome = p.nome || "";
      card.dataset.ncm = p.ncm || "";
      card.dataset.precoAtacado = String(precoAtacado);
      card.dataset.precoVarejo = String(precoVarejo);
      card.dataset.imagem = capa || "";

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
            <span class="text-[11px] text-slate-400">SKU: ${p.sku || ""}</span>
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

      // Abre o modal usando APENAS os dados já carregados no card
      card.addEventListener("click", () => {
        abrirModalProdutoDoCard(card);
      });

      container.appendChild(card);
    }
  } catch (err) {
    console.error(err);
    container.innerHTML =
      '<div class="col-span-full px-3 py-3 text-xs text-red-500">Erro ao buscar produtos.</div>';
  }
}

// ===============================
// NORMALIZAR DETALHE DA REIN
// ===============================
function normalizarDetalheRein(raw) {
  if (!raw) return null;

  const base =
    raw && raw.data && (raw.data.ProdutoGrade || raw.data.ProdutoDescricao)
      ? raw.data
      : raw;

  const det = {};

  det.nome = base.Nome || "";
  det.ncm = base.Ncm || "";

  // descrição via ProdutoDescricao
  let desc = "";
  if (Array.isArray(base.ProdutoDescricao) && base.ProdutoDescricao.length) {
    const ativo =
      base.ProdutoDescricao.find((d) => d.Ativo) || base.ProdutoDescricao[0];
    desc = ativo.Descricao || ativo.Titulo || "";
  }
  det.descricao = desc;

  const grades = base.ProdutoGrade || [];
  const grade = grades[0] || {};

  det.sku = grade.Sku || "";

  const pesoLiq = Number(grade.PesoLiquido ?? base.PesoLiquido ?? 0);
  const pesoBru = Number(grade.PesoBruto ?? base.PesoBruto ?? pesoLiq);
  det.peso_liquido = Number.isFinite(pesoLiq) ? pesoLiq : 0;
  det.peso_bruto = Number.isFinite(pesoBru) ? pesoBru : det.peso_liquido;

  const largura = Number(grade.Largura ?? base.Largura ?? 0);
  const altura = Number(grade.Altura ?? base.Altura ?? 0);
  const comp = Number(grade.Comprimento ?? base.Comprimento ?? 0);
  det.largura_cm = Number.isFinite(largura) ? largura : 0;
  det.altura_cm = Number.isFinite(altura) ? altura : 0;
  det.comprimento_cm = Number.isFinite(comp) ? comp : 0;

  if (det.largura_cm && det.altura_cm && det.comprimento_cm) {
    det.cubagem =
      (det.largura_cm * det.altura_cm * det.comprimento_cm) / 1_000_000;
  } else {
    det.cubagem = 0;
  }

  // preços pela ProdutoMargem
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

  // categorias
  const categorias = [];
  for (const pc of base.ProdutoCategoria || []) {
    const cat = pc.Categoria || {};
    const pai = cat.CategoriaPai || {};
    if (pai.Nome && cat.Nome) categorias.push(`${pai.Nome} > ${cat.Nome}`);
    else if (cat.Nome) categorias.push(cat.Nome);
  }
  det.categorias = categorias;

  // imagens
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

  return det;
}

// ===============================
// MODAL DE PRODUTO
// ===============================
function fecharModalProduto() {
  const modal = document.getElementById("modalProduto");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

function abrirModalProdutoDoCard(card) {
  const modal = document.getElementById("modalProduto");
  if (!modal) return;

  const produtoId = card.dataset.produtoId || "";

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

  // Dados imediatos vindos do card (sem novo GET)
  const nome = card.dataset.nome || "Produto";
  const sku = card.dataset.sku || "-";
  const ncm = card.dataset.ncm || "-";
  const precoAtacado = Number(card.dataset.precoAtacado || 0);
  const precoVarejo = Number(card.dataset.precoVarejo || 0);
  const capa = card.dataset.imagem || "";

  titulo.textContent = nome;
  skuEl.textContent = `SKU: ${sku} • NCM: ${ncm}`;
  catEl.textContent = "-";
  descEl.textContent = "Sem descrição cadastrada.";
  pesoEl.textContent = "-";
  dimEl.textContent = "-";
  precoAEl.textContent = `R$ ${precoAtacado.toFixed(2)}`;
  precoVEl.textContent = `R$ ${precoVarejo.toFixed(2)}`;

  if (capa) {
    imagensEl.innerHTML = `
      <img src="${capa}" alt="${nome.replace(
        /"/g,
        "&quot;"
      )}" class="w-full h-full object-contain" />
    `;
  } else {
    imagensEl.innerHTML =
      '<div class="text-[11px] text-slate-400">Sem imagens cadastradas.</div>';
  }
  thumbsEl.innerHTML = "";

  // Completa com detalhe da REIN (peso, descrição, mais imagens, etc.)
  if (produtoId) {
    completarDetalhePorId(produtoId);
  }
}

async function completarDetalhePorId(produtoId) {
  const catEl = document.getElementById("modalProdutoCategoria");
  const descEl = document.getElementById("modalProdutoDescricao");
  const pesoEl = document.getElementById("modalProdutoPeso");
  const dimEl = document.getElementById("modalProdutoDimensoes");
  const precoAEl = document.getElementById("modalProdutoPrecoAtacado");
  const precoVEl = document.getElementById("modalProdutoPrecoVarejo");
  const imagensEl = document.getElementById("modalProdutoImagens");
  const thumbsEl = document.getElementById("modalProdutoThumbs");
  const titulo = document.getElementById("modalProdutoTitulo");

  try {
    const res = await fetch(`${API_BASE}/rein/produto/${produtoId}`);
    if (!res.ok) return;

    const payload = await res.json();
    const det = normalizarDetalheRein(payload);
    if (!det) return;

    if (det.nome) {
      titulo.textContent = det.nome;
    }

    if (det.categorias && det.categorias.length) {
      catEl.textContent = det.categorias.join(" | ");
    }

    if (det.descricao) {
  // A descrição vem da REIN em HTML (com <p>, <br>, entidades etc.)
  // innerHTML faz o navegador renderizar certinho com acentos e quebras.
      descEl.innerHTML = det.descricao;
    }


    const pesoLiq = Number(det.peso_liquido ?? 0);
    const pesoBru = Number(det.peso_bruto ?? 0);
    if (pesoLiq || pesoBru) {
      const liq = Number.isFinite(pesoLiq) ? pesoLiq : 0;
      const bru = Number.isFinite(pesoBru) ? pesoBru : liq;
      pesoEl.textContent = `Líquido: ${liq.toFixed(
        3
      )} kg • Bruto: ${bru.toFixed(3)} kg`;
    }

    const largura = Number(det.largura_cm ?? 0);
    const altura = Number(det.altura_cm ?? 0);
    const comp = Number(det.comprimento_cm ?? 0);
    const cub = Number(det.cubagem ?? 0);
    if (largura || altura || comp) {
      let textoDim = `${largura.toFixed(1)} x ${altura.toFixed(
        1
      )} x ${comp.toFixed(1)} cm`;
      if (cub) {
        textoDim += ` (Cubagem: ${cub.toFixed(4)})`;
      }
      dimEl.textContent = textoDim;
    }

    if (typeof det.preco_atacado === "number") {
      precoAEl.textContent = `R$ ${det.preco_atacado.toFixed(2)}`;
    }
    if (typeof det.preco_varejo === "number") {
      precoVEl.textContent = `R$ ${det.preco_varejo.toFixed(2)}`;
    }

    const imagens = det.imagens || [];
    if (imagens.length) {
      function renderPrincipal(src) {
        imagensEl.innerHTML = `
          <img src="${src}" alt="${(det.nome || "")
            .replace(/"/g, "&quot;")}" class="w-full h-full object-contain" />
        `;
      }

      renderPrincipal(imagens[0].conteudo);

      thumbsEl.innerHTML = "";
      for (const img of imagens) {
        const src = img.conteudo;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className =
          "border border-slate-700 rounded-md overflow-hidden w-16 h-16 flex-shrink-0 hover:border-sky-500";
        btn.innerHTML = `<img src="${src}" class="w-full h-full object-cover" />`;
        btn.addEventListener("click", () => renderPrincipal(src));
        thumbsEl.appendChild(btn);
      }
    }
  } catch (err) {
    console.error(err);
  }
}

// Fechar modal por clique / ESC
document.addEventListener("click", (ev) => {
  const closeBtn = ev.target.closest("#modalProdutoFechar");
  if (closeBtn) {
    fecharModalProduto();
    return;
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

// ===============================
// SALDO / PEDIDOS
// ===============================
async function carregarSaldo(id) {
  try {
    const res = await fetch(`${API_BASE}/auth/saldo/${id}`);
    const data = await res.json();
    const val = data?.total || 0;
    const el = document.getElementById("saldo");
    if (el) el.textContent = "R$ " + val.toFixed(2);
  } catch (err) {
    console.error(err);
  }
}

async function carregarPedidos(id) {
  try {
    const res = await fetch(`${API_BASE}/auth/pedidos/${id}`);
    const pedidos = await res.json();
    const elQtd = document.getElementById("pedidos");
    if (elQtd) elQtd.textContent = pedidos.length || 0;

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
// UTM / LINK AFILIADO
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
    if (document.getElementById("nome"))
      document.getElementById("nome").textContent = atualizado.nome;
    if (document.getElementById("email"))
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
// NAVEGAÇÃO / SESSÃO DO PAINEL
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

// Carregar subhtml de busca de produto
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

// Protege o painel e carrega dados iniciais
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
