// "Pick the article area" tool: the popup injects this into the page (like
// toolbar.js) so the user can click the parts of the page that should be
// clipped (and optionally the parts to drop) instead of writing CSS selectors.
// On save it stores a site rule in chrome.storage.local "siteRules"
// ([{host, content, remove}]) — the same list the settings page edits and
// content.js (jcpUserSiteRule) reads at clip time.
//
// Drawn inside a closed shadow root so the page's CSS can't restyle it; the
// page's own click handlers are blocked (capture phase) while it is open so
// clicking a link or button just picks it. Re-injection safe: a second
// injection closes the previous instance first.
(function () {
  const HOST_ID = "__jcp-picker";
  const old = document.getElementById(HOST_ID);
  if (old && old.__jcpClose) old.__jcpClose();

  const include = []; // elements to clip
  const remove = []; // elements to drop from the clip
  let mode = "include";
  let busy = false;
  let hoverEl = null;

  const host = document.createElement("div");
  host.id = HOST_ID;
  host.style.cssText = "all: initial; position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      .box { position: fixed; pointer-events: none; box-sizing: border-box; border-radius: 2px; }
      #hover { border: 2px dashed #1a73e8; background: rgba(26,115,232,.08); }
      .inc { border: 2px solid #1a7f37; background: rgba(26,127,55,.12); }
      .rem { border: 2px solid #c62828; background: rgba(198,40,40,.14); }
      .bar { position: fixed; top: 16px; right: 16px; width: 280px; pointer-events: auto;
             font: 13px -apple-system, "Segoe UI", Arial, sans-serif; color: #222; background: #fff;
             border: 1px solid #ccc; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.2); padding: 10px 12px; }
      .title { font-weight: 600; margin-bottom: 6px; }
      .tabs { display: flex; gap: 6px; margin-bottom: 8px; }
      .tabs button { flex: 1; padding: 6px 4px; font: inherit; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; border: 1px solid #ccc; background: #fafafa; color: #222; }
      .tabs button.on.inc-t { background: #1a7f37; border-color: #1a7f37; color: #fff; }
      .tabs button.on.rem-t { background: #c62828; border-color: #c62828; color: #fff; }
      .hint { font-size: 12px; color: #555; margin-bottom: 8px; line-height: 1.45; }
      .count { font-size: 12px; margin-bottom: 8px; }
      .row { display: flex; gap: 6px; }
      .row button, .link { padding: 7px 6px; font: inherit; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; border: 1px solid #ccc; background: #fafafa; color: #222; }
      .row button { flex: 1; }
      #save { background: #1a73e8; border-color: #1a73e8; color: #fff; }
      #save:disabled { background: #999; border-color: #999; cursor: default; }
      #del { width: 100%; margin-top: 6px; color: #c62828; }
      .ok { color: #1a7f37; } .err { color: #c62828; }
    </style>
    <div id="boxes"></div>
    <div id="hover" class="box" hidden></div>
    <div class="bar" id="bar">
      <div class="title">🎯 이 사이트에서 클리핑할 영역 고르기</div>
      <div class="tabs">
        <button id="tInc" class="on inc-t">✅ 넣을 영역</button>
        <button id="tRem" class="rem-t">🗑 지울 영역</button>
      </div>
      <div class="hint" id="hint"></div>
      <div class="count" id="count"></div>
      <div class="row">
        <button id="undo">↩ 마지막 취소</button>
        <button id="save">💾 저장</button>
        <button id="cancel">✕ 닫기</button>
      </div>
      <button id="del" class="link" hidden>🗑 이 사이트 규칙 삭제</button>
    </div>`;
  const $ = (id) => root.getElementById(id);
  const boxesEl = $("boxes");
  const hoverBox = $("hover");
  const hintEl = $("hint");
  const countEl = $("count");
  const saveBtn = $("save");
  const delBtn = $("del");

  const normHost = (h) => String(h || "").trim().toLowerCase().replace(/^www\./, "");
  const here = normHost(location.hostname);

  function setHint(text, cls) {
    hintEl.textContent = text;
    hintEl.className = "hint " + (cls || "");
  }

  // ---- selector generation: short, stable, and matching exactly this element ----
  // Skip classes that look generated (hashes, framework prefixes) or that
  // reflect transient state, so the rule keeps matching after a redeploy.
  const BAD_STATE = /active|open|hover|select|focus|show|hidden|visible|loading|^is-|^has-/i;
  const BAD_HASH = /\d{3,}|^(css|sc|jsx|svelte)[-_]|^_|^[a-z]{1,2}[A-Z0-9][A-Za-z0-9_-]{5,}$/;
  const stable = (c) => c && c.length <= 30 && !BAD_STATE.test(c) && !BAD_HASH.test(c);
  function isUnique(sel, el) {
    try {
      const n = document.querySelectorAll(sel);
      return n.length === 1 && n[0] === el;
    } catch (e) {
      return false;
    }
  }
  function segment(el) {
    const tag = el.tagName.toLowerCase();
    const cls = Array.from(el.classList).filter(stable).slice(0, 3);
    return tag + cls.map((c) => "." + CSS.escape(c)).join("");
  }
  function nth(el) {
    const parent = el.parentElement;
    if (!parent) return el.tagName.toLowerCase();
    const same = Array.from(parent.children).filter((c) => c.tagName === el.tagName);
    const tag = el.tagName.toLowerCase();
    return same.length > 1 ? `${tag}:nth-of-type(${same.indexOf(el) + 1})` : tag;
  }
  function selectorFor(el) {
    if (el.id && isUnique("#" + CSS.escape(el.id), el)) return "#" + CSS.escape(el.id);
    // 1) classes only, walking up until the chain is unique
    const parts = [];
    for (let cur = el, depth = 0; cur && cur !== document.documentElement && depth < 6; cur = cur.parentElement, depth++) {
      if (cur !== el && cur.id && isUnique("#" + CSS.escape(cur.id), cur)) {
        parts.unshift("#" + CSS.escape(cur.id));
        const sel = parts.join(" > ");
        if (isUnique(sel, el)) return sel;
        break;
      }
      parts.unshift(segment(cur));
      const sel = parts.join(" > ");
      if (isUnique(sel, el)) return sel;
    }
    // 2) positional chain from the nearest unique-id ancestor (or <body>)
    const chain = [];
    let cur = el;
    while (cur && cur !== document.body && cur !== document.documentElement) {
      if (cur !== el && cur.id && isUnique("#" + CSS.escape(cur.id), cur)) {
        chain.unshift("#" + CSS.escape(cur.id));
        return chain.join(" > ");
      }
      chain.unshift(nth(cur));
      cur = cur.parentElement;
    }
    chain.unshift("body");
    return chain.join(" > ");
  }

  // ---- drawing ----
  function place(box, el) {
    const r = el.getBoundingClientRect();
    box.style.cssText = `left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px;`;
  }
  function renderBoxes() {
    boxesEl.innerHTML = "";
    [[include, "inc"], [remove, "rem"]].forEach(([list, cls]) => {
      list.forEach((el) => {
        const b = document.createElement("div");
        b.className = "box " + cls;
        b.dataset.k = cls;
        boxesEl.appendChild(b);
        place(b, el);
      });
    });
  }
  let raf = 0;
  function tick() {
    const boxes = boxesEl.children;
    let i = 0;
    for (const el of include) if (boxes[i]) place(boxes[i++], el);
    for (const el of remove) if (boxes[i]) place(boxes[i++], el);
    if (hoverEl && document.contains(hoverEl)) {
      hoverBox.hidden = false;
      place(hoverBox, hoverEl);
    } else hoverBox.hidden = true;
    raf = requestAnimationFrame(tick);
  }
  function refresh() {
    renderBoxes();
    countEl.textContent = `넣을 영역 ${include.length}개 · 지울 영역 ${remove.length}개`;
    saveBtn.disabled = busy || include.length === 0;
    if (!busy) {
      setHint(
        mode === "include"
          ? "페이지에서 클리핑할 부분(제목, 부제, 본문 등)을 하나씩 클릭하세요. 다시 클릭하면 해제됩니다."
          : "넣을 영역 안에 딸려오는 광고·공유 버튼 같은 것을 클릭하세요."
      );
    }
  }

  // ---- interaction ----
  function inToolbar(e) {
    return e.composedPath().includes(host);
  }
  function targetAt(e) {
    const el = e.target;
    if (!(el instanceof Element) || el === document.documentElement || el === document.body) return null;
    return el;
  }
  function onMove(e) {
    if (inToolbar(e)) {
      hoverEl = null;
      return;
    }
    hoverEl = targetAt(e);
  }
  function block(e) {
    if (inToolbar(e)) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
  }
  function onClick(e) {
    if (inToolbar(e)) return;
    block(e);
    const el = targetAt(e);
    if (!el || busy) return;
    const list = mode === "include" ? include : remove;
    const other = mode === "include" ? remove : include;
    const i = list.indexOf(el);
    if (i >= 0) list.splice(i, 1);
    else {
      const j = other.indexOf(el);
      if (j >= 0) other.splice(j, 1); // moving it to the other list
      list.push(el);
    }
    refresh();
  }
  function onKey(e) {
    if (e.key === "Escape" && !busy) close();
  }

  function setMode(m) {
    mode = m;
    $("tInc").classList.toggle("on", m === "include");
    $("tRem").classList.toggle("on", m === "remove");
    refresh();
  }

  function close() {
    cancelAnimationFrame(raf);
    ["mousemove"].forEach((t) => document.removeEventListener(t, onMove, true));
    ["click", "mousedown", "mouseup", "pointerdown", "pointerup", "auxclick", "dblclick", "contextmenu"].forEach((t) =>
      document.removeEventListener(t, t === "click" ? onClick : block, true)
    );
    document.removeEventListener("keydown", onKey, true);
    host.remove();
  }
  host.__jcpClose = close;

  function save() {
    if (busy || !include.length) return;
    busy = true;
    saveBtn.disabled = true;
    const rule = {
      host: here,
      content: include.map(selectorFor).join(", "),
      remove: remove.map(selectorFor).join(", "),
    };
    chrome.storage.local.get("siteRules", (data) => {
      const rules = Array.isArray(data.siteRules) ? data.siteRules.filter((r) => r && normHost(r.host) !== here) : [];
      rules.push(rule);
      chrome.storage.local.set({ siteRules: rules }, () => {
        busy = false;
        if (chrome.runtime.lastError) {
          setHint("저장 실패: " + chrome.runtime.lastError.message, "err");
          saveBtn.disabled = false;
          return;
        }
        setHint("저장했어요 ✓ 이제 이 사이트는 Article 모드에서 이 규칙으로 클리핑됩니다. 지우려면 이 도구를 다시 열어 '이 사이트 규칙 삭제'를 누르세요.", "ok");
        delBtn.hidden = false;
        saveBtn.disabled = false;
      });
    });
  }

  $("tInc").addEventListener("click", () => setMode("include"));
  $("tRem").addEventListener("click", () => setMode("remove"));
  $("undo").addEventListener("click", () => {
    const list = mode === "include" ? include : remove;
    list.pop();
    refresh();
  });
  $("cancel").addEventListener("click", () => !busy && close());
  saveBtn.addEventListener("click", save);
  delBtn.addEventListener("click", () => {
    chrome.storage.local.get("siteRules", (data) => {
      const rules = (Array.isArray(data.siteRules) ? data.siteRules : []).filter((r) => r && normHost(r.host) !== here);
      chrome.storage.local.set({ siteRules: rules }, () => {
        delBtn.hidden = true;
        setHint("이 사이트 규칙을 삭제했어요.", "ok");
      });
    });
  });

  document.addEventListener("mousemove", onMove, true);
  ["click", "mousedown", "mouseup", "pointerdown", "pointerup", "auxclick", "dblclick", "contextmenu"].forEach((t) =>
    document.addEventListener(t, t === "click" ? onClick : block, true)
  );
  document.addEventListener("keydown", onKey, true);
  (document.body || document.documentElement).appendChild(host);

  // An existing rule for this site can be deleted from here.
  chrome.storage.local.get("siteRules", (data) => {
    const has = Array.isArray(data.siteRules) && data.siteRules.some((r) => r && normHost(r.host) === here);
    delBtn.hidden = !has;
  });

  refresh();
  tick();
})();
