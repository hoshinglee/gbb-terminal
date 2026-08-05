const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
const setStatus = (value) => { $("#status").textContent = `● ${value}`; };
const formatNumber = (value, decimals = 2) => Number.isFinite(Number(value)) ? Number(value).toFixed(decimals) : String(value ?? "—");
const signed = (number, suffix = "%") => `<span class="${number >= 0 ? "positive" : "negative"}">${number >= 0 ? "+" : ""}${formatNumber(number)}${suffix}</span>`;

let selectedStrategyId = null;
let catalogueStrategies = [];
let templates = [];
let currentTemplate = null;
let definitionMode = "natural";
let pendingProposal = null;
let lastOptionRequest = null;
let currentPosition = null;
let lastOptionSimulation = null;

function notify(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.style.display = "block";
  window.clearTimeout(notify.timeout);
  notify.timeout = window.setTimeout(() => { toast.style.display = "none"; }, 6500);
}

async function api(url, options = {}) {
  setStatus("LOADING");
  try {
    const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) throw new Error(payload.detail || "The data request failed.");
    return payload;
  } catch (error) {
    if (error instanceof TypeError) throw new Error("Cannot reach the terminal API. Start FastAPI and refresh this page.");
    throw error;
  } finally {
    setStatus("READY");
  }
}

function withLoading(selector, work) {
  return async () => {
    const button = $(selector);
    const label = button.textContent;
    button.disabled = true;
    button.textContent = "Working…";
    try { await work(); } catch (error) { setStatus("ERROR"); notify(error.message); }
    finally { button.disabled = false; button.textContent = label; }
  };
}

function metricCards(target, items) {
  $(target).innerHTML = items.map((item) => `<div class="metric"><span>${escapeHtml(item.label)}</span><strong class="${Number(item.value) < 0 ? "negative" : Number(item.value) > 0 ? "positive" : ""}">${escapeHtml(item.display)}</strong></div>`).join("");
}

function dataTable(rows, fields) {
  return `<div class="table-row chain-head">${fields.map((field) => `<span>${field.label}</span>`).join("")}</div>${rows.map((row) => `<div class="table-row">${fields.map((field) => `<span>${field.format ? field.format(row[field.key]) : escapeHtml(row[field.key])}</span>`).join("")}</div>`).join("")}`;
}

function drawChart(canvas, series, lines, xKey, tooltipFormatter = null) {
  if (!series?.length) return;
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  const padding = { top: 18, right: 14, bottom: 31, left: 14 };
  const plotHeight = height - padding.top - padding.bottom;
  const plotWidth = width - padding.left - padding.right;
  const values = lines.flatMap((line) => series.map((point) => Number(point[line.key])).filter(Number.isFinite));
  if (!values.length) return;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  const x = (index) => padding.left + index * plotWidth / Math.max(series.length - 1, 1);
  const y = (value) => padding.top + (maximum - value) / range * plotHeight;

  function render(highlightIndex = null) {
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.strokeStyle = "#26332e";
    context.lineWidth = 1;
    for (let grid = 0; grid < 4; grid += 1) {
      const position = padding.top + grid * plotHeight / 3;
      context.beginPath(); context.moveTo(padding.left, position); context.lineTo(width - padding.right, position); context.stroke();
    }
    if (minimum < 0 && maximum > 0) {
      context.strokeStyle = "#52635c";
      context.beginPath(); context.moveTo(padding.left, y(0)); context.lineTo(width - padding.right, y(0)); context.stroke();
    }
    lines.forEach((line) => {
      context.strokeStyle = line.color;
      context.lineWidth = 2;
      context.beginPath();
      let started = false;
      series.forEach((point, index) => {
        const value = Number(point[line.key]);
        if (!Number.isFinite(value)) return;
        if (started) context.lineTo(x(index), y(value)); else { context.moveTo(x(index), y(value)); started = true; }
      });
      context.stroke();
    });
    if (xKey) {
      context.fillStyle = "#789087"; context.font = "10px DM Mono";
      context.textAlign = "left"; context.fillText(series[0][xKey], padding.left, height - 7);
      context.textAlign = "center"; context.fillText(series[Math.floor(series.length / 2)][xKey], width / 2, height - 7);
      context.textAlign = "right"; context.fillText(series.at(-1)[xKey], width - padding.right, height - 7);
    }
    if (highlightIndex !== null) {
      context.strokeStyle = "#8ba097"; context.lineWidth = 1;
      context.beginPath(); context.moveTo(x(highlightIndex), padding.top); context.lineTo(x(highlightIndex), height - padding.bottom); context.stroke();
      lines.forEach((line) => {
        const value = Number(series[highlightIndex][line.key]);
        if (!Number.isFinite(value)) return;
        context.fillStyle = line.color; context.beginPath(); context.arc(x(highlightIndex), y(value), 3.5, 0, Math.PI * 2); context.fill();
      });
    }
  }

  render();
  const shell = canvas.closest(".chart-shell");
  const tooltip = shell?.querySelector(".chart-tooltip");
  canvas.onmousemove = (event) => {
    const bounds = canvas.getBoundingClientRect();
    const index = Math.max(0, Math.min(series.length - 1, Math.round((event.clientX - bounds.left - padding.left) / plotWidth * (series.length - 1))));
    render(index);
    if (!tooltip) return;
    const point = series[index];
    const defaultRows = lines.map((line) => `<span><i style="background:${line.color}"></i>${escapeHtml(line.label || line.key)}</span><b>${formatNumber(point[line.key], 4)}</b>`).join("");
    tooltip.innerHTML = tooltipFormatter ? tooltipFormatter(point) : `<strong>${escapeHtml(point[xKey])}</strong><div>${defaultRows}</div>`;
    tooltip.hidden = false;
    tooltip.style.left = `${Math.min(Math.max(event.clientX - bounds.left + 14, 8), width - tooltip.offsetWidth - 8)}px`;
    tooltip.style.top = `${Math.max(event.clientY - bounds.top - tooltip.offsetHeight - 12, 6)}px`;
  };
  canvas.onmouseleave = () => { render(); if (tooltip) tooltip.hidden = true; };
}

