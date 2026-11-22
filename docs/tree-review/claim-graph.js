// Each lane starts once at a concept and branches to the outcomes named by its claims.
function drawClaimGraph(example, nodeId, selectedClaim) {
  const node = example.nodes[nodeId];
  const visible = new Set(node.claims);
  const overrides = example.exceptions.filter(edge =>
    edge.condition === nodeId && visible.has(edge.base) && visible.has(edge.local)
  );
  const replaced = new Set(overrides.map(edge => edge.base));
  const lanes = new Map();

  function element(tag, className, text) {
    const el = document.createElement(tag);
    el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function claimButton(id, className) {
    const claim = example.claims[id];
    const button = element("button", className);
    button.type = "button";
    button.dataset.claim = id;
    button.setAttribute("aria-pressed", String(id === selectedClaim));
    button.setAttribute("aria-label", id + " " + claim.text);
    return button;
  }

  const graph = element("div", "claim-graph");
  graph.setAttribute("role", "group");
  graph.setAttribute("aria-label", node.label + "的主張關係圖");
  if (!visible.size) return graph;

  for (const id of visible) {
    const claim = example.claims[id];
    if (!lanes.has(claim.from)) lanes.set(claim.from, []);
    lanes.get(claim.from).push(id);
  }

  for (const [from, ids] of lanes) {
    const lane = element("div", "cg-lane");
    const branches = element("div", "cg-branches");
    lane.append(element("span", "cg-origin", from), branches);

    for (const id of ids) {
      const claim = example.claims[id];
      const branch = element("div", "cg-branch");
      if (replaced.has(id)) branch.classList.add("cg-replaced");
      const relation = claimButton(id, "cg-edge");
      relation.append(element("b", "cg-id", id), element("span", "cg-verb", claim.relation));
      const target = element("span", "cg-target", claim.to);
      if (replaced.has(id)) target.append(element("small", "cg-note", "此處被取代"));
      branch.append(relation, target);
      branches.append(branch);
    }
    graph.append(lane);
  }

  const links = element("div", "cg-links");
  function linkClaims(first, label, second) {
    const row = element("span", "cg-link");
    const a = claimButton(first, "cg-ref");
    const b = claimButton(second, "cg-ref");
    a.textContent = first;
    b.textContent = second;
    row.append(a, element("span", "cg-link-label", label), b);
    links.append(row);
  }
  for (const edge of overrides) linkClaims(edge.local, "取代", edge.base);
  for (const id of visible) {
    const target = example.claims[id].reasonFor;
    if (visible.has(target)) linkClaims(id, "解釋", target);
  }
  if (links.childElementCount) graph.append(links);
  return graph;
}
