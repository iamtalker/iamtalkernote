// Shared between Joplin Clipper Plus and Obsidian Clipper Plus — keep this
// file backend-agnostic. It holds page injection, every capture fallback
// (tab screenshot, background fetch) and the message router; the
// note-saving side lives in background.js, which loads this file with
// importScripts() and defines globalThis.BACKEND:
//   testConnection() -> { ok, error? }
//   listFolders()    -> [{ id, title }]   (Joplin notebooks / vault folders)
//   defaultFolderLabel() -> string        (optional; popup's first option)
//   saveClip({ clip, parentId, tags, titleOverride }) -> saved note info

const LIB_FILES = ["lib/Readability.js", "lib/turndown.js", "lib/turndown-plugin-gfm.js", "content.js"];

async function arrayBufferToBase64(buf) {
  const bytes = new Uint8Array(buf);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

// chrome.tabs.captureVisibleTab enforces its own quota (Chrome allows at
// most ~2 calls/second per profile) — a post with several images in a row
// that all need the screenshot fallback (see SCREENSHOT_FALLBACK_HOSTS in
// content.js) can fire captures faster than that. When the quota is hit the
// call just throws, which the caller in content.js catches and silently
// gives up on that one image — the site's original (CORS-blocked, so
// unloadable once clipped) URL is left in place, which is what actually
// looked like "some images go missing" from a multi-image post. Throttle
// every call to at least MIN_CAPTURE_INTERVAL_MS apart, and retry once if
// the quota error slips through anyway (e.g. another tab captured around
// the same time).
const MIN_CAPTURE_INTERVAL_MS = 550;
let lastCaptureAt = 0;

async function throttleCapture() {
  const wait = lastCaptureAt + MIN_CAPTURE_INTERVAL_MS - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastCaptureAt = Date.now();
}

async function captureVisibleTabThrottled(windowId) {
  await throttleCapture();
  try {
    return await chrome.tabs.captureVisibleTab(windowId, { format: "jpeg", quality: 90 });
  } catch (e) {
    if (!/MAX_CAPTURE_VISIBLE_TAB_CALLS_PER_SECOND/.test(e.message || "")) throw e;
    await new Promise((r) => setTimeout(r, MIN_CAPTURE_INTERVAL_MS));
    lastCaptureAt = Date.now();
    return chrome.tabs.captureVisibleTab(windowId, { format: "jpeg", quality: 90 });
  }
}

// Fallback for images fetch() can't read due to CORS (see content.js). We
// screenshot the whole visible tab, then crop to just the image's rect in an
// OffscreenCanvas — screenshot pixels aren't subject to the CORS check.
// Captured/output as JPEG rather than PNG: a very tall image can mean
// dozens of these in one clip (see jcpCaptureImageViaTab's segmented
// capture), and PNG's slower encode + much bigger base64 payload was a real
// contributor to clips timing out on those.
async function captureImageRect(tabId, rect) {
  const tab = await chrome.tabs.get(tabId);
  const shotDataUrl = await captureVisibleTabThrottled(tab.windowId);
  const shotBlob = await (await fetch(shotDataUrl)).blob();
  const bitmap = await createImageBitmap(shotBlob);
  const dpr = rect.dpr || 1;
  const sx = Math.max(0, Math.round(rect.x * dpr));
  const sy = Math.max(0, Math.round(rect.y * dpr));
  const sw = Math.max(1, Math.min(bitmap.width - sx, Math.round(rect.width * dpr)));
  const sh = Math.max(1, Math.min(bitmap.height - sy, Math.round(rect.height * dpr)));
  const canvas = new OffscreenCanvas(sw, sh);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, sx, sy, sw, sh, 0, 0, sw, sh);
  const outBlob = await canvas.convertToBlob({ type: "image/jpeg", quality: 0.9 });
  const base64 = await arrayBufferToBase64(await outBlob.arrayBuffer());
  return `data:image/jpeg;base64,${base64}`;
}

// Safety net for the whole clip operation: content.js has its own per-image
// fetch timeout now, but this guards against any other stuck step (script
// injection, a hung message round-trip, something not yet anticipated) so
// the popup always gets a response instead of sitting on "Clipping…" forever.
function withTimeout(promise, ms, message) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

