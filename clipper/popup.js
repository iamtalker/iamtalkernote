let mode = "article";
// Shared with the Obsidian fork: name the target app from the manifest.
const APP = /obsidian/i.test(chrome.runtime.getManifest().name) ? "Obsidian" : "Joplin";
const statusEl = document.getElementById("status");
const titleEl = document.getElementById("title");
const notebookEl = document.getElementById("notebook");
const tagsEl = document.getElementById("tags");
const clipBtn = document.getElementById("clip");

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = cls || "";
}

function setMode(m) {
  const btn = document.querySelector(`.modes button[data-mode="${m}"]`);
  if (!btn) return false;
  document.querySelectorAll(".modes button").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  mode = m;
  return true;
}

document.querySelectorAll(".modes button").forEach((btn) => {
  btn.addEventListener("click", () => {
    setMode(btn.dataset.mode);
    if (mode === "selection") startSelection();
  });
});

// Selection mode, "mode first" flow: if nothing is selected on the page yet,
// hand off to an in-page floating toolbar (the popup would close the moment
// the user clicks into the page to select) and close. If something is
// already selected, stay here and let Clip save it as before.
let tabTitle = "";
let pageUrl = "";
function startSelection(onHasSelection) {
  const title = titleEl.value.trim();
  chrome.runtime.sendMessage(
    {
      type: "startSelectionToolbar",
      parentId: notebookEl.value || undefined,
      tags: tagsEl.value.trim() || undefined,
      // Only override when edited; otherwise the page title at save time.
      title: title && title !== tabTitle ? title : undefined,
    },
    (res) => {
      if (!res || !res.ok) {
        setStatus((res && res.error) || "Unknown error", "err");
      } else if (res.hasSelection) {
        if (onHasSelection) onHasSelection();
        else setStatus("선택된 부분이 있어요 — Clip을 누르세요");
      } else {
        window.close();
      }
    }
  );
}

// Hands off to the in-page picker (picker.js) so the user can click the parts
// of this site to clip instead of writing selectors; the popup closes.
const pickBtn = document.getElementById("pickArea");
if (pickBtn) {
  pickBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "startPicker" }, (res) => {
      if (!res || !res.ok) setStatus((res && res.error) || "Unknown error", "err");
      else window.close();
    });
  });
}

document.getElementById("settingsLink").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

async function init() {
  document.getElementById("version").textContent = "v" + chrome.runtime.getManifest().version;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  tabTitle = tab.title || "";
  // SPA sites (YouTube playlists) change the page without a navigation, so
  // Chrome's tab.title can lag behind; the page's own document.title is live.
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.title,
    });
    if (result) tabTitle = result;
  } catch (e) {
    // restricted page: keep the tab title
  }
  titleEl.value = tabTitle;
  pageUrl = tab.url || "";

  // Defaults picked on the options page, so the popup opens ready to Clip.
  // Choosing a default mode here doesn't open the Selection toolbar by
  // itself — that only happens on an actual click (button or Clip).
  const { defaultMode, defaultFolderId } = await chrome.storage.local.get(["defaultMode", "defaultFolderId"]);
  if (defaultMode) setMode(defaultMode);

  chrome.runtime.sendMessage({ type: "listFolders" }, (res) => {
    notebookEl.innerHTML = "";
    if (!res || !res.ok) {
      notebookEl.innerHTML = '<option value="">(default notebook)</option>';
      if (res && res.error) setStatus(res.error, "err");
      return;
    }
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = res.defaultLabel || "(default notebook)";
    notebookEl.appendChild(opt0);
    res.folders
      .sort((a, b) => a.title.localeCompare(b.title))
      .forEach((f) => {
        const opt = document.createElement("option");
        opt.value = f.id;
        opt.textContent = f.title;
        notebookEl.appendChild(opt);
      });
    // Only if it still exists — a deleted notebook falls back to the default.
    if (defaultFolderId && res.folders.some((f) => f.id === defaultFolderId)) {
      notebookEl.value = defaultFolderId;
    }
  });
}

clipBtn.addEventListener("click", () => {
  // Selection as the default mode: with nothing selected yet, Clip opens
  // the in-page toolbar instead of failing with "No text is selected".
  if (mode === "selection") startSelection(clip);
  else clip();
});

function clip() {
  clipBtn.disabled = true;
  setStatus("Clipping…");
  chrome.runtime.sendMessage(
    {
      type: "clip",
      mode,
      parentId: notebookEl.value || undefined,
      tags: tagsEl.value.trim() || undefined,
      // YouTube clips build their own title from the player; only send the
      // box's text there when the user edited it.
      title:
        /^https?:\/\/(www\.|m\.|music\.)?youtube\.com\//.test(pageUrl) && titleEl.value.trim() === tabTitle
          ? undefined
          : titleEl.value.trim() || undefined,
    },
    (res) => {
      clipBtn.disabled = false;
      if (res && res.ok) {
        const via = res.preview && res.preview.via;
        const where = res.note && res.note.path ? " → " + res.note.path : "";
        setStatus("Saved to " + APP + " ✓" + where + (via ? " (" + via + ")" : ""), "ok");
      } else {
        setStatus((res && res.error) || "Unknown error", "err");
      }
    }
  );
}

init();
