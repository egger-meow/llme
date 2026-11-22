"use strict";

const byId = id => document.getElementById(id);

function element(tag, text, className) {
  const result = document.createElement(tag);
  if (text) result.textContent = text;
  if (className) result.className = className;
  return result;
}

function button(text, className, action, value) {
  const result = element("button", text, className);
  result.type = "button";
  result.dataset[action] = value;
  return result;
}

function pathTo(example, target, path = [example.root]) {
  const current = path.at(-1);
  if (current === target) return path;
  for (const id of example.nodes[current].children) {
    if (path.includes(id)) continue;
    const found = pathTo(example, target, [...path, id]);
    if (found) return found;
  }
}

// Keep the path as well as the node ID. The same claim can be reached from two roles or topics.
function readState() {
  const params = new URLSearchParams(location.hash.slice(1));
  const caseId = Object.hasOwn(REVIEW_CASES, params.get("case")) ? params.get("case") : "p46";
  const example = REVIEW_CASES[caseId];
  let path = (params.get("path") || "").split("/");
  if (path[0] !== example.root || !path.every((id, i) => !i || example.nodes[path[i - 1]].children.includes(id))) {
    path = pathTo(example, example.initial);
  }
  const node = example.nodes[path.at(-1)];
  const claim = node.claims.includes(params.get("claim")) ? params.get("claim") : node.focus || node.claims[0];
  const mode = params.get("mode") === "trial" ? "trial" : "inspect";
  const trial = Number(params.get("trial"));
  return { caseId, path, claim, mode, trial: Number.isInteger(trial) && example.trials[trial] ? trial : 0 };
}

let state = readState();
const currentCase = () => REVIEW_CASES[state.caseId];

function go(next) {
  const params = new URLSearchParams({case: next.caseId, path: next.path.join("/")});
  if (next.claim) params.set("claim", next.claim);
  if (next.mode === "trial") {
    params.set("mode", "trial");
    params.set("trial", next.trial);
  }
  const url = "#" + params;
  if (location.hash !== url) history.pushState(null, "", url);
  state = next;
  render();
}

function choosePath(path) {
  const node = currentCase().nodes[path.at(-1)];
  go({...state, path, claim: node.focus || node.claims[0], mode: "inspect"});
}

function chooseTrial(index) {
  const example = currentCase();
  const trial = example.trials[index];
  const leaf = trial.conditions.at(-1);
  const path = pathTo(example, leaf);
  const node = example.nodes[leaf];
  go({...state, path, claim: node.focus || node.claims[0], mode: "trial", trial: index});
}

function nodeButton(path, style) {
  const nodeId = path.at(-1);
  const data = currentCase().nodes[nodeId];
  const result = button(data.label, "tree-button " + style, "path", path.join("/"));
  const selected = path.join("/") === state.path.join("/");
  result.setAttribute("aria-pressed", String(selected));
  if (state.mode === "trial" && currentCase().trials[state.trial].conditions.includes(nodeId)) {
    result.classList.add("match");
    result.append(element("span", "符合", "match-hint"));
  }
  if (path.length !== 2) {
    const icon = element("i", "", path.length === 1 ? "root-icon" : "local-icon");
    icon.setAttribute("aria-hidden", "true");
    result.prepend(icon);
  }
  return result;
}

function graphFrame(example, nodeId) {
  const frame = element("section", "", "graph-frame");
  frame.setAttribute("aria-label", example.nodes[nodeId].label + "的關係圖");
  const title = element("div", "", "graph-title");
  title.append(element("strong", "此節點的關係圖"), element("small", "點箭頭看主張"));
  frame.append(title, drawClaimGraph(example, nodeId, state.claim));
  const jump = button("看選取的主張與依據", "mobile-inspect link-chip", "jump", "evidence");
  frame.append(jump);
  return frame;
}

function branches(parentPath) {
  const example = currentCase();
  const list = element("ul", "", "branches");
  for (const child of example.nodes[parentPath.at(-1)].children) {
    const path = [...parentPath, child];
    const node = example.nodes[child];
    const entry = element("li", "", "branch");
    const control = nodeButton(path, "");
    if (path.join("/") === state.path.join("/") && node.claims.length) {
      const selectedNode = element("div", "", "selected-node");
      selectedNode.append(control, graphFrame(example, child));
      entry.append(selectedNode);
    } else {
      entry.append(control);
    }
    if (node.children.length) entry.append(branches(path));
    list.append(entry);
  }
  return list;
}

function drawMap() {
  const example = currentCase();
  const map = byId("map");
  const rootRow = element("div", "", "root-row");
  rootRow.append(nodeButton([example.root], "root-button"));
  const domains = element("ul", "", "domains");
  domains.setAttribute("aria-label", "大情境");
  const topNodes = example.nodes[example.root].children;
  const top = state.path[1];
  for (const id of topNodes) {
    const item = element("li", "", "domain");
    item.append(nodeButton([example.root, id], id === top ? "on-path" : ""));
    domains.append(item);
  }
  map.replaceChildren(rootRow, domains);
  if (!top) {
    if (example.nodes[example.root].claims.length) map.append(graphFrame(example, example.root));
    else map.append(element("p", "選一個分枝，展開這個人處在其中的情境。", "root-empty"));
    return;
  }
  const node = example.nodes[top];
  const inner = element("section", "", "inner");
  inner.style.setProperty("--entry", ((topNodes.indexOf(top) + 0.5) / topNodes.length * 100) + "%");
  const title = element("h3", node.label);
  title.append(element("small", "局部條件樹"));
  inner.append(title);
  if (state.path.length === 2 && node.claims.length) inner.append(graphFrame(example, top));
  if (node.children.length) inner.append(branches([example.root, top]));
  else if (!node.claims.length) inner.append(element("p", node.about, "empty"));
  map.append(inner);
}

