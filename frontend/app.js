/* ═══════════════════════════════════════════════════════
   Legal Brief Analyzer — Frontend Logic
   ═══════════════════════════════════════════════════════ */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const API = (window.BRIEFAI_API || '').replace(/\/+$/, '');

// ─── Theme ───
(function initTheme() {
  const saved = localStorage.getItem('brief-ai-theme');
  const theme = saved || 'light';
  document.documentElement.setAttribute('data-theme', theme);
})();

$('#theme-toggle').addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('brief-ai-theme', next);
  if (weaknessChart && lastWeaknesses) {
    renderWeaknessChart(lastWeaknesses);
  }
});

// ─── Screens ───
const screenUpload     = $('#screen-upload');
const screenProcessing = $('#screen-processing');
const screenResults    = $('#screen-results');

// ─── Upload elements ───
const dropZone    = $('#drop-zone');
const fileInput   = $('#file-input');
const fileInfo    = $('#file-info');
const fileName    = $('#file-name');
const removeFile  = $('#remove-file');
const analyzeBtn  = $('#analyze-btn');
const newBtn      = $('#new-analysis-btn');

let selectedFile = null;
let elapsedInterval = null;
let notifyWhenDone = false;

// ─── Notify button ───
const notifyBtn = $('#notify-btn');
notifyBtn.addEventListener('click', async () => {
  if (notifyWhenDone) {
    notifyWhenDone = false;
    notifyBtn.classList.remove('active');
    notifyBtn.querySelector('.notify-label').textContent = 'Notify me';
    return;
  }

  if (!('Notification' in window)) {
    alert('This browser does not support notifications.');
    return;
  }

  let perm = Notification.permission;
  if (perm === 'default') {
    perm = await Notification.requestPermission();
  }

  if (perm === 'granted') {
    notifyWhenDone = true;
    notifyBtn.classList.add('active');
    notifyBtn.querySelector('.notify-label').textContent = 'Will notify';
  } else {
    alert('Notification permission was denied. Enable it in your browser settings.');
  }
});

// ═══════════════════════════════════════════
// Screen transitions
// ═══════════════════════════════════════════

function showScreen(screen) {
  [screenUpload, screenProcessing, screenResults].forEach((s) => {
    s.classList.remove('active');
  });
  screen.classList.add('active');
  newBtn.classList.toggle('hidden', screen === screenUpload);
}

// ═══════════════════════════════════════════
// File handling
// ═══════════════════════════════════════════

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const files = e.dataTransfer.files;
  if (files.length && files[0].name.toLowerCase().endsWith('.pdf')) {
    setFile(files[0]);
  }
});

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    setFile(fileInput.files[0]);
  }
});

function setFile(file) {
  selectedFile = file;
  fileName.textContent = file.name;
  fileInfo.classList.remove('hidden');
  analyzeBtn.classList.remove('hidden');
  dropZone.style.display = 'none';
}

removeFile.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  analyzeBtn.classList.add('hidden');
  dropZone.style.display = '';
});

newBtn.addEventListener('click', () => {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  analyzeBtn.classList.add('hidden');
  dropZone.style.display = '';
  resetPipeline();
  showScreen(screenUpload);
});

// ═══════════════════════════════════════════
// Analysis — SSE streaming
// ═══════════════════════════════════════════

analyzeBtn.addEventListener('click', startAnalysis);

function startAnalysis() {
  if (!selectedFile) return;

  showScreen(screenProcessing);
  resetPipeline();
  startTimer();

  const formData = new FormData();
  formData.append('file', selectedFile);

  fetch(API + '/analyze/stream', { method: 'POST', body: formData })
    .then((res) => {
      if (!res.ok) throw new Error('Upload failed: ' + res.status);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      function pump() {
        return reader.read().then(({ done, value }) => {
          if (done) {
            stopTimer();
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          let currentEvent = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6);
              try {
                handleSSE(currentEvent, JSON.parse(data));
              } catch (_) {}
              currentEvent = '';
            }
          }
          return pump();
        });
      }

      return pump();
    })
    .catch((err) => {
      stopTimer();
      console.error(err);
      alert('Analysis failed: ' + err.message);
      showScreen(screenUpload);
    });
}

