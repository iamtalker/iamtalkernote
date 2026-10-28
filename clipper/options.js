const portEl = document.getElementById("port");
const tokenEl = document.getElementById("token");
const modeEl = document.getElementById("defMode");
const notebookEl = document.getElementById("defNotebook");
const statusEl = document.getElementById("status");

function setStatus(text, ok) {
  statusEl.textContent = text;
  statusEl.className = ok === undefined ? "" : ok ? "ok" : "err";
}

// Fills the notebook picker from Joplin, keeping `selected` chosen. If the
// saved notebook isn't in the list (Joplin closed, or it was deleted) it's
// kept as an extra option so saving the page doesn't silently drop it.
function loadNotebooks(selected) {
  chrome.runtime.sendMessage({ type: "listFolders" }, (res) => {
    notebookEl.innerHTML = '<option value="">(조플린 기본 노트북)</option>';
    const folders = res && res.ok ? res.folders : [];
    folders
      .sort((a, b) => a.title.localeCompare(b.title))
      .forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.id;
        opt.textContent = f.title;
        notebookEl.appendChild(opt);
      });
    if (selected && !folders.some((f) => f.id === selected)) {
      const opt = document.createElement("option");
      opt.value = selected;
      opt.textContent = "(저장된 노트북 — 조플린에 연결할 수 없음)";
      notebookEl.appendChild(opt);
    }
    notebookEl.value = selected || "";
  });
}

chrome.storage.local.get(["joplinToken", "joplinPort", "defaultMode", "defaultFolderId"], (data) => {
  tokenEl.value = data.joplinToken || "";
  portEl.value = data.joplinPort || "41184";
  modeEl.value = data.defaultMode || "article";
  loadNotebooks(data.defaultFolderId || "");
});

function collect() {
  return {
    joplinToken: tokenEl.value.trim(),
    joplinPort: portEl.value.trim() || "41184",
    defaultMode: modeEl.value,
    defaultFolderId: notebookEl.value,
  };
}

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.local.set(collect(), () => setStatus("저장했습니다.", true));
});

document.getElementById("test").addEventListener("click", async () => {
  await chrome.storage.local.set(collect());
  setStatus("연결 확인 중…");
  chrome.runtime.sendMessage({ type: "testConnection" }, (res) => {
    if (res && res.ok) {
      setStatus("조플린에 연결되었습니다 ✓", true);
      loadNotebooks(notebookEl.value); // token may have just been entered
    } else setStatus("실패: " + (res ? res.error : "응답 없음"), false);
  });
});
