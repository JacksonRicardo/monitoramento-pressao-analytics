/* Gráficos do dashboard (Chart.js 4) */
(function () {
  "use strict";

  const ler = (id) => {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  };

  const series = ler("dados-series");
  const diarios = ler("dados-diarios");
  const faixas = ler("dados-faixas");
  const periodos = ler("dados-periodos");
  const semana = ler("dados-semana");
  const meta = ler("dados-meta");
  if (!series) return;

  // Garante o registro do plugin de anotações (linhas de referência)
  if (window["chartjs-plugin-annotation"]) Chart.register(window["chartjs-plugin-annotation"]);

  const CORES = {
    sis: "#c0392b",
    dia: "#2e86c1",
    pul: "#27ae60",
    sisFundo: "rgba(192,57,43,.12)",
    diaFundo: "rgba(46,134,193,.12)",
  };

  const graficos = [];

  function aplicarTema() {
    const escuro = document.documentElement.getAttribute("data-bs-theme") === "dark";
    Chart.defaults.color = escuro ? "#adb5bd" : "#6c757d";
    Chart.defaults.borderColor = escuro ? "rgba(255,255,255,.08)" : "rgba(0,0,0,.06)";
    graficos.forEach((g) => g.update("none"));
  }

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.maintainAspectRatio = false;
  aplicarTema();

  // ------------------------------------------------------------------ Evolução
  const linhasReferencia = {
    ref140: {
      type: "line", yMin: 140, yMax: 140, borderColor: "rgba(192,57,43,.45)", borderWidth: 1, borderDash: [6, 4],
      label: { display: true, content: "140", position: "start", backgroundColor: "rgba(192,57,43,.7)", font: { size: 10 } },
    },
    ref90: {
      type: "line", yMin: 90, yMax: 90, borderColor: "rgba(46,134,193,.45)", borderWidth: 1, borderDash: [6, 4],
      label: { display: true, content: "90", position: "start", backgroundColor: "rgba(46,134,193,.7)", font: { size: 10 } },
    },
  };
  if (meta) {
    linhasReferencia.metaSis = {
      type: "line", yMin: meta.sistolica, yMax: meta.sistolica, borderColor: "rgba(25,135,84,.7)", borderWidth: 1.5,
      label: { display: true, content: "Meta " + meta.sistolica, position: "end", backgroundColor: "rgba(25,135,84,.8)", font: { size: 10 } },
    };
  }

  function datasetsMedicoes() {
    return {
      labels: series.labels,
      datasets: [
        { label: "Sistólica", data: series.sistolica, borderColor: CORES.sis, backgroundColor: CORES.sisFundo, fill: false, tension: 0.3, pointRadius: 3 },
        { label: "Diastólica", data: series.diastolica, borderColor: CORES.dia, backgroundColor: CORES.diaFundo, fill: false, tension: 0.3, pointRadius: 3 },
        { label: "Pulsação", data: series.pulsacao, borderColor: CORES.pul, borderDash: [4, 3], tension: 0.3, pointRadius: 2, spanGaps: true, hidden: false },
        { label: "Média móvel sist. (7)", data: series.mm_sistolica, borderColor: "rgba(192,57,43,.45)", borderWidth: 3, pointRadius: 0, tension: 0.4, spanGaps: true },
        { label: "Média móvel diast. (7)", data: series.mm_diastolica, borderColor: "rgba(46,134,193,.45)", borderWidth: 3, pointRadius: 0, tension: 0.4, spanGaps: true },
      ],
    };
  }

  function datasetsDiarios() {
    return {
      labels: diarios.labels,
      datasets: [
        { label: "Sistólica (média do dia)", data: diarios.sistolica, borderColor: CORES.sis, backgroundColor: CORES.sisFundo, fill: "+1", tension: 0.3, pointRadius: 3 },
        { label: "Diastólica (média do dia)", data: diarios.diastolica, borderColor: CORES.dia, backgroundColor: CORES.diaFundo, fill: false, tension: 0.3, pointRadius: 3 },
      ],
    };
  }

  const evolucao = new Chart(document.getElementById("grafico-evolucao"), {
    type: "line",
    data: datasetsMedicoes(),
    options: {
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10 } },
        y: { suggestedMin: 50, suggestedMax: 160, title: { display: true, text: "mmHg" } },
      },
      plugins: {
        annotation: { annotations: linhasReferencia },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.formattedValue ?? "-"}` } },
      },
    },
  });
  graficos.push(evolucao);

  document.querySelectorAll('input[name="modo-evolucao"]').forEach((radio) =>
    radio.addEventListener("change", (e) => {
      evolucao.data = e.target.value === "diario" ? datasetsDiarios() : datasetsMedicoes();
      evolucao.update();
    })
  );

  // ------------------------------------------------------------------ Faixas
  const faixasComDados = faixas.filter((f) => f.n > 0);
  graficos.push(
    new Chart(document.getElementById("grafico-faixas"), {
      type: "doughnut",
      data: {
        labels: faixasComDados.map((f) => f.rotulo),
        datasets: [{ data: faixasComDados.map((f) => f.n), backgroundColor: faixasComDados.map((f) => f.hex), borderWidth: 2 }],
      },
      options: {
        cutout: "62%",
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              label: (c) => {
                const f = faixasComDados[c.dataIndex];
                return ` ${f.rotulo}: ${f.n} (${f.pct.toLocaleString("pt-BR")}%)`;
              },
            },
          },
        },
      },
    })
  );

  // ------------------------------------------------------------------ Barras
  function barras(id, itens, chaveRotulo) {
    return new Chart(document.getElementById(id), {
      type: "bar",
      data: {
        labels: itens.map((i) => i[chaveRotulo]),
        datasets: [
          { label: "Sistólica", data: itens.map((i) => i.sistolica), backgroundColor: CORES.sis, borderRadius: 6 },
          { label: "Diastólica", data: itens.map((i) => i.diastolica), backgroundColor: CORES.dia, borderRadius: 6 },
        ],
      },
      options: {
        scales: { y: { beginAtZero: false, suggestedMin: 50 } },
        plugins: {
          tooltip: {
            callbacks: { afterBody: (ctx) => `Medições: ${itens[ctx[0].dataIndex].n}` },
          },
        },
      },
    });
  }
  graficos.push(barras("grafico-periodos", periodos, "periodo"));
  graficos.push(barras("grafico-semana", semana, "dia"));

  // ------------------------------------------------------------------ Dispersão
  graficos.push(
    new Chart(document.getElementById("grafico-dispersao"), {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Medições",
            data: series.dispersao,
            pointBackgroundColor: series.dispersao.map((p) => p.c),
            pointRadius: 5,
            pointHoverRadius: 7,
          },
        ],
      },
      options: {
        scales: {
          x: { title: { display: true, text: "Diastólica" }, suggestedMin: 50, suggestedMax: 110 },
          y: { title: { display: true, text: "Sistólica" }, suggestedMin: 90, suggestedMax: 180 },
        },
        plugins: {
          legend: { display: false },
          annotation: {
            annotations: {
              zona: {
                type: "box", xMax: 90, yMax: 140, xMin: 0, yMin: 0,
                backgroundColor: "rgba(25,135,84,.06)", borderWidth: 0,
              },
            },
          },
          tooltip: { callbacks: { label: (c) => ` ${c.raw.y}/${c.raw.x} mmHg` } },
        },
      },
    })
  );

  document.addEventListener("tema-alterado", aplicarTema);
})();