function handleSSE(event, data) {
  if (event === 'agent_start') {
    setPipelineState(data.agent, 'running');
  } else if (event === 'agent_complete') {
    setPipelineState(data.agent, 'done', data);
  } else if (event === 'final_result') {
    stopTimer();
    renderResults(data);
    setTimeout(() => showScreen(screenResults), 600);
    if (notifyWhenDone && Notification.permission === 'granted') {
      const assessment = (data.strategy || {}).overall_assessment || 'complete';
      new Notification('BriefAI — Analysis Complete', {
        body: `Case strength: ${assessment}. Click to view results.`,
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">&#9878;</text></svg>',
      });
      notifyWhenDone = false;
      notifyBtn.classList.remove('active');
      notifyBtn.querySelector('.notify-label').textContent = 'Notify me';
    }
  } else if (event === 'error') {
    stopTimer();
    alert('Error: ' + (data.error || 'Unknown error'));
    showScreen(screenUpload);
  }
}

// ═══════════════════════════════════════════
// Pipeline visualization
// ═══════════════════════════════════════════

function resetPipeline() {
  $$('.pipeline-step').forEach((el) => {
    el.classList.remove('running', 'done');
    el.querySelector('.step-meta').textContent = '';
  });
}

function setPipelineState(agent, state, data) {
  const el = $(`.pipeline-step[data-agent="${agent}"]`);
  if (!el) return;

  el.classList.remove('running', 'done');
  el.classList.add(state);

  if (state === 'done' && data) {
    const meta = el.querySelector('.step-meta');
    if (agent === 'extractor') {
      const parts = [`${data.claims_found || 0} claims`, `${data.parties || 0} parties`];
      if (data.dates) parts.push(`${data.dates} dates`);
      if (data.contacts) parts.push(`${data.contacts} contacts`);
      meta.textContent = parts.join(', ');
    } else if (agent === 'weakness_analyzer') {
      meta.textContent = `${data.reports || 0} reports, avg ${data.avg_score || 0}`;
    } else if (agent === 'counterargument_predictor') {
      meta.textContent = `${data.counterarguments || 0} counterarguments`;
    } else if (agent === 'synthesizer') {
      meta.textContent = `${data.actions || 0} actions → ${data.overall_assessment || ''}`;
    }
  }
}

// ─── Timer ───
function startTimer() {
  const start = Date.now();
  const el = $('#elapsed-time');
  el.textContent = '0s';
  elapsedInterval = setInterval(() => {
    const s = Math.floor((Date.now() - start) / 1000);
    el.textContent = s + 's';
  }, 1000);
}

function stopTimer() {
  if (elapsedInterval) clearInterval(elapsedInterval);
}

// ═══════════════════════════════════════════
// Results rendering
// ═══════════════════════════════════════════

let weaknessChart = null;
let lastWeaknesses = null;

function renderResults(data) {
  const ext  = data.extraction || {};
  const weak = data.weaknesses || [];
  const ca   = data.counterarguments || [];
  const strat = data.strategy || {};

  // Overall badge — shows CASE STRENGTH, not analysis quality
  const badge = $('#overall-badge');
  const assessment = strat.overall_assessment || 'unknown';
  badge.textContent = 'Case Strength: ' + assessment;
  badge.className = 'results-badge ' + assessment;

  // ─── Results header extras ───
  renderActionBanner(ext);
  renderSummaryCard(ext);
  renderDatesStrip(ext.key_dates || []);

  // ─── Overview tab ───
  renderParties(ext.parties || []);
  renderCaseInfo(ext);
  renderContacts(ext.contacts || []);
  renderClaims(ext.claims || []);
  renderFacts(ext.facts || []);
  renderRelief(ext.relief_sought || '');

  // ─── Weaknesses tab ───
  lastWeaknesses = weak;
  renderWeaknessChart(weak);
  renderWeaknesses(weak);

  // ─── Counterarguments tab ───
  renderCounterarguments(ca);

  // ─── Strategy tab ───
  renderRiskMatrix(ext.claims || [], weak, ca);
  renderStrategy(strat);

  // Reset tabs
  $$('.tab').forEach((t) => t.classList.remove('active'));
  $$('.tab-panel').forEach((p) => p.classList.remove('active'));
  $('.tab[data-tab="tab-overview"]').classList.add('active');
  $('#tab-overview').classList.add('active');
}