function researchTooltip(point) {
  const indicators = Object.entries(point.indicators || {}).map(([key, value]) => `<span>${escapeHtml(key.replaceAll("_", " "))}</span><b>${formatNumber(value, 3)}</b>`).join("");
  return `<strong>${escapeHtml(point.date)}</strong><div><span>OHLC</span><b>${formatNumber(point.open)} / ${formatNumber(point.high)} / ${formatNumber(point.low)} / ${formatNumber(point.close)}</b><span>Volume</span><b>${Number(point.volume || 0).toLocaleString()}</b><span>Position</span><b>${point.position === 1 ? "Long" : point.position === -1 ? "Short" : "Cash"}</b><span>Strategy Equity</span><b>${formatNumber(point.strategy, 4)}</b><span>Buy & Hold</span><b>${formatNumber(point.buyHold, 4)}</b><span>SPY</span><b>${formatNumber(point.spy, 4)}</b>${indicators}</div>`;
}

function animateMonteCarlo(paths) {
  const canvas = $("#simulation-chart");
  const start = performance.now();
  const duration = 1000;
  const render = (now) => {
    const amount = Math.max(2, Math.floor(paths.length * Math.min((now - start) / duration, 1)));
    drawChart(canvas, paths.slice(0, amount), [{ key: "p10", label: "10th", color: "#ff6a6a" }, { key: "p50", label: "Median", color: "#b6f559" }, { key: "p90", label: "90th", color: "#64d5c7" }], "day");
    if (amount < paths.length) requestAnimationFrame(render);
  };
  requestAnimationFrame(render);
}

function renderTrades(trades) {
  const safeTrades = Array.isArray(trades) ? trades : [];
  const closed = safeTrades.filter((trade) => trade.status === "Closed").length;
  $("#trade-count").textContent = `${closed} Closed · ${safeTrades.length - closed} Open`;
  if (!safeTrades.length) {
    $("#trade-ledger").innerHTML = "<p class=\"empty-state\">No entries were triggered in this test window.</p>";
    return;
  }
  const row = (trade) => `<div class="trade-row"><span>${escapeHtml(trade.status)}</span><span>${escapeHtml(trade.side)}</span><span>${escapeHtml(trade.entryDate)}</span><span>$${formatNumber(trade.entryPrice)}</span><span>${escapeHtml(trade.exitDate || `Open · ${trade.asOfDate}`)}</span><span>$${formatNumber(trade.exitPrice)}</span><span class="${trade.pnl >= 0 ? "positive" : "negative"}">$${formatNumber(trade.pnl)}</span><span class="${trade.pnlPercent >= 0 ? "positive" : "negative"}">${formatNumber(trade.pnlPercent)}%</span></div>`;
  $("#trade-ledger").innerHTML = `<div class="trade-row trade-head"><span>STATUS</span><span>SIDE</span><span>ENTRY</span><span>PRICE</span><span>EXIT / AS OF</span><span>PRICE</span><span>P&amp;L</span><span>RETURN</span></div>${safeTrades.map(row).join("")}`;
  $("#trade-ledger").hidden = false;
  $("#toggle-trades").setAttribute("aria-expanded", "true");
}

function renderCatalogue(strategies) {
  catalogueStrategies = strategies;
  $("#catalogue-count").textContent = `${strategies.length} Saved Strateg${strategies.length === 1 ? "y" : "ies"}`;
  const groups = Object.groupBy ? Object.groupBy(strategies, (strategy) => strategy.family || "Custom Strategies") : strategies.reduce((result, strategy) => { const family = strategy.family || "Custom Strategies"; (result[family] ||= []).push(strategy); return result; }, {});
  $("#strategy-catalogue").innerHTML = strategies.length ? Object.entries(groups).map(([family, items]) => `<section class="catalogue-family"><h3>${escapeHtml(family)}</h3>${items.map((strategy) => `<div class="catalogue-item"><div><strong>${escapeHtml(strategy.name)}</strong><p>${escapeHtml(strategy.description)}</p><span>${escapeHtml(strategy.templateId || "Custom Rule Graph")} · ${escapeHtml(strategy.updatedAt.slice(0, 10))}</span><div class="parameter-chips">${Object.entries(strategy.strategyJson?.parameter_values || {}).map(([key, value]) => `<em>${escapeHtml(key.replaceAll("_", " "))}: ${escapeHtml(value)}</em>`).join("")}</div></div><button class="outline load-strategy" data-strategy-id="${escapeHtml(strategy.id)}">Load</button><details><summary>Advanced · Export Definition</summary><textarea readonly>${escapeHtml(strategy.strategyJson ? JSON.stringify(strategy.strategyJson, null, 2) : strategy.strategyYaml || "Legacy definition")}</textarea></details></div>`).join("")}</section>`).join("") : "<p class=\"empty-state\">Saved strategies appear here after confirmation or template testing.</p>";
  $$(".load-strategy").forEach((button) => button.addEventListener("click", () => loadStrategyFromCatalogue(button.dataset.strategyId)));
}

