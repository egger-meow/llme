"use strict";
function concepts(edits) {
  const nodes = new Map(),
    edges = edits.map(({ claim }, i) => {
      for (const label of [claim.source, claim.target])
        if (!nodes.has(label)) nodes.set(label, { label, id: nodes.size + 1, near: new Set(), edges: [] });
      const from = nodes.get(claim.source),
        to = nodes.get(claim.target);
      from.near.add(to);
      to.near.add(from);
      from.edges.push(i);
      if (from !== to) to.edges.push(i);
      return { from, to, i, label: claim.relation };
    });
  const seen = new Set(),
    groups = [];
  for (const node of nodes.values()) {
    if (seen.has(node)) continue;
    const group = [node];
    seen.add(node);
    for (const n of group)
      for (const next of n.near)
        if (!seen.has(next)) {
          seen.add(next);
          group.push(next);
        }
    groups.push(group);
  }
  return { nodes, edges, groups: groups.sort((a, b) => b.length - a.length) };
}
function scopeQs(sid) {
  return Q.filter((q) => q.scope === sid);
}
function structure(view, requested) {
  const q =
    requested ||
    Q.find(
      (r) =>
        r.task === "T1" &&
        r.arms.graph.hit &&
        !r.arms.raw.hit &&
        D.scopes[r.scope].status !== "evidence_only",
    ) ||
    Q[0];
  const scope = D.scopes[q.scope],
    tree = view === "tree",
    model = concepts(scope.edits);
  const available = Object.entries(D.scopes).filter(([, s]) => s.person === q.person);
  const fallback = scope.status === "evidence_only";
  main.innerHTML = `<h1>${tree ? "Tree 條件樹" : "Graph 關係圖"}</h1><p class="intro">${tree ? "由本次訪談的已存主張整理。展開條件可查看主張與原話。這棵樹供報告導覽，本輪沒有以 Tree 作答。" : "節點是這份 Graph 輸入的概念，箭頭是有方向的關係。點節點看相鄰關係，點箭頭讀主張與訪談引文。"}</p>
  <div class="tools">${select(
    "who",
    "受訪者",
    Object.keys(D.runs).map((p) => [p, p]),
    q.person,
  )}
  ${select(
    "sid",
    "可用訪談",
    available.map(([id, s], i) => [
      id,
      `${names[s.topic]} · 訪談 ${i + 1} · ${scopeQs(id).length} 題 · ${names[s.status] || s.status}`,
    ]),
    q.scope,
  )}
  ${link(tree ? "切換 Graph" : "切換 Tree", tree ? "graph" : "tree", { id: q.id }, "btn")}</div>
  <div class="panel"><b>${esc(q.person)} · ${esc(names[q.topic])}</b>　${model.nodes.size} 個節點 · ${scope.edits.length} 條${fallback ? "證據" : "主張"}關係 · ${scope.history.length} 段訪談
  <div class="links">${link("回到題目與三份回答", "question", { id: q.id })}${link("看使用這份訪談的 " + scopeQs(q.scope).length + " 題", "questions", { scope: q.scope })}<a href="../${esc(D.runs[q.person].name)}/audit.html#${encodeURIComponent(q.id)}">重播建圖過程</a></div></div>
  ${fallback ? '<p class="note">這份訪談沒有可採用的信念主張。圖中每條線連接證據編號與原問題，模型讀到的是問答原文。</p>' : ""}
  <h2>${tree ? "訪談的條件與主張" : "概念與關係"}</h2><div id="structureTools"></div><div class="diagram"><div id="drawing"></div><aside id="evidence" aria-live="polite" class="panel inspect"></aside></div>`;
  byId("who").onchange = () =>
    (location.hash = url(view, { id: Q.find((r) => r.person === byId("who").value).id }));
  byId("sid").onchange = () => (location.hash = url(view, { id: scopeQs(byId("sid").value)[0].id }));
  function evidence(i) {
    const e = scope.edits[i],
      c = e.claim,
      qa = scope.history.find((r) => r.evidence_id === c.evidence_id);
    const cites = [
      { ...qa, quote: c.quote, role: "主要證據" },
      ...(c.additional_evidence || []).map((a) => ({
        ...scope.history.find((r) => r.evidence_id === a.evidence_id),
        quote: a.quote,
        role: a.role,
      })),
    ];
    byId("evidence").innerHTML =
      `<small>${fallback ? "證據" : "主張"} #${i + 1} · ${esc(c.basis)}</small><h3>${esc(c.source)} → ${esc(c.target)}</h3>
    <p><b>關係</b>　${esc(c.relation)}</p><p><b>結果</b>　${esc(c.outcome)}</p><p><b>條件</b>　${esc(c.condition || "未指定")}</p>
    ${c.overrides ? `<p>覆寫主張 #${Number(c.overrides)}</p>` : ""}
    ${cites
      .map(
        (
          r,
        ) => `<hr><small>${esc(r.role)} · ${esc(r.evidence_id)}</small><p>${esc(r.question)}</p><blockquote>${esc(r.quote)}</blockquote>
      <details><summary>完整訪談回答</summary><p>${esc(r.answer)}</p></details>`,
      )
      .join("")}`;
  }
  if (!model.edges.length) {
    byId("drawing").textContent = "此訪談沒有已保存的關係。";
    byId("evidence").hidden = true;
    return;
  }
  if (tree) drawTree(scope, evidence);
  else graphPanel(model, evidence);
}
function drawTree(scope, evidence) {
  const conditions = new Map(),
    children = new Map();
  scope.edits.forEach(({ claim: c }, i) => {
    if (c.overrides != null) {
      if (!children.has(c.overrides - 1)) children.set(c.overrides - 1, []);
      children.get(c.overrides - 1).push(i);
      return;
    }
    const label = scope.status === "evidence_only" ? "訪談原文證據" : c.condition?.trim() || "未指定條件";
    if (!conditions.has(label)) conditions.set(label, []);
    conditions.get(label).push(i);
  });
  function branch(i) {
    const c = scope.edits[i].claim,
      sub = children.get(i) || [];
    return `<li><button data-i="${i}">#${i + 1}　${esc(c.source)} → ${esc(c.target)}</button>${sub.length ? `<ul><li>明示覆寫<ul>${sub.map(branch).join("")}</ul></li></ul>` : ""}</li>`;
  }
  const ordered = [...conditions].sort(([a], [b]) => Number(a === "未指定條件") - Number(b === "未指定條件"));
  byId("drawing").innerHTML =
    `<div class="panel limit"><ul class="tree"><li><strong>${scope.person} · ${names[scope.topic]}</strong><ul>${ordered.map(([label, ids], idx) => `<li><details ${idx === 0 ? "open" : ""}><summary>${esc(label)}（${ids.length}）</summary><ul>${ids.map(branch).join("")}</ul></details></li>`).join("")}</ul></li></ul></div>`;
  function choose(btn) {
    byId("drawing").querySelector(".selected")?.classList.remove("selected");
    btn.classList.add("selected");
    evidence(Number(btn.dataset.i));
  }
  for (const btn of byId("drawing").querySelectorAll("button")) btn.onclick = () => choose(btn);
  choose(byId("drawing").querySelector("button"));
}
function shortLines(label) {
  const lines = [""];
  for (const word of label.split(/\s+/)) {
    if ((lines.at(-1) + " " + word).trim().length > 20 && lines.at(-1)) lines.push("");
    lines[lines.length - 1] = (lines.at(-1) + " " + word).trim();
  }
  return lines
    .slice(0, 2)
    .map((s, i) => (s.length > 22 ? s.slice(0, 20) + "…" : i === 1 && lines.length > 2 ? s + "…" : s));
}
// Lay out each connected component independently, then pack components into rows.
function networkPositions(groups, pos, width) {
  let left = 0,
    top = 0,
    rowHeight = 0;
  for (const group of groups) {
    const w = Math.min(width, Math.max(176, Math.ceil(Math.sqrt(group.length) * 105)));
    const h = Math.max(100, w * 0.76);
    if (left + w > width) {
      left = 0;
      top += rowHeight;
      rowHeight = 0;
    }
    const points = group.map((node, i) => ({
      node,
      x: 0.36 * w * Math.cos((i * 2 * Math.PI) / group.length),
      y: 0.36 * h * Math.sin((i * 2 * Math.PI) / group.length),
    }));
    for (let pass = 0; pass < 130; pass++) {
      const forces = points.map((p) => ({ x: -p.x * 0.018, y: -p.y * 0.018 }));
      for (let i = 0; i < points.length; i++)
        for (let j = i + 1; j < points.length; j++) {
          const a = points[i],
            b = points[j],
            dx = b.x - a.x,
            dy = b.y - a.y,
            d = Math.max(1, Math.hypot(dx, dy));
          const f = (a.node.near.has(b.node) ? (d - 64) * 0.12 : 0) - 3200 / (d * d);
          const fx = (f * dx) / d,
            fy = (f * dy) / d;
          forces[i].x += fx;
          forces[i].y += fy;
          forces[j].x -= fx;
          forces[j].y -= fy;
        }
      points.forEach((p, i) => {
        p.x += Math.max(-5, Math.min(5, forces[i].x));
        p.y += Math.max(-5, Math.min(5, forces[i].y));
      });
    }
    const xs = points.map((p) => p.x),
      ys = points.map((p) => p.y);
    const xmin = Math.min(...xs),
      ymin = Math.min(...ys),
      dx = Math.max(...xs) - xmin,
      dy = Math.max(...ys) - ymin;
    const scale = Math.min((w - 72) / (dx || 1), (h - 62) / (dy || 1));
    for (const p of points)
      pos.set(p.node, {
        x: left + w / 2 + (p.x - xmin - dx / 2) * scale,
        y: top + h / 2 + (p.y - ymin - dy / 2) * scale,
      });
    left += w;
    rowHeight = Math.max(rowHeight, h);
  }
  return top + rowHeight;
}
function graphPanel(model, evidence) {
  let zoom = 1;
  const options = [
    ["all", `完整關係圖 · ${model.groups.length} 個連通群`],
    ...model.groups.map((g, i) => [String(i), `群 ${i + 1} · ${g.length} 節點 · ${g[0].label.slice(0, 42)}`]),
  ];
  byId("structureTools").innerHTML =
    `<div class="tools">${select("groupSelect", "圖的範圍", options, "all")}${select(
      "layout",
      "配置",
      [
        ["network", "網絡圖"],
        ["labels", "完整名稱分層圖"],
      ],
      "network",
    )}<button id="smaller" aria-label="縮小關係圖">−</button><button id="larger" aria-label="放大關係圖">＋</button><span id="zoom"></span></div>`;
  const drawing = byId("drawing");
  function draw() {
    const index = byId("groupSelect").value,
      groups = index === "all" ? model.groups : [model.groups[Number(index)]];
    const pos = new Map();
    let top = 20,
      width = 0;
    const compact = byId("layout").value === "network";
    if (compact) {
      width = Math.max(350, Math.min(800, drawing.clientWidth - 4));
      top = networkPositions(groups, pos, width);
    } else
      for (const group of groups) {
        // Layer each connected component from its most connected concept. Node IDs retain snapshot order.
        const root = group.reduce((a, b) => (a.near.size >= b.near.size ? a : b)),
          layers = [[root]],
          seen = new Set([root]);
        for (const layer of layers) {
          const next = [];
          for (const node of layer)
            for (const n of node.near)
              if (!seen.has(n)) {
                seen.add(n);
                next.push(n);
              }
          if (next.length) layers.push(next);
        }
        const height = Math.max(...layers.map((l) => l.length)) * 86;
        layers.forEach((layer, col) =>
          layer.forEach((node, row) =>
            pos.set(node, { x: 120 + col * 255, y: top + height / 2 + (row - (layer.length - 1) / 2) * 86 }),
          ),
        );
        width = Math.max(width, 240 + (layers.length - 1) * 255);
        top += height + 34;
      }
    const edges = model.edges.filter((e) => pos.has(e.from)),
      pairs = new Map(),
      svg = [];
    const arrow = `<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#506d70"/></marker></defs>`;
    for (const e of edges) {
      const key = [e.from.id, e.to.id].sort((a, b) => a - b).join("-");
      if (!pairs.has(key)) pairs.set(key, []);
      pairs.get(key).push(e);
    }
    for (const group of pairs.values())
      group.forEach((e, i) => {
        const a = pos.get(e.from),
          b = pos.get(e.to),
          dx = b.x - a.x,
          dy = b.y - a.y;
        let d, lx, ly;
        if (a === b) {
          const rise = (compact ? 22 : 39) + i * 10,
            half = compact ? 10 : 40,
            y = a.y - (compact ? 11 : 25);
          d = `M${a.x - half} ${y} C${a.x - half - 26} ${y - rise} ${a.x + half + 26} ${y - rise} ${a.x + half} ${y}`;
          lx = a.x;
          ly = y - 0.75 * rise;
        } else {
          const scale = compact
            ? 16 / Math.hypot(dx, dy)
            : Math.min(86 / (Math.abs(dx) || 0.001), 25 / (Math.abs(dy) || 0.001));
          const ax = a.x + dx * scale,
            ay = a.y + dy * scale,
            bx = b.x - dx * scale,
            by = b.y - dy * scale;
          const bend = (i - (group.length - 1) / 2) * 38;
          const horizontal = dx !== 0,
            cx = (ax + bx) / 2 + (horizontal ? 0 : bend),
            cy = (ay + by) / 2 + (horizontal ? bend : 0);
          d = `M${ax} ${ay} Q${cx} ${cy} ${bx} ${by}`;
          lx = (ax + 2 * cx + bx) / 4;
          ly = (ay + 2 * cy + by) / 4;
        }
        svg.push(`<g class="edge" data-edge="${e.i}" role="button" tabindex="0" aria-label="${esc(e.label)}，主張 ${e.i + 1}"><title>${esc(e.from.label + " — " + e.label + " → " + e.to.label)}</title>
        <path d="${d}" stroke="transparent" stroke-width="16" fill="none"/><path class="line" d="${d}" marker-end="url(#arrow)"/><rect x="${lx - 12}" y="${ly - 9}" width="24" height="18" rx="6" fill="#e2ece9"/><text x="${lx}" y="${ly + 4}" text-anchor="middle">${e.i + 1}</text></g>`);
      });
    for (const [n, p] of pos) {
      const lines = shortLines(n.label);
      if (compact) {
        svg.push(`<g class="node" data-node="${n.id}" role="button" tabindex="0" aria-label="${esc(n.label)}"><title>${esc(n.label)}</title><circle cx="${p.x}" cy="${p.y}" r="15"/><text class="node-id" x="${p.x}" y="${p.y + 4}" text-anchor="middle">N${n.id}</text>
        <text class="caption" text-anchor="middle" x="${p.x}" y="${p.y + 29}">${esc(n.label.length > 16 ? n.label.slice(0, 15) + "…" : n.label)}</text></g>`);
      } else
        svg.push(`<g class="node" data-node="${n.id}" role="button" tabindex="0" aria-label="${esc("N" + n.id + " " + n.label)}"><title>${esc(n.label)}</title>
        <rect x="${p.x - 86}" y="${p.y - 25}" width="172" height="50" rx="12"/><text text-anchor="middle" x="${p.x}" y="${p.y - 10}" style="font-size:10px;fill:#376b63">N${n.id}</text>
        ${lines.map((s, i) => `<text text-anchor="middle" x="${p.x}" y="${p.y + 5 + i * 13}">${esc(s)}</text>`).join("")}</g>`);
    }
    drawing.innerHTML = `<div class="canvas ${compact ? "network" : ""}" tabindex="0" aria-label="可捲動的概念關係圖"><svg aria-label="有向概念關係圖" width="${width * zoom}" height="${top * zoom}" viewBox="0 0 ${width} ${top}">${arrow + svg.join("")}</svg></div>
    <p class="muted">箭頭指向目標概念。線上數字是主張編號。可捲動查看全圖。</p>`;
    const highlight = (selector) =>
      drawing.querySelectorAll(selector).forEach((el) => el.classList.add("active"));
    const clear = () => drawing.querySelectorAll(".active").forEach((el) => el.classList.remove("active"));
    function chooseEdge(i) {
      clear();
      const e = model.edges[i];
      highlight(`[data-edge="${i}"],[data-node="${e.from.id}"],[data-node="${e.to.id}"]`);
      evidence(i);
    }
    function chooseNode(id) {
      clear();
      const n = [...pos.keys()].find((n) => n.id === id);
      highlight(`[data-node="${id}"]`);
      for (const i of n.edges) highlight(`[data-edge="${i}"]`);
      byId("evidence").innerHTML =
        `<small>概念節點 N${id}</small><h3>${esc(n.label)}</h3><p>${n.edges.length} 條相鄰關係</p><div class="detail">${n.edges
          .map((i) => {
            const e = model.edges[i];
            return `<p><button data-pick="${i}">#${i + 1}　${esc(e.from.label + " — " + e.label + " → " + e.to.label)}</button></p>`;
          })
          .join("")}</div>`;
      for (const btn of byId("evidence").querySelectorAll("button"))
        btn.onclick = () => chooseEdge(Number(btn.dataset.pick));
    }
    for (const el of drawing.querySelectorAll("g[role=button]")) {
      el.onclick = () =>
        el.hasAttribute("data-edge")
          ? chooseEdge(Number(el.dataset.edge))
          : chooseNode(Number(el.dataset.node));
      el.onkeydown = (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          el.onclick();
        }
      };
    }
    chooseEdge(edges.find((e) => groups[0].includes(e.from)).i);
    byId("zoom").textContent = Math.round(zoom * 100) + "%";
  }
  byId("groupSelect").onchange = draw;
  byId("layout").onchange = draw;
  function resize(step) {
    const svg = drawing.querySelector("svg"),
      box = svg.viewBox.baseVal;
    zoom = Math.max(0.4, Math.min(2, zoom + step));
    svg.setAttribute("width", box.width * zoom);
    svg.setAttribute("height", box.height * zoom);
    byId("zoom").textContent = Math.round(zoom * 100) + "%";
  }
  byId("smaller").onclick = () => resize(-0.2);
  byId("larger").onclick = () => resize(0.2);
  draw();
}
