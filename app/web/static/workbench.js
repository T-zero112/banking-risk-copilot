"use strict";
const $ = (selector) => document.querySelector(selector);
const icons = () => window.lucide?.createIcons();
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (name) => `<i data-lucide="${name}"></i>`;
const statuses = {
  succeeded: "审查完成",
  partial_success: "AI 生成失败",
  failed: "审查失败",
  started: "记录未完成",
};
const signalNames = {
  kyc_follow_up: "KYC 待复核",
  demo_high_aml_score: "演示评分阈值",
  existing_alert: "未解决告警",
  matching_payment_candidate: "进出交易候选",
};
const factNames = {
  customer_id: "客户 ID",
  kyc_status: "KYC 状态",
  kyc_last_review_date: "最近 KYC 复核",
  due_diligence_level: "尽职调查",
  aml_risk_score: "AML 评分",
  score_date: "评分日期",
  unresolved_alert_count: "未解决告警",
  transaction_count: "交易笔数",
  inbound_sgd: "入账总额",
  outbound_sgd: "出账总额",
  cross_border_count: "跨境笔数",
  unknown_cross_border_count: "跨境未知笔数",
};
const kycNames = {
  expired: "已过期",
  incomplete: "不完整",
  complete: "已完成",
};
const types = {
  transfer_in: "转入",
  transfer_out: "转出",
  card_payment: "刷卡支付",
  deposit: "存款",
  withdrawal: "提现",
};
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
let current = null,
  busy = false,
  records = [];
let signedUser = null;
function signedOut() {
  signedUser = null;
  current = null;
  records = [];
  sessionStorage.removeItem("review-ids");
  sessionStorage.removeItem("review-owner");
  $("#workspace").hidden = true;
  $("#login-panel").hidden = false;
  $("#signed-user").textContent = "";
  $("#logout").hidden = true;
  $("#consent").checked = false;
  $("input[name=mode][value=deterministic]").checked = true;
  $("#paid-notice").hidden = true;
  resetView();
  document.querySelectorAll(".panel").forEach((panel) => { panel.textContent = ""; });
  renderHistory();
}
async function refreshIdentity() {
  const user = await request("/auth/me");
  if (sessionStorage.getItem("review-owner") !== user.username) {
    records = [];
    sessionStorage.removeItem("review-ids");
  }
  sessionStorage.setItem("review-owner", user.username);
  signedUser = user;
  $("#signed-user").textContent = `${user.username} · ${user.role === "admin" ? "管理员" : "审查员"}`;
  $("#workspace").hidden = false;
  $("#login-panel").hidden = true;
  $("#logout").hidden = false;
  $("#customer").value = user.role === "admin" ? "C003" : user.customers[0] || "";
  renderHistory();
}
try {
  records = JSON.parse(sessionStorage.getItem("review-ids") || "[]")
    .filter((r) => uuidPattern.test(r.id) && /^C\d{3}$/.test(r.customer))
    .slice(0, 12);
} catch {
  records = [];
}