function renderParties(parties) {
  const el = $('#parties-list');
  el.innerHTML = parties
    .map(
      (p) =>
        `<span class="party-tag">
          <span class="party-name">${esc(p.name)}</span>
          <span class="party-role">${esc(p.role)}</span>
        </span>`
    )
    .join('');
}

function renderCaseInfo(ext) {
  const el = $('#case-info');
  const rows = [
    ['Jurisdiction', ext.jurisdiction],
    ['Case Type', ext.case_type],
    ['Posture', ext.procedural_posture],
  ];
  el.innerHTML = rows
    .filter(([_, v]) => v)
    .map(
      ([k, v]) =>
        `<div class="meta-row">
          <span class="meta-key">${k}</span>
          <span class="meta-val">${esc(v)}</span>
        </div>`
    )
    .join('');
}

function renderClaims(claims) {
  const el = $('#claims-list');
  el.innerHTML = claims
    .map(
      (c) =>
        `<div class="claim-card">
          <div class="claim-header">
            <span class="claim-id">Claim ${c.claim_id}</span>
            <span class="claim-text">${esc(c.text)}</span>
          </div>
          <div class="claim-basis">Legal basis: ${esc(c.legal_basis)}</div>
        </div>`
    )
    .join('');
}

function renderFacts(facts) {
  const el = $('#facts-list');
  el.innerHTML = facts.map((f) => `<div class="fact-item">${esc(f)}</div>`).join('');
}

function renderRelief(text) {
  $('#relief-text').textContent = text;
}

// ─── Action banner ───
function renderActionBanner(ext) {
  const banner = $('#action-banner');
  if (ext.action_required) {
    $('#action-banner-desc').textContent = ext.action_description || 'This document requires action from the recipient.';
    banner.classList.remove('hidden');
  } else {
    banner.classList.add('hidden');
  }
}

// ─── Summary card + doc type badge ───
function renderSummaryCard(ext) {
  const card = $('#summary-card');
  if (ext.summary) {
    const badge = $('#doc-type-badge');
    badge.textContent = ext.document_type || 'Document';
    $('#summary-text').textContent = ext.summary;
    card.classList.remove('hidden');
  } else {
    card.classList.add('hidden');
  }
}

// ─── Key dates strip ───
function renderDatesStrip(dates) {
  const strip = $('#dates-strip');
  const list = $('#dates-strip-list');
  if (!dates || !dates.length) {
    strip.classList.add('hidden');
    return;
  }
  strip.classList.remove('hidden');

  const urgencyOrder = { past_due: 0, urgent: 1, upcoming: 2, informational: 3 };
  const sorted = [...dates].sort((a, b) => (urgencyOrder[a.urgency] || 3) - (urgencyOrder[b.urgency] || 3));

  list.innerHTML = sorted
    .map(
      (d) =>
        `<div class="date-chip urgency-border-${d.urgency}">
          <span class="date-chip-date">${esc(d.date)}</span>
          <span class="date-chip-desc">${esc(d.description)}</span>
          <span class="date-chip-urgency urgency-${d.urgency}">${esc(d.urgency).replace('_', ' ')}</span>
        </div>`
    )
    .join('');
}

