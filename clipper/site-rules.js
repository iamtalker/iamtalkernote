// Settings-page UI for user-defined site rules (shared with the Obsidian fork;
// the host options.html just needs the #siteRules container).
// Rules live in chrome.storage.local "siteRules": [{host, content, remove}],
// read by content.js (jcpUserSiteRule) at clip time and created by picker.js
// (the "pick the area by clicking" tool). The page has a single "edit rules"
// button that opens a text box holding the rules as text (the header comments
// explain the format); saving REPLACES the stored rules with the text, so
// deleting a rule = deleting its lines. Export/import of the same text as a
// file stays below the box for backups.
//
// File format:
//   # comment
//   사이트 주소: www.example.com
//   추가할 것: h1.title, #articleBody
//   삭제할 것: .ad, .share
// (Also accepted: "[host]" headers and content=/remove= keys.)
(function () {
  const root = document.getElementById("siteRules");
  if (!root) return;

  root.innerHTML = `
    <button type="button" id="editRules" style="margin-top:6px">✏️ 규칙 편집</button>
    <div id="editor" hidden>
      <textarea id="rulesText" spellcheck="false" wrap="off"
        style="width:100%;box-sizing:border-box;height:340px;margin-top:10px;padding:8px;font:12px/1.5 Consolas,'Courier New',monospace;border:1px solid #ccc;border-radius:4px;white-space:pre;"></textarea>
      <div>
        <button type="button" id="saveText">저장</button>
        <button type="button" id="closeText" class="secondary">닫기</button>
        <button type="button" id="exportRules" class="secondary">⬇ 파일로 내보내기</button>
        <button type="button" id="importRules" class="secondary">⬆ 파일에서 불러오기</button>
        <input type="file" id="importFile" accept=".txt,text/plain" hidden />
      </div>
    </div>
    <div id="rulesStatus" class="hint"></div>
  `;

  const statusEl = document.getElementById("rulesStatus");
  const fileEl = document.getElementById("importFile");
  const editorEl = document.getElementById("editor");
  const textEl = document.getElementById("rulesText");

  const normHost = (h) =>
    String(h || "")
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/\/.*$/, "");

  function setStatus(text, ok) {
    statusEl.textContent = text;
    statusEl.style.color = ok ? "#1a7f37" : ok === false ? "#c62828" : "";
  }

  function validSelector(sel) {
    try {
      document.createDocumentFragment().querySelector(sel);
      return true;
    } catch (e) {
      return false;
    }
  }

  function getRules(cb) {
    chrome.storage.local.get("siteRules", (data) => {
      cb(Array.isArray(data.siteRules) ? data.siteRules.filter((r) => r && r.host && r.content) : []);
    });
  }

  // ---- text format ----
  const HEADER = [
    "# ============================================================",
    "#  클리퍼 사이트 규칙",
    "# ============================================================",
    "#",
    "# 사이트마다 \"기사에서 어느 부분을 가져올지\"를 적어 둔 파일입니다.",
    "#",
    "# [규칙 만드는 법]",
    "#   잘 안 되는 기사 페이지에서 확장 아이콘 → \"이 사이트 영역 직접 고르기\"를",
    "#   누르고, 넣을 부분을 클릭한 뒤 저장하면 규칙이 만들어집니다.",
    "#   (이 파일을 직접 고쳐서 만들 수도 있습니다.)",
    "#",
    "# [항목 설명]",
    "#   사이트 주소 : 규칙을 적용할 사이트 (예: www.example.com)",
    "#   추가할 것   : 클리핑에 넣을 영역의 CSS 셀렉터. 여러 개는 쉼표(,)로 구분.",
    "#                 제목·본문처럼 빠진 부분은 여기에 이어 붙이면 추가됩니다.",
    "#   삭제할 것   : 넣은 영역 안에서 지울 영역(광고, 공유 버튼 등). 없으면 비워 둡니다.",
    "#",
    "# [고치는 법]",
    "#   - 규칙 수정 : 해당 줄을 고친 뒤 설정 화면에서 \"불러오기\"",
    "#   - 규칙 삭제 : 그 사이트의 3줄(사이트 주소/추가할 것/삭제할 것)을 지운 뒤 \"불러오기\"",
    "#   - 규칙 추가 : 아래 형식대로 3줄을 새로 적은 뒤 \"불러오기\"",
    "#   ※ 불러오기는 현재 저장된 규칙을 이 파일의 내용으로 통째로 바꿉니다.",
    "#     (파일에 없는 사이트의 규칙은 삭제됩니다.)",
    "#   ※ #으로 시작하는 줄은 설명이므로 무시됩니다.",
    "#",
    "# [예시]",
    "#   사이트 주소: www.example.com",
    "#   추가할 것: h1.title, #articleBody",
    "#   삭제할 것: .ad, .share-buttons",
    "# ============================================================",
    "",
  ];

  function serialize(rules) {
    const lines = HEADER.slice();
    if (!rules.length) lines.push("# (저장된 규칙이 없습니다)", "");
    rules.forEach((r) => {
      lines.push(`사이트 주소: ${r.host}`, `추가할 것: ${r.content}`, `삭제할 것: ${r.remove || ""}`, "");
    });
    return lines.join("\n");
  }

  const KEYS = {
    // Keys are compared without spaces, so "추가할것" and "추가할 것" both work.
    사이트주소: "host",
    사이트: "host",
    host: "host",
    site: "host",
    추가할것: "content",
    추가: "content",
    content: "content",
    삭제할것: "remove",
    삭제: "remove",
    remove: "remove",
  };

  // Returns { rules, errors }.
  function parse(text) {
    const rules = [];
    const errors = [];
    let cur = null;
    const flush = () => {
      if (!cur) return;
      if (!cur.content) errors.push(`${cur.host}: "추가할 것"이 비어 있어 건너뜀`);
      else if (!validSelector(cur.content)) errors.push(`${cur.host}: "추가할 것"의 셀렉터가 올바르지 않아 건너뜀`);
      else if (cur.remove && !validSelector(cur.remove)) errors.push(`${cur.host}: "삭제할 것"의 셀렉터가 올바르지 않아 건너뜀`);
      else rules.push({ host: cur.host, content: cur.content, remove: cur.remove || "" });
      cur = null;
    };
    const startRule = (hostRaw, lineNo) => {
      flush();
      const host = normHost(hostRaw);
      if (host) cur = { host, content: "", remove: "" };
      else errors.push(`${lineNo}번째 줄: 사이트 주소가 비어 있어 건너뜀`);
    };
    text
      .replace(/^﻿/, "")
      .split(/\r?\n/)
      .forEach((raw, i) => {
        const line = raw.trim();
        if (!line || line.startsWith("#")) return;
        const h = line.match(/^\[(.+)\]$/);
        if (h) return startRule(h[1], i + 1);
        const kv = line.match(/^([^:=]+?)\s*[:=]\s*(.*)$/);
        const key = kv && KEYS[kv[1].replace(/\s+/g, "").toLowerCase()];
        if (!key) return errors.push(`${i + 1}번째 줄을 이해하지 못해 건너뜀: ${line.slice(0, 40)}`);
        if (key === "host") return startRule(kv[2], i + 1);
        if (cur) cur[key] = kv[2].trim();
        else errors.push(`${i + 1}번째 줄: 사이트 주소보다 앞에 있어 건너뜀`);
      });
    flush();
    // Same site twice: the later block wins.
    const byHost = new Map();
    rules.forEach((r) => byHost.set(r.host, r));
    return { rules: Array.from(byHost.values()), errors };
  }

  // ---- buttons ----
  document.getElementById("exportRules").addEventListener("click", () => {
    getRules((rules) => {
      // CRLF so the exported file opens properly in Notepad.
      const blob = new Blob([serialize(rules).replace(/\n/g, "\r\n")], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "clipper-site-rules.txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      setStatus(`규칙 ${rules.length}개를 clipper-site-rules.txt로 내보냈습니다.`, true);
    });
  });

  // Replaces the stored rules with the rules described by `text` (the editor
  // box or an imported file). Rules missing from the text are deleted, after
  // a confirmation that lists them.
  function applyText(text, verb, then) {
    const { rules: incoming, errors } = parse(text);
    const hasContent = text.split(/\r?\n/).some((l) => l.trim() && !l.trim().startsWith("#"));
    if (!incoming.length && hasContent) {
      return setStatus(`적용할 규칙이 없습니다. ${errors[0] || ""}`, false);
    }
    getRules((cur) => {
      const keep = new Set(incoming.map((r) => r.host));
      const dropped = cur.filter((r) => !keep.has(normHost(r.host)));
      if (
        dropped.length &&
        !confirm(`목록에 없는 사이트 규칙 ${dropped.length}개가 삭제됩니다. 계속할까요?\n\n` + dropped.map((r) => r.host).join("\n"))
      ) {
        return setStatus(`${verb}를 취소했습니다.`);
      }
      chrome.storage.local.set({ siteRules: incoming }, () => {
        setStatus(
          `규칙 ${incoming.length}개를 ${verb === "저장" ? "저장했습니다" : "불러왔습니다"}.` +
            (dropped.length ? ` (삭제 ${dropped.length}개)` : "") +
            (errors.length ? ` — 건너뜀 ${errors.length}건: ${errors[0]}` : ""),
          true
        );
        if (then) then();
      });
    });
  }

  // On a wide window the settings column is narrow and the right side is
  // empty, so the editor fills that space (full height); on a narrow window
  // it opens inline below the button instead.
  function layoutEditor() {
    if (editorEl.hidden) return;
    if (window.innerWidth >= 900) {
      editorEl.style.cssText =
        "position:fixed;top:16px;bottom:16px;left:500px;right:16px;display:flex;flex-direction:column;background:#fff;z-index:5;";
      textEl.style.height = "auto";
      textEl.style.flex = "1";
      textEl.style.marginTop = "0";
    } else {
      editorEl.style.cssText = "";
      textEl.style.flex = "";
      textEl.style.height = "340px";
      textEl.style.marginTop = "10px";
    }
  }
  window.addEventListener("resize", layoutEditor);

  document.getElementById("editRules").addEventListener("click", () => {
    getRules((rules) => {
      textEl.value = serialize(rules);
      editorEl.hidden = false;
      layoutEditor();
      setStatus("");
      textEl.focus();
      textEl.scrollTop = textEl.scrollHeight; // rules sit below the explanation
    });
  });
  document.getElementById("saveText").addEventListener("click", () => applyText(textEl.value, "저장"));
  document.getElementById("closeText").addEventListener("click", () => {
    editorEl.hidden = true;
    editorEl.style.cssText = "";
    setStatus("");
  });

  document.getElementById("importRules").addEventListener("click", () => fileEl.click());
  fileEl.addEventListener("change", () => {
    const file = fileEl.files && fileEl.files[0];
    if (!file) return;
    file.text().then((text) => {
      fileEl.value = "";
      applyText(text, "불러오기", () => getRules((rules) => (textEl.value = serialize(rules))));
    });
  });
})();
