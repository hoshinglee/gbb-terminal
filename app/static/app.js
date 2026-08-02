const $ = (selector) => document.querySelector(selector);
const setStatus = (value) => { $("#status").textContent = `● ${value}`; };
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
const notify = (message) => { const toast = $("#toast"); toast.textContent = message; toast.style.display = "block"; window.clearTimeout(notify.timeout); notify.timeout = window.setTimeout(() => { toast.style.display = "none"; }, 6000); };
const signed = (number, suffix = "%") => `<span class="${number >= 0 ? "positive" : "negative"}">${number >= 0 ? "+" : ""}${number}${suffix}</span>`;
let selectedStrategyId = null;
let catalogueStrategies = [];
const api = async (url, options = {}) => {
  setStatus("LOADING");
  try {
    const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) throw new Error(payload.detail || "The data request failed.");
    return payload;
  } catch (error) {
    if (error instanceof TypeError) throw new Error("Cannot reach the terminal API. Start the FastAPI server, then refresh this page.");
    throw error;
  } finally { setStatus("READY"); }
};
function withLoading(buttonSelector, work) { return async () => { const button = $(buttonSelector); const label = button.textContent; button.disabled = true; button.textContent = "Loading…"; try { await work(); } catch (error) { setStatus("ERROR"); notify(error.message); } finally { button.disabled = false; button.textContent = label; } }; }
function metricCards(target, items) { $(target).innerHTML = items.map(item => `<div class="metric"><span>${item.label}</span><strong class="${item.value < 0 ? "negative" : item.value > 0 ? "positive" : ""}">${item.display}</strong></div>`).join(""); }
function table(rows, fields) { return `<div class="table-row chain-head">${fields.map(field => `<span>${field.label}</span>`).join("")}</div>${rows.map(row => `<div class="table-row">${fields.map(field => `<span>${field.format ? field.format(row[field.key]) : row[field.key]}</span>`).join("")}</div>`).join("")}`; }
function chain(rows) { if (!rows?.length) return "<p class=\"eyebrow\">No contracts available for this expiration.</p>"; return `<div class="chain-row chain-head"><span>STRIKE</span><span>LAST</span><span>BID / ASK</span><span>VOL</span><span>IV</span></div>${rows.map(row => `<div class="chain-row"><span>${row.strike.toFixed(2)}</span><span>${row.last.toFixed(2)}</span><span>${row.bid.toFixed(2)} / ${row.ask.toFixed(2)}</span><span>${row.volume.toLocaleString()}</span><span>${row.iv.toFixed(1)}%</span></div>`).join("")}`; }

