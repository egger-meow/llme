"use strict";
const D = JSON.parse(document.getElementById("data").textContent);
const Q = D.questions,
  ARMS = ["raw", "graph", "flat"],
  main = document.getElementById("main");
const names = {
  raw: "Raw",
  graph: "Graph",
  flat: "Flat",
  healthcare: "醫療",
  surveillance: "監控",
  zoning: "都市分區",
  causal_direction: "因果方向",
  baseline_stance: "基準立場",
  hypothetical_scenario: "假設情境",
  reason_influence: "理由影響",
  experience_or_perception: "經驗或感受",
  strict: "直接通過",
  recovered: "格式修復",
  partial: "部分主張通過",
  evidence_only: "僅保留原文證據",
};
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
const fmt = (n, k = 2) => (n == null ? "—" : Number(n).toFixed(k));
const signed = (n) => (n > 0 ? "+" : "") + fmt(n);
const byId = (id) => document.getElementById(id);
const mapQ = new Map(Q.map((q) => [q.id, q]));
const state = () => Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
function url(view, params = {}) {
  return (
    "#" +
    new URLSearchParams(
      Object.entries({ ...params, view }).filter(([, v]) => v !== "" && v != null),
    ).toString()
  );
}
function link(text, view, params = {}, css = "") {
  return `<a class="${css}" href="${esc(url(view, params))}">${esc(text)}</a>`;
}
function table(headers, rows, cls = "") {
  return `<div class="tbl"><table class="${cls}"><thead><tr>${headers.map((h) => `<th scope="col">${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function select(id, label, options, current) {
  return `<label>${label}<select id="${id}">${options.map(([v, t]) => `<option value="${esc(v)}" ${v === current ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
}
function opts(values, all) {
  return [["", all], ...values.map((v) => [v, names[v] || v])];
}
function verdict(q, a) {
  const r = q.arms[a];
  if (r.parsed == null)
    return `<span class="badge missing">${r.finish === "MAX_TOKENS" ? "截斷缺答" : r.text?.trim() ? "無法解析" : "缺答"}</span>`;
  const label =
    q.task === "T1" ? (r.hit ? "正確" : "錯誤") : r.error === 0 ? "完全命中" : r.hit ? "容許內" : "超出容許";
  return `<span class="badge ${r.hit ? "ok" : "bad"}">${label}</span>`;
}
function matches(q, s) {
  if (s.status && D.scopes[q.scope].status !== s.status) return false;
  if (
    ["person", "topic", "task", "measure"].some((k) => s[k] && q[k] !== s[k]) ||
    (s.scope && q.scope !== s.scope)
  )
    return false;
  if (
    s.term &&
    ![q.id, q.prompt, ...Object.values(q.options || {}), q.person]
      .join(" ")
      .toLowerCase()
      .includes(s.term.trim().toLowerCase())
  )
    return false;
  const a = q.arms;
  switch (s.result) {
    case "split":
      return ARMS.some((k) => a[k].hit !== a.raw.hit);
    case "different":
      return ARMS.some((k) => a[k].parsed !== a.raw.parsed);
    case "allhit":
      return ARMS.every((k) => a[k].hit);
    case "allmiss":
      return ARMS.every((k) => !a[k].hit);
    case "graphwin":
      return a.graph.hit && !a.raw.hit;
    case "rawwin":
      return a.raw.hit && !a.graph.hit;
    case "blank":
      return ARMS.some((k) => a[k].parsed == null);
    default:
      return !ARMS.some((k) => s.result === k + "miss" && a[k].hit);
  }
}
function charts(key, title, unit, maximum) {
  return `<div class="panel"><h3>${title}</h3>${ARMS.map((a) => {
    const v = D.scores[a].overall[key];
    return `<div class="chart ${a}"><span class="name">${names[a]}</span><span class="rail"><i class="bar" style="width:${(100 * v) / maximum}%"></i></span><b>${fmt(v)}${unit}</b></div>`;
  }).join("")}</div>`;
}
function overview() {
  const t1 = Q.filter((q) => q.task === "T1").length,
    scores = (a) => D.scores[a].overall;
  const pair = D.paired.find((p) => p.task === "T2" && p.left === "graph" && p.right === "raw");
  const blank = Q.flatMap((q) => Object.values(q.arms)).filter((r) => r.parsed == null);
  const examples = ["graphwin", "rawwin"]
    .map((result) =>
      Q.find(
        (q) =>
          q.task === "T1" &&
          matches(q, { result }) &&
          ARMS.every((a) => q.arms[a].parsed != null) &&
          D.scopes[q.scope].status !== "evidence_only",
      ),
    )
    .filter(Boolean);
  const winner = (key, dir) => names[[...ARMS].sort((a, b) => dir * (scores(b)[key] - scores(a)[key]))[0]];
  const rows = ARMS.map((a) => {
    const m = scores(a);
    return [
      `<b class="name ${a}">${names[a]}</b>`,
      `${Q.filter((q) => q.task === "T1" && q.arms[a].hit).length} / ${t1}`,
      `${Q.filter((q) => q.task === "T2" && q.arms[a].hit).length} / ${Q.length - t1}`,
      fmt(m.bdu_dir_acc) + "%",
      fmt(m.ati),
      m.unparsed,
    ];
  });
  main.innerHTML = `<section class="hero"><small>HugAgent 個人信念預測實驗</small><h1>同一份訪談，哪種表示預測得準？</h1>
  <p>在這批受訪者中，${winner("bsi_acc", 1)} 的 T1 正確率最高，${winner("bdu_mae", -1)} 的 T2 平均誤差最低。</p><div class="kpis">${[
    [Object.keys(D.runs).length, "位受訪者"],
    [Q.length, "道考題"],
    [Object.keys(D.scopes).length, "份可用訪談"],
    [Q.length * 3, "格模式作答"],
  ]
    .map(([v, t]) => `<div><strong>${v.toLocaleString()}</strong><small>${t}</small></div>`)
    .join("")}</div></section>
  <h2>三種模式的表現</h2><p class="subtitle">Raw 讀完整訪談。Graph 讀概念與關係。Flat 讀相同主張與引文的平鋪文字。官方總分先在各領域計算，再給三個領域相同權重。</p>
  <div class="grid3">${charts("bsi_acc", `T1 選擇題正確率 ↑`, "%", 100)}${charts("bdu_acc", "T2 量表容許命中率 ↑", "%", 100)}${charts("bdu_mae", "T2 平均絕對誤差 ↓", "", 6)}</div>
  <p class="subtitle">T1 共 ${t1} 題。T2 共 ${Q.length - t1} 題，10 分量表的誤差除以 2，再與 5 分量表一起計算。</p>
  ${table(["模式", "T1 答對題數", "T2 容許內題數", "立場變化方向分數 ↑", "官方綜合指標 ATI ↑", "缺答或無法解析"], rows)}
  <div class="links">${link("查看全部題目 →", "questions")} ${link("看三組判分不同的題目 →", "questions", { result: "split" })} ${link("追查缺答與原始輸出 →", "questions", { result: "blank" })}</div>
  <p class="note">在 ${Q.length - t1} 道量表題上，Graph 的平均誤差比 Raw ${pair.delta >= 0 ? "高" : "低"} ${fmt(Math.abs(pair.delta), 3)} 分。全批共 ${blank.length} 格未解析，其中 ${blank.filter((r) => r.finish === "MAX_TOKENS").length} 格因輸出達 token 上限而以缺答計分。</p>
  <h2>Graph 與 Raw 在哪些題目互有得失？</h2><p class="subtitle">點題數查看題目與三份回答。T2 以是否落在官方容許範圍內判定。</p>
  ${table(
    ["任務", "Graph 命中、Raw 失分", "Raw 命中、Graph 失分", "兩組判分相同"],
    ["T1", "T2"].map((task) => {
      const qs = Q.filter((q) => q.task === task),
        cell = (r) =>
          link(qs.filter((q) => matches(q, { result: r })).length + " 題", "questions", { task, result: r });
      return [
        task,
        cell("graphwin"),
        cell("rawwin"),
        qs.filter((q) => q.arms.raw.hit === q.arms.graph.hit).length + " 題",
      ];
    }),
  )}
  <div class="grid2 spaced">${examples
    .map(
      (
        q,
      ) => `<article class="panel"><small>${q.person} · ${names[q.topic]} · ${q.arms.graph.hit ? "Graph 答對、Raw 答錯" : "Raw 答對、Graph 答錯"}</small><h3>${link(q.prompt, "question", { id: q.id })}</h3>
  <p>標準答案 ${esc(q.gold)}　·　${ARMS.map((a) => names[a] + " " + esc(q.arms[a].parsed)).join("　")}</p></article>`,
    )
    .join("")}</div>
  <h2>配對差異與不確定性</h2><p class="subtitle">同一人、同一題配對。以人為單位重抽 5,000 次，保留三組回答與領域權重。區間為探索性 95% 百分位區間，僅描述這批受訪者。</p>
  ${table(
    ["比較（前者減後者）", "T1 正確率差［95% 區間］，百分點 ↑", "T2 誤差差［95% 區間］，分 ↓"],
    D.paired
      .filter((p) => p.task === "T1")
      .map((p) => {
        const other = D.paired.find((x) => x.task === "T2" && x.left === p.left && x.right === p.right);
        const val = (x) => `${signed(x.delta)} ［${signed(x.lo)}, ${signed(x.hi)}］`;
        return [names[p.left] + " − " + names[p.right], val(p), val(other)];
      }),
  )}
  <h2>分組查看結果</h2><div class="tools">${select(
    "group",
    "分組依據",
    [
      ["topic", "領域"],
      ["person", "受訪者"],
      ["measure", "題型"],
      ["status", "建圖狀態"],
    ],
    "topic",
  )}</div><div id="groups"></div>`;
  function groups() {
    const k = byId("group").value,
      groupOf = (q) => (k === "status" ? D.scopes[q.scope].status : q[k]),
      keys = [...new Set(Q.map(groupOf))].sort();
    byId("groups").innerHTML =
      table(
        ["分組", "題數", "任務", "Raw", "Graph", "Flat"],
        keys.flatMap((v) =>
          ["T1", "T2"].flatMap((task) => {
            const qs = Q.filter((q) => groupOf(q) === v && q.task === task);
            return qs.length
              ? [
                  [
                    link(names[v] || v, "questions", { [k]: v, task }),
                    qs.length,
                    task === "T1" ? "T1 正確率 ↑" : "T2 平均誤差 ↓",
                    ...ARMS.map((a) =>
                      task === "T1"
                        ? fmt((100 * qs.filter((q) => q.arms[a].hit).length) / qs.length) + "%"
                        : fmt(qs.reduce((n, q) => n + q.arms[a].error, 0) / qs.length),
                    ),
                  ],
                ]
              : [];
          }),
        ),
      ) + '<p class="muted">此表在各組內逐題平均。點組名可查看分母內的每一題。</p>';
  }
  byId("group").onchange = groups;
  groups();
}
const resultOpts = [
  ["", "全部判分"],
  ["split", "三組判分不同"],
  ["different", "三組答案不同"],
  ["graphwin", "Graph 命中、Raw 失分"],
  ["rawwin", "Raw 命中、Graph 失分"],
  ["allhit", "三組都命中"],
  ["allmiss", "三組都失分"],
  ...ARMS.map((a) => [a + "miss", names[a] + " 失分"]),
  ["blank", "有缺答或無法解析"],
];
function filteredState(s) {
  return Object.fromEntries(
    ["person", "topic", "task", "result", "measure", "term", "scope", "status", "page"]
      .filter((k) => s[k])
      .map((k) => [k, s[k]]),
  );
}
function questionList(s) {
  main.innerHTML = `<h1>逐題比較</h1><p class="intro">點題幹看本人答案、三種模式的完整回答，以及這一題實際使用的圖。</p>
  <div class="tools"><label>搜尋題目<input type="search" id="term" placeholder="輸入題幹、選項或編號" value="${esc(s.term)}"></label>
  ${select("person", "受訪者", opts(Object.keys(D.runs), "全部受訪者"), s.person)}${select("topic", "領域", opts(["healthcare", "surveillance", "zoning"], "全部領域"), s.topic)}
  ${select("task", "任務", opts(["T1", "T2"], "全部任務"), s.task)}${select("result", "回答結果", resultOpts, s.result)} ${link("清除篩選", "questions")}</div>
  ${s.scope || s.measure || s.status ? `<p class="note">目前範圍 · ${esc(names[s.measure] || names[s.status] || s.scope || "")}</p>` : ""}<div id="found"></div>`;
  function results(current) {
    const rows = Q.filter((q) => matches(q, current)),
      size = 18,
      pages = Math.ceil(rows.length / size),
      page = Math.max(1, Math.min(Number(current.page) || 1, pages));
    const pagination = `<div class="toolbar"><b>${rows.length} 題${pages ? ` · 第 ${page} / ${pages} 頁` : ""}</b><div class="wrap">${page > 1 ? link("上一頁", "questions", { ...current, page: page - 1 }, "btn") : ""}${page < pages ? link("下一頁", "questions", { ...current, page: page + 1 }, "btn") : ""}</div></div>`;
    byId("found").innerHTML =
      pagination +
      (rows.length
        ? table(
            ["題目", "本人答案", "Raw", "Graph", "Flat"],
            rows
              .slice((page - 1) * size, page * size)
              .map((q) => [
                `<small>${q.person} · ${names[q.topic]} · ${q.task}</small>${link(q.prompt, "question", { ...current, id: q.id })}`,
                esc(q.gold),
                ...ARMS.map((a) => verdict(q, a) + `<small>${esc(q.arms[a].parsed ?? "—")}</small>`),
              ]),
            "qtable",
          )
        : "<p>沒有符合條件的題目。</p>") +
      (rows.length > size ? pagination : "");
  }
  for (const id of ["term", "person", "topic", "task", "result"]) {
    byId(id)[id === "term" ? "oninput" : "onchange"] = () => {
      const current = filteredState(state());
      delete current.page;
      current[id] = byId(id).value;
      history.replaceState(null, "", url("questions", current));
      results(current);
    };
  }
  results(filteredState(s));
}
function question(s, q) {
  const filters = filteredState(s),
    set = Q.filter((row) => matches(row, filters)),
    i = set.indexOf(q);
  main.innerHTML = `<div class="toolbar">${link("← 題目列表", "questions", filters)}<div class="wrap">${i > 0 ? link("上一題", "question", { ...filters, id: set[i - 1].id }, "btn") : ""}${i >= 0 && i + 1 < set.length ? link("下一題", "question", { ...filters, id: set[i + 1].id }, "btn") : ""}</div></div>
  <p class="subtitle">${q.person} · ${names[q.topic]} · ${q.task} ${names[q.measure]} · <span class="mono">${esc(q.id)}</span></p><h1 class="question">${esc(q.prompt)}</h1>
  ${
    q.options
      ? `<div class="panel spaced">${Object.entries(q.options)
          .map(([k, v]) => `<p><b>${esc(k)}</b>　${esc(v)}</p>`)
          .join("")}</div>`
      : ""
  }
  <p class="note"><b>${q.task === "T1" ? "標準答案" : "本人量表答案"}　${esc(q.gold)}</b>　${q.scale ? `${q.scale.join("–")} 分量表，與本人答案相差 ${q.scale[1] - q.scale[0] > 5 ? 2 : 1} 分以內算命中。` : "以官方可接受的選項判分。"}</p>
  <div class="grid3">${ARMS.map((a) => {
    const r = q.arms[a];
    return `<article class="panel answer ${a}"><div class="toolbar"><b class="name">${names[a]}</b>${verdict(q, a)}</div><div class="big">${esc(r.parsed ?? "—")}</div>
  ${q.options && q.options[r.parsed] ? `<p>${esc(q.options[r.parsed])}</p>` : ""}${q.scale ? `<p>標準化絕對誤差　<b>${fmt(r.error, 1)}</b></p>` : ""}
  ${r.finish === "MAX_TOKENS" ? `<p>模型輸出達長度上限，評分時記為缺答。</p><details><summary>查看截斷時的原始輸出</summary><pre>${esc(r.original || "（空白）")}</pre></details>` : `<small>模型原始回答</small><pre>${esc(r.original ?? r.text ?? "（空白）")}</pre>`}</article>`;
  }).join("")}</div>
  <h2>這一題用了什麼資料？</h2><div class="wrap">${link("開啟 Graph 關係圖", "graph", { id: q.id }, "btn primary")}${link("展開 Tree 條件樹", "tree", { id: q.id }, "btn")}
  <a class="btn" href="../${esc(D.runs[q.person].name)}/audit.html#${encodeURIComponent(q.id)}">建圖重播與完整提示詞</a></div>`;
}
function processView() {
  const scopes = Object.values(D.scopes),
    counts = {};
  for (const s of scopes) counts[s.status] = (counts[s.status] || 0) + 1;
  const evidence = scopes.filter((s) => s.status === "evidence_only"),
    claims = scopes.filter((s) => s.status !== "evidence_only").flatMap((s) => s.edits);
  main.innerHTML = `<h1>從訪談到評分</h1><p class="intro">每題只讀該題獲准的訪談。相同訪談可供多題共用，標準答案只在離線評分時加入。</p>
 <div class="grid2"><div class="panel"><h3>建圖驗證狀態</h3>${Object.entries(counts)
   .map(([k, n]) => `<div class="statusline"><span>${names[k] || k}</span><b>${n} 份</b></div>`)
   .join("")}</div>
 <div class="panel"><h3>實際進入模型的資料</h3><p>共 ${claims.length.toLocaleString()} 筆通過證據驗證的主張，其中 ${claims.filter((e) => e.claim.condition?.trim()).length} 筆有條件，${claims.filter((e) => e.claim.overrides != null).length} 筆有明示覆寫。</p><p>${evidence.length} 份訪談只保留問答原文，共 ${evidence.reduce((n, s) => n + s.edits.length, 0)} 筆證據關係。這些訪談也計入整體表現。</p>
 <p>報告中的 Tree 依主張的條件分組。本輪模型使用 Raw、Graph、Flat 三種輸入，沒有執行 Tree 路由。</p></div></div>
 <h2>逐人實驗紀錄</h2><p class="subtitle">P01 採續跑版，P07 採補跑版。每題計一次。點 run 名稱查看訪談、建圖原始回覆、操作鏈、修復與模型輸入。</p>
 ${table(
   ["受訪者", "保存的 run", "模型", "題數", "訪談數", "供應商回報 token", "已計量回覆估計 USD"],
   Object.entries(D.runs).map(([p, r]) => [
     link(p, "questions", { person: p }),
     '<a href="../' + esc(r.name) + '/audit.html">' + esc(r.name) + "</a>",
     esc(r.model),
     r.usage.questions,
     r.usage.scopes,
     r.usage.provider_reported_tokens?.toLocaleString() ?? "—",
     fmt(r.usage.estimated_usd_for_metered_responses, 4),
   ]),
 )}`;
}
function render() {
  const s = state(),
    view = s.view || "overview",
    q = mapQ.get(s.id);
  document.querySelectorAll("nav a").forEach((a) => {
    const key = new URLSearchParams(a.hash.slice(1)).get("view");
    if (["graph", "tree"].includes(key)) a.href = url(key, q ? { id: q.id } : {});
    if (key === (view === "question" ? "questions" : view)) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if (view === "questions") questionList(s);
  else if (view === "question" && q) question(s, q);
  else if (view === "graph" || view === "tree") structure(view, q);
  else if (view === "process") processView();
  else overview();
  window.scrollTo(0, 0);
}
