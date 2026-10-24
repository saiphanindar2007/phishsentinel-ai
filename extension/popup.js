/**
 * PhishSentinel AI — Popup Script
 * ------------------------------------
 * Fetches the cached verdict for the active tab from the background
 * worker and renders it, with feedback buttons wired to /feedback.
 */

const main = document.getElementById("main");
const statusDot = document.getElementById("statusDot");

const VERDICT_COLORS = { safe: "#0E8F6C", suspicious: "#BA7517", phishing: "#E14B4B" };

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  const tabId = tabs[0]?.id;
  if (!tabId) return renderEmpty();

  chrome.runtime.sendMessage({ type: "GET_VERDICT", tabId }, (verdict) => {
    if (!verdict) return renderEmpty();
    render(verdict);
  });
});

function renderEmpty() {
  main.innerHTML = `<div class="empty-state">No verdict yet for this tab.<br/>Navigate to a page to see PhishSentinel AI's analysis.</div>`;
}

function render(verdict) {
  statusDot.style.background = VERDICT_COLORS[verdict.verdict] || "#7C90AC";

  main.innerHTML = `
    <span class="verdict-badge ${verdict.verdict}">${verdict.verdict}</span>
    <div class="confidence">${Math.round(verdict.confidence * 100)}%</div>
    <div class="explanation">${escapeHtml(verdict.explanation)}</div>
    <div class="breakdown">
      <div class="breakdown-item"><div class="label">URL</div><div class="value">${Math.round(verdict.breakdown.url_score * 100)}%</div></div>
      <div class="breakdown-item"><div class="label">Content</div><div class="value">${Math.round(verdict.breakdown.nlp_score * 100)}%</div></div>
      <div class="breakdown-item"><div class="label">Visual</div><div class="value">${Math.round(verdict.breakdown.visual_score * 100)}%</div></div>
      <div class="breakdown-item"><div class="label">Sender</div><div class="value">${Math.round(verdict.breakdown.reputation_score * 100)}%</div></div>
    </div>
    <div class="feedback-row">
      <button id="btnCorrect">✓ Correct</button>
      <button id="btnWrong">✗ Wrong</button>
    </div>
  `;

  document.getElementById("btnCorrect").addEventListener("click", () => sendFeedback(verdict, true));
  document.getElementById("btnWrong").addEventListener("click", () => sendFeedback(verdict, false));
}

function sendFeedback(verdict, isCorrect) {
  const actualLabel = isCorrect ? verdict.verdict : verdict.verdict === "safe" ? "phishing" : "safe";
  chrome.runtime.sendMessage(
    {
      type: "SUBMIT_FEEDBACK",
      payload: { verdict_id: verdict.verdict_id, is_correct: isCorrect, actual_label: actualLabel, source: "web" },
    },
    () => {
      main.innerHTML = `<div class="empty-state">Thanks — feedback recorded.</div>`;
    }
  );
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