async function loadCatalogue() {
  const response = await api("/api/strategies");
  renderCatalogue(response.strategies);
}

function loadStrategyFromCatalogue(strategyId) {
  const strategy = catalogueStrategies.find((item) => item.id === strategyId);
  if (!strategy) return;
  if (strategy.strategyJson) {
    const template = templates.find((item) => item.template_id === strategy.strategyJson.template_id);
    if (template) {
      currentTemplate = template;
      definitionMode = "template";
      $("#strategy-template").value = template.template_id;
      renderParameterControls(template, strategy.strategyJson.parameter_values);
      $("#configuration-name").textContent = strategy.name;
      $("#configuration-description").textContent = strategy.description;
      $("#strategy-ticker").value = strategy.strategyJson.ticker || $("#strategy-ticker").value;
      $("#strategy-benchmark").value = strategy.strategyJson.benchmark || "SPY";
      $("#backtest-window").value = strategy.strategyJson.timeframe || "1y";
      $("#universe-field").hidden = template.rule_graph.kind !== "ranked_portfolio";
      if (strategy.strategyJson.universe?.length) $("#strategy-universe").value = strategy.strategyJson.universe.join(", ");
    }
  } else {
    selectedStrategyId = strategy.id;
    definitionMode = "catalogue";
    $("#configuration-name").textContent = strategy.name;
    $("#configuration-description").textContent = strategy.description;
  }
  $("#strategy-input").value = "";
  $("#strategy-input").placeholder = strategy.description;
  $("#strategy-source").textContent = `Loaded “${strategy.name}” from the local catalogue.`;
  $("#strategy-catalogue-modal").close();
}

async function loadTemplates() {
  const response = await api("/api/v2/strategy-templates");
  templates = response.templates;
  const grouped = templates.reduce((result, template) => { (result[template.family] ||= []).push(template); return result; }, {});
  $("#strategy-template").innerHTML = `<option value="">Choose a strategy family…</option>${Object.entries(grouped).map(([family, items]) => `<optgroup label="${escapeHtml(family)}">${items.map((template) => `<option value="${escapeHtml(template.template_id)}">${escapeHtml(template.name)}</option>`).join("")}</optgroup>`).join("")}`;
}

function renderParameterControls(template, selectedValues = {}) {
  $("#parameter-controls").innerHTML = template.parameters.map((parameter) => {
    const value = selectedValues[parameter.key] ?? parameter.default;
    const inputType = parameter.parameter_type === "boolean" ? "checkbox" : "number";
    const checked = inputType === "checkbox" && value ? "checked" : "";
    const valueAttribute = inputType === "checkbox" ? "" : `value="${escapeHtml(value)}"`;
    const adaptive = parameter.adaptive_modes?.length ? `<option value="adaptive">Adaptive</option>` : "";
    return `<div class="parameter-card" data-key="${escapeHtml(parameter.key)}" data-type="${escapeHtml(parameter.parameter_type)}"><div><label>${escapeHtml(parameter.label)}</label><small>${escapeHtml(parameter.unit || "Value")}</small></div><input class="parameter-value" type="${inputType}" ${valueAttribute} ${checked} min="${parameter.minimum ?? ""}" max="${parameter.maximum ?? ""}" step="${parameter.step ?? 1}" /><select class="parameter-mode"><option value="fixed">Fixed</option>${adaptive}<option value="search">Search Range</option></select><div class="search-controls" hidden><input class="range-min" type="number" value="${parameter.minimum ?? value}" step="${parameter.step ?? 1}" /><span>to</span><input class="range-max" type="number" value="${parameter.maximum ?? value}" step="${parameter.step ?? 1}" /></div></div>`;
  }).join("");
  $$(".parameter-mode").forEach((select) => select.addEventListener("change", () => { select.closest(".parameter-card").querySelector(".search-controls").hidden = select.value !== "search"; }));
}

