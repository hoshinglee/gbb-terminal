(() => {
  const COLORS = {
    grid: "#26332e",
    axis: "#789087",
    crosshair: "#8ba097",
    up: "#b6f559",
    down: "#ff6a6a",
    cyan: "#64d5c7",
    amber: "#f8bd5e",
    violet: "#a78bfa",
    mutedBar: "#52635c",
  };
  const PADDING = { top: 16, right: 72, bottom: 28, left: 12 };

  const finite = (value) => Number.isFinite(Number(value));
  const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(value, maximum));
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
  const formatNumber = (value, decimals = 2) => finite(value) ? Number(value).toFixed(decimals) : "—";
  const compactNumber = (value) => new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value) || 0);

  function setupCanvas(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(canvas.clientWidth, 320);
    const height = Math.max(canvas.clientHeight, 120);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    return { context, width, height };
  }

  function xCoordinate(index, count, width) {
    const plotWidth = width - PADDING.left - PADDING.right;
    return PADDING.left + (index + 0.5) * plotWidth / Math.max(count, 1);
  }

  function drawHorizontalGrid(context, width, top, bottom, minimum, maximum, formatter = (value) => formatNumber(value)) {
    const range = maximum - minimum || 1;
    context.font = "9px DM Mono";
    context.textAlign = "right";
    for (let row = 0; row < 5; row += 1) {
      const ratio = row / 4;
      const yPosition = top + ratio * (bottom - top);
      const value = maximum - ratio * range;
      context.strokeStyle = COLORS.grid;
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(PADDING.left, yPosition);
      context.lineTo(width - PADDING.right, yPosition);
      context.stroke();
      context.fillStyle = COLORS.axis;
      context.fillText(formatter(value), width - 7, yPosition + 3);
    }
  }

  function drawDateAxis(context, points, width, height) {
    if (!points.length) return;
    const indexes = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];
    context.fillStyle = COLORS.axis;
    context.font = "9px DM Mono";
    indexes.forEach((index, position) => {
      context.textAlign = position === 0 ? "left" : position === indexes.length - 1 ? "right" : "center";
      const xPosition = position === 0 ? PADDING.left : position === indexes.length - 1 ? width - PADDING.right : xCoordinate(index, points.length, width);
      context.fillText(points[index].periodEnd, xPosition, height - 7);
    });
  }

  function drawLine(context, points, width, yForValue, valueForPoint, color, lineWidth = 1.6) {
    context.strokeStyle = color;
    context.lineWidth = lineWidth;
    context.beginPath();
    let started = false;
    points.forEach((point, index) => {
      const value = valueForPoint(point);
      if (!finite(value)) {
        started = false;
        return;
      }
      const xPosition = xCoordinate(index, points.length, width);
      const yPosition = yForValue(Number(value));
      if (started) context.lineTo(xPosition, yPosition); else context.moveTo(xPosition, yPosition);
      started = true;
    });
    context.stroke();
  }

  function drawCrosshair(context, index, count, width, top, bottom) {
    if (index === null) return;
    const xPosition = xCoordinate(index, count, width);
    context.strokeStyle = COLORS.crosshair;
    context.lineWidth = 1;
    context.setLineDash([3, 4]);
    context.beginPath();
    context.moveTo(xPosition, top);
    context.lineTo(xPosition, bottom);
    context.stroke();
    context.setLineDash([]);
  }

  class ResearchMarketChart {
    constructor(root) {
      this.root = root;
      this.payload = null;
      this.trades = [];
      this.symbol = "";
      this.interval = "day";
      this.overlays = new Set(["sma"]);
      this.hoverIndex = null;
      this.eventsByIndex = new Map();
      this.empty = root.querySelector(".market-chart-empty");
      this.content = root.querySelector(".market-chart-content");
      this.canvases = {
        price: root.querySelector('[data-market-pane="price"]'),
        volume: root.querySelector('[data-market-pane="volume"]'),
        momentum: root.querySelector('[data-market-pane="momentum"]'),
      };
      root.querySelectorAll("[data-market-interval]").forEach((button) => button.addEventListener("click", () => {
        this.interval = button.dataset.marketInterval;
        this.hoverIndex = null;
        this.syncControls();
        this.render();
      }));
      root.querySelectorAll("[data-market-overlay]").forEach((button) => button.addEventListener("click", () => {
        const overlay = button.dataset.marketOverlay;
        if (this.overlays.has(overlay)) this.overlays.delete(overlay); else this.overlays.add(overlay);
        this.syncControls();
        this.render();
      }));
      Object.values(this.canvases).forEach((canvas) => {
        canvas.addEventListener("mousemove", (event) => this.handleHover(canvas, event));
        canvas.addEventListener("mouseleave", () => this.clearHover());
      });
      window.addEventListener("resize", () => {
        window.clearTimeout(this.resizeTimer);
        this.resizeTimer = window.setTimeout(() => this.render(this.hoverIndex), 120);
      });
      this.syncControls();
    }

    setData(payload, trades = [], symbol = "") {
      this.payload = payload;
      this.trades = Array.isArray(trades) ? trades : [];
      this.symbol = symbol;
      this.interval = payload?.defaultInterval || "day";
      this.hoverIndex = null;
      const available = Boolean(payload?.intervals?.day?.length);
      this.root.dataset.state = available ? "ready" : "unavailable";
      this.empty.hidden = available;
      this.content.hidden = !available;
      this.empty.textContent = available ? "" : "Candlesticks are available for individual-stock runs. Ranked portfolios do not fabricate synthetic OHLC candles.";
      this.root.querySelector("#market-chart-symbol").textContent = available && symbol ? `· ${symbol}` : "";
      this.syncControls();
      if (available) window.requestAnimationFrame(() => this.render());
    }

    points() {
      return this.payload?.intervals?.[this.interval] || [];
    }

    syncControls() {
      const available = Boolean(this.payload?.intervals?.day?.length);
      this.root.querySelectorAll("[data-market-interval]").forEach((button) => {
        const active = button.dataset.marketInterval === this.interval;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
        button.disabled = !available;
      });
      this.root.querySelectorAll("[data-market-overlay]").forEach((button) => {
        const active = this.overlays.has(button.dataset.marketOverlay);
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
        button.disabled = !available;
      });
      this.root.querySelectorAll("[data-overlay-legend]").forEach((legend) => {
        legend.hidden = !this.overlays.has(legend.dataset.overlayLegend);
      });
    }

    buildTradeEvents(points) {
      const events = new Map();
      const addEvent = (date, event) => {
        if (!date) return;
        const index = points.findIndex((point) => date >= point.periodStart && date <= point.periodEnd);
        if (index < 0) return;
        if (!events.has(index)) events.set(index, []);
        events.get(index).push(event);
      };
      this.trades.forEach((trade) => {
        addEvent(trade.entryDate, { type: "entry", label: `${trade.side} Entry`, price: trade.entryPrice });
        if (trade.status === "Closed") addEvent(trade.exitDate, { type: "exit", label: "Exit", price: trade.exitPrice });
      });
      return events;
    }

    render(highlightIndex = null) {
      const points = this.points();
      if (!points.length || this.content.hidden) return;
      this.eventsByIndex = this.buildTradeEvents(points);
      const first = points[0];
      const last = points.at(-1);
      this.root.querySelector("#market-chart-range").textContent = `${this.interval.toUpperCase()} · ${points.length} BARS · ${first.periodStart} → ${last.periodEnd}`;
      this.drawPrice(points, highlightIndex);
      this.drawVolume(points, highlightIndex);
      this.drawMomentum(points, highlightIndex);
    }

    drawPrice(points, highlightIndex) {
      const { context, width, height } = setupCanvas(this.canvases.price);
      const bottom = height - PADDING.bottom;
      const values = points.flatMap((point) => [point.low, point.high]);
      if (this.overlays.has("sma")) values.push(...points.map((point) => point.indicators.sma20));
      if (this.overlays.has("ema")) values.push(...points.map((point) => point.indicators.ema20));
      if (this.overlays.has("bollinger")) values.push(...points.flatMap((point) => [point.indicators.bollingerUpper20, point.indicators.bollingerLower20]));
      const finiteValues = values.filter(finite).map(Number);
      const rawMinimum = Math.min(...finiteValues);
      const rawMaximum = Math.max(...finiteValues);
      const padding = Math.max((rawMaximum - rawMinimum) * 0.06, rawMaximum * 0.002, 0.01);
      const minimum = rawMinimum - padding;
      const maximum = rawMaximum + padding;
      const yForValue = (value) => PADDING.top + (maximum - value) / (maximum - minimum || 1) * (bottom - PADDING.top);
      drawHorizontalGrid(context, width, PADDING.top, bottom, minimum, maximum);

      const plotWidth = width - PADDING.left - PADDING.right;
      const candleWidth = clamp(plotWidth / Math.max(points.length, 1) * 0.66, 1, 13);
      points.forEach((point, index) => {
        const xPosition = xCoordinate(index, points.length, width);
        const rising = Number(point.close) >= Number(point.open);
        const color = rising ? COLORS.up : COLORS.down;
        context.strokeStyle = color;
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(xPosition, yForValue(Number(point.high)));
        context.lineTo(xPosition, yForValue(Number(point.low)));
        context.stroke();
        const openY = yForValue(Number(point.open));
        const closeY = yForValue(Number(point.close));
        const bodyTop = Math.min(openY, closeY);
        const bodyHeight = Math.max(Math.abs(closeY - openY), 1);
        context.fillStyle = color;
        context.fillRect(xPosition - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

        const tradeEvents = this.eventsByIndex.get(index) || [];
        tradeEvents.forEach((tradeEvent, eventIndex) => {
          const entry = tradeEvent.type === "entry";
          const markerY = entry ? clamp(yForValue(Number(point.low)) + 7 + eventIndex * 5, PADDING.top + 6, bottom - 3) : clamp(yForValue(Number(point.high)) - 7 - eventIndex * 5, PADDING.top + 3, bottom - 6);
          context.fillStyle = entry ? COLORS.cyan : COLORS.amber;
          context.beginPath();
          if (entry) {
            context.moveTo(xPosition, markerY - 5);
            context.lineTo(xPosition - 4, markerY + 3);
            context.lineTo(xPosition + 4, markerY + 3);
          } else {
            context.moveTo(xPosition, markerY + 5);
            context.lineTo(xPosition - 4, markerY - 3);
            context.lineTo(xPosition + 4, markerY - 3);
          }
          context.closePath();
          context.fill();
        });
      });

      if (this.overlays.has("sma")) drawLine(context, points, width, yForValue, (point) => point.indicators.sma20, COLORS.cyan);
      if (this.overlays.has("ema")) drawLine(context, points, width, yForValue, (point) => point.indicators.ema20, COLORS.amber);
      if (this.overlays.has("bollinger")) {
        drawLine(context, points, width, yForValue, (point) => point.indicators.bollingerMiddle20, COLORS.violet, 1.2);
        drawLine(context, points, width, yForValue, (point) => point.indicators.bollingerUpper20, COLORS.violet, 1.2);
        drawLine(context, points, width, yForValue, (point) => point.indicators.bollingerLower20, COLORS.violet, 1.2);
      }
      drawDateAxis(context, points, width, height);
      drawCrosshair(context, highlightIndex, points.length, width, PADDING.top, bottom);
    }

    drawVolume(points, highlightIndex) {
      const { context, width, height } = setupCanvas(this.canvases.volume);
      const bottom = height - PADDING.bottom;
      const maximum = Math.max(...points.flatMap((point) => [point.volume, point.indicators.volumeSma20]).filter(finite).map(Number), 1);
      const yForValue = (value) => PADDING.top + (maximum - value) / maximum * (bottom - PADDING.top);
      drawHorizontalGrid(context, width, PADDING.top, bottom, 0, maximum, compactNumber);
      const plotWidth = width - PADDING.left - PADDING.right;
      const barWidth = clamp(plotWidth / Math.max(points.length, 1) * 0.7, 1, 14);
      points.forEach((point, index) => {
        const xPosition = xCoordinate(index, points.length, width);
        const barTop = yForValue(Number(point.volume));
        context.fillStyle = Number(point.close) >= Number(point.open) ? "#b6f55988" : "#ff6a6a88";
        context.fillRect(xPosition - barWidth / 2, barTop, barWidth, bottom - barTop);
      });
      drawLine(context, points, width, yForValue, (point) => point.indicators.volumeSma20, COLORS.cyan, 1.5);
      drawDateAxis(context, points, width, height);
      drawCrosshair(context, highlightIndex, points.length, width, PADDING.top, bottom);
    }

    drawMomentum(points, highlightIndex) {
      const { context, width, height } = setupCanvas(this.canvases.momentum);
      const rsiTop = PADDING.top;
      const rsiBottom = Math.floor(height * 0.43);
      const macdTop = Math.floor(height * 0.55);
      const macdBottom = height - PADDING.bottom;
      const rsiY = (value) => rsiTop + (100 - value) / 100 * (rsiBottom - rsiTop);
      [70, 50, 30].forEach((level) => {
        context.strokeStyle = level === 50 ? COLORS.grid : "#5a4b32";
        context.setLineDash(level === 50 ? [] : [4, 4]);
        context.beginPath();
        context.moveTo(PADDING.left, rsiY(level));
        context.lineTo(width - PADDING.right, rsiY(level));
        context.stroke();
        context.fillStyle = COLORS.axis;
        context.font = "9px DM Mono";
        context.textAlign = "right";
        context.fillText(String(level), width - 7, rsiY(level) + 3);
      });
      context.setLineDash([]);
      context.fillStyle = COLORS.axis;
      context.font = "9px DM Mono";
      context.textAlign = "left";
      context.fillText("RSI 14", PADDING.left, rsiTop + 9);
      drawLine(context, points, width, rsiY, (point) => point.indicators.rsi14, COLORS.cyan, 1.6);

      const macdValues = points.flatMap((point) => [point.indicators.macd, point.indicators.macdSignal, point.indicators.macdHistogram]).filter(finite).map((value) => Math.abs(Number(value)));
      const macdMaximum = Math.max(...macdValues, 0.0001);
      const macdY = (value) => macdTop + (macdMaximum - value) / (macdMaximum * 2) * (macdBottom - macdTop);
      const zeroY = macdY(0);
      context.strokeStyle = COLORS.grid;
      context.beginPath();
      context.moveTo(PADDING.left, zeroY);
      context.lineTo(width - PADDING.right, zeroY);
      context.stroke();
      context.fillStyle = COLORS.axis;
      context.textAlign = "left";
      context.fillText("MACD 12 · 26 · 9", PADDING.left, macdTop + 9);
      context.textAlign = "right";
      context.fillText(formatNumber(macdMaximum, 2), width - 7, macdTop + 3);
      context.fillText(formatNumber(-macdMaximum, 2), width - 7, macdBottom);
      const plotWidth = width - PADDING.left - PADDING.right;
      const histogramWidth = clamp(plotWidth / Math.max(points.length, 1) * 0.65, 1, 11);
      points.forEach((point, index) => {
        const value = point.indicators.macdHistogram;
        if (!finite(value)) return;
        const xPosition = xCoordinate(index, points.length, width);
        const valueY = macdY(Number(value));
        context.fillStyle = Number(value) >= 0 ? "#b6f55970" : "#ff6a6a70";
        context.fillRect(xPosition - histogramWidth / 2, Math.min(valueY, zeroY), histogramWidth, Math.max(Math.abs(valueY - zeroY), 1));
      });
      drawLine(context, points, width, macdY, (point) => point.indicators.macd, COLORS.amber, 1.5);
      drawLine(context, points, width, macdY, (point) => point.indicators.macdSignal, COLORS.violet, 1.3);
      drawDateAxis(context, points, width, height);
      drawCrosshair(context, highlightIndex, points.length, width, rsiTop, macdBottom);
    }

    handleHover(canvas, event) {
      const points = this.points();
      if (!points.length) return;
      const bounds = canvas.getBoundingClientRect();
      const plotWidth = bounds.width - PADDING.left - PADDING.right;
      const relative = clamp(event.clientX - bounds.left - PADDING.left, 0, plotWidth);
      const index = clamp(Math.floor(relative / Math.max(plotWidth, 1) * points.length), 0, points.length - 1);
      this.hoverIndex = index;
      this.render(index);
      this.showTooltip(canvas, event, points[index], index);
    }

    showTooltip(canvas, event, point, index) {
      this.hideTooltips();
      const shell = canvas.closest(".market-canvas-shell");
      const tooltip = shell.querySelector(".chart-tooltip");
      const indicators = point.indicators || {};
      const period = point.periodStart === point.periodEnd ? point.periodEnd : `${point.periodStart} → ${point.periodEnd}`;
      const change = (Number(point.close) / Number(point.open) - 1) * 100;
      const rows = [
        ["Open / High", `$${formatNumber(point.open)} / $${formatNumber(point.high)}`],
        ["Low / Close", `$${formatNumber(point.low)} / $${formatNumber(point.close)}`],
        ["Bar Change", `${change >= 0 ? "+" : ""}${formatNumber(change)}%`],
        ["Volume", compactNumber(point.volume)],
        ["Position", point.position === 1 ? "Long" : point.position === -1 ? "Short" : "Cash"],
        ["Strategy Equity", formatNumber(point.strategyEquity, 4)],
      ];
      if (this.overlays.has("sma")) rows.push(["SMA 20", formatNumber(indicators.sma20)]);
      if (this.overlays.has("ema")) rows.push(["EMA 20", formatNumber(indicators.ema20)]);
      if (this.overlays.has("bollinger")) rows.push(["Bollinger U / L", `${formatNumber(indicators.bollingerUpper20)} / ${formatNumber(indicators.bollingerLower20)}`]);
      rows.push(["RSI 14", formatNumber(indicators.rsi14)], ["MACD / Signal", `${formatNumber(indicators.macd, 3)} / ${formatNumber(indicators.macdSignal, 3)}`]);
      const tradeEvents = this.eventsByIndex.get(index) || [];
      tradeEvents.forEach((tradeEvent) => rows.push([tradeEvent.label, `$${formatNumber(tradeEvent.price)}`]));
      tooltip.innerHTML = `<strong>${escapeHtml(period)}</strong><div>${rows.map(([label, value]) => `<span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b>`).join("")}</div>`;
      tooltip.hidden = false;
      const bounds = shell.getBoundingClientRect();
      tooltip.style.left = `${clamp(event.clientX - bounds.left + 14, 8, bounds.width - tooltip.offsetWidth - 8)}px`;
      tooltip.style.top = `${clamp(event.clientY - bounds.top - tooltip.offsetHeight - 12, 6, bounds.height - tooltip.offsetHeight - 6)}px`;
    }

    hideTooltips() {
      this.root.querySelectorAll(".market-canvas-shell .chart-tooltip").forEach((tooltip) => { tooltip.hidden = true; });
    }

    clearHover() {
      this.hoverIndex = null;
      this.hideTooltips();
      this.render();
    }
  }

  window.ResearchMarketChart = ResearchMarketChart;
})();
