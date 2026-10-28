// Joplin backend. Everything shared with the Obsidian version (injection,
// capture fallbacks, message routing) is in core.js.
importScripts("core.js");

async function getSettings() {
  const { joplinToken = "", joplinPort = "41184" } = await chrome.storage.local.get([
    "joplinToken",
    "joplinPort",
  ]);
  return { joplinToken, joplinPort };
}

function apiBase(port) {
  return `http://127.0.0.1:${port}`;
}

async function joplinFetch(path, options = {}) {
  const { joplinToken, joplinPort } = await getSettings();
  if (!joplinToken) {
    throw new Error("Joplin API token is not set. Open the extension options first.");
  }
  const sep = path.includes("?") ? "&" : "?";
  const url = `${apiBase(joplinPort)}${path}${sep}token=${encodeURIComponent(joplinToken)}`;
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).error || "";
    } catch (e) {}
    throw new Error(`Joplin API ${res.status}: ${detail || res.statusText}`);
  }
  return res.json();
}

async function testConnection() {
  const { joplinToken } = await getSettings();
  if (!joplinToken) return { ok: false, error: "No token set." };
  try {
    await joplinFetch("/folders?limit=1");
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function listFolders() {
  const all = [];
  let page = 1;
  while (true) {
    const data = await joplinFetch(`/folders?fields=id,title,parent_id&limit=100&page=${page}`);
    all.push(...data.items);
    if (!data.has_more) break;
    page++;
  }
  return all;
}

function buildNoteBody(clip) {
  const base = { source_url: clip.url };
  if (clip.mode === "full") {
    return { ...base, title: clip.title, body_html: clip.html, base_url: clip.url };
  }
  if (clip.mode === "bookmark") {
    return {
      ...base,
      title: clip.title,
      body: `${clip.description ? clip.description + "\n\n" : ""}[${clip.title}](${clip.url})`,
    };
  }
  // article / selection
  return { ...base, title: clip.title, body: clip.markdown };
}

async function createNote({ clip, parentId, tags, titleOverride }) {
  const payload = buildNoteBody(clip);
  if (titleOverride) payload.title = titleOverride;
  if (parentId) payload.parent_id = parentId;
  if (tags) payload.tags = tags;
  Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
  return joplinFetch("/notes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

globalThis.BACKEND = {
  testConnection,
  listFolders,
  saveClip: createNote,
};
