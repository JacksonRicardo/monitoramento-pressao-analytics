/* Scripts globais */
(function () {
  "use strict";

  // ---- Tema claro/escuro ----------------------------------------------------
  const botao = document.getElementById("alternar-tema");
  const raiz = document.documentElement;

  function atualizarIcone() {
    if (!botao) return;
    const escuro = raiz.getAttribute("data-bs-theme") === "dark";
    botao.innerHTML = escuro ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
  }

  if (botao) {
    botao.addEventListener("click", () => {
      const novo = raiz.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      raiz.setAttribute("data-bs-theme", novo);
      localStorage.setItem("tema", novo);
      atualizarIcone();
      document.dispatchEvent(new Event("tema-alterado"));
    });
  }
  atualizarIcone();

  // ---- Fecha alertas de sucesso automaticamente -----------------------------
  setTimeout(() => {
    document.querySelectorAll(".alert-success, .alert-info").forEach((el) => {
      if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(el).close();
    });
  }, 6000);

  // ---- Formulário de medição: período automático pela hora ------------------
  const hora = document.getElementById("id_hora");
  const periodo = document.getElementById("id_periodo");
  const dica = document.getElementById("dica-periodo");
  if (hora && periodo && dica) {
    const calcular = () => {
      const h = parseInt((hora.value || "").split(":")[0], 10);
      if (isNaN(h)) return (dica.textContent = "");
      const p = h >= 5 && h < 12 ? "Manhã" : h >= 12 && h < 18 ? "Tarde" : "Noite";
      dica.textContent = periodo.value ? "" : `Será registrado como: ${p}`;
    };
    hora.addEventListener("input", calcular);
    periodo.addEventListener("change", calcular);
    calcular();
  }

  // ---- Prévia da faixa de referência no formulário -------------------------
  const sis = document.getElementById("id_sistolica");
  const dia = document.getElementById("id_diastolica");
  const previa = document.getElementById("previa-faixa");
  if (sis && dia && previa) {
    const faixas = [
      ["otima", "Ótima", 0, 0],
      ["normal", "Normal", 120, 80],
      ["pre", "Pré-hipertensão", 130, 85],
      ["ha1", "Estágio 1", 140, 90],
      ["ha2", "Estágio 2", 160, 100],
      ["ha3", "Estágio 3", 180, 110],
    ];
    const atualizar = () => {
      const s = parseInt(sis.value, 10);
      const d = parseInt(dia.value, 10);
      if (isNaN(s) || isNaN(d)) {
        previa.innerHTML = '<span class="text-body-secondary">Informe sistólica e diastólica</span>';
        return;
      }
      let escolhida = faixas[0];
      faixas.forEach((f) => { if (s >= f[2] || d >= f[3]) escolhida = f; });
      const pam = Math.round((s + 2 * d) / 3);
      previa.innerHTML =
        `<span class="display-6 fw-bold me-2">${s}/${d}</span>` +
        `<span class="badge rounded-pill faixa-${escolhida[0]}">${escolhida[1]}</span>` +
        `<div class="small text-body-secondary mt-1">PAM ${pam} mmHg · Pressão de pulso ${s - d} mmHg</div>` +
        (d >= s ? '<div class="small text-danger mt-1">A diastólica deve ser menor que a sistólica.</div>' : "");
    };
    sis.addEventListener("input", atualizar);
    dia.addEventListener("input", atualizar);
    atualizar();
  }
})();