// ─── Contacts card ───
function renderContacts(contacts) {
  const card = $('#contacts-card');
  const list = $('#contacts-list');
  if (!contacts || !contacts.length) {
    card.classList.add('hidden');
    return;
  }
  card.classList.remove('hidden');

  list.innerHTML = contacts
    .map((c) => {
      const initials = (c.name || '?')
        .split(' ')
        .map((w) => w[0])
        .slice(0, 2)
        .join('')
        .toUpperCase();

      let details = '';
      if (c.phone) details += `<div class="contact-detail">${esc(c.phone)}</div>`;
      if (c.address) details += `<div class="contact-detail">${esc(c.address)}</div>`;

      return `<div class="contact-row">
        <div class="contact-avatar">${initials}</div>
        <div class="contact-info">
          <div class="contact-name">${esc(c.name)}</div>
          <div class="contact-role">${esc(c.role)}</div>
          ${c.organization ? `<div class="contact-org">${esc(c.organization)}</div>` : ''}
          ${details}
        </div>
      </div>`;
    })
    .join('');
}

// ─── Weakness chart (Chart.js horizontal bar) ───
function renderWeaknessChart(weaknesses) {
  if (weaknessChart) {
    weaknessChart.destroy();
    weaknessChart = null;
  }

  if (!weaknesses || !weaknesses.length) return;

  const canvas = $('#weakness-chart');
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

  const labels = weaknesses.map((w) => 'Claim ' + w.claim_id);
  const scores = weaknesses.map((w) => w.weakness_score);
  const colors = scores.map((s) =>
    s <= 0.35 ? (isDark ? '#4ADE80' : '#2D7A4F')
    : s <= 0.65 ? (isDark ? '#FBBF24' : '#A16207')
    : (isDark ? '#F87171' : '#B91C1C')
  );
  const bgColors = scores.map((s) =>
    s <= 0.35 ? (isDark ? 'rgba(74,222,128,0.18)' : 'rgba(45,122,79,0.12)')
    : s <= 0.65 ? (isDark ? 'rgba(251,191,36,0.18)' : 'rgba(161,98,7,0.12)')
    : (isDark ? 'rgba(248,113,113,0.18)' : 'rgba(185,28,28,0.1)')
  );

  const textColor = isDark ? '#8C877E' : '#78716C';
  const gridColor = isDark ? 'rgba(61,58,50,0.5)' : 'rgba(226,221,212,0.7)';

  weaknessChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Weakness Score',
        data: scores,
        backgroundColor: bgColors,
        borderColor: colors,
        borderWidth: 2,
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.raw;
              const label = v <= 0.35 ? 'Strong' : v <= 0.65 ? 'Moderate' : 'Weak';
              return `${label} — ${v.toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          min: 0,
          max: 1,
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            font: { family: "'JetBrains Mono', monospace", size: 11 },
            callback: (v) => v.toFixed(1),
          },
          title: {
            display: true,
            text: '0 = Strong ← → Weak = 1',
            color: textColor,
            font: { family: "'DM Sans', sans-serif", size: 12 },
          },
        },
        y: {
          grid: { display: false },
          ticks: {
            color: textColor,
            font: { family: "'DM Sans', sans-serif", size: 13, weight: '600' },
          },
        },
      },
      layout: { padding: { top: 4, bottom: 4 } },
    },
  });

  canvas.parentElement.style.height = Math.max(120, weaknesses.length * 52 + 60) + 'px';
}

// ─── Claim risk summary ───
function renderRiskMatrix(claims, weaknesses, counterargs) {
  const wrapper = $('#risk-matrix');
  if (!claims || !claims.length) {
    wrapper.classList.add('hidden');
    return;
  }
  wrapper.classList.remove('hidden');

  const weakMap = {};
  (weaknesses || []).forEach((w) => { weakMap[w.claim_id] = w; });
  const counterMap = {};
  (counterargs || []).forEach((ca) => { counterMap[ca.claim_id] = ca; });

  const rows = claims.map((c) => {
    const w = weakMap[c.claim_id];
    const ca = counterMap[c.claim_id];
    const score = w ? w.weakness_score : null;
    const severity = ca ? ca.severity : null;

    let verdict, verdictClass;
    if ((score !== null && score > 0.65) || severity === 'critical') {
      verdict = 'High Risk';
      verdictClass = 'verdict-high';
    } else if ((score !== null && score > 0.35) || severity === 'moderate') {
      verdict = 'Needs Attention';
      verdictClass = 'verdict-mid';
    } else {
      verdict = 'On Track';
      verdictClass = 'verdict-low';
    }

    return { claim: c, score, severity, verdict, verdictClass };
  });

  rows.sort((a, b) => {
    const order = { 'verdict-high': 0, 'verdict-mid': 1, 'verdict-low': 2 };
    return (order[a.verdictClass] || 2) - (order[b.verdictClass] || 2);
  });

  const highCount = rows.filter((r) => r.verdictClass === 'verdict-high').length;
  const midCount = rows.filter((r) => r.verdictClass === 'verdict-mid').length;
  const lowCount = rows.filter((r) => r.verdictClass === 'verdict-low').length;

  wrapper.innerHTML = `
    <div class="risk-summary-header">
      <div class="risk-summary-title">Claim Risk Overview</div>
      <div class="risk-summary-counts">
        ${highCount ? `<span class="risk-count risk-count-high">${highCount} high risk</span>` : ''}
        ${midCount ? `<span class="risk-count risk-count-mid">${midCount} needs attention</span>` : ''}
        ${lowCount ? `<span class="risk-count risk-count-low">${lowCount} on track</span>` : ''}
      </div>
    </div>
    <div class="risk-summary-list">
      ${rows.map((r) => {
        const pct = r.score !== null ? Math.round(r.score * 100) : null;
        const strengthLabel = r.score !== null
          ? (r.score <= 0.35 ? 'Strong' : r.score <= 0.65 ? 'Moderate' : 'Weak')
          : 'N/A';
        const barClass = r.score !== null
          ? (r.score <= 0.35 ? 'bar-strong' : r.score <= 0.65 ? 'bar-moderate' : 'bar-weak')
          : '';

        return `<div class="risk-row ${r.verdictClass}">
          <div class="risk-row-left">
            <span class="risk-row-id">Claim ${r.claim.claim_id}</span>
            <span class="risk-row-verdict ${r.verdictClass}">${r.verdict}</span>
          </div>
          <div class="risk-row-claim">${esc(r.claim.text)}</div>
          <div class="risk-row-meters">
            <div class="risk-meter">
              <div class="risk-meter-label">Strength</div>
              <div class="risk-meter-track">
                ${pct !== null ? `<div class="risk-meter-fill ${barClass}" style="width:${100 - pct}%"></div>` : ''}
              </div>
              <div class="risk-meter-value">${strengthLabel}</div>
            </div>
            <div class="risk-meter">
              <div class="risk-meter-label">Counter threat</div>
              <div class="risk-severity">
                ${r.severity
                  ? `<span class="severity-badge severity-${r.severity}">${r.severity}</span>`
                  : '<span class="risk-meter-value">None found</span>'}
              </div>
            </div>
          </div>
        </div>`;
      }).join('')}
    </div>
  `;
}

function renderWeaknesses(weaknesses) {
  const el = $('#weaknesses-container');
  el.innerHTML = weaknesses
    .map((w) => {
      const scoreClass = w.weakness_score <= 0.35 ? 'score-low' : w.weakness_score <= 0.65 ? 'score-mid' : 'score-high';
      const scoreLabel = w.weakness_score <= 0.35 ? 'Strong' : w.weakness_score <= 0.65 ? 'Moderate' : 'Weak';

      let casesHtml = '';
      if (w.supporting_cases && w.supporting_cases.length) {
        casesHtml += `<div class="result-cases">
          <div class="result-cases-label">Supporting</div>
          ${w.supporting_cases.map((c) => renderCaseTag(c)).join('')}
        </div>`;
      }
      if (w.contradicting_cases && w.contradicting_cases.length) {
        casesHtml += `<div class="result-cases">
          <div class="result-cases-label">Contradicting</div>
          ${w.contradicting_cases.map((c) => renderCaseTag(c)).join('')}
        </div>`;
      }

      return `<div class="result-card">
        <div class="result-card-header">
          <span class="result-card-title">Claim ${w.claim_id}</span>
          <span class="score-badge ${scoreClass}">${scoreLabel} · ${w.weakness_score.toFixed(2)}</span>
        </div>
        <div class="result-reasoning">${esc(w.reasoning)}</div>
        ${casesHtml}
      </div>`;
    })
    .join('');
}

function renderCounterarguments(counterargs) {
  const el = $('#counter-container');
  el.innerHTML = counterargs
    .map((ca) => {
      let casesHtml = '';
      if (ca.grounding_cases && ca.grounding_cases.length) {
        casesHtml = `<div class="result-cases">
          <div class="result-cases-label">Grounding Cases</div>
          ${ca.grounding_cases.map((c) => renderCaseTag(c)).join('')}
        </div>`;
      }

      return `<div class="result-card">
        <div class="result-card-header">
          <span class="result-card-title">Claim ${ca.claim_id}</span>
          <span class="severity-badge severity-${ca.severity}">${ca.severity}</span>
        </div>
        <div class="result-reasoning">${esc(ca.predicted_rebuttal)}</div>
        ${casesHtml}
        ${
          ca.suggested_preemption
            ? `<div class="preemption-box">
                <div class="preemption-label">Suggested Preemption</div>
                ${esc(ca.suggested_preemption)}
              </div>`
            : ''
        }
      </div>`;
    })
    .join('');
}

function renderStrategy(strat) {
  const container = $('#strategy-container');
  let html = '';

  // Actions
  if (strat.actions && strat.actions.length) {
    html += `<div class="strategy-section">
      <div class="strategy-section-label">Prioritized Actions</div>
      ${strat.actions
        .map(
          (a) => `<div class="action-card">
            <div class="action-priority">${a.priority}</div>
            <div class="action-body">
              <div class="action-text">${esc(a.action)}</div>
              <div class="action-rationale">${esc(a.rationale)}</div>
              <div class="action-footer">
                <div class="confidence-bar"><div class="confidence-fill" style="width:${Math.round(a.confidence * 100)}%"></div></div>
                <span class="confidence-label">${Math.round(a.confidence * 100)}%</span>
                <div class="claims-tags">
                  ${(a.related_claims || []).map((id) => `<span class="claim-ref">C${id}</span>`).join('')}
                </div>
              </div>
            </div>
          </div>`
        )
        .join('')}
    </div>`;
  }

  // Key risks
  if (strat.key_risks && strat.key_risks.length) {
    html += `<div class="strategy-section">
      <div class="strategy-section-label">Key Risks</div>
      ${strat.key_risks.map((r) => `<div class="risk-item">${esc(r)}</div>`).join('')}
    </div>`;
  }

  // Focus areas
  if (strat.recommended_focus_areas && strat.recommended_focus_areas.length) {
    html += `<div class="strategy-section">
      <div class="strategy-section-label">Recommended Focus Areas</div>
      ${strat.recommended_focus_areas.map((f) => `<div class="focus-item">${esc(f)}</div>`).join('')}
    </div>`;
  }

  container.innerHTML = html;
}

function renderCaseTag(c) {
  return `<span class="case-tag">
    <span class="case-title">${esc(c.title)}</span>
    ${c.date ? `<span class="case-date">${esc(c.date)}</span>` : ''}
  </span>`;
}

// ─── Tabs ───
$$('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach((t) => t.classList.remove('active'));
    $$('.tab-panel').forEach((p) => p.classList.remove('active'));
    tab.classList.add('active');
    const panel = $(`#${tab.dataset.tab}`);
    if (panel) panel.classList.add('active');
  });
});

// ─── Utility ───
function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
