/**
 * PhishSentinel AI — Background Service Worker
 * -----------------------------------------------
 * On every completed top-level navigation: check the URL against the
 * backend, set the toolbar badge, and show an on-page banner for
 * suspicious/phishing pages.
 *
 * Settings (API base + key) live in chrome.storage.sync and are edited on
 * the extension's Options page. Fails OPEN: if the backend is down the
 * user's browsing is never blocked.
 */

const DEFAULTS = { apiBase: "http://localhost:8000", apiKey: "" };
const CACHE_TTL_MS = 5 * 60 * 1000;
const CACHE_MAX = 500;
const verdictByTab = {};          // tabId -> verdict (session)
const urlCache = new Map();       // url -> { at, verdict }

async function getSettings() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  return { apiBase: String(s.apiBase || DEFAULTS.apiBase).replace(/\/+$/, ""), apiKey: s.apiKey || "" };
}

function apiHeaders(apiKey) {
  return { "Content-Type": "application/json", ...(apiKey ? { "X-API-Key": apiKey } : {}) };
}

// Never send private/intranet/local addresses to the backend: it leaks
// internal hostnames and the verdict is meaningless for them.
function isCheckable(rawUrl) {
  let u;
  try { u = new URL(rawUrl); } catch { return false; }
  if (u.protocol !== "http:" && u.protocol !== "https:") return false;
  const h = u.hostname.toLowerCase();
  if (h === "localhost" || h.endsWith(".local") || h.endsWith(".internal") || h.endsWith(".lan")) return false;
  if (!h.includes(".") && !h.includes(":")) return false;                       // bare intranet name
  if (/^(10\.|127\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h)) return false;
  if (h === "[::1]" || h.startsWith("[fc") || h.startsWith("[fd") || h.startsWith("[fe80")) return false;
  return true;
}

function cacheGet(url) {
  const hit = urlCache.get(url);
  if (!hit) return null;
  if (Date.now() - hit.at > CACHE_TTL_MS) { urlCache.delete(url); return null; }
  return hit.verdict;
}

function cacheSet(url, verdict) {
  urlCache.set(url, { at: Date.now(), verdict });
  if (urlCache.size > CACHE_MAX) urlCache.delete(urlCache.keys().next().value);   // oldest first
}

async function analyzeUrl(url) {
  const cached = cacheGet(url);
  if (cached) return cached;
  try {
    const { apiBase, apiKey } = await getSettings();
    const res = await fetch(`${apiBase}/analyze/url`, {
      method: "POST",
      headers: apiHeaders(apiKey),
      body: JSON.stringify({ url }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    const verdict = await res.json();
    cacheSet(url, verdict);
    return verdict;
  } catch (err) {
    console.warn("PhishSentinel: analysis failed, failing open", err);
    return null;
  }
}

function paintBadge(tabId, verdict) {
  const v = verdict?.verdict;
  chrome.action.setBadgeText({ tabId, text: !v || v === "safe" ? "" : v === "suspicious" ? "!" : "X" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: v === "phishing" ? "#E14B4B" : v === "suspicious" ? "#D9A441" : "#0E8F6C" });
}

chrome.webNavigation.onCompleted.addListener(async (details) => {
  if (details.frameId !== 0) return;                 // top-level frame only
  if (!isCheckable(details.url)) {
    delete verdictByTab[details.tabId];
    paintBadge(details.tabId, null);
    return;
  }
  const verdict = await analyzeUrl(details.url);
  if (!verdict) return;

  verdictByTab[details.tabId] = verdict;
  paintBadge(details.tabId, verdict);
  if (verdict.verdict !== "safe") {
    chrome.tabs.sendMessage(details.tabId, { type: "PHISHSENTINEL_VERDICT", verdict }).catch(() => {});
  }
});

chrome.tabs.onRemoved.addListener((tabId) => { delete verdictByTab[tabId]; });

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_VERDICT") {
    sendResponse(verdictByTab[message.tabId] || null);
    return;
  }
  if (message.type === "SUBMIT_FEEDBACK") {
    (async () => {
      try {
        const { apiBase, apiKey } = await getSettings();
        const res = await fetch(`${apiBase}/feedback`, {
          method: "POST",
          headers: apiHeaders(apiKey),
          body: JSON.stringify({ ...message.payload, source: "extension" }),
        });
        const data = await res.json().catch(() => ({}));
        sendResponse(res.ok ? { ok: true, data } : { ok: false, error: data.detail || `HTTP ${res.status}` });
      } catch (err) {
        sendResponse({ ok: false, error: String(err) });
      }
    })();
    return true;                                      // async response
  }
});

// First install: open the options page so the user can enter their server.
chrome.runtime.onInstalled.addListener((d) => {
  if (d.reason === "install") chrome.runtime.openOptionsPage();
});