function drawChart(canvas, series, lines, xKey) {
  if (!series?.length) return;
  const ratio = window.devicePixelRatio || 1, width = canvas.clientWidth, height = canvas.clientHeight;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const context = canvas.getContext("2d"); context.scale(ratio, ratio);
  const padding = { top: 16, right: 12, bottom: 29, left: 10 }, plotHeight = height - padding.top - padding.bottom;
  const values = lines.flatMap(line => series.map(point => point[line.key]).filter(Number.isFinite));
  if (!values.length) return;
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const y = value => padding.top + (max - value) / range * plotHeight;
  const x = index => padding.left + index * (width - padding.left - padding.right) / Math.max(series.length - 1, 1);
  context.clearRect(0, 0, width, height); context.strokeStyle = "#26332e"; context.lineWidth = 1;
  for (let grid = 0; grid < 4; grid += 1) { const position = padding.top + grid * plotHeight / 3; context.beginPath(); context.moveTo(padding.left, position); context.lineTo(width - padding.right, position); context.stroke(); }
  lines.forEach(line => { context.strokeStyle = line.color; context.lineWidth = 2; context.beginPath(); series.forEach((point, index) => { index ? context.lineTo(x(index), y(point[line.key])) : context.moveTo(x(index), y(point[line.key])); }); context.stroke(); });
  if (xKey) { context.fillStyle = "#789087"; context.font = "10px DM Mono"; context.textAlign = "left"; context.fillText(series[0][xKey], padding.left, height - 7); context.textAlign = "center"; context.fillText(series[Math.floor(series.length / 2)][xKey], width / 2, height - 7); context.textAlign = "right"; context.fillText(series.at(-1)[xKey], width - padding.right, height - 7); }
}
function animateMonteCarlo(paths) {
  const canvas = $("#simulation-chart"), start = performance.now(), duration = 950;
  const render = now => { const amount = Math.max(2, Math.floor(paths.length * Math.min((now - start) / duration, 1))); drawChart(canvas, paths.slice(0, amount), [{ key: "p10", color: "#ff6a6a" }, { key: "p50", color: "#b6f559" }, { key: "p90", color: "#64d5c7" }], "day"); if (amount < paths.length) requestAnimationFrame(render); };
  requestAnimationFrame(render);
}
function renderTrades(trades) {
  $("#trade-count").textContent = `${trades.length} closed trade${trades.length === 1 ? "" : "s"}`;
  if (!trades.length) { $("#trade-ledger").innerHTML = "<p class=\"eyebrow\">No closed trades in this backtest window.</p>"; return; }
  const row = trade => `<div class="trade-row"><span>${trade.side}</span><span>${trade.entryDate}</span><span>$${trade.entryPrice.toFixed(2)}</span><span>${trade.exitDate}</span><span>$${trade.exitPrice.toFixed(2)}</span><span class="${trade.pnl >= 0 ? "positive" : "negative"}">$${trade.pnl.toFixed(2)}</span><span class="${trade.pnlPercent >= 0 ? "positive" : "negative"}">${trade.pnlPercent.toFixed(2)}%</span></div>`;
  $("#trade-ledger").innerHTML = `<div class="trade-row trade-head"><span>SIDE</span><span>ENTRY</span><span>PRICE</span><span>EXIT</span><span>PRICE</span><span>P&amp;L</span><span>RETURN</span></div>${trades.map(row).join("")}`;
}
function renderCatalogue(strategies) {
  catalogueStrategies = strategies;
  $("#catalogue-count").textContent = `${strategies.length} saved strateg${strategies.length === 1 ? "y" : "ies"}`;
  $("#strategy-catalogue").innerHTML = strategies.length ? strategies.map(strategy => `<div class="catalogue-item"><div><strong>${escapeHtml(strategy.name)}</strong><p>${escapeHtml(strategy.description)}</p><span>${escapeHtml(strategy.provider)} · ${escapeHtml(strategy.strategy_type)} · ${escapeHtml(strategy.updatedAt.slice(0, 10))}</span></div><button class="outline load-strategy" data-strategy-id="${escapeHtml(strategy.id)}">Load</button><details><summary>Preview YAML</summary><pre>${escapeHtml(strategy.strategyYaml || "Legacy strategy: YAML will be generated after its next translation.")}</pre></details></div>`).join("") : "<p class=\"eyebrow\">Saved strategy definitions appear here.</p>";
  document.querySelectorAll(".load-strategy").forEach(button => button.addEventListener("click", () => loadStrategyFromCatalogue(button.dataset.strategyId)));
}
async function loadCatalogue() { const response = await api("/api/strategies"); renderCatalogue(response.strategies); }
function loadStrategyFromCatalogue(strategyId) {
  const strategy = catalogueStrategies.find(item => item.id === strategyId);
  if (!strategy) return;
  selectedStrategyId = strategy.id;
  $("#strategy-input").value = strategy.instruction;
  $("#strategy-source").textContent = `Loaded from catalogue: ${strategy.name}.`;
  $("#strategy-catalogue-modal").close();
}