function selectedTemplateInstance() {
  if (!currentTemplate) throw new Error("Choose a validated strategy template first.");
  const values = {};
  const modes = {};
  $$(".parameter-card").forEach((card) => {
    const input = card.querySelector(".parameter-value");
    values[card.dataset.key] = card.dataset.type === "integer" ? Number.parseInt(input.value, 10) : card.dataset.type === "boolean" ? input.checked : Number(input.value);
    modes[card.dataset.key] = card.querySelector(".parameter-mode").value;
  });
  return {
    template_id: currentTemplate.template_id,
    template_version: currentTemplate.version,
    name: currentTemplate.name,
    description: currentTemplate.description,
    parameter_values: values,
    parameter_modes: modes,
    ticker: $("#strategy-ticker").value.trim().toUpperCase(),
    universe: currentTemplate.rule_graph.kind === "ranked_portfolio" ? $("#strategy-universe").value.split(",").map((symbol) => symbol.trim().toUpperCase()).filter(Boolean) : [],
    benchmark: $("#strategy-benchmark").value.trim().toUpperCase() || "SPY",
    timeframe: $("#backtest-window").value,
    risk: {},
    execution: { initial_capital: 100000, commission_bps: Number($("#commission-bps").value), slippage_bps: Number($("#slippage-bps").value), annual_cash_rate: 0 },
  };
}

function searchRanges() {
  const ranges = {};
  $$(".parameter-card").filter((card) => card.querySelector(".parameter-mode").value === "search").forEach((card) => {
    const minimum = Number(card.querySelector(".range-min").value);
    const maximum = Number(card.querySelector(".range-max").value);
    const step = Number(card.querySelector(".parameter-value").step || 1);
    const values = [];
    for (let value = minimum; value <= maximum + step / 10 && values.length < 30; value += step) values.push(Number(value.toFixed(8)));
    ranges[card.dataset.key] = values;
  });
  return ranges;
}

async function runBacktest() {
  const ticker = $("#strategy-ticker").value.trim().toUpperCase();
  if (!ticker) throw new Error("Enter a US ticker before running research.");
  if (definitionMode === "template") {
    const strategy = selectedTemplateInstance();
    const ranges = searchRanges();
    await api("/api/v2/strategies", { method: "POST", body: JSON.stringify({ strategy, original_instruction: "" }) });
    if (Object.keys(ranges).length) {
      const search = await api("/api/v2/parameter-searches", { method: "POST", body: JSON.stringify({ strategy, ranges, max_trials: 60 }) });
      renderBacktest(search.finalTest, `Guarded ${search.method}; final test began ${search.finalTestStart}.`);
      notify(`Parameter search completed ${search.attempts.length} trials. Best: ${JSON.stringify(search.bestParameters)}.`);
    } else {
      const run = await api("/api/v2/research-runs", { method: "POST", body: JSON.stringify({ strategy }) });
      renderBacktest(run.results, `Strategy Model V2 · Run ${run.run_id.slice(0, 8)}.`);
    }
    await loadCatalogue();
    return;
  }
  if (selectedStrategyId) {
    const data = await api("/api/backtest", { method: "POST", body: JSON.stringify({ ticker, instruction: "", strategy_id: selectedStrategyId, window: $("#backtest-window").value, benchmark: $("#strategy-benchmark").value.trim().toUpperCase(), commission_bps: Number($("#commission-bps").value), slippage_bps: Number($("#slippage-bps").value) }) });
    renderBacktest(data, `Loaded catalogue strategy · ${data.catalogueStrategy.provider.replaceAll("_", " ")}.`);
    return;
  }
  const instruction = $("#strategy-input").value.trim();
  if (instruction.length < 8) throw new Error("Describe a strategy or load one from the catalogue.");
  pendingProposal = await api("/api/strategy/propose", { method: "POST", body: JSON.stringify({ instruction }) });
  showProposal(pendingProposal);
}

