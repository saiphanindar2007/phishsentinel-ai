const $ = (id) => document.getElementById(id);
const msg = (text, ok) => { $("msg").textContent = text; $("msg").className = ok ? "ok" : "bad"; };

chrome.storage.sync.get({ apiBase: "http://localhost:8000", apiKey: "" }).then((s) => {
  $("base").value = s.apiBase;
  $("key").value = s.apiKey;
});

$("save").addEventListener("click", async () => {
  const apiBase = $("base").value.trim().replace(/\/+$/, "");
  const apiKey = $("key").value.trim();
  try {
    const u = new URL(apiBase);
    if (u.protocol !== "http:" && u.protocol !== "https:") throw new Error();
  } catch { return msg("Enter a valid http(s) URL.", false); }
  await chrome.storage.sync.set({ apiBase, apiKey });
  try {
    const res = await fetch(`${apiBase}/health/ready`, { signal: AbortSignal.timeout(6000) });
    if (!res.ok) return msg(`Saved, but server reports not ready (HTTP ${res.status}).`, false);
    if (apiKey) {                                     // verify the key against an authenticated route
      const t = await fetch(`${apiBase}/analyze/stats`, { headers: { "X-API-Key": apiKey }, signal: AbortSignal.timeout(6000) });
      if (!t.ok) return msg(`Saved, but the API key was rejected (HTTP ${t.status}).`, false);
    }
    msg("Saved. Server reachable.", true);
  } catch { msg("Saved, but the server is unreachable.", false); }
});