function amount(value) {
  const raw = String(value ?? "");
  if (!/^\d+(\.\d+)?$/.test(raw)) return esc(raw || "未提供");
  const [whole, fraction = "00"] = raw.split(".");
  return (
    whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + fraction.padEnd(2, "0")
  );
}
function date(value) {
  if (!value) return "未提供";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? esc(value)
    : new Intl.DateTimeFormat("zh-CN", {
        timeZone: "Asia/Singapore",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(parsed);
}
function notify(text, success = false) {
  $("#notification").textContent = text;
  $("#notification").className = success ? "success" : "";
  $("#notification").hidden = !text;
}
function setBusy(value) {
  busy = value;
  $("#review-form")
    .querySelectorAll("input,button")
    .forEach((el) => (el.disabled = value));
  $("#lookup-form")
    .querySelectorAll("input,button")
    .forEach((el) => (el.disabled = value));
  document
    .querySelectorAll(".history-row,#audit-refresh")
    .forEach((el) => (el.disabled = value));
  $("#run").innerHTML = value
    ? `${icon("loader-circle")}<span>审查处理中</span>`
    : `${icon("play")}<span>开始审查</span>`;
  $("#run i").classList.toggle("loading-icon", value);
  $("#main").setAttribute("aria-busy", String(value));
  icons();
}
function resetView() {
  current = null;
  $("#result").hidden = true;
  $("#empty").hidden = false;
  $("#report-title").textContent = "审查工作台";
  $("#copy-request").disabled = true;
  $("#download").disabled = true;
}
function remember(id, customer, status, mode) {
  if (!uuidPattern.test(id) || !/^C\d{3}$/.test(customer)) return;
  records = [
    { id, customer, status, mode, time: new Date().toISOString() },
    ...records.filter((r) => r.id !== id),
  ].slice(0, 12);
  try {
    sessionStorage.setItem("review-ids", JSON.stringify(records));
  } catch {
    /* Browsing without storage remains usable. */
  }
  renderHistory();
}
function renderHistory() {
  $("#history-list").innerHTML = records.length
    ? records
        .map(
          (r) =>
            `<button class="history-row ${current?.id === r.id ? "active" : ""}" data-request="${esc(r.id)}" ${busy ? "disabled" : ""}><span><strong>${esc(r.customer)}</strong><small>${r.mode === "deepseek" ? "DeepSeek" : "固定规则"} · ${date(r.time)}</small></span><span class="history-state">${esc(statuses[r.status] || "待查询")}</span></button>`,
        )
        .join("")
    : "<p class='muted'>暂无记录</p>";
}
function selectTab(view) {
  document.querySelectorAll("[data-view]").forEach((button) => {
    const selected = button.dataset.view === view;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    $(`#panel-${button.dataset.view}`).hidden = !selected;
  });
}
function metric(label, value, unit, note = "") {
  return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}<span class="unit">${esc(unit)}</span></div>${note ? `<small>${esc(note)}</small>` : ""}</div>`;
}
function policyButtons(ids) {
  return (ids || [])
    .map(
      (id) =>
        `<button class="reference" data-citation="${esc(id)}">政策 [${esc(id)}]</button>`,
    )
    .join("");
}
function renderOverview(report) {
  if (!report)
    return "<p class='empty-panel'>没有可用审查报告。失败阶段与状态保留在审计记录中。</p>";
  const f = report.facts || {},
    ai = report.ai_explanation,
    signals = report.review_signals || [];
  const observations = ai?.observations
    ?.map(
      (n) =>
        `<div class="note ${n.kind === "inference" ? "inference" : ""}"><span class="kind">${n.kind === "fact" ? "事实" : "推断"}</span>${esc(n.text)}<div class="references">${(n.fact_refs || []).map((ref) => `<span class="reference">${esc(factNames[ref] || ref)}</span>`).join("")}${(n.transaction_refs || []).map((id) => `<button class="reference" data-transaction="${esc(id)}">${esc(id)}</button>`).join("")}</div></div>`,
    )
    .join("");
  const facts = Object.entries(f)
    .map(
      ([key, value]) =>
        `<dt>${esc(factNames[key] || key)}</dt><dd>${esc(key === "kyc_status" ? kycNames[value] || value : key === "due_diligence_level" ? { enhanced: "增强型", standard: "标准型" }[value] || value : (value ?? "未提供"))}</dd>`,
    )
    .join("");
  return `<div class="metrics">${metric("AML 风险评分", f.aml_risk_score ?? "未提供", "/ 100", "演示评分，非监管判定")}${metric("KYC 状态", kycNames[f.kyc_status] || "未提供", "", f.kyc_last_review_date || "")}${metric("近 30 日交易", f.transaction_count ?? "未提供", "笔", `${f.cross_border_count ?? 0} 笔跨境`)}${metric("未解决告警", f.unresolved_alert_count ?? "未提供", "条")}</div>
  <div class="overview-grid"><div><div class="section-heading"><h3>规则审查信号</h3><span>${signals.length} 项</span></div>${signals.length ? signals.map((s) => `<div class="signal">${icon("flag")}<div><strong>${esc(signalNames[s.code] || s.code)}</strong><p>${esc(s.reason)}</p>${s.applicability_note ? `<p>${esc(s.applicability_note)}</p>` : ""}<div class="references">${policyButtons(s.policy_citations)}</div></div></div>`).join("") : "<p class='empty-panel'>未触发演示规则，不代表客户低风险。</p>"}
  <details class="limits"><summary>审查边界与限制</summary><ul>${(report.limitations || []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul></details></div>
  <div><div class="section-heading"><h3>${ai ? "DeepSeek 审查说明" : "数据库事实"}</h3><span>${ai ? "需人工核实" : "SQL 快照"}</span></div>${ai ? `<div class="narrative">${observations}${(ai.policy_context || []).map((p) => `<div class="note inference"><span class="kind">政策背景</span>${esc(p.text)}<div class="references">${policyButtons(p.policy_citations)}</div></div>`).join("")}</div><h3>建议核查事项</h3><ol class="checks">${(ai.suggested_checks || []).map((c) => `<li>${esc(c)}</li>`).join("")}</ol><p class="muted">引用检查仅验证来源存在，不保证说明正确。</p>` : `${report.ai_generation?.status === "failed" ? "<div class='notice-strip'>AI 说明未生成或未通过校验；规则报告仍可使用。</div>" : ""}<dl class="detail-list">${facts}</dl>`}</div></div>`;
}
function renderTransactions(report) {
  const txs = report?.transactions || [],
    pairs = report?.candidate_pairs || [];
  const used = new Set(
    pairs.flatMap((p) => [
      p.incoming_transaction_id,
      p.outgoing_transaction_id,
    ]),
  );
  const pairMarkup = pairs
    .map((p) => {
      const incoming = txs.find(
          (t) => t.transaction_id === p.incoming_transaction_id,
        ),
        outgoing = txs.find(
          (t) => t.transaction_id === p.outgoing_transaction_id,
        );
      return `<div class="pair"><div><small>入账 · ${esc(p.incoming_transaction_id)}</small><strong>SGD ${amount(incoming?.amount)}</strong><small>${date(incoming?.transaction_time)}</small></div><div class="pair-link"><span>${esc(p.elapsed_minutes)} 分钟</span>${icon("arrow-right")}<small>规则候选</small></div><div><small>出账 · ${esc(p.outgoing_transaction_id)}</small><strong>SGD ${amount(outgoing?.amount)}</strong><small>${date(outgoing?.transaction_time)}</small></div></div>`;
    })
    .join("");
  return `<div class="pairs"><div class="section-heading"><h3>进出交易候选</h3><span>${pairs.length} 组</span></div>${pairs.length ? pairMarkup : "<p class='muted'>没有短时间、金额接近的交易候选。</p>"}</div><div class="section-heading"><h3>窗口内 SGD 交易</h3><span>${txs.length} 笔</span></div>${txs.length ? `<div class="table-wrap"><table><thead><tr><th>交易 ID</th><th>时间 · 新加坡</th><th>类型</th><th>账户</th><th class="amount">金额 · SGD</th><th>跨境</th></tr></thead><tbody>${txs.map((t) => `<tr id="tx-${esc(t.transaction_id)}" class="${used.has(t.transaction_id) ? "highlight" : ""}"><td>${esc(t.transaction_id)}</td><td>${date(t.transaction_time)}</td><td>${esc(types[t.transaction_type] || t.transaction_type)}</td><td>${esc(t.account_id)}</td><td class="amount">${amount(t.amount)}</td><td>${t.is_cross_border === true ? "是" : t.is_cross_border === false ? "否" : "未知"}</td></tr>`).join("")}</tbody></table></div>` : "<p class='empty-panel'>没有可用交易明细。</p>"}`;
}
function renderPolicies(report) {
  const policies = report?.policy_evidence || [];
  const notice = report?.policy_evidence_notice || (policies.length
    ? "现金入账条件尚未确认；相关条目仅作背景参考。"
    : "历史记录未标注检索状态，且没有政策证据；不能据此确认合规或风险程度。");
  return `<div class="section-heading"><h3>政策证据</h3><span>${policies.length} 条引用</span></div><div class="notice-strip">${esc(notice)}</div>${
    policies.length
      ? policies
          .map((p) => {
            let url = "";
            try {
              const parsed = new URL(p.citation_url);
              if (parsed.protocol === "https:") url = parsed.href;
            } catch {}
            return `<article class="policy" id="policy-${esc(p.citation_id)}"><div class="policy-header"><span class="citation-number">${esc(p.citation_id)}</span><div><h3>${esc(p.title)}</h3><p class="policy-meta">${esc(p.source)} · ${esc(p.locator)}</p></div></div>${url ? `<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">官方来源 ${icon("external-link")}</a>` : ""}<details><summary>原文与版本</summary><blockquote class="excerpt">${esc(p.excerpt)}</blockquote><p class="policy-meta">文档版本：${esc(p.document_version)}</p><p class="hash">分块：${esc(p.chunk_id)}<br>SHA-256：${esc(p.content_sha256)}</p></details></article>`;
          })
          .join("")
      : ""
  }`;
}
function renderAudit(record) {
  const a = record.audit;
  return `<div class="section-heading"><h3>审计追溯</h3><button id="audit-refresh" class="audit-refresh" ${busy ? "disabled" : ""}>${icon("refresh-cw")}查询最新记录</button></div>${a ? `<dl class="detail-list"><dt>状态</dt><dd>${esc(statuses[a.status] || a.status)}</dd><dt>请求 ID</dt><dd>${esc(a.request_id)}</dd><dt>创建时间</dt><dd>${date(a.created_at)}</dd><dt>完成时间</dt><dd>${a.finished_at ? date(a.finished_at) : "尚无完成记录"}</dd><dt>耗时</dt><dd>${a.elapsed_ms == null ? "未提供" : `${esc(a.elapsed_ms)} ms`}</dd><dt>SQL 状态</dt><dd>${esc({ succeeded: "证据查询完成", failed: "查询失败", not_requested: "未执行" }[a.sql_execution_status] || a.sql_execution_status)}</dd><dt>模型</dt><dd>${esc(a.metadata?.model || "未调用模型")}</dd><dt>失败码</dt><dd>${esc(a.error_code || "无")}</dd></dl><details class="limits"><summary>版本、哈希与证据快照</summary><pre class="audit-json">${esc(JSON.stringify(a.metadata, null, 2))}</pre></details>` : "<p class='empty-panel'>审查接口已确认保存。完整审计记录尚未载入。</p>"}<p class="muted" style="margin-top:24px">本机可追溯记录，尚非防篡改审计。</p>`;
}
function render(record) {
  current = record;
  const report = record.report;
  $("#empty").hidden = true;
  $("#result").hidden = false;
  $("#report-title").textContent = `客户 ${record.customer}`;
  $("#outcome").textContent = statuses[record.status] || record.status;
  $("#outcome").className =
    `status-tag ${record.status !== "succeeded" ? "warning" : ""}`;
  $("#review-mode").textContent =
    record.mode === "deepseek" ? "DeepSeek 说明" : "固定规则";
  $("#as-of").textContent = report?.as_of
    ? `数据截至 ${date(report.as_of)}`
    : "";
  $("#duration").textContent =
    record.audit?.elapsed_ms != null ? `${record.audit.elapsed_ms} ms` : "";
  $("#request-id").textContent = record.id;
  $("#audit-label").textContent = record.audit
    ? "审计记录已载入"
    : "审计写入已确认";
  $("#panel-overview").innerHTML = renderOverview(report);
  $("#panel-transactions").innerHTML = renderTransactions(report);
  $("#panel-policies").innerHTML = renderPolicies(report);
  $("#panel-audit").innerHTML = renderAudit(record);
  $("#copy-request").disabled = false;
  $("#download").disabled = !report;
  renderHistory();
  icons();
}
const errorMessages = {
  customer_not_found: "客户不存在。请核对客户 ID。",
  review_not_found: "未找到该请求的审查记录。",
  review_busy: "同时运行的审查已达上限，稍后再试。",
  audit_start_unconfirmed: "审计开始记录未确认，审查未执行。",
  audit_completion_unconfirmed:
    "审计完成写入未确认。先查询请求记录，不要直接重复付费调用。",
  audit_read_unavailable: "暂时无法查询审计数据库。",
  invalid_request_or_configuration: "审查配置不可用。请检查数据库或模型配置。",
  database_error: "数据库暂时不可用。",
  review_capacity_exceeded: "交易数量超过当前审查上限，未进行部分分析。",
  invalid_request: "请求格式无效。",
  cross_origin_not_allowed: "该页面来源不允许访问本地接口。",
};
async function request(path, options = {}) {
  const controller = new AbortController(),
    timeout = setTimeout(
      () => controller.abort(),
      options.method === "POST" ? 120000 : 15000,
    );
  try {
    const response = await fetch(path, {
      ...options,
      signal: controller.signal,
      cache: "no-store",
    });
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 401 && signedUser) signedOut();
      const detail = body.detail || {};
      const error = new Error(
        ({login_required:"请重新登录。", invalid_credentials:"用户名或密码错误。", login_throttled:"登录尝试过多，请稍后再试。", authentication_unavailable:"账号服务不可用，请检查本地账号配置。", customer_access_denied:"你没有该客户的访问权限。", paid_consent_required:"请确认本次付费调用。"})[detail.code] || errorMessages[detail.code] ||
          "请求失败。请查询审计记录或检查服务状态。",
      );
      error.id = detail.request_id;
      throw error;
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError" || error instanceof TypeError)
      throw new Error(
        "连接中断或请求超时。服务可能仍在执行，请勿直接重复付费调用。",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
async function loadAudit(id) {
  if (busy) return;
  if (!uuidPattern.test(id)) {
    notify("请求 ID 格式无效。");
    $("#request-lookup").focus();
    return;
  }
  setBusy(true);
  notify("正在查询审计记录…");
  try {
    const audit = await request(`/reviews/${id}`);
    render({
      id: audit.request_id,
      customer: audit.customer_id,
      mode: audit.mode,
      status: audit.status,
      report: audit.report,
      audit,
    });
    remember(audit.request_id, audit.customer_id, audit.status, audit.mode);
    selectTab(audit.report ? "overview" : "audit");
    notify(
      audit.status === "started"
        ? "记录未完成；这不代表审查成功，也不确认模型调用已停止。"
        : audit.status === "failed"
          ? "审查失败，已保留审计记录。"
          : "",
      true,
    );
  } catch (error) {
    notify(error.message);
  } finally {
    setBusy(false);
  }
}
$("#review-form").noValidate = true;
$("#review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const customer = $("#customer").value.trim().toUpperCase(),
    mode = $("input[name=mode]:checked").value;
  $("#customer-error").hidden = /^C\d{3}$/.test(customer);
  $("#customer").setAttribute(
    "aria-invalid",
    String(!$("#customer-error").hidden),
  );
  if (!$("#customer-error").hidden) {
    $("#customer").focus();
    return;
  }
  if (mode === "deepseek" && !$("#consent").checked) {
    notify("请先确认向 DeepSeek 发送模拟证据并承担 API 费用。");
    $("#consent").focus();
    return;
  }
  $("#customer").value = customer;
  resetView();
  setBusy(true);
  notify(
    mode === "deepseek"
      ? "审查处理中，等待模型返回；请勿重复提交。"
      : "正在查询客户事实与政策证据…",
  );
  try {
    const result = await request("/reviews", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_id: customer, mode, paid_consent: mode === "deepseek" && $("#consent").checked }),
    });
    let audit = null;
    try {
      audit = await request(`/reviews/${result.request_id}`);
    } catch {}
    render({
      id: result.request_id,
      customer,
      mode,
      status: result.status,
      report: result.report,
      audit,
    });
    remember(result.request_id, customer, result.status, mode);
    selectTab("overview");
    notify(
      result.status === "partial_success"
        ? "AI 说明失败。SQL 事实、规则报告与审计记录已保留。"
        : !audit
          ? "审查完成；审计写入已确认，但暂时无法读取完整记录。"
          : "",
      result.status === "succeeded",
    );
  } catch (error) {
    notify(error.message + (error.id ? ` 请求 ID：${error.id}` : ""));
    if (error.id) {
      remember(error.id, customer, "failed", mode);
      $("#request-lookup").value = error.id;
      try {
        const audit = await request(`/reviews/${error.id}`);
        render({
          id: error.id,
          customer,
          mode,
          status: audit.status,
          report: audit.report,
          audit,
        });
        selectTab("audit");
      } catch {}
    }
  } finally {
    $("#consent").checked = false;
    setBusy(false);
  }
});
document.querySelectorAll("input[name=mode]").forEach((el) =>
  el.addEventListener("change", () => {
    $("#paid-notice").hidden = el.value !== "deepseek";
    $("#consent").checked = false;
  }),
);
$("#lookup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  loadAudit($("#request-lookup").value.trim());
});
$("#history-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-request]");
  if (button) loadAudit(button.dataset.request);
});
$("#clear-history").addEventListener("click", () => {
  records = [];
  try {
    sessionStorage.removeItem("review-ids");
  } catch {}
  renderHistory();
});
$(".tabs").addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (button) selectTab(button.dataset.view);
});
$(".tabs").addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const tabs = [...document.querySelectorAll("[data-view]")];
  const idx = tabs.indexOf(document.activeElement);
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (idx + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
          tabs.length;
  selectTab(tabs[next].dataset.view);
  tabs[next].focus();
});
$("#result").addEventListener("click", (event) => {
  const citation = event.target.closest("[data-citation]"),
    transaction = event.target.closest("[data-transaction]");
  if (citation) {
    selectTab("policies");
    const target = $(`#policy-${citation.dataset.citation}`);
    if (target) {
      target.querySelector("details").open = true;
      target.scrollIntoView({ block: "nearest" });
    }
  }
  if (transaction) {
    selectTab("transactions");
    document
      .getElementById(`tx-${transaction.dataset.transaction}`)
      ?.scrollIntoView({ block: "nearest" });
  }
  if (event.target.closest("#audit-refresh") && current) loadAudit(current.id);
});
$("#copy-request").addEventListener("click", async () => {
  if (!current) return;
  try {
    await navigator.clipboard.writeText(current.id);
    notify("请求 ID 已复制。", true);
  } catch {
    notify("复制失败。请求 ID 保留在报告标题下方。");
  }
});
$("#download").addEventListener("click", async () => {
  if (!current?.report) return;
  const selected = current;
  let verified;
  try { verified = await request(`/reviews/${selected.id}`); }
  catch (error) { resetView(); notify(error.message); return; }
  if (!signedUser || current !== selected || !verified.report) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(verified.report, null, 2)], {
      type: "application/json",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `review-${current.customer}-${current.id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#login-form button");
  button.disabled = true;
  $("#login-error").hidden = true;
  try {
    await request("/auth/login", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({username:$("#username").value.trim(), password:$("#password").value})});
    $("#password").value = "";
    await refreshIdentity();
    authChannel?.postMessage("identity-changed");
  } catch (error) {
    $("#login-error").textContent = error.message;
    $("#login-error").hidden = false;
  } finally { button.disabled = false; }
});
const authChannel = window.BroadcastChannel ? new BroadcastChannel("banking-auth") : null;
if (authChannel) authChannel.onmessage = () => signedOut();
$("#logout").addEventListener("click", async () => {
  if (busy) return;
  try { await request("/auth/logout", {method:"POST"}); signedOut(); authChannel?.postMessage("signed-out"); }
  catch (error) { notify(error.message); }
});
refreshIdentity().catch(() => signedOut());
request("/health")
  .then(() => {
    $("#health").textContent = "服务在线";
  })
  .catch(() => {
    $("#health").textContent = "服务不可用";
  });
renderHistory();
icons();