function showProposal(proposal) {
  $("#proposal-name").textContent = proposal.strategy.name;
  $("#proposal-description").textContent = proposal.normalizedInstruction;
  $("#proposal-yaml").value = proposal.strategyYaml;
  const existing = $("#proposal-existing");
  existing.hidden = !proposal.existingStrategy;
  existing.textContent = proposal.existingStrategy ? `This rule graph already exists as “${proposal.existingStrategy.name}”. It will be reused instead of duplicated.` : "";
  $("#proposal-clarifications").innerHTML = proposal.clarifications.length ? `<strong>REVIEW THESE ASSUMPTIONS</strong><ul>${proposal.clarifications.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "";
  $("#strategy-confirmation-modal").showModal();
}

async function confirmProposal() {
  if (!pendingProposal) return;
  $("#strategy-confirmation-modal").close();
  const payload = { ticker: $("#strategy-ticker").value.trim().toUpperCase(), instruction: $("#strategy-input").value.trim(), strategy_yaml: $("#proposal-yaml").value, window: $("#backtest-window").value, benchmark: $("#strategy-benchmark").value.trim().toUpperCase(), commission_bps: Number($("#commission-bps").value), slippage_bps: Number($("#slippage-bps").value) };
  const data = await api("/api/backtest", { method: "POST", body: JSON.stringify(payload) });
  renderBacktest(data, `LLM-assisted definition · ${data.catalogueStrategy.provider.replaceAll("_", " ")}.`);
  selectedStrategyId = data.catalogueStrategy.id;
  $("#strategy-input").value = "";
  $("#strategy-input").placeholder = data.strategy.description;
  pendingProposal = null;
  await loadCatalogue();
}

function renderBacktest(data, source) {
  const metrics = data.metrics;
  metricCards("#backtest-metrics", [
    { label: "TOTAL RETURN", value: metrics.totalReturn, display: `${formatNumber(metrics.totalReturn)}%` },
    { label: "BUY & HOLD", value: metrics.benchmarkReturn, display: `${formatNumber(metrics.benchmarkReturn)}%` },
    { label: "MAX DRAWDOWN", value: metrics.maxDrawdown, display: `${formatNumber(metrics.maxDrawdown)}%` },
    { label: "SHARPE", value: metrics.sharpeRatio, display: formatNumber(metrics.sharpeRatio) },
    { label: "EXPOSURE", value: metrics.exposure, display: metrics.exposure === undefined ? "—" : `${formatNumber(metrics.exposure, 1)}%` },
  ]);
  $("#parsed-strategy").textContent = data.strategy.description;
  $("#strategy-source").textContent = source;
  $("#chart-window").textContent = `${$("#backtest-window").value.toUpperCase()} · NORMALIZED TO 1.00`;
  $("#outcome-explanation").textContent = data.explanation || "Review return, drawdown, exposure, and trade count together.";
  const verdict = data.verdict || { label: "Research Complete", reason: "Inspect all evidence before changing a strategy." };
  $("#evidence-verdict").textContent = verdict.label;
  $("#evidence-verdict").className = `verdict ${verdict.label.includes("Robust") ? "positive-verdict" : verdict.label.includes("Complexity") ? "negative-verdict" : "neutral"}`;
  $("#evidence-verdict").title = verdict.reason;
  const assumptions = data.assumptions || {};
  $("#assumption-list").innerHTML = `<li>Commission ${formatNumber(assumptions.commission_bps ?? 0, 1)} bps</li><li>Slippage ${formatNumber(assumptions.slippage_bps ?? 0, 1)} bps</li><li>Next-session signal execution</li>`;
  drawChart($("#backtest-chart"), data.chart, [{ key: "strategy", label: "Strategy", color: "#b6f559" }, { key: "buyHold", label: "Buy & Hold", color: "#64d5c7" }, { key: "spy", label: "SPY", color: "#f8bd5e" }], "date", researchTooltip);
  renderTrades(data.trades);
}

async function runSimulation() {
  const data = await api("/api/simulate", { method: "POST", body: JSON.stringify({ ticker: $("#strategy-ticker").value.trim().toUpperCase(), days: Number($("#simulation-days").value) }) });
  const metrics = data.metrics;
  metricCards("#simulation-metrics", [{ label: "MEDIAN RETURN", value: metrics.medianReturn, display: `${formatNumber(metrics.medianReturn)}%` }, { label: "10TH PERCENTILE", value: metrics.downsideReturn, display: `${formatNumber(metrics.downsideReturn)}%` }, { label: "90TH PERCENTILE", value: metrics.upsideReturn, display: `${formatNumber(metrics.upsideReturn)}%` }, { label: "PROFIT PROBABILITY", value: metrics.profitProbability, display: `${formatNumber(metrics.profitProbability, 1)}%` }]);
  animateMonteCarlo(data.paths);
}

function optionKindDefinition(kind) {
  const definitions = {
    long_call: [["call", "long"]], long_put: [["put", "long"]], short_call: [["call", "short"]], short_put: [["put", "short"]],
    covered_call: [["call", "short"]], cash_secured_put: [["put", "short"]],
    bull_call_spread: [["call", "long"], ["call", "short"]], bear_call_spread: [["call", "short"], ["call", "long"]],
    bull_put_spread: [["put", "short"], ["put", "long"]], bear_put_spread: [["put", "long"], ["put", "short"]],
  };
  return definitions[kind];
}

function optionRequest(includeName = false) {
  const kind = $("#option-kind").value;
  const expiration = $("#option-expiration").value;
  if (!expiration) throw new Error("Choose an option expiration date.");
  const quantity = Number($("#option-quantity").value);
  const volatility = Number($("#option-iv").value) / 100;
  const legs = optionKindDefinition(kind).map(([optionType, side], index) => ({
    option_type: optionType,
    side,
    strike: Number(index ? $("#option-strike-two").value : $("#option-strike-one").value),
    expiration,
    premium: Number(index ? $("#option-premium-two").value : $("#option-premium-one").value),
    quantity,
    implied_volatility: volatility,
    multiplier: 100,
  }));
  const request = {
    ticker: $("#option-ticker").value.trim().toUpperCase(),
    underlying_price: Number($("#option-spot").value),
    position_kind: kind,
    legs,
    shares: kind === "covered_call" ? Number($("#option-shares").value) : 0,
    share_cost_basis: kind === "covered_call" ? Number($("#option-spot").value) : null,
    interest_rate: 0.04,
    dividend_yield: 0,
    paths: 200,
    seed: 42,
  };
  if (includeName) request.name = `${$("#option-ticker").value.trim().toUpperCase()} ${$("#option-kind option:checked").textContent}`;
  return request;
}

async function simulateOption() {
  lastOptionRequest = optionRequest();
  const data = await api("/api/v2/options/simulations", { method: "POST", body: JSON.stringify(lastOptionRequest) });
  lastOptionSimulation = data;
  metricCards("#option-summary", [
    { label: "BREAK-EVEN", value: 0, display: data.summary.breakEvens.length ? data.summary.breakEvens.map((value) => `$${formatNumber(value)}`).join(" · ") : "None In Range" },
    { label: "MAXIMUM GAIN", value: 0, display: typeof data.summary.maximumGain === "number" ? `$${formatNumber(data.summary.maximumGain)}` : data.summary.maximumGain },
    { label: "MAXIMUM LOSS", value: typeof data.summary.maximumLoss === "number" ? data.summary.maximumLoss : 0, display: typeof data.summary.maximumLoss === "number" ? `$${formatNumber(data.summary.maximumLoss)}` : data.summary.maximumLoss },
    { label: "COLLATERAL", value: 0, display: `$${formatNumber(data.summary.collateral)}` },
    { label: "MODEL", value: 0, display: "AMERICAN" },
  ]);
  drawChart($("#option-payoff-chart"), data.payoff, [{ key: "pnl", label: "Position P&L", color: "#b6f559" }], "underlyingPrice", (point) => `<strong>Underlying $${formatNumber(point.underlyingPrice)}</strong><div><span>Position P&amp;L</span><b class="${point.pnl >= 0 ? "positive" : "negative"}">$${formatNumber(point.pnl)}</b></div>`);
  $("#option-greeks").innerHTML = data.greeks.map((leg) => `<div class="greek-card"><strong>${escapeHtml(leg.side.toUpperCase())} ${escapeHtml(leg.optionType.toUpperCase())} · $${formatNumber(leg.strike)}</strong><span>American Mark <b>$${formatNumber(leg.americanPrice, 4)}</b></span><span>Delta <b>${formatNumber(leg.delta, 4)}</b></span><span>Gamma <b>${formatNumber(leg.gamma, 5)}</b></span><span>Theta / Day <b>${formatNumber(leg.theta, 4)}</b></span><span>Vega / IV Point <b>${formatNumber(leg.vega, 4)}</b></span><span>Probability ITM <b>${formatNumber(leg.probabilityInTheMoney, 1)}%</b></span></div>`).join("");
  $("#option-limitations").innerHTML = data.limitations.map((limitation) => `<li>${escapeHtml(limitation)}</li>`).join("");
  const timeline = $("#option-timeline");
  timeline.disabled = false;
  timeline.max = String(data.surface.length - 1);
  timeline.value = "0";
  renderOptionTimeSlice(0);
  animateOptionPaths(data.monteCarlo);
  $("#create-paper-position").disabled = false;
  $("#event-spot").value = lastOptionRequest.underlying_price;
  $("#event-mark").value = lastOptionRequest.legs[0].premium;
}

function renderOptionTimeSlice(index) {
  if (!lastOptionSimulation) return;
  const slice = lastOptionSimulation.surface[index];
  $("#option-timeline-label").textContent = slice.day === 0 ? "Entry" : `Day ${slice.day}`;
  drawChart($("#option-surface-chart"), slice.points, [{ key: "pnl", label: "Position P&L", color: "#64d5c7" }], "underlyingPrice", (point) => `<strong>Day ${slice.day} · Underlying $${formatNumber(point.underlyingPrice)}</strong><div><span>Modeled P&amp;L</span><b class="${point.pnl >= 0 ? "positive" : "negative"}">$${formatNumber(point.pnl)}</b></div>`);
}

function animateOptionPaths(paths) {
  if (!paths?.length) return;
  const days = paths[0].points.map((point) => ({ day: point.day }));
  paths.slice(0, 12).forEach((path, pathIndex) => path.points.forEach((point, index) => { days[index][`path${pathIndex}`] = point.underlyingPrice; }));
  const lines = paths.slice(0, 12).map((_, index) => ({ key: `path${index}`, label: `Path ${index + 1}`, color: index === 0 ? "#b6f559" : "rgba(100,213,199,.28)" }));
  const canvas = $("#option-path-chart");
  const started = performance.now();
  const render = (now) => {
    const amount = Math.max(2, Math.floor(days.length * Math.min((now - started) / 1200, 1)));
    drawChart(canvas, days.slice(0, amount), lines, "day");
    if (amount < days.length) requestAnimationFrame(render);
  };
  requestAnimationFrame(render);
}

function chain(rows, side) {
  if (!rows?.length) return "<p class=\"empty-state\">No contracts available.</p>";
  return `<div class="chain-row chain-head"><span>STRIKE</span><span>LAST</span><span>BID / ASK</span><span>OI</span><span>IV</span></div>${rows.slice(0, 16).map((row) => `<button class="chain-row contract-row" data-side="${side}" data-strike="${row.strike}" data-premium="${row.last || (row.bid + row.ask) / 2}" data-iv="${row.iv}"><span>${formatNumber(row.strike)}</span><span>${formatNumber(row.last)}</span><span>${formatNumber(row.bid)} / ${formatNumber(row.ask)}</span><span>${Number(row.openInterest || 0).toLocaleString()}</span><span>${formatNumber(row.iv, 1)}%</span></button>`).join("")}`;
}

async function loadOptionChain() {
  const ticker = $("#option-ticker").value.trim().toUpperCase();
  const data = await api(`/api/v2/options/chains/${ticker}`);
  $("#lab-chain-status").textContent = data.expiration ? `${ticker} · ${data.expiration} · ${data.dataStatus?.status || "Delayed"}` : "No current contracts returned.";
  $("#lab-chain").innerHTML = `<h3>CALLS</h3>${chain(data.calls, "call")}<h3>PUTS</h3>${chain(data.puts, "put")}`;
  if (data.expiration) $("#option-expiration").value = data.expiration;
  $$("#lab-chain .contract-row").forEach((row) => row.addEventListener("click", () => {
    $("#option-strike-one").value = row.dataset.strike;
    $("#option-premium-one").value = row.dataset.premium;
    $("#option-iv").value = row.dataset.iv;
    notify(`Loaded ${row.dataset.side} contract inputs into the first leg.`);
  }));
}

async function createPaperPosition() {
  const request = optionRequest(true);
  const data = await api("/api/v2/options/positions", { method: "POST", body: JSON.stringify(request) });
  renderPosition(data);
  notify("Paper position created. No brokerage order was sent.");
}

function renderPosition(data) {
  currentPosition = data.position;
  $("#position-id").textContent = currentPosition.position_id;
  $("#position-status").textContent = `${currentPosition.status.toUpperCase()} · Cash $${formatNumber(currentPosition.cash)} · ${currentPosition.shares} shares · Realized P&L $${formatNumber(currentPosition.realized_pnl)} · Collateral $${formatNumber(currentPosition.collateral)}`;
  $("#apply-lifecycle-event").disabled = currentPosition.status !== "open";
  $("#position-ledger").innerHTML = `<div class="event-row event-head"><span>#</span><span>EVENT</span><span>TIME</span><span>STATUS AFTER</span><span>CASH AFTER</span><span>REALIZED P&amp;L</span></div>${data.events.map((event) => `<div class="event-row"><span>${event.eventNumber}</span><span>${escapeHtml(event.eventType.replaceAll("_", " ").toUpperCase())}</span><span>${escapeHtml(event.createdAt.slice(0, 19).replace("T", " "))}</span><span>${escapeHtml(event.stateAfter.status.toUpperCase())}</span><span>$${formatNumber(event.stateAfter.cash)}</span><span class="${event.stateAfter.realized_pnl >= 0 ? "positive" : "negative"}">$${formatNumber(event.stateAfter.realized_pnl)}</span></div>`).join("")}`;
}

