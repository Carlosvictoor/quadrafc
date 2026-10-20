/* =====================================================================
   QuadraPro — interações no navegador (JavaScript puro, sem bibliotecas)
   Todas as regras importantes são validadas também no servidor (Python);
   aqui ficam só as melhorias de uso.
   ===================================================================== */
(function () {
  "use strict";

  /* ---------- Menu lateral no celular (botão ☰) ---------- */
  const toggle = document.querySelector("[data-menu-toggle]");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const open = document.body.classList.toggle("menu-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    // Tocar fora do menu (no fundo escuro) fecha o menu.
    document.addEventListener("click", (e) => {
      if (document.body.classList.contains("menu-open") &&
          !e.target.closest(".sidebar") && !e.target.closest("[data-menu-toggle]")) {
        document.body.classList.remove("menu-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ---------- Mostrar / ocultar senha (botão de olho) ---------- */
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = btn.parentElement.querySelector("input");
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
    });
  });

  /* ---------- Mensagens (toasts) somem sozinhas depois de 5 segundos ---------- */
  document.querySelectorAll(".toast").forEach((toast) => {
    setTimeout(() => {
      toast.classList.add("hide");
      setTimeout(() => toast.remove(), 400);
    }, 5000);
  });

  /** Mostra uma mensagem rápida criada pelo JavaScript. */
  function showToast(message, kind) {
    let box = document.querySelector(".toasts");
    if (!box) {
      box = document.createElement("div");
      box.className = "toasts";
      document.body.appendChild(box);
    }
    const el = document.createElement("div");
    el.className = "toast " + (kind || "success");
    el.setAttribute("role", "status");
    el.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 13l4 4L19 7"/></svg><span></span>';
    el.querySelector("span").textContent = message; // textContent evita injeção de HTML
    box.appendChild(el);
    setTimeout(() => { el.classList.add("hide"); setTimeout(() => el.remove(), 400); }, 3500);
  }

  /* ---------- Confirmação antes de ações importantes ----------
     Qualquer formulário com data-confirm="Mensagem" pede confirmação
     numa janela própria (não usamos o alert() do navegador). */
  const modal = document.getElementById("confirm-modal");
  let pendingForm = null;
  let pendingSubmitter = null; // botão clicado (o servidor usa o nome dele)
  if (modal) {
    const title = modal.querySelector("[data-modal-title]");
    const text = modal.querySelector("[data-modal-text]");
    const ok = modal.querySelector("[data-modal-ok]");
    const close = () => { modal.classList.remove("open"); pendingForm = null; pendingSubmitter = null; };

    document.addEventListener("submit", (e) => {
      const form = e.target;
      if (!form.dataset.confirm || form.dataset.confirmed === "1") return;
      e.preventDefault();
      pendingForm = form;
      pendingSubmitter = e.submitter || null;
      title.textContent = form.dataset.confirmTitle || "Tem certeza?";
      text.textContent = form.dataset.confirm;
      ok.textContent = form.dataset.confirmOk || "Confirmar";
      modal.classList.add("open");
      ok.focus();
    }, true);

    ok.addEventListener("click", () => {
      if (!pendingForm) return;
      const form = pendingForm;
      const submitter = pendingSubmitter;
      form.dataset.confirmed = "1";
      close();
      form.requestSubmit(submitter);
    });
    modal.querySelector("[data-modal-cancel]").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  }

  /* ---------- Evita clique duplo: botão mostra "Salvando..." ao enviar ---------- */
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.dataset.confirm && form.dataset.confirmed !== "1") return;
    const btn = e.submitter || form.querySelector("button[type=submit]");
    if (btn && btn.dataset.loading !== "off") {
      // Atraso mínimo para o navegador enviar o nome do botão antes de desabilitar.
      setTimeout(() => {
        btn.classList.add("is-loading");
        if (btn.dataset.loadingText) btn.textContent = btn.dataset.loadingText;
      }, 0);
    }
  });

  /* ---------- Busca instantânea na lista de jogadores ---------- */
  const search = document.querySelector("[data-live-search]");
  if (search) {
    // Remove acentos para "joao" encontrar "João".
    const normalize = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const items = document.querySelectorAll("[data-search-item]");
    const empty = document.querySelector("[data-search-empty]");
    search.addEventListener("input", () => {
      const q = normalize(search.value.trim());
      let visible = 0;
      items.forEach((item) => {
        const show = normalize(item.dataset.searchItem).includes(q);
        item.hidden = !show;
        if (show) visible++;
      });
      if (empty) empty.hidden = visible > 0;
    });
  }

  /* ---------- Animações das barras de progresso e da rosca ---------- */
  requestAnimationFrame(() => {
    document.querySelectorAll("[data-progress]").forEach((bar) => {
      bar.style.width = Math.max(0, Math.min(100, Number(bar.dataset.progress))) + "%";
    });
    document.querySelectorAll("[data-donut]").forEach((donut) => {
      // Anima de 0 até o valor, atualizando a variável CSS --p.
      const target = Number(donut.dataset.donut);
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / 900);
        const eased = 1 - Math.pow(1 - t, 3);
        donut.style.setProperty("--p", (target * eased).toFixed(1));
        if (t < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  });

  /* ---------- Copiar texto (tela "Compartilhar resumo") ---------- */
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const source = document.querySelector(btn.dataset.copy);
      const text = source ? source.textContent : "";
      try {
        await navigator.clipboard.writeText(text);
      } catch (err) {
        // Navegadores antigos: copia selecionando o texto.
        const area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      showToast("Texto copiado! É só colar no grupo.");
    });
  });

  /* ---------- Registrar pagamento: ao trocar o jogador, preenche o valor ---------- */
  const playerSelect = document.querySelector("[data-player-select]");
  if (playerSelect) {
    const players = JSON.parse(document.getElementById("players-data").textContent);
    const amount = document.querySelector("[data-amount]");
    const warning = document.querySelector("[data-paid-warning]");
    const update = (fillAmount) => {
      const p = players[playerSelect.value];
      if (!p) return;
      if (fillAmount) amount.value = p.amount;
      if (warning) warning.hidden = !p.paid;
    };
    playerSelect.addEventListener("change", () => update(true));
    update(false);
  }

  /* ---------- Campos de dinheiro: aceita só números, vírgula e ponto ---------- */
  document.querySelectorAll("[data-money]").forEach((input) => {
    input.addEventListener("input", () => {
      const clean = input.value.replace(/[^0-9.,]/g, "");
      if (clean !== input.value) input.value = clean;
    });
  });
})();
