const state = {
  snapshot: null,
  live: null,
  agent: null,
  bar: "15m",
  candleWindow: 60,
  liveLoading: false,
};

const isTurkish = document.documentElement.lang.toLowerCase().startsWith("tr");
const ui = {
  tr: {
    technical: "Teknik", onchain: "Zincir üstü", news: "Duyarlılık", macro: "Makro", signal: "Sinyal",
    technicalPass: "Trend ve giriş formasyonu uyumlu.", technicalFail: "Trend veya giriş formasyonu henüz hazır değil.",
    onchainPass: "Ağ ve piyasa yapısı destekleyici.", onchainFail: "Ağ veya piyasa yapısı destekleyici değil.",
    newsPass: "Piyasa duyarlılığı kurulumu destekliyor.", newsFail: "Haber duyarlılığı kuruluma karşı.",
    macroPass: "Yüksek etkili olay, işlem yasağı penceresinde değil.", macroFail: "Yüksek etkili olay, işlem yasağı penceresinde.",
    buyReason: "Dört sinyal de geçti ve emir planı tüm risk korumalarını aştı.",
    blockedReason: "Kurulum geçerli görünse de zorunlu bir risk koruması işlemi durdurdu.",
    waitReason: "Bir veya daha fazla sinyal hazır değil. Nexa bekleyerek sermayeyi koruyor.",
    snapshotUnavailable: "kayıt verisi alınamadı", refreshLabel: "Veriler yenilendi", source: "KAYNAK",
    noHistory: "Henüz kayıtlı piyasa kararı bulunmuyor.", auditedCycles: "kayıtlı döngü",
    pass: "GEÇTİ", fail: "KALDI", neutral: "NÖTR", buy: "AL", noTrade: "İŞLEM YOK", blocked: "ENGELLENDİ",
    live: "CANLI", hybrid: "KARMA", fallback: "YEDEK KAYNAK", unknown: "BİLİNMİYOR",
    priceRange: "Fiyat aralığı", notEnough: "Henüz yeterli OKX mum verisi yok.",
    marketLive: "PİYASA: OKX CANLI", marketUnavailable: "PİYASA: ERİŞİLEMİYOR", chartLive: "OKX canlı piyasa verisi", chartUnavailable: "OKX bağlantısı kurulamadı", endpointUnavailable: "OKX uç noktasına şu anda erişilemiyor.",
    walletUnavailable: "Cüzdan verisi alınamadı", agentRunning: "Ajan çalışıyor", agentStopped: "Ajan çalışmıyor", running: "ÇALIŞIYOR", stopped: "DURDU", external: "TERMİNALDE ÇALIŞIYOR",
    startConfirm: "Nexa-Trader ajanı OKX DEMO hesabında 30 saniyelik döngüyle başlatılacak. Demo emirleri gönderilebilir. Başlatılsın mı?",
    controlError: "Kontrol isteği başarısız oldu.", starting: "Ajan başlatılıyor…", stopping: "Ajan durduruluyor…", rulesSaved: "Risk kuralları kaydedildi.", savingRules: "Kurallar kaydediliyor…",
    o: "A", h: "Y", l: "D", c: "K", volume: "Hacim",
  },
  en: {
    technical: "Technical", onchain: "On-chain", news: "Sentiment", macro: "Macro", signal: "Signal",
    technicalPass: "Trend and entry pattern agree.", technicalFail: "Trend or entry pattern is not ready.",
    onchainPass: "Network and market structure are supportive.", onchainFail: "Network or market structure is not supportive.",
    newsPass: "Market sentiment supports the setup.", newsFail: "News sentiment is hostile to the setup.",
    macroPass: "No high-impact event is inside the blackout window.", macroFail: "A high-impact event is inside the blackout window.",
    buyReason: "All four signals passed and the order plan cleared every risk guardrail.",
    blockedReason: "The setup looked valid, but a mandatory risk guardrail stopped execution.",
    waitReason: "One or more signals are not ready. Nexa protects capital by waiting.",
    snapshotUnavailable: "audit data unavailable", refreshLabel: "Data refreshed", source: "SOURCE",
    noHistory: "No audited market decisions have been recorded yet.", auditedCycles: "audited cycles",
    pass: "PASS", fail: "FAIL", neutral: "NEUTRAL", buy: "BUY", noTrade: "NO TRADE", blocked: "BLOCKED",
    live: "LIVE", hybrid: "HYBRID", fallback: "FALLBACK", unknown: "UNKNOWN",
    priceRange: "Price range", notEnough: "Not enough OKX candle data yet.",
    marketLive: "MARKET: OKX LIVE", marketUnavailable: "MARKET: UNAVAILABLE", chartLive: "OKX live market data", chartUnavailable: "Could not connect to OKX", endpointUnavailable: "The OKX endpoint is currently unavailable.",
    walletUnavailable: "Wallet data unavailable", agentRunning: "Agent is running", agentStopped: "Agent is not running", running: "RUNNING", stopped: "STOPPED", external: "RUNNING IN TERMINAL",
    startConfirm: "Nexa-Trader will start a 30-second loop on the OKX DEMO account. Demo orders may be submitted. Start the agent?",
    controlError: "Control request failed.", starting: "Starting agent…", stopping: "Stopping agent…", rulesSaved: "Risk rules saved.", savingRules: "Saving rules…",
    o: "O", h: "H", l: "L", c: "C", volume: "Volume",
  },
}[isTurkish ? "tr" : "en"];

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const text = (selector, value, root = document) => {
  const element = $(selector, root);
  if (element) element.textContent = value ?? "—";
};
const number = (value, digits = 3) => Number.isFinite(Number(value))
  ? Number(value).toLocaleString(isTurkish ? "tr-TR" : "en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
  : "—";
const money = (value, digits = 2) => Number.isFinite(Number(value)) ? `$${number(value, digits)}` : "—";

function shortSignalName(key) {
  return ({ technical: ui.technical, onchain: ui.onchain, news: ui.news, macro: ui.macro })[key] || ui.signal;
}
function pillarSummary(pillar) {
  const suffix = pillar.status === "PASS" ? "Pass" : "Fail";
  return ui[`${pillar.key}${suffix}`] || pillar.reason || ui.signal;
}
function decisionSummary(decision) {
  if (decision.action === "BUY") return ui.buyReason;
  if (decision.action === "BLOCKED") return ui.blockedReason;
  const failedPillar = (decision.pillars || []).find((pillar) => pillar.status !== "PASS");
  if (failedPillar) {
    const detail = isTurkish && failedPillar.reason ? failedPillar.reason : pillarSummary(failedPillar);
    return `${shortSignalName(failedPillar.key)}: ${detail}`;
  }
  return ui.waitReason;
}
function statusClass(status) {
  if (status === "PASS") return "pass";
  if (status === "FAIL") return "fail";
  return "neutral";
}
function actionClass(action) {
  if (action === "BUY") return "pass";
  if (action === "BLOCKED") return "blocked";
  return "wait";
}
function localizedStatus(value) {
  return ({ PASS: ui.pass, FAIL: ui.fail, NEUTRAL: ui.neutral, BUY: ui.buy, NO_TRADE: ui.noTrade, BLOCKED: ui.blocked })[value] || value;
}
function localizedSource(value) {
  const normalized = String(value || "UNKNOWN").toUpperCase();
  if (normalized.includes("TRADINGVIEW")) return isTurkish ? "CANLI: TRADINGVIEW" : value;
  return ({ LIVE: ui.live, HYBRID: ui.hybrid, FALLBACK: ui.fallback, UNKNOWN: ui.unknown })[normalized] || value;
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

async function loadAudit() {
  try {
    state.snapshot = await fetchJSON("/api/snapshot");
  } catch (error) {
    try { state.snapshot = await fetchJSON("assets/snapshot.json"); }
    catch { text("[data-updated]", ui.snapshotUnavailable); return; }
  }
  renderAudit(state.snapshot);
}

async function loadLive(force = false) {
  if (state.liveLoading) return;
  state.liveLoading = true;
  try {
    const suffix = force ? `&force=${Date.now()}` : "";
    state.live = await fetchJSON(`/api/live?bar=${encodeURIComponent(state.bar)}&limit=160${suffix}`);
    renderLive(state.live);
  } catch (error) {
    renderLiveError(error);
  } finally {
    state.liveLoading = false;
  }
}

async function loadAgent() {
  try {
    const payload = await fetchJSON("/api/agent");
    state.agent = payload.agent;
    renderAgent(payload.agent, payload.rules);
  } catch (error) {
    feedback(error.message || ui.controlError, true);
  }
}

async function refreshAll({ announce = false } = {}) {
  const button = $("[data-refresh]");
  button?.classList.add("loading");
  await Promise.all([loadAudit(), loadLive(true), loadAgent()]);
  button?.classList.remove("loading");
  if (announce) button?.setAttribute("aria-label", ui.refreshLabel);
}

function renderAudit(snapshot) {
  const latest = snapshot.latest;
  text("[data-instrument]", snapshot.instrument);
  text("[data-chart-title]", String(snapshot.instrument).replace("-", " / "));
  if (latest) {
    if (!state.live?.ticker?.last) {
      const { price, bid, ask } = latest.market || {};
      text("[data-price]", price == null ? "—" : money(price, 3));
      const spread = Number(ask) > 0 && Number(bid) > 0 ? ((Number(ask) - Number(bid)) / Number(ask)) * 100 : null;
      text("[data-spread]", spread == null ? "—" : `${number(spread, 3)}%`);
    }
    renderDecision(latest);
    renderPillars(latest.pillars || []);
  }
  renderHistory(snapshot.history || []);
  renderSummary(snapshot.summary || {});
}

function renderLive(live) {
  const marketChip = $("[data-market-source]");
  const connected = live.marketDataStatus === "LIVE";
  marketChip?.classList.toggle("safe", connected);
  marketChip?.classList.toggle("error", !connected);
  text("[data-market-source]", connected ? ui.marketLive : ui.marketUnavailable);
  text("[data-chart-source]", connected ? ui.chartLive : ui.chartUnavailable);
  text("[data-updated]", new Date(live.generatedAt).toLocaleTimeString(isTurkish ? "tr-TR" : "en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
  $(".sync-state")?.classList.toggle("error", !connected);
  if (!connected) {
    text("[data-price]", "—");
    text("[data-spread]", "—");
  }

  const ticker = live.ticker || {}; 
  if (Number.isFinite(Number(ticker.last))) {
    text("[data-price]", money(ticker.last, 3));
    const spread = Number(ticker.ask) > 0 && Number(ticker.bid) > 0 ? ((Number(ticker.ask) - Number(ticker.bid)) / Number(ticker.ask)) * 100 : null;
    text("[data-spread]", spread == null ? "—" : `${number(spread, 3)}%`);
  }
  renderWallet(live.wallet || {}, live.activity || {}, live.accountDataStatus);
  renderCandleChart(live.candles || []);
  if (!connected) {
    const message = $("[data-chart-message]");
    const detail = isTurkish ? ui.endpointUnavailable : (Object.values(live.errors || {})[0] || ui.endpointUnavailable);
    if (message) { message.hidden = false; message.textContent = `${ui.chartUnavailable}: ${detail}`; }
  }
}

function renderLiveError(error) {
  text("[data-market-source]", ui.marketUnavailable);
  $("[data-market-source]")?.classList.add("error");
  text("[data-chart-source]", ui.chartUnavailable);
  const message = $("[data-chart-message]");
  if (message) { message.hidden = false; message.textContent = `${ui.chartUnavailable}: ${error.message || ""}`; }
}

function renderWallet(wallet, activity, accountStatus) {
  const available = accountStatus !== "UNAVAILABLE";
  text("[data-wallet-total]", available ? number(wallet.portfolioValueUsdt, 2) : "—");
  text("[data-wallet-usdt]", available ? number(wallet.usdtAvailable, 2) : "—");
  text("[data-wallet-avax]", available ? number(wallet.avaxTotal, 5) : "—");
  text("[data-wallet-avax-value]", available ? `${number(wallet.avaxValueUsdt, 2)} USDT` : ui.walletUnavailable);
  setPnl("[data-realized-pnl]", wallet.realizedPnlUsdt);
  setPnl("[data-unrealized-pnl]", wallet.unrealizedPnlUsdt);
  text("[data-open-lots]", wallet.openLots ?? 0);
  text("[data-open-orders]", activity.openOrders ?? 0);
  text("[data-protection-orders]", activity.openProtectionOrders ?? 0);
  text("[data-wallet-sync]", wallet.lastSyncAt ? new Date(wallet.lastSyncAt).toLocaleString(isTurkish ? "tr-TR" : "en-US") : "—");
}
function setPnl(selector, value) {
  const element = $(selector);
  if (!element || !Number.isFinite(Number(value))) { text(selector, "—"); return; }
  const numeric = Number(value);
  element.textContent = `${numeric >= 0 ? "+" : ""}${number(numeric, 2)}`;
  element.classList.toggle("positive", numeric > 0);
  element.classList.toggle("negative", numeric < 0);
}

function renderDecision(decision) {
  const card = $("[data-decision-card]");
  const action = decision.action || "NO_TRADE";
  card?.classList.toggle("is-pass", action === "BUY");
  card?.classList.toggle("is-fail", action === "BLOCKED");
  text("[data-action]", localizedStatus(action));
  text("[data-decision-time]", decision.timestamp);
  text("[data-reason]", decisionSummary(decision));
}
function renderPillars(pillars) {
  const container = $("[data-pillars]");
  if (!container) return;
  container.replaceChildren();
  const order = ["technical", "onchain", "news", "macro"];
  [...pillars].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key)).forEach((pillar, index) => {
    const article = document.createElement("article");
    article.className = `signal-card ${statusClass(pillar.status)}`;
    const count = Object.assign(document.createElement("span"), { className: "signal-index", textContent: `0${index + 1}` });
    const badge = Object.assign(document.createElement("span"), { className: "signal-status", textContent: localizedStatus(pillar.status) });
    const heading = Object.assign(document.createElement("h4"), { textContent: shortSignalName(pillar.key) });
    const reason = Object.assign(document.createElement("p"), { textContent: pillarSummary(pillar), title: pillarSummary(pillar) });
    const source = Object.assign(document.createElement("span"), { className: "signal-source", textContent: `${ui.source} · ${localizedSource(pillar.source)}` });
    article.append(count, badge, heading, reason, source);
    container.append(article);
  });
}

function renderHistory(history) {
  const body = $("[data-history]");
  if (!body) return;
  body.replaceChildren();
  if (!history.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7; cell.textContent = ui.noHistory; row.append(cell); body.append(row); return;
  }
  history.slice(0, 8).forEach((decision) => {
    const row = document.createElement("tr");
    const byKey = Object.fromEntries((decision.pillars || []).map((pillar) => [pillar.key, pillar.status]));
    const values = [decision.timestamp, decision.market?.price == null ? "—" : money(decision.market.price, 3), decision.action, byKey.technical || "—", byKey.onchain || "—", byKey.news || "—", byKey.macro || "—"];
    values.forEach((value, index) => {
      const cell = document.createElement("td");
      if (index >= 2) {
        const badge = document.createElement("span");
        badge.className = `status-badge ${index === 2 ? actionClass(value) : statusClass(value)}`;
        badge.textContent = localizedStatus(value); cell.append(badge);
      } else cell.textContent = value;
      row.append(cell);
    });
    body.append(row);
  });
}
function renderSummary(summary) {
  const actions = summary.actions || {};
  const buy = actions.BUY || 0, wait = actions.NO_TRADE || 0, blocked = actions.BLOCKED || 0;
  const total = summary.total || buy + wait + blocked;
  text("[data-total-decisions]", `${total} ${ui.auditedCycles}`);
  text("[data-donut-total]", total); text("[data-count-buy]", buy); text("[data-count-wait]", wait); text("[data-count-blocked]", blocked);
  const donut = $("[data-donut]");
  donut?.style.setProperty("--buy", `${total ? (buy / total) * 100 : 0}%`);
  donut?.style.setProperty("--wait", `${total ? ((buy + wait) / total) * 100 : 0}%`);
}

function renderCandleChart(candles) {
  const canvas = $("[data-candle-chart]");
  const message = $("[data-chart-message]");
  if (!canvas) return;
  const visible = candles.slice(-state.candleWindow);
  if (visible.length < 2) {
    if (message) { message.hidden = false; message.textContent = ui.notEnough; }
    return;
  }
  if (message) message.hidden = true;
  canvas._candles = visible;
  drawCandles(canvas, visible);
}

function drawCandles(canvas, candles) {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  const width = rect.width, height = rect.height, left = 14, right = 70, top = 18, bottom = 32;
  const chartW = width - left - right, chartH = height - top - bottom;
  const min = Math.min(...candles.map((c) => c.low)); const max = Math.max(...candles.map((c) => c.high));
  const span = Math.max(max - min, max * .001); const y = (value) => top + ((max - value) / span) * chartH;
  ctx.clearRect(0, 0, width, height); ctx.font = '10px "Pixelify Sans", monospace'; ctx.textAlign = "left";
  for (let i = 0; i <= 4; i += 1) {
    const gy = top + (chartH / 4) * i; ctx.strokeStyle = "#292731"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(left, gy); ctx.lineTo(width - right, gy); ctx.stroke();
    ctx.fillStyle = "#777382"; ctx.fillText(number(max - (span / 4) * i, 3), width - right + 8, gy + 3);
  }
  const step = chartW / candles.length; const bodyWidth = Math.max(2, Math.min(10, step * .62));
  candles.forEach((candle, index) => {
    const cx = left + step * index + step / 2; const rising = candle.close >= candle.open; const color = rising ? "#71f8ad" : "#ff6e77";
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(cx, y(candle.high)); ctx.lineTo(cx, y(candle.low)); ctx.stroke();
    const bodyTop = Math.min(y(candle.open), y(candle.close)); const bodyHeight = Math.max(1, Math.abs(y(candle.open) - y(candle.close)));
    ctx.fillRect(cx - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight);
  });
  const last = candles.at(-1); const lastY = y(last.close); ctx.strokeStyle = "#b087ff"; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(left, lastY); ctx.lineTo(width - right, lastY); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = "#b087ff"; ctx.fillText(number(last.close, 3), width - right + 8, lastY + 3);
  canvas._geometry = { left, right, step, width, candles };
  text("[data-chart-range]", `${money(min, 3)} — ${money(max, 3)}`);
}

function chartPointer(event) {
  const canvas = event.currentTarget; const geometry = canvas._geometry; if (!geometry) return;
  const rect = canvas.getBoundingClientRect(); const x = event.clientX - rect.left;
  const index = Math.max(0, Math.min(geometry.candles.length - 1, Math.floor((x - geometry.left) / geometry.step)));
  const candle = geometry.candles[index]; const tooltip = $("[data-chart-tooltip]"); if (!tooltip) return;
  const date = new Date(candle.ts).toLocaleString(isTurkish ? "tr-TR" : "en-US", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  tooltip.innerHTML = `<strong>${date}</strong><span>${ui.o} ${number(candle.open, 3)}</span><span>${ui.h} ${number(candle.high, 3)}</span><span>${ui.l} ${number(candle.low, 3)}</span><span>${ui.c} ${number(candle.close, 3)}</span><span>${ui.volume} ${number(candle.volume, 2)}</span>`;
  tooltip.hidden = false; tooltip.style.left = `${Math.min(rect.width - 165, Math.max(8, x + 12))}px`; tooltip.style.top = `${Math.max(8, event.clientY - rect.top - 70)}px`;
}

function renderAgent(agent, rules) {
  const badge = $("[data-agent-state]");
  badge?.classList.toggle("running", agent.running); badge?.classList.toggle("stopped", !agent.running);
  text("[data-agent-state]", agent.external ? ui.external : (agent.running ? ui.running : ui.stopped));
  text("[data-agent-copy]", agent.running ? ui.agentRunning : ui.agentStopped);
  $("[data-power-orb]")?.classList.toggle("running", agent.running);
  const start = $("[data-agent-start]"), stop = $("[data-agent-stop]");
  if (start) start.disabled = !agent.canStart;
  if (stop) stop.disabled = !agent.canStop;
  const form = $("[data-rules-form]");
  if (form) $$('input, button[type="submit"]', form).forEach((control) => { control.disabled = agent.running; });
  if (rules && form) {
    Object.entries(rules).forEach(([key, value]) => { const input = form.elements.namedItem(key); if (input) input.value = value; });
    updateRatioPreview();
  }
}
function feedback(message, isError = false) {
  const element = $("[data-control-feedback]"); if (!element) return;
  element.textContent = message; element.classList.toggle("error", isError); element.classList.toggle("success", !isError);
}
async function postControl(url, body = {}) {
  return fetchJSON(url, { method: "POST", headers: { "Content-Type": "application/json", "X-Nexa-Control": "web-ui" }, body: JSON.stringify(body) });
}
async function startAgent() {
  if (!window.confirm(ui.startConfirm)) return;
  feedback(ui.starting);
  try { const payload = await postControl("/api/agent/start"); state.agent = payload.agent; renderAgent(payload.agent, payload.rules); feedback(ui.agentRunning); }
  catch (error) { feedback(error.message || ui.controlError, true); await loadAgent(); }
}
async function stopAgent() {
  feedback(ui.stopping);
  try { const payload = await postControl("/api/agent/stop"); state.agent = payload.agent; renderAgent(payload.agent, payload.rules); feedback(ui.agentStopped); }
  catch (error) { feedback(error.message || ui.controlError, true); await loadAgent(); }
}
function updateRatioPreview() {
  const form = $("[data-rules-form]"); if (!form) return;
  const sl = Number(form.elements.namedItem("stopLossPct")?.value); const tp = Number(form.elements.namedItem("takeProfitPct")?.value);
  text("[data-rr-preview]", sl > 0 && tp > 0 ? `1 : ${number(tp / sl, 2)}` : "—");
}
async function saveRules(event) {
  event.preventDefault(); const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const payload = Object.fromEntries(new FormData(form).entries());
  Object.keys(payload).forEach((key) => { payload[key] = Number(payload[key]); });
  feedback(ui.savingRules);
  try { const response = await postControl("/api/rules", payload); renderAgent(response.agent, response.rules); feedback(ui.rulesSaved); await loadAudit(); }
  catch (error) { feedback(error.message || ui.controlError, true); }
}

function setupInteractions() {
  const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
    if (entry.isIntersecting) { entry.target.classList.add("visible"); observer.unobserve(entry.target); }
  }), { threshold: 0.08 });
  $$(".reveal").forEach((element) => observer.observe(element));
  $("[data-refresh]")?.addEventListener("click", () => refreshAll({ announce: true }));
  $$("[data-bar]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-bar]").forEach((item) => item.classList.remove("active")); button.classList.add("active"); state.bar = button.dataset.bar; loadLive(true);
  }));
  $$('[data-zoom]').forEach((button) => button.addEventListener("click", () => {
    state.candleWindow = Math.max(20, Math.min(150, state.candleWindow + (button.dataset.zoom === "out" ? 20 : -20)));
    renderCandleChart(state.live?.candles || []);
  }));
  $("[data-chart-reset]")?.addEventListener("click", () => { state.candleWindow = 60; renderCandleChart(state.live?.candles || []); });
  const canvas = $("[data-candle-chart]"); canvas?.addEventListener("mousemove", chartPointer); canvas?.addEventListener("mouseleave", () => { const tip = $("[data-chart-tooltip]"); if (tip) tip.hidden = true; });
  $("[data-agent-start]")?.addEventListener("click", startAgent); $("[data-agent-stop]")?.addEventListener("click", stopAgent);
  $("[data-rules-form]")?.addEventListener("submit", saveRules); $("[data-rules-form]")?.addEventListener("input", updateRatioPreview);
  $$(".side-button").forEach((button) => button.addEventListener("click", () => { $$(".side-button").forEach((item) => item.classList.remove("active")); button.classList.add("active"); }));
  let resizeTimer; window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => renderCandleChart(state.live?.candles || []), 100); });
}

setupInteractions();
refreshAll();
setInterval(() => { loadAudit(); loadLive(); }, 15_000);
setInterval(loadAgent, 5_000);