async function applyLifecycleEvent() {
  if (!currentPosition) throw new Error("Create a paper position first.");
  const firstOpenLeg = currentPosition.legs.find((leg) => (currentPosition.closed_quantities[leg.leg_id] || 0) < leg.quantity);
  const eventType = $("#lifecycle-event").value;
  const event = {
    event_type: eventType,
    underlying_price: Number($("#event-spot").value),
    option_marks: firstOpenLeg ? { [firstOpenLeg.leg_id]: Number($("#event-mark").value) } : {},
    quantity: ["partial_close", "exercise", "early_assignment", "expiry_assignment"].includes(eventType) ? Number($("#event-quantity").value) : null,
    leg_id: ["hold", "expire"].includes(eventType) ? null : firstOpenLeg?.leg_id,
    new_strike: $("#event-new-strike").value ? Number($("#event-new-strike").value) : null,
    new_expiration: $("#event-new-expiration").value || null,
    new_premium: $("#event-new-premium").value ? Number($("#event-new-premium").value) : null,
    note: "Paper lifecycle event from local Option Lab",
  };
  const data = await api(`/api/v2/options/positions/${currentPosition.position_id}/events`, { method: "POST", body: JSON.stringify(event) });
  renderPosition(data);
}

async function loadStock() {
  const ticker = $("#stock-ticker").value.trim().toUpperCase();
  if (!ticker) throw new Error("Enter a US ticker before loading the observatory.");
  const stock = await api(`/api/stock/${ticker}`);
  const quote = stock.quote;
  metricCards("#quote-metrics", [{ label: "LAST PRICE", value: 0, display: `$${formatNumber(quote.price)}` }, { label: "DAY CHANGE", value: quote.changePercent, display: `${formatNumber(quote.changePercent)}%` }, { label: "DATA STATUS", value: 0, display: quote.dataStatus?.status || "DELAYED" }]);
  $("#stock-symbol").textContent = quote.symbol;
  drawChart($("#stock-chart"), stock.chart, [{ key: "close", label: "Close", color: "#b6f559" }], "date", (point) => `<strong>${escapeHtml(point.date)}</strong><div><span>Close</span><b>$${formatNumber(point.close)}</b><span>Volume</span><b>${Number(point.volume || 0).toLocaleString()}</b><span>Short Data</span><b>Not Loaded</b></div>`);
  try {
    const options = await api(`/api/options/${ticker}`);
    $("#option-expiry").textContent = options.expiration ? `Nearest Expiry · ${options.expiration} · ${options.dataStatus?.status || "Delayed"}` : "Options unavailable";
    $("#calls").innerHTML = chain(options.calls, "call");
    $("#puts").innerHTML = chain(options.puts, "put");
  } catch (error) {
    $("#option-expiry").textContent = "Options temporarily unavailable";
    $("#calls").innerHTML = $("#puts").innerHTML = "<p class=\"empty-state\">Option data could not be loaded.</p>";
    notify(error.message);
  }
}