function claimLinks(example, claimId) {
  const group = element("div", "", "relations");
  for (const edge of example.exceptions) {
    if (edge.base !== claimId && edge.local !== claimId) continue;
    const target = edge.local === claimId ? edge.base : edge.local;
    const label = edge.local === claimId ? "查看原判斷" : "查看例外";
    const link = button(label + " · " + example.claims[target].to, "link-chip", "related", target);
    // Open the condition where both ends can be compared.
    link.dataset.condition = edge.condition;
    group.append(link);
  }
  return group;
}

function inspector() {
  const example = currentCase();
  const body = element("div", "", "inspector-content");
  const node = example.nodes[state.path.at(-1)];
  const claim = example.claims[state.claim];
  if (!claim) {
    body.append(element("p", node.kind, "overline"), element("h3", node.label), element("p", node.about));
    if (node.children.length) {
      const group = element("div", "", "relations");
      for (const id of node.children) {
        group.append(button(example.nodes[id].label, "link-chip", "path", [...state.path, id].join("/")));
      }
      body.append(group);
    }
    return body;
  }
  body.append(element("p", state.claim + "　" + claim.kind, "overline claim-type"));
  body.append(element("h3", claim.to), element("p", claim.text));
  const links = claimLinks(example, state.claim);
  if (links.childElementCount) body.append(links);
  const source = example.sources[claim.source];
  const box = element("div", "", "source");
  box.append(element("b", source.label), element("p", source.note));
  if (source.href) {
    const link = element("a", source.linkText);
    link.href = source.href;
    link.target = "_blank";
    link.rel = "noopener";
    box.append(link);
  }
  body.append(box);
  return body;
}

function trialInspector() {
  const example = currentCase();
  const trial = example.trials[state.trial];
  const body = element("div", "", "inspector-content");
  const label = element("label", "用假設情況檢查這棵樹", "overline");
  label.htmlFor = "trial-select";
  const select = element("select", "", "trial-select");
  select.id = label.htmlFor;
  example.trials.forEach((item, index) => select.add(new Option(item.label, String(index))));
  select.value = String(state.trial);
  select.addEventListener("change", () => chooseTrial(Number(select.value)));
  body.append(label, select, element("h3", trial.result), element("p", trial.explanation));
  const statuses = element("dl", "", "trial-status");
  for (const [field, text] of [["active", "成立"], ["overridden", "被覆寫"], ["provisional", "暫定"], ["pending", "待確認"]]) {
    if (!trial[field]?.length) continue;
    statuses.append(element("dt", text), element("dd", trial[field].map(id => id + " " + example.claims[id].to).join("、")));
  }
  if (statuses.childElementCount) body.append(statuses);
  body.append(button("回樹上看符合的條件", "mobile-inspect link-chip", "jump", "map"));
  return body;
}

function render() {
  const focus = document.activeElement;
  const focusKey = focus?.closest("button")?.dataset;
  const trialFocused = focus?.id === "trial-select";
  const example = currentCase();
  byId("case-title").textContent = example.name;
  byId("case-intro").textContent = example.intro;
  byId("case-type").textContent = example.type;
  byId("case-switch").replaceChildren(...Object.entries(REVIEW_CASES).map(([id, item]) => {
    const choice = button(item.tab, "", "case", id);
    choice.setAttribute("aria-pressed", String(id === state.caseId));
    return choice;
  }));
  for (const tab of document.querySelectorAll("[data-mode]")) {
    tab.setAttribute("aria-pressed", String(tab.dataset.mode === state.mode));
  }
  drawMap();
  byId("inspector-body").replaceChildren(state.mode === "trial" ? trialInspector() : inspector());
  if (trialFocused) byId("trial-select")?.focus({preventScroll: true});
  else if (focusKey && !focus.isConnected) {
    const replacement = [...document.querySelectorAll("button")].find(el =>
      Object.entries(focusKey).every(([key, value]) => el.dataset[key] === value));
    replacement?.focus({preventScroll: true});
  }
}

document.addEventListener("click", event => {
  const target = event.target.closest("[data-case],[data-path],[data-mode],[data-related],[data-claim],[data-jump]");
  if (!target) return;
  const action = target.dataset;
  if (action.case) {
    const example = REVIEW_CASES[action.case];
    const initial = example.nodes[example.initial];
    go({caseId: action.case, path: pathTo(example, example.initial), claim: initial.focus, mode: "inspect", trial: 0});
  } else if (action.path) choosePath(action.path.split("/"));
  else if (action.claim) go({...state, claim: action.claim, mode: "inspect"});
  else if (action.related) go({...state, path: pathTo(currentCase(), action.condition), claim: action.related, mode: "inspect"});
  else if (action.mode === "trial") chooseTrial(state.trial);
  else if (action.mode === "inspect") go({...state, mode: "inspect"});
  else if (action.jump) {
    const dest = action.jump === "map" ? byId("map") : byId("inspector-body");
    dest.tabIndex = -1;
    dest.focus({preventScroll: true});
    dest.scrollIntoView({block: "start"});
  }
});

window.addEventListener("hashchange", () => { state = readState(); render(); });
render();
