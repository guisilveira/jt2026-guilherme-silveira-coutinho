(function () {
  "use strict";

  const dataNode = document.getElementById("dashboard-data");
  if (!dataNode) throw new Error("Dados incorporados do dashboard não encontrados.");
  const data = JSON.parse(dataNode.textContent);
  const state = { ...data.scenarioControls.default };

  const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  const pct = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const decimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  function grossYield(segment, occupancy, seasonality, purchaseBasis) {
    return segment.airbnbTypicalPrice * seasonality * 365 * occupancy / segment.purchasePrice[purchaseBasis];
  }

  function shortLabel(segment) {
    return `${segment.bairro} · ${segment.quartos}Q`;
  }

  function makeControls(containerId, values, selectedKey, formatter, onChange) {
    const container = document.getElementById(containerId);
    container.replaceChildren();
    values.forEach((value) => {
      const key = typeof value === "object" ? value.key : value;
      const label = typeof value === "object" ? value.label : formatter(value);
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.dataset.value = key;
      button.className = String(key) === String(selectedKey) ? "active" : "";
      button.setAttribute("aria-pressed", String(String(key) === String(selectedKey)));
      button.addEventListener("click", () => {
        onChange(key);
        [...container.children].forEach((item) => {
          const active = item.dataset.value === String(key);
          item.classList.toggle("active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        updateScenario();
      });
      container.appendChild(button);
    });
  }

  function updateScenario() {
    const ranking = data.segments
      .map((segment) => ({ segment, yield: grossYield(segment, state.occupancy, state.seasonality, state.purchaseBasis) }))
      .sort((a, b) => b.yield - a.yield);
    const maxYield = ranking[0].yield;
    document.getElementById("scenario-leader").textContent = ranking[0].segment.label;
    document.getElementById("scenario-yield").textContent = pct.format(ranking[0].yield);
    const isIntermediate = state.occupancy === 0.45 && state.seasonality === 0.8;
    const basisLabel = data.scenarioControls.purchaseBases.find((item) => item.key === state.purchaseBasis).label;
    document.getElementById("scenario-note").textContent = `${isIntermediate ? "Cenário intermediário ilustrativo" : "Teste de estresse selecionado"} · preço de compra: ${basisLabel}. ${state.purchaseBasis === "p25" ? "Centro/1 quarto assume a liderança: a decisão não é totalmente robusta ao preço de aquisição." : "Ocupação e sazonalidade não são observadas."}`;

    const chart = document.getElementById("ranking-chart");
    chart.replaceChildren();
    ranking.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = `rank-row${item.segment.key === data.recommendation.segmentKey ? " recommended" : ""}`;
      row.innerHTML = `
        <span class="rank-number">${index + 1}</span>
        <span class="rank-label"><strong>${shortLabel(item.segment)}</strong><small>${item.segment.airbnbListings} Airbnb · ${item.segment.vivarealListings.toLocaleString("pt-BR")} VivaReal</small></span>
        <span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${(item.yield / maxYield) * 100}%"></span></span>
        <span class="rank-value">${pct.format(item.yield)}</span>`;
      chart.appendChild(row);
    });

    renderStressGrid();
  }

  function renderStressGrid() {
    const segment = data.segments.find((item) => item.key === data.recommendation.segmentKey);
    const grid = document.getElementById("stress-grid");
    grid.replaceChildren();
    const corner = document.createElement("div");
    corner.className = "stress-cell header";
    corner.textContent = "Ocupação ↓";
    grid.appendChild(corner);
    data.scenarioControls.seasonality.forEach((seasonality) => {
      const header = document.createElement("div");
      header.className = "stress-cell header";
      header.textContent = `${Math.round(seasonality * 100)}% da diária`;
      grid.appendChild(header);
    });
    data.scenarioControls.occupancy.forEach((occupancy) => {
      const rowHeader = document.createElement("div");
      rowHeader.className = "stress-cell header";
      rowHeader.textContent = `${Math.round(occupancy * 100)}% ocup.`;
      grid.appendChild(rowHeader);
      data.scenarioControls.seasonality.forEach((seasonality) => {
        const cell = document.createElement("div");
        const intermediate = occupancy === 0.45 && seasonality === 0.8;
        cell.className = `stress-cell${intermediate ? " intermediate" : ""}`;
        const value = grossYield(segment, occupancy, seasonality, state.purchaseBasis);
        cell.innerHTML = `<strong>${pct.format(value)}</strong><small>${intermediate ? "intermediário ilustrativo" : "teste de estresse"}</small>`;
        grid.appendChild(cell);
      });
    });
  }

  function renderAssociations() {
    const positive = document.getElementById("positive-associations");
    data.characteristics.positive.forEach((item) => {
      const card = document.createElement("div");
      card.className = "association-card";
      card.innerHTML = `<span>+${decimal.format(item.effect * 100)}%</span><strong>${item.label}</strong><small>${item.unit} · n=${item.listings} imóveis · ${item.hosts} anfitriões</small><div class="association-ci">IC95 ${pct.format(item.ciLow)} a ${pct.format(item.ciHigh)}</div>`;
      positive.appendChild(card);
    });
    const negative = document.getElementById("negative-associations");
    data.characteristics.negative.forEach((item) => {
      const card = document.createElement("div");
      card.innerHTML = `<span>${decimal.format(item.effect * 100)}%</span>${item.label}`;
      negative.appendChild(card);
    });
  }

  function renderLimitations() {
    const grid = document.getElementById("limitations-grid");
    data.quality.limitations.forEach((text, index) => {
      const card = document.createElement("div");
      card.className = "limitation-card";
      card.innerHTML = `<span>Limitação ${String(index + 1).padStart(2, "0")}</span><p>${text}</p>`;
      grid.appendChild(card);
    });
  }

  makeControls("occupancy-controls", data.scenarioControls.occupancy, state.occupancy, (value) => `${Math.round(value * 100)}%`, (value) => { state.occupancy = Number(value); });
  makeControls("seasonality-controls", data.scenarioControls.seasonality, state.seasonality, (value) => `${Math.round(value * 100)}%`, (value) => { state.seasonality = Number(value); });
  makeControls("purchase-controls", data.scenarioControls.purchaseBases, state.purchaseBasis, () => "", (value) => { state.purchaseBasis = value; });
  renderAssociations();
  renderLimitations();
  updateScenario();

  window.__dashboardTestApi = {
    data,
    grossYield,
    getState: () => ({ ...state }),
    select: (control, value) => {
      const id = { occupancy: "occupancy-controls", seasonality: "seasonality-controls", purchaseBasis: "purchase-controls" }[control];
      const button = [...document.getElementById(id).querySelectorAll("button")].find((item) => item.dataset.value === String(value));
      if (!button) throw new Error(`Controle inválido: ${control}=${value}`);
      button.click();
    },
  };
})();