async function loadMarket() {
  const data = await api("/api/market-overview");
  $("#sectors").innerHTML = dataTable(data.sectors, [{ label: "SECTOR", key: "name" }, { label: "LAST", key: "price", format: (value) => `$${formatNumber(value)}` }, { label: "DAY", key: "changePercent", format: signed }, { label: "RS VS SPY", key: "relativeStrength", format: signed }]);
  $("#macro").innerHTML = dataTable(data.macro, [{ label: "ASSET", key: "name" }, { label: "LAST", key: "price", format: (value) => `$${formatNumber(value)}` }, { label: "DAY", key: "changePercent", format: signed }, { label: "SYMBOL", key: "symbol" }]);
}

function updateOptionKind() {
  const kind = $("#option-kind").value;
  const multiLeg = optionKindDefinition(kind).length > 1;
  $("#second-strike-field").hidden = !multiLeg;
  $("#second-premium-field").hidden = !multiLeg;
  $("#shares-field").hidden = kind !== "covered_call";
}

function initializeExpiration() {
  const expiration = new Date();
  expiration.setDate(expiration.getDate() + 45);
  $("#option-expiration").value = expiration.toISOString().slice(0, 10);
}

$$('.nav-item').forEach((button) => button.addEventListener("click", () => {
  $$(".nav-item,.panel").forEach((element) => element.classList.remove("active"));
  button.classList.add("active");
  $(`#${button.dataset.panel}`).classList.add("active");
  $("#page-title").textContent = button.textContent.replace(/^\s*\d+\s*/, "").trim();
}));