async function runClipOnTab(tabId, mode) {
  await chrome.scripting.executeScript({ target: { tabId }, files: LIB_FILES });
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: (m) => window.__jcpRunClip(m),
    args: [mode],
  });
  return result;
}

async function clipAndSave(tabId, mode, opts) {
  const clip = await withTimeout(
    runClipOnTab(tabId, mode),
    120000,
    "클리핑이 2분 안에 끝나지 않았어요. 이미지가 너무 크거나 사이트가 느릴 수 있어요."
  );
  if (clip.error) return { ok: false, error: clip.error };
  const note = await BACKEND.saveClip({
    clip,
    parentId: opts.parentId,
    tags: opts.tags,
    titleOverride: opts.title,
  });
  return { ok: true, note, preview: clip };
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "testConnection") {
        sendResponse(await BACKEND.testConnection());
      } else if (msg.type === "listFolders") {
        sendResponse({
          ok: true,
          folders: await BACKEND.listFolders(),
          defaultLabel: BACKEND.defaultFolderLabel ? await BACKEND.defaultFolderLabel() : undefined,
        });
      } else if (msg.type === "clip") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        sendResponse(await clipAndSave(tab.id, msg.mode, msg));
      } else if (msg.type === "startSelectionToolbar") {
        // Popup asks: does the page already have a selection? If yes, the
        // popup clips it right away as before; if no, show the in-page
        // toolbar so the user can select first and save from there.
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const [{ result: hasSelection }] = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => {
            const s = window.getSelection();
            return !!(s && s.rangeCount && !s.isCollapsed);
          },
        });
        if (hasSelection) {
          sendResponse({ ok: true, hasSelection: true });
          return;
        }
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (o) => {
            window.__jcpToolbarOpts = o;
          },
          args: [{ parentId: msg.parentId, tags: msg.tags, title: msg.title }],
        });
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["toolbar.js"] });
        sendResponse({ ok: true, hasSelection: false });
      } else if (msg.type === "startPicker") {
        // Popup asks for the in-page "pick the article area" tool (picker.js).
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["picker.js"] });
        sendResponse({ ok: true });
      } else if (msg.type === "clipSelectionFromToolbar") {
        sendResponse(await clipAndSave(sender.tab.id, "selection", msg));
      } else if (msg.type === "captureImageRect") {
        const dataUrl = await captureImageRect(sender.tab.id, msg.rect);
        sendResponse({ ok: true, dataUrl });
      } else if (msg.type === "fetchImageBytes") {
        // Extension contexts (unlike content scripts under MV3) get CORS
        // bypass for hosts covered by host_permissions, so this can pull
        // the original file from CDNs that block fetch() from the page.
        // A post's images are all requested at once, which some image hosts
        // (arca.live) answer with 429 Too Many Requests — wait and retry.
        let res;
        for (let attempt = 0; ; attempt++) {
          res = await fetch(msg.url, { credentials: "include" });
          if (res.status !== 429 || attempt >= 3) break;
          await new Promise((r) => setTimeout(r, 1000 * (attempt + 1) + Math.random() * 500));
        }
        if (!res.ok) throw new Error(`HTTP ${res.status} fetching image`);
        const blob = await res.blob();
        if (!blob.size) throw new Error("empty image response");
        if (blob.size > 40 * 1024 * 1024) throw new Error("image larger than 40MB");
        const b64 = await arrayBufferToBase64(await blob.arrayBuffer());
        sendResponse({ ok: true, dataUrl: `data:${blob.type || "image/jpeg"};base64,${b64}`, size: blob.size });
      } else if (msg.type === "getZoom") {
        const zoom = await chrome.tabs.getZoom(sender.tab.id);
        sendResponse({ ok: true, zoom });
      } else if (msg.type === "setZoom") {
        await chrome.tabs.setZoom(sender.tab.id, msg.factor);
        sendResponse({ ok: true });
      } else if (msg.type === "preview") {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        const clip = await runClipOnTab(tab.id, msg.mode);
        sendResponse({ ok: !clip.error, clip, error: clip.error });
      }
    } catch (e) {
      sendResponse({ ok: false, error: e.message });
    }
  })();
  return true; // async response
});