async function runBacktest() {
  const ticker = $("#strategy-ticker").value.trim().toUpperCase();
  if (!ticker) throw new Error("Enter a US ticker before running the backtest.");
  const windowValue = $("#backtest-window").value;
  const data = await api("/api/backtest", { method: "POST", body: JSON.stringify({ ticker, instruction: $("#strategy-input").value, strategy_id: selectedStrategyId, window: windowValue }) });
  const metrics = data.metrics;
  metricCards("#backtest-metrics", [{ label: "TOTAL RETURN", value: metrics.totalReturn, display: `${metrics.totalReturn}%` }, { label: "BUY & HOLD", value: metrics.benchmarkReturn, display: `${metrics.benchmarkReturn}%` }, { label: "SPY", value: metrics.spyReturn, display: `${metrics.spyReturn}%` }, { label: "MAX DRAWDOWN", value: metrics.maxDrawdown, display: `${metrics.maxDrawdown}%` }, { label: "SHARPE RATIO", value: metrics.sharpeRatio, display: metrics.sharpeRatio }]);
  $("#parsed-strategy").textContent = data.strategy.description;
  $("#strategy-source").textContent = `Translation source: ${data.catalogueStrategy.provider.replaceAll("_", " ")}. Saved to catalogue.`;
  selectedStrategyId = data.catalogueStrategy.id;
  $("#chart-window").textContent = `${windowValue.toUpperCase()} · NORMALIZED TO 1.00`;
  drawChart($("#backtest-chart"), data.chart, [{ key: "strategy", color: "#b6f559" }, { key: "buyHold", color: "#64d5c7" }, { key: "spy", color: "#f8bd5e" }], "date");
  renderTrades(data.trades); await loadCatalogue();
}
async function runSimulation() { const data = await api("/api/simulate", { method: "POST", body: JSON.stringify({ ticker: $("#strategy-ticker").value.trim().toUpperCase(), days: Number($("#simulation-days").value) }) }); const metrics = data.metrics; metricCards("#simulation-metrics", [{ label: "MEDIAN RETURN", value: metrics.medianReturn, display: `${metrics.medianReturn}%` }, { label: "10TH PERCENTILE", value: metrics.downsideReturn, display: `${metrics.downsideReturn}%` }, { label: "90TH PERCENTILE", value: metrics.upsideReturn, display: `${metrics.upsideReturn}%` }, { label: "PROFIT PROBABILITY", value: metrics.profitProbability, display: `${metrics.profitProbability}%` }]); animateMonteCarlo(data.paths); }
async function loadStock() { const ticker = $("#stock-ticker").value.trim().toUpperCase(); if (!ticker) throw new Error("Enter a US ticker before loading the observatory."); const stock = await api(`/api/stock/${ticker}`); const quote = stock.quote; metricCards("#quote-metrics", [{label:"LAST PRICE",value:0,display:`$${quote.price.toFixed(2)}`},{label:"DAY CHANGE",value:quote.changePercent,display:`${quote.changePercent}%`},{label:"DATA STATUS",value:0,display:"YAHOO / CACHED"}]); $("#stock-symbol").textContent = quote.symbol; drawChart($("#stock-chart"), stock.chart, [{key:"close",color:"#b6f559"}], "date"); try { const options = await api(`/api/options/${ticker}`); $("#option-expiry").textContent = options.expiration ? `Nearest expiry · ${options.expiration}` : "Options unavailable"; $("#calls").innerHTML = chain(options.calls); $("#puts").innerHTML = chain(options.puts); } catch (error) { $("#option-expiry").textContent = "Options temporarily unavailable"; $("#calls").innerHTML = $("#puts").innerHTML = "<p class=\"eyebrow\">Option data could not be loaded.</p>"; notify(error.message); } }
async function loadMarket() { const data = await api("/api/market-overview"); $("#sectors").innerHTML = table(data.sectors, [{label:"SECTOR",key:"name"},{label:"LAST",key:"price",format:value=>`$${value}`},{label:"DAY",key:"changePercent",format:signed},{label:"RS VS SPY",key:"relativeStrength",format:signed}]); $("#macro").innerHTML = table(data.macro, [{label:"ASSET",key:"name"},{label:"LAST",key:"price",format:value=>`$${value}`},{label:"DAY",key:"changePercent",format:signed},{label:"SYMBOL",key:"symbol"}]); }
document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => { document.querySelectorAll(".nav-item,.panel").forEach(element => element.classList.remove("active")); button.classList.add("active"); $(`#${button.dataset.panel}`).classList.add("active"); $("#page-title").textContent = button.textContent.replace(/^\s*\d+\s*/, "").trim(); }));
$("#run-backtest").addEventListener("click", withLoading("#run-backtest", runBacktest)); $("#run-simulation").addEventListener("click", withLoading("#run-simulation", runSimulation)); $("#load-stock").addEventListener("click", withLoading("#load-stock", loadStock)); $("#load-market").addEventListener("click", withLoading("#load-market", loadMarket));
$("#open-catalogue").addEventListener("click", async () => { try { await loadCatalogue(); $("#strategy-catalogue-modal").showModal(); } catch (error) { notify(error.message); } });
$("#close-catalogue").addEventListener("click", () => $("#strategy-catalogue-modal").close());
$("#strategy-input").addEventListener("input", () => { selectedStrategyId = null; $("#strategy-source").textContent = "Instruction edited; it will be translated into a new YAML strategy."; });
withLoading("#run-backtest", runBacktest)(); loadCatalogue().catch(error => notify(error.message));