$("#strategy-template").addEventListener("change", () => {
  currentTemplate = templates.find((template) => template.template_id === $("#strategy-template").value) || null;
  if (!currentTemplate) return;
  definitionMode = "template";
  selectedStrategyId = null;
  $("#strategy-input").value = "";
  $("#strategy-input").placeholder = currentTemplate.description;
  $("#configuration-name").textContent = currentTemplate.name;
  $("#configuration-description").textContent = currentTemplate.description;
  $("#universe-field").hidden = currentTemplate.rule_graph.kind !== "ranked_portfolio";
  renderParameterControls(currentTemplate);
});
$("#strategy-input").addEventListener("input", () => {
  definitionMode = "natural";
  selectedStrategyId = null;
  currentTemplate = null;
  $("#strategy-template").value = "";
  $("#configuration-name").textContent = "LLM-Assisted Definition";
  $("#configuration-description").textContent = "The exact executable rule graph will be shown for confirmation.";
  $("#parameter-controls").innerHTML = "<p class=\"empty-state\">Confirm the translated rule before it is stored or tested.</p>";
});
$("#run-backtest").addEventListener("click", withLoading("#run-backtest", runBacktest));
$("#run-simulation").addEventListener("click", withLoading("#run-simulation", runSimulation));
$("#load-stock").addEventListener("click", withLoading("#load-stock", loadStock));
$("#load-market").addEventListener("click", withLoading("#load-market", loadMarket));
$("#simulate-option").addEventListener("click", withLoading("#simulate-option", simulateOption));
$("#load-option-chain").addEventListener("click", withLoading("#load-option-chain", loadOptionChain));
$("#create-paper-position").addEventListener("click", withLoading("#create-paper-position", createPaperPosition));
$("#apply-lifecycle-event").addEventListener("click", withLoading("#apply-lifecycle-event", applyLifecycleEvent));
$("#option-kind").addEventListener("change", updateOptionKind);
$("#option-timeline").addEventListener("input", () => renderOptionTimeSlice(Number($("#option-timeline").value)));
$("#open-catalogue").addEventListener("click", async () => { try { await loadCatalogue(); $("#strategy-catalogue-modal").showModal(); } catch (error) { notify(error.message); } });
$("#close-catalogue").addEventListener("click", () => $("#strategy-catalogue-modal").close());
$("#toggle-trades").addEventListener("click", () => { const expanded = $("#toggle-trades").getAttribute("aria-expanded") === "true"; $("#toggle-trades").setAttribute("aria-expanded", String(!expanded)); $("#trade-ledger").hidden = expanded; });
$("#close-confirmation").addEventListener("click", () => $("#strategy-confirmation-modal").close());
$("#cancel-proposal").addEventListener("click", () => $("#strategy-confirmation-modal").close());
$("#confirm-proposal").addEventListener("click", withLoading("#confirm-proposal", confirmProposal));

initializeExpiration();
updateOptionKind();
Promise.all([loadTemplates(), loadCatalogue()]).catch((error) => notify(error.message));
