/**
 * PhishSentinel AI — Content Script
 * -------------------------------------
 * Renders an on-page banner when the background worker reports a
 * suspicious or phishing verdict for the current URL. This is the
 * "warns inline, before a click ever happens" feature from the project.
 */

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "PHISHSENTINEL_VERDICT") {
    renderBanner(message.verdict);
  }
});

function renderBanner(verdict) {
  if (document.getElementById("phishsentinel-banner")) return; // avoid duplicates

  const isPhishing = verdict.verdict === "phishing";
  const banner = document.createElement("div");
  banner.id = "phishsentinel-banner";
  banner.className = isPhishing ? "phishsentinel-banner phishsentinel-danger" : "phishsentinel-banner phishsentinel-warning";

  banner.innerHTML = `
    <div class="phishsentinel-content">
      <span class="phishsentinel-icon">${isPhishing ? "⛔" : "⚠"}</span>
      <div class="phishsentinel-text">
        <strong>${isPhishing ? "PhishSentinel AI: Likely Phishing Site" : "PhishSentinel AI: Proceed with Caution"}</strong>
        <p>${escapeHtml(verdict.explanation)}</p>
      </div>
      <div class="phishsentinel-actions">
        <button id="phishsentinel-dismiss">Dismiss</button>
        <button id="phishsentinel-wrong">This is wrong</button>
      </div>
    </div>
  `;

  document.documentElement.prepend(banner);

  document.getElementById("phishsentinel-dismiss").addEventListener("click", () => {
    banner.remove();
  });

  document.getElementById("phishsentinel-wrong").addEventListener("click", () => {
    chrome.runtime.sendMessage({
      type: "SUBMIT_FEEDBACK",
      payload: {
        verdict_id: verdict.verdict_id,
        is_correct: false,
        actual_label: "safe",
        source: "web",
      },
    });
    banner.querySelector(".phishsentinel-text").innerHTML = "<strong>Thanks — feedback recorded.</strong>";
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
