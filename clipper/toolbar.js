// Floating toolbar for Selection mode: "pick the mode first, then select,
// then save". The popup can't do this itself — it closes as soon as the user
// clicks into the page to make a selection — so the popup injects this into
// the page instead and closes. Saving still goes through background.js (the
// page's CSP would block calling the Joplin/Obsidian API from here).
//
// Rendered inside a closed shadow root so the page's CSS can't restyle it,
// and every mousedown on it is preventDefault'ed so clicking a button doesn't
// collapse the user's selection before it's read.
//
// Re-injection safe: a second injection just refreshes the saved options on
// the existing toolbar instead of adding another one.
(function () {
  const HOST_ID = "__jcp-selection-toolbar";
  const opts = window.__jcpToolbarOpts || {};

  const existing = document.getElementById(HOST_ID);
  if (existing && existing.__jcpSetOpts) {
    existing.__jcpSetOpts(opts);
    return;
  }

  let current = opts;
  const APP = /obsidian/i.test(chrome.runtime.getManifest().name) ? "Obsidian" : "Joplin";
  const host = document.createElement("div");
  host.id = HOST_ID;
  host.style.cssText = "all: initial; position: fixed; top: 16px; right: 16px; z-index: 2147483647;";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      .bar { font: 13px -apple-system, "Segoe UI", Arial, sans-serif; color: #222; background: #fff;
             border: 1px solid #ccc; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.18);
             padding: 10px 12px; width: 240px; }
      .title { font-weight: 600; margin-bottom: 6px; }
      .hint { font-size: 12px; color: #555; margin-bottom: 8px; min-height: 16px; }
      .row { display: flex; gap: 6px; }
      button { flex: 1; padding: 7px 6px; font-family: inherit; font-size: 12px; font-weight: 600; border-radius: 6px; cursor: pointer; border: 1px solid #ccc; background: #fafafa; color: #222; }
      #save { background: #1a7f37; border-color: #1a7f37; color: #fff; }
      #save:disabled { background: #999; border-color: #999; cursor: default; }
      .ok { color: #1a7f37; } .err { color: #c62828; }
    </style>
    <div class="bar">
      <div class="title">📎 ${APP} — Selection</div>
      <div class="hint" id="hint"></div>
      <div class="row">
        <button id="save">💾 Save</button>
        <button id="cancel">✕ Cancel</button>
      </div>
    </div>`;
  const hintEl = root.getElementById("hint");
  const saveBtn = root.getElementById("save");
  const cancelBtn = root.getElementById("cancel");
  let busy = false;

  function setHint(text, cls) {
    hintEl.textContent = text;
    hintEl.className = "hint " + (cls || "");
  }

  function selectedLength() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return 0;
    return sel.toString().trim().length || 1; // image-only selections have no text
  }

  function refresh() {
    if (busy) return;
    const n = selectedLength();
    saveBtn.disabled = n === 0;
    setHint(n ? `${n}자 선택됨 — Save를 누르세요` : "저장할 부분을 드래그해서 선택하세요");
  }

  function close() {
    document.removeEventListener("selectionchange", refresh);
    document.removeEventListener("keydown", onKey, true);
    host.remove();
  }

  function onKey(e) {
    if (e.key === "Escape" && !busy) close();
  }

  // Keep clicks on the toolbar from clearing the page selection.
  root.addEventListener("mousedown", (e) => e.preventDefault());
  cancelBtn.addEventListener("click", () => !busy && close());
  saveBtn.addEventListener("click", () => {
    if (busy || !selectedLength()) return;
    busy = true;
    saveBtn.disabled = true;
    setHint("저장 중…");
    chrome.runtime.sendMessage({ type: "clipSelectionFromToolbar", ...current }, (res) => {
      busy = false;
      if (chrome.runtime.lastError) {
        setHint(chrome.runtime.lastError.message, "err");
        saveBtn.disabled = false;
        return;
      }
      if (res && res.ok) {
        setHint(APP + "에 저장했어요 ✓", "ok");
        setTimeout(close, 1500);
      } else {
        setHint((res && res.error) || "Unknown error", "err");
        saveBtn.disabled = false;
      }
    });
  });

  host.__jcpSetOpts = (o) => {
    current = o || {};
    refresh();
  };
  document.addEventListener("selectionchange", refresh);
  document.addEventListener("keydown", onKey, true);
  (document.body || document.documentElement).appendChild(host);
  refresh();
})();
