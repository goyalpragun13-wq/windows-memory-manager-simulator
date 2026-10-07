/**
 * Windows Memory Manager Simulator - Client Architecture & API Controller
 */

// Global State
let state = {
  isBackendOnline: false,
  apiBase: '/api/v1',
  currentProcess: 0,
  writeMode: false,
  autoTimer: null,
  snapshot: null,
  tlbStatus: null,
  pageTable: [],
  tourStep: 0,
  tourCompleted: false,
  tourFreeMode: false,
  baselineData: null,
  labData: null,
  testReport: null,
  tourBaselineStats: { soft: 0, wr: 0 }
};

// Guided Tour Definitions
const TOUR_STEPS = [
  {
    title: "Understanding Windows Memory Management",
    desc: "Welcome to the Windows Virtual Memory Manager (VMM) Simulator. In modern Windows (NT through Windows 11), physical RAM is partitioned into process Working Sets and global Page Frame Database (PFN) lists. Each step guides you through an architectural concept.",
    showSections: ["sec-controls", "sec-pfn", "sec-lists", "sec-ws", "sec-stats", "sec-log"],
    task: "Click Start Tour below to begin hands-on experiments.",
    isCompleted: () => true
  },
  {
    title: "1. Demand Paging & Hard Faults",
    desc: "When a process references a page not present in physical RAM, the MMU triggers a Page Fault Exception. The OS allocates an empty physical frame from the Zeroed or Free list and reads the page from disk.",
    showSections: ["sec-controls", "sec-pfn", "sec-ws", "sec-stats", "sec-log"],
    task: "Access virtual pages 0, 1, and 2 for Process P1.",
    highlightPages: [0, 1, 2],
    isCompleted: (s) => s.working_sets[0].active_count >= 3,
    progressText: (s) => `${Math.min(3, s.working_sets[0].active_count)} of 3 pages loaded into P1 working set`,
    explanation: "Because none of these pages were resident in RAM, Windows serviced each access via a slow Hard Fault (disk read) and mapped them into active frames."
  },
  {
    title: "2. Working Set Quotas & Page Trimming",
    desc: "To prevent memory monopolization, Windows assigns each process a Working Set Limit (default: 4 pages for P1). When limit is exceeded, Working Set Trimming evicts the least recently used page.",
    showSections: ["sec-controls", "sec-pfn", "sec-ws", "sec-lists", "sec-log"],
    task: "Access pages 3 and 4 for P1 to exceed its 4-page quota.",
    highlightPages: [3, 4],
    isCompleted: (s) => s.lists.stby.length > 0 || s.lists.mod.length > 0,
    progressText: (s) => `P1 holds ${s.working_sets[0].active_count} of 4 pages (Waiting for trim)`,
    explanation: "The oldest page was trimmed from P1's working set. Rather than being discarded, its frame was moved to the Standby List (clean cache) preserving its data."
  },
  {
    title: "3. Standby List & Soft Faults (Zero Disk I/O)",
    desc: "If a process references a trimmed page still resident on the Standby or Modified list, Windows performs a Soft Fault: it simply reattaches the frame to the working set without any disk read!",
    showSections: ["sec-controls", "sec-pfn", "sec-lists", "sec-stats", "sec-log"],
    task: "Touch the page currently sitting on the Standby list (yellow frame).",
    highlightPages: (s) => {
      const stby = s.lists.stby;
      if (stby.length) {
        const frame = s.frames[stby[0]];
        return frame.p === s.current_process ? [frame.pg] : [];
      }
      return [];
    },
    isCompleted: (s) => s.stats.soft > state.tourBaselineStats.soft,
    progressText: (s) => s.stats.soft > state.tourBaselineStats.soft ? "Soft fault resolved!" : "Waiting for soft fault access",
    explanation: "Soft Fault achieved! Notice that Soft Faults incremented while Disk Reads stayed unchanged. This caching mechanism is fundamental to Windows system responsiveness."
  },
  {
    title: "4. Dirty Pages & The Modified List",
    desc: "When a page is written to, its hardware dirty bit (d) is asserted. When trimmed, dirty pages cannot go to Standby—they must be placed on the Modified List until saved.",
    showSections: ["sec-controls", "sec-pfn", "sec-lists", "sec-ws", "sec-stats", "sec-log"],
    task: "Toggle Write Mode (marks dirty *), then access pages 5, 6, 7, 8 in sequence.",
    highlightButtons: ["btn-toggle-write"],
    highlightPages: [5, 6, 7, 8],
    isCompleted: (s) => s.lists.mod.length >= 1,
    progressText: (s) => `Modified list has ${s.lists.mod.length} page(s)`,
    explanation: "Dirty pages (*) are routed to the Modified List (red) because their contents differ from the pagefile on disk."
  },
  {
    title: "5. Modified Page Writer & Disk Flushing",
    desc: "The Modified Page Writer is a kernel worker thread that periodically writes dirty frames to pagefile.sys, clears dirty bits, and transitions frames to Standby.",
    showSections: ["sec-controls", "sec-pfn", "sec-lists", "sec-stats", "sec-log"],
    task: "Click 'Run Modified Page Writer' to flush dirty pages to disk.",
    highlightButtons: ["btn-flush"],
    isCompleted: (s) => s.stats.wr > state.tourBaselineStats.wr,
    progressText: (s) => `Disk writes logged: ${s.stats.wr}`,
    explanation: "Dirty pages were flushed to disk. Their dirty flags were cleared and frames transitioned to Standby, making them available for reallocation or soft reclamation."
  },
  {
    title: "6. Hardware MMU & Address Translation",
    desc: "The MMU translates Virtual Addresses (VA) to Physical Addresses (PA) using VPN (Virtual Page Number) and byte offset, accelerated by a 4-entry associative TLB.",
    showSections: ["sec-mmu", "sec-pfn", "sec-controls"],
    task: "Click 'Translate & Access' in the MMU panel with virtual address 0x2A3C.",
    highlightButtons: ["btn-translate"],
    isCompleted: () => state.translatedOnce === true,
    progressText: () => state.translatedOnce ? "Address translated!" : "Awaiting address translation",
    explanation: "Virtual Address 0x2A3C = Page 2 + Offset 0xA3C. The MMU queried the TLB and Page Table, resolved the physical frame, and computed the physical byte address."
  },
  {
    title: "7. Working Set Thrashing",
    desc: "Thrashing occurs when active working sets are insufficient to hold resident working pages, causing excessive, continuous hard page faults and disk saturation.",
    showSections: ["sec-scenarios", "sec-stats", "sec-controls"],
    task: "In the Scenarios panel, click Scenario 2: 'Thrashing'.",
    highlightButtons: ["btn-scen-2"],
    isCompleted: (s) => s.is_thrashing,
    progressText: (s) => `Thrashing indicator: ${s.is_thrashing ? 'ACTIVE' : 'INACTIVE'}`,
    explanation: "Thrashing detected! With limits constricted to 1 frame, every access evicts the next needed page, saturating disk I/O."
  },
  {
    title: "Tour Complete! Academic Experimentation",
    desc: "You have completed the core Windows Virtual Memory architecture tour. Explore the Replacement Algorithm Lab, compare Windows VMM against Global FIFO/LRU, and run the self-test suite below.",
    showSections: ["sec-controls", "sec-pfn", "sec-lists", "sec-ws", "sec-stats", "sec-mmu", "sec-scenarios", "sec-benchmark", "sec-lab", "sec-tests", "sec-log"],
    task: "Free exploration unlocked.",
    isCompleted: () => true
  }
];

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initEventHandlers();
  checkBackendHealth();
  // Fetch initial state or boot local engine
  fetchSimulationState();
});

// Theme Management
function initTheme() {
  const saved = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
  updateThemeIcon(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const el = document.getElementById("theme-toggle-btn");
  if (el) el.innerHTML = theme === "dark" ? "☀️ Light" : "🌙 Dark";
}

// Check Backend Connection
async function checkBackendHealth() {
  try {
    const res = await fetch("/health");
    if (res.ok) {
      state.isBackendOnline = true;
      updateBackendStatusBadge(true);
      return;
    }
  } catch (e) {
    // Offline / Standalone
  }
  state.isBackendOnline = false;
  updateBackendStatusBadge(false);
}

function updateBackendStatusBadge(online) {
  const badge = document.getElementById("backend-badge");
  if (!badge) return;
  if (online) {
    badge.className = "badge badge-connected";
    badge.innerHTML = `<span class="badge-pulse"></span> FastAPI Engine Active (Port 8000)`;
  } else {
    badge.className = "badge";
    badge.style.background = "rgba(234, 179, 8, 0.15)";
    badge.style.color = "#eab308";
    badge.style.border = "1px solid rgba(234, 179, 8, 0.3)";
    badge.innerHTML = `⚡ Standalone Client Engine`;
  }
}

// Event Listeners
function initEventHandlers() {
  document.getElementById("theme-toggle-btn")?.addEventListener("click", toggleTheme);
  document.getElementById("btn-toggle-write")?.addEventListener("click", toggleWriteMode);
  document.getElementById("btn-flush")?.addEventListener("click", triggerFlush);
  document.getElementById("btn-zero-step")?.addEventListener("click", triggerZeroStep);
  document.getElementById("btn-auto")?.addEventListener("click", toggleAutoWorkload);
  document.getElementById("btn-reset")?.addEventListener("click", resetSimulation);
  document.getElementById("btn-translate")?.addEventListener("click", handleTranslate);
  document.getElementById("btn-kill-proc")?.addEventListener("click", handleKillProcess);
  document.getElementById("btn-run-lab")?.addEventListener("click", handleRunLab);
  document.getElementById("btn-run-tests")?.addEventListener("click", handleRunTests);
  document.getElementById("btn-export-trace")?.addEventListener("click", exportTrace);

  // Modal triggers
  document.getElementById("btn-open-theory")?.addEventListener("click", () => openModal("modal-theory"));
  document.getElementById("btn-close-theory")?.addEventListener("click", () => closeModal("modal-theory"));
  document.getElementById("btn-open-tests")?.addEventListener("click", () => {
    openModal("modal-tests");
    handleRunTests();
  });
  document.getElementById("btn-close-tests")?.addEventListener("click", () => closeModal("modal-tests"));
}

function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.style.display = "flex";
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.style.display = "none";
}

// API Dispatchers
async function fetchSimulationState() {
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/state`);
      if (res.ok) {
        state.snapshot = await res.json();
        renderAll();
        return;
      }
    } catch (e) {
      state.isBackendOnline = false;
      updateBackendStatusBadge(false);
    }
  }
  // Local fallback
  if (!window.localKernel) initLocalKernel();
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

async function accessPage(proc, page, isWrite) {
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/access`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ process_id: proc, page_number: page, is_write: isWrite })
      });
      if (res.ok) {
        const data = await res.json();
        state.snapshot = data.state;
        renderAll();
        return;
      }
    } catch (e) {
      state.isBackendOnline = false;
      updateBackendStatusBadge(false);
    }
  }
  window.localKernel.accessPage(proc, page, isWrite);
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

async function toggleWriteMode() {
  state.writeMode = !state.writeMode;
  if (state.isBackendOnline) {
    try {
      await fetch(`${state.apiBase}/sim/mode/toggle`, { method: "POST" });
    } catch (e) {}
  } else if (window.localKernel) {
    window.localKernel.writeMode = state.writeMode;
  }
  renderControls();
}

async function triggerFlush() {
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/flush`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        state.snapshot = data.state;
        renderAll();
        return;
      }
    } catch (e) {}
  }
  window.localKernel.flushModified();
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

async function triggerZeroStep() {
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/zero-step`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        state.snapshot = data.state;
        renderAll();
        return;
      }
    } catch (e) {}
  }
  window.localKernel.pfnDb.stepZeroPageThread();
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

async function resetSimulation() {
  if (state.autoTimer) toggleAutoWorkload();
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/reset`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        state.snapshot = data.state;
        renderAll();
        return;
      }
    } catch (e) {}
  }
  window.localKernel.reset();
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

function selectProcess(p) {
  state.currentProcess = p;
  if (state.isBackendOnline) {
    fetch(`${state.apiBase}/sim/process/${p}`, { method: "POST" }).catch(() => {});
  } else if (window.localKernel) {
    window.localKernel.currentProcess = p;
  }
  renderAll();
}

async function adjustWorkingSetLimit(proc, delta) {
  const current = state.snapshot.working_sets[proc].limit;
  const target = Math.max(1, Math.min(8, current + delta));
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/limit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ process_id: proc, limit: target })
      });
      if (res.ok) {
        const data = await res.json();
        state.snapshot = data.state;
        renderAll();
        return;
      }
    } catch (e) {}
  }
  window.localKernel.wsManager.setLimit(proc, target, window.localKernel.pfnDb, window.localKernel.tlb);
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

async function handleKillProcess() {
  const p = state.currentProcess;
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/sim/kill/${p}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        state.snapshot = data.state;
        renderAll();
        return;
      }
    } catch (e) {}
  }
  window.localKernel.terminateProcess(p);
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

function toggleAutoWorkload() {
  const btn = document.getElementById("btn-auto");
  if (state.autoTimer) {
    clearInterval(state.autoTimer);
    state.autoTimer = null;
    if (btn) btn.textContent = "▶ Start Auto Workload";
  } else {
    state.autoTimer = setInterval(async () => {
      if (state.isBackendOnline) {
        try {
          const res = await fetch(`${state.apiBase}/sim/step`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ count: 1 })
          });
          if (res.ok) {
            const data = await res.json();
            state.snapshot = data.state;
            renderAll();
            return;
          }
        } catch (e) {}
      }
      window.localKernel.stepAuto();
      state.snapshot = window.localKernel.getSnapshot();
      renderAll();
    }, 600);
    if (btn) btn.textContent = "⏸ Pause Auto Workload";
  }
}

// MMU & Translation
async function handleTranslate() {
  const inputEl = document.getElementById("mmu-va-input");
  const resultEl = document.getElementById("mmu-result-box");
  const raw = inputEl.value.trim();
  state.translatedOnce = true;

  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/mmu/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          virtual_address: raw,
          process_id: state.currentProcess,
          is_write: state.writeMode
        })
      });
      if (res.ok) {
        const data = await res.json();
        resultEl.innerHTML = `
          <div style="color: ${data.fault_type === 'hit' ? '#10b981' : data.fault_type === 'soft' ? '#eab308' : '#f43f5e'}; font-weight: 600;">
            ${data.message}
          </div>
        `;
        fetchSimulationState();
        return;
      }
    } catch (e) {}
  }

  // Local fallback translation
  const addr = parseInt(raw, 16);
  if (isNaN(addr) || addr < 0 || addr > 0x9FFF) {
    resultEl.innerHTML = `<span style="color:#f43f5e">Invalid virtual address (must be 0x0000 - 0x9FFF).</span>`;
    return;
  }
  const res = window.localKernel.translateAndAccess(addr, state.currentProcess, state.writeMode);
  resultEl.innerHTML = `
    <div style="color: ${res.fault_type === 'hit' ? '#10b981' : res.fault_type === 'soft' ? '#eab308' : '#f43f5e'}; font-weight: 600;">
      ${res.message}
    </div>
  `;
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

// Scenarios
async function runScenario(id) {
  if (state.autoTimer) toggleAutoWorkload();
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/scenarios/${id}/run`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        await fetchSimulationState();
        return;
      }
    } catch (e) {}
  }
  window.localKernel.runScenario(id);
  state.snapshot = window.localKernel.getSnapshot();
  renderAll();
}

// Replacement Algorithm Lab
async function handleRunLab() {
  const workload = document.getElementById("lab-workload-select").value;
  const customStr = document.getElementById("lab-custom-input").value;
  const container = document.getElementById("lab-results-box");

  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/algorithms/lab`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workload, custom_string: customStr, frame_min: 1, frame_max: 10 })
      });
      if (res.ok) {
        state.labData = await res.json();
        renderLabResults();
        return;
      }
    } catch (e) {}
  }

  state.labData = window.localKernel.runLab(workload, customStr);
  renderLabResults();
}

function renderLabResults() {
  if (!state.labData) return;
  const d = state.labData;
  const container = document.getElementById("lab-results-box");
  const chartEl = document.getElementById("lab-svg-chart");
  const anomalyEl = document.getElementById("lab-anomaly-box");

  // Summary & Anomaly callout
  if (d.belady_anomalies && d.belady_anomalies.length > 0) {
    const a = d.belady_anomalies[0];
    anomalyEl.style.display = "block";
    anomalyEl.innerHTML = `
      <b>⚠️ Belady's Anomaly Observed in FIFO:</b> Faults increased from ${a.faults_before} to ${a.faults_after} 
      when physical frames increased from ${a.from_frames} to ${a.to_frames}.
    `;
  } else {
    anomalyEl.style.display = "none";
  }

  // Table
  const policies = ["FIFO", "LRU", "Clock", "OPT"];
  const colors = { FIFO: "#f43f5e", LRU: "#8b5cf6", Clock: "#f97316", OPT: "#10b981" };
  let html = `<table><tr><th>Algorithm</th>${d.frame_range.map(f => `<th>${f} F</th>`).join("")}</tr>`;
  policies.forEach(p => {
    html += `<tr><td><b style="color:${colors[p]}">${p}</b></td>${d.results[p].map(v => `<td>${v}</td>`).join("")}</tr>`;
  });
  html += `</table>`;
  container.innerHTML = html;

  // Render SVG Chart
  renderLabChart(d, colors);
}

function renderLabChart(d, colors) {
  const svg = document.getElementById("lab-svg-chart");
  if (!svg) return;
  const maxVal = Math.max(1, d.trace_length);
  const w = 480;
  const h = 180;
  const padX = 40;
  const padY = 25;
  const plotW = w - padX * 2;
  const plotH = h - padY * 2;

  const getX = (idx) => padX + (idx / (d.frame_range.length - 1)) * plotW;
  const getY = (val) => padY + plotH - (val / maxVal) * plotH;

  let lines = `
    <line x1="${padX}" y1="${padY + plotH}" x2="${padX + plotW}" y2="${padY + plotH}" stroke="rgba(255,255,255,0.2)"/>
    <line x1="${padX}" y1="${padY}" x2="${padX}" y2="${padY + plotH}" stroke="rgba(255,255,255,0.2)"/>
    <text x="${padX}" y="${h - 6}" font-size="10" fill="#94a3b8">1 Frame</text>
    <text x="${padX + plotW - 40}" y="${h - 6}" font-size="10" fill="#94a3b8">10 Frames</text>
    <text x="6" y="${padY + 10}" font-size="10" fill="#94a3b8">${maxVal}</text>
  `;

  ["FIFO", "LRU", "Clock", "OPT"].forEach((p, k) => {
    const pts = d.results[p].map((val, i) => `${getX(i).toFixed(1)},${getY(val).toFixed(1)}`).join(" ");
    lines += `
      <polyline fill="none" stroke="${colors[p]}" stroke-width="2.5" points="${pts}"/>
      <text x="${padX + k * 85}" y="14" font-size="11" font-weight="bold" fill="${colors[p]}">${p}</text>
    `;
  });

  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = lines;
}

// Self-Test Runner
async function handleRunTests() {
  const container = document.getElementById("test-results-container");
  container.innerHTML = `<p style="color:var(--text-muted)">Executing automated verification suite...</p>`;

  let report = null;
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/telemetry/tests/run`, { method: "POST" });
      if (res.ok) {
        report = await res.json();
      }
    } catch (e) {}
  }
  if (!report) {
    report = window.localKernel.runSelfTests();
  }

  let html = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
      <b>Test Results: ${report.passed_tests} / ${report.total_tests} Passed (${report.success_rate_pct}%)</b>
      <span class="badge" style="background:${report.failed_tests === 0 ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'}; color:${report.failed_tests === 0 ? '#10b981' : '#f43f5e'}">
        ${report.failed_tests === 0 ? 'ALL VERIFICATIONS PASSED' : `${report.failed_tests} FAILURES`}
      </span>
    </div>
    <table>
      <tr><th>Test Assertion</th><th>Expected</th><th>Actual</th><th>Status</th></tr>
  `;

  report.results.forEach(r => {
    html += `
      <tr>
        <td>${r.name}</td>
        <td><code>${r.expected}</code></td>
        <td><code>${r.actual}</code></td>
        <td><b style="color:${r.passed ? '#10b981' : '#f43f5e'}">${r.passed ? 'PASS' : 'FAIL'}</b></td>
      </tr>
    `;
  });
  html += `</table>`;
  container.innerHTML = html;
}

// Export Trace JSON
function exportTrace() {
  if (!state.snapshot) return;
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state.snapshot, null, 2));
  const downloadAnchor = document.createElement("a");
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `windows_vmm_trace_${Date.now()}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}

// Main Render Loop
function renderAll() {
  if (!state.snapshot) return;
  renderTourGuide();
  renderControls();
  renderPfnGrid();
  renderSystemLists();
  renderWorkingSets();
  renderTelemetry();
  renderEventLog();
  renderPageTable();
  renderTrendChart();
  renderBaselineComparison();
}

// Guided Tour Renderer
function renderTourGuide() {
  const guideCard = document.getElementById("guide-card");
  if (!guideCard) return;

  if (state.tourFreeMode) {
    guideCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <b>🎓 Free Exploration Mode</b>
          <p style="font-size:12px; color:var(--text-muted)">All controls, scenarios, and experiment labs are unlocked.</p>
        </div>
        <button class="btn btn-sm" onclick="restartTour()">Restart Guided Tour</button>
      </div>
    `;
    document.querySelectorAll(".section-block").forEach(el => el.style.display = "");
    return;
  }

  const step = TOUR_STEPS[state.tourStep];
  const isDone = step.isCompleted(state.snapshot);

  // Toggle Visibility of Sections based on step
  document.querySelectorAll(".section-block").forEach(el => {
    const id = el.id;
    if (step.showSections && step.showSections.includes(id)) {
      el.style.display = "";
    } else {
      el.style.display = "none";
    }
  });

  // Render Pips
  const pips = TOUR_STEPS.map((_, i) => `
    <div class="guide-step-pip ${i < state.tourStep ? 'completed' : i === state.tourStep ? 'active' : ''}"></div>
  `).join("");

  guideCard.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <span class="badge" style="background:rgba(168,85,247,0.2); color:#c084fc;">
        Step ${state.tourStep + 1} of ${TOUR_STEPS.length}
      </span>
      <button class="btn btn-sm" onclick="skipTour()">Skip to Free Mode</button>
    </div>
    <div class="guide-step-bar">${pips}</div>
    <h3 style="font-size:16px; margin:4px 0 6px 0;">${step.title}</h3>
    <p style="font-size:13px; color:var(--text-muted);">${step.desc}</p>
    
    <div class="guide-task-box">
      <b>Objective:</b> ${step.task}<br/>
      <small style="color:var(--text-dim);">${typeof step.progressText === 'function' ? step.progressText(state.snapshot) : ''}</small>
    </div>

    ${isDone && step.explanation ? `
      <div class="guide-win-box">
        <span>✓ <b>Completed:</b> ${step.explanation}</span>
      </div>
    ` : ''}

    <div style="display:flex; gap:8px; margin-top:12px;">
      ${state.tourStep > 0 ? `<button class="btn btn-sm" onclick="prevTourStep()">Back</button>` : ''}
      ${isDone && state.tourStep < TOUR_STEPS.length - 1 ? `
        <button class="btn btn-primary btn-sm" onclick="nextTourStep()">Next Concept ➔</button>
      ` : ''}
      ${state.tourStep === TOUR_STEPS.length - 1 ? `
        <button class="btn btn-primary btn-sm" onclick="skipTour()">Explore Lab Freely ➔</button>
      ` : ''}
    </div>
  `;
}

function nextTourStep() {
  state.tourStep++;
  state.tourBaselineStats = {
    soft: state.snapshot.stats.soft,
    wr: state.snapshot.stats.wr
  };
  renderAll();
}

function prevTourStep() {
  if (state.tourStep > 0) state.tourStep--;
  renderAll();
}

function skipTour() {
  state.tourFreeMode = true;
  renderAll();
}

function restartTour() {
  state.tourFreeMode = false;
  state.tourStep = 0;
  resetSimulation();
}

// Controls
function renderControls() {
  // Process Tabs
  [0, 1, 2].forEach(p => {
    const tab = document.getElementById(`tab-p${p + 1}`);
    if (tab) {
      tab.className = `process-tab ${state.currentProcess === p ? `active-p${p + 1}` : ''}`;
    }
  });

  // Write mode button
  const writeBtn = document.getElementById("btn-toggle-write");
  if (writeBtn) {
    writeBtn.innerHTML = state.writeMode
      ? `✏️ Write Mode (Dirty <b>*</b>)`
      : `👁️ Read Mode`;
    writeBtn.className = `btn ${state.writeMode ? 'btn-active' : ''}`;
  }

  // Page Buttons
  const pbContainer = document.getElementById("page-buttons-container");
  if (!pbContainer) return;

  const currentStep = TOUR_STEPS[state.tourStep];
  let highlightedPages = [];
  if (!state.tourFreeMode && currentStep && currentStep.highlightPages) {
    highlightedPages = typeof currentStep.highlightPages === 'function'
      ? currentStep.highlightPages(state.snapshot)
      : currentStep.highlightPages;
  }

  pbContainer.innerHTML = Array.from({ length: 10 }, (_, pg) => {
    const frame = state.snapshot.frames.find(
      f => f.p === state.currentProcess && f.pg === pg && f.s !== 'free' && f.s !== 'zero'
    );
    let borderClass = "";
    if (frame) {
      if (frame.s === 'act') borderClass = "in-working-set";
      else if (frame.s === 'stby') borderClass = "on-standby";
      else if (frame.s === 'mod') borderClass = "on-modified";
    }
    const isPulse = highlightedPages.includes(pg);
    return `
      <button class="page-btn ${borderClass} ${isPulse ? 'highlight-pulse' : ''}" 
              onclick="accessPage(${state.currentProcess}, ${pg}, state.writeMode)">
        ${pg}
      </button>
    `;
  }).join("");
}

// Physical Memory Grid
function renderPfnGrid() {
  const grid = document.getElementById("pfn-grid");
  if (!grid || !state.snapshot) return;

  const stateLabels = {
    free: "Free",
    zero: "Zeroed",
    stby: "Standby",
    mod: "Modified",
    act: "Active"
  };

  grid.innerHTML = state.snapshot.frames.map(f => {
    const isActive = f.s === 'act';
    const procClass = isActive ? `p${f.p + 1}` : '';
    const content = (f.s === 'free' || f.s === 'zero')
      ? '&nbsp;'
      : `P${f.p + 1}:${f.pg}${f.d ? '*' : ''}`;

    return `
      <div class="frame-cell state-${f.s} ${procClass}" title="Frame #${f.i} | State: ${f.s} | Timestamp: ${f.u}">
        <div class="frame-header">PFN #${f.i}</div>
        <div class="frame-content">${content}</div>
        <span class="frame-state-tag" style="background:var(--state-${f.s}); color:#fff;">
          ${stateLabels[f.s]}
        </span>
      </div>
    `;
  }).join("");
}

// System Lists
function renderSystemLists() {
  const lists = state.snapshot.lists;
  const renderQueue = (id, listKey, colorVar) => {
    const el = document.getElementById(id);
    if (!el) return;
    const items = lists[listKey] || [];
    if (items.length === 0) {
      el.innerHTML = `<span style="font-size:12px; color:var(--text-dim)">Empty</span>`;
      return;
    }
    el.innerHTML = items.map(idx => {
      const f = state.snapshot.frames[idx];
      const text = (listKey === 'free' || listKey === 'zero')
        ? `#${idx}`
        : `P${f.p + 1}:${f.pg}${f.d ? '*' : ''}`;
      return `<span class="chip" style="border: 1px solid ${colorVar};">${text}</span>`;
    }).join("");
  };

  renderQueue("queue-free", "free", "var(--state-free)");
  renderQueue("queue-zero", "zero", "var(--state-zero)");
  renderQueue("queue-stby", "stby", "var(--state-stby)");
  renderQueue("queue-mod", "mod", "var(--state-mod)");
}

// Working Sets
function renderWorkingSets() {
  const wsContainer = document.getElementById("working-sets-container");
  if (!wsContainer || !state.snapshot) return;

  wsContainer.innerHTML = state.snapshot.working_sets.map(ws => {
    const pct = Math.min(100, Math.round((ws.active_count / ws.limit) * 100));
    return `
      <div class="ws-card">
        <div class="ws-header">
          <span style="color:${ws.color}; font-weight:700;">${ws.process_name}</span>
          <div class="quota-controls">
            <button class="quota-btn" onclick="adjustWorkingSetLimit(${ws.process_id}, -1)">-</button>
            <span style="font-size:12px; margin:0 4px;">Limit: ${ws.limit}</span>
            <button class="quota-btn" onclick="adjustWorkingSetLimit(${ws.process_id}, 1)">+</button>
          </div>
        </div>
        <div class="quota-bar-track">
          <div class="quota-bar-fill" style="width:${pct}%; background:${ws.color};"></div>
        </div>
        <div style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">
          Active: ${ws.active_count} / ${ws.limit} pages
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:4px; min-height:26px;">
          ${ws.active_pages.map(pg => {
            const f = state.snapshot.frames.find(x => x.p === ws.process_id && x.pg === pg && x.s === 'act');
            return `<span class="chip" style="background:${ws.color}; color:#fff;">${pg}${f && f.d ? '*' : ''}</span>`;
          }).join("") || `<span style="font-size:11px; color:var(--text-dim)">No resident pages</span>`}
        </div>
      </div>
    `;
  }).join("");
}

// Telemetry
function renderTelemetry() {
  const s = state.snapshot.stats;
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setVal("stat-accesses", s.accesses);
  setVal("stat-hits", s.hit);
  setVal("stat-soft", s.soft);
  setVal("stat-hard", s.hard);
  setVal("stat-reads", s.rd);
  setVal("stat-writes", s.wr);
  setVal("stat-fault-rate", `${s.fault_rate_pct}%`);
  setVal("stat-tlb-rate", `${s.tlb_hit_rate_pct}%`);

  const thrashingBanner = document.getElementById("thrashing-alert");
  if (thrashingBanner) {
    thrashingBanner.style.display = state.snapshot.is_thrashing ? "flex" : "none";
  }
}

// Event Log
function renderEventLog() {
  const logContainer = document.getElementById("event-log-container");
  if (!logContainer || !state.snapshot) return;

  logContainer.innerHTML = state.snapshot.log.map(msg => `
    <div class="event-entry">${msg}</div>
  `).join("") || `<div style="color:var(--text-dim)">No events yet. Access pages to begin.</div>`;
}

// Page Table
function renderPageTable() {
  const ptContainer = document.getElementById("page-table-container");
  if (!ptContainer || !state.snapshot) return;

  const frames = state.snapshot.frames;
  const p = state.currentProcess;

  let html = `
    <table>
      <tr><th>VPN</th><th>PTE State</th><th>PFN</th><th>Dirty</th><th>TLB</th></tr>
  `;

  for (let pg = 0; pg < 10; pg++) {
    const f = frames.find(x => x.p === p && x.pg === pg && x.s !== 'free' && x.s !== 'zero');
    let stateBadge = `<span style="color:var(--text-dim)">Invalid (Disk)</span>`;
    let pfnText = "-";
    let isDirty = "";
    if (f) {
      if (f.s === 'act') stateBadge = `<span style="color:#10b981; font-weight:600;">Valid (Active)</span>`;
      else if (f.s === 'stby') stateBadge = `<span style="color:#eab308; font-weight:600;">Transition (Standby)</span>`;
      else if (f.s === 'mod') stateBadge = `<span style="color:#f43f5e; font-weight:600;">Transition (Modified)</span>`;
      pfnText = `#${f.i}`;
      if (f.d) isDirty = "Dirty (*)";
    }
    const inTlb = state.snapshot.tlb.includes(p * 100 + pg);

    html += `
      <tr>
        <td><b>0x${pg.toString(16).toUpperCase()}</b></td>
        <td>${stateBadge}</td>
        <td>${pfnText}</td>
        <td>${isDirty}</td>
        <td>${inTlb ? '<b style="color:#38bdf8">HIT</b>' : '<span style="color:var(--text-dim)">-</span>'}</td>
      </tr>
    `;
  }
  html += `</table>`;
  ptContainer.innerHTML = html;
}

// Trend Chart
function renderTrendChart() {
  const svg = document.getElementById("trend-svg-chart");
  if (!svg || !state.snapshot) return;

  const history = state.snapshot.history.slice(-50);
  if (history.length < 2) {
    svg.innerHTML = "";
    return;
  }

  const w = 480;
  const h = 80;
  const maxVal = Math.max(1, ...history.map(pt => pt[0] + pt[1] + pt[2]));

  const getPoints = (metricIdx) => history.map((pt, i) => {
    const x = (i / (history.length - 1)) * w;
    const y = h - (pt[metricIdx] / maxVal) * (h - 10) - 5;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = `
    <polyline fill="none" stroke="#10b981" stroke-width="2" points="${getPoints(0)}"/>
    <polyline fill="none" stroke="#eab308" stroke-width="2" points="${getPoints(1)}"/>
    <polyline fill="none" stroke="#f43f5e" stroke-width="2" points="${getPoints(2)}"/>
  `;
}

// Baseline Comparison
async function renderBaselineComparison() {
  const container = document.getElementById("baseline-compare-container");
  if (!container || !state.snapshot) return;

  let comp = null;
  if (state.isBackendOnline) {
    try {
      const res = await fetch(`${state.apiBase}/algorithms/compare`);
      if (res.ok) comp = await res.json();
    } catch (e) {}
  }
  if (!comp) {
    comp = window.localKernel.getBaselineComparison();
  }

  container.innerHTML = `
    <table>
      <tr><th>Paging Architecture (${comp.access_count} accesses)</th><th>Disk Reads</th><th>Disk Writes</th></tr>
      <tr style="background:rgba(99,102,241,0.08);">
        <td><b>Windows Model (Working Sets + Standby/Modified Lists)</b></td>
        <td><b style="color:#10b981">${comp.windows_model.reads}</b></td>
        <td><b>${comp.windows_model.writes}</b></td>
      </tr>
      <tr>
        <td>Traditional Global FIFO (No Caching Lists)</td>
        <td><b style="color:#f43f5e">${comp.global_fifo.reads}</b></td>
        <td><b>${comp.global_fifo.writes}</b></td>
      </tr>
      <tr>
        <td>Traditional Global LRU (No Caching Lists)</td>
        <td><b style="color:#8b5cf6">${comp.global_lru.reads}</b></td>
        <td><b>${comp.global_lru.writes}</b></td>
      </tr>
    </table>
  `;
}

// Client-Side Simulation Engine (Standalone Fallback)
function initLocalKernel() {
  window.localKernel = {
    numFrames: 16,
    pagesPerProc: 10,
    currentProcess: 0,
    writeMode: false,
    clock: 0,
    trace: [],
    history: [],
    log: ["Windows VMM local standalone simulation engine initialized."],
    limits: [4, 4, 3],
    hotPages: [[0, 1, 2], [3, 4, 5], [6, 7, 8]],
    stats: { accesses: 0, hit: 0, soft: 0, hard: 0, rd: 0, wr: 0, tlb_hits: 0, tlb_misses: 0, fault_rate_pct: 0, tlb_hit_rate_pct: 0, soft_fault_ratio_pct: 0 },
    tlb: [],
    pfnDb: {
      frames: Array.from({ length: 16 }, (_, i) => ({ i, s: "free", p: -1, pg: -1, d: 0, u: 0 })),
      lists: { free: Array.from({ length: 16 }, (_, i) => i), zero: [], stby: [], mod: [] },
      moveFrame(f, s) {
        if (s !== "act" && f.s === "act") window.localKernel.tlbDrop(f.p, f.pg);
        for (const k in this.lists) {
          const idx = this.lists[k].indexOf(f.i);
          if (idx > -1) this.lists[k].splice(idx, 1);
        }
        f.s = s;
        if (s !== "act") this.lists[s].push(f.i);
      },
      stepZeroPageThread() {
        if (this.lists.free.length) {
          const f = this.frames[this.lists.free[0]];
          this.moveFrame(f, "zero");
          return f.i;
        }
        return null;
      }
    },
    reset(lim) {
      this.limits = lim || [4, 4, 3];
      this.clock = 0;
      this.trace = [];
      this.history = [];
      this.tlb = [];
      this.stats = { accesses: 0, hit: 0, soft: 0, hard: 0, rd: 0, wr: 0, tlb_hits: 0, tlb_misses: 0, fault_rate_pct: 0, tlb_hit_rate_pct: 0, soft_fault_ratio_pct: 0 };
      this.pfnDb.frames = Array.from({ length: 16 }, (_, i) => ({ i, s: "free", p: -1, pg: -1, d: 0, u: 0 }));
      this.pfnDb.lists = { free: Array.from({ length: 16 }, (_, i) => i), zero: [], stby: [], mod: [] };
      this.log = ["Windows Memory Manager reset to boot condition."];
    },
    tlbDrop(p, pg) {
      const idx = this.tlb.indexOf(p * 100 + pg);
      if (idx > -1) this.tlb.splice(idx, 1);
    },
    tlbLookup(p, pg) {
      const k = p * 100 + pg;
      const idx = this.tlb.indexOf(k);
      if (idx > -1) {
        this.tlb.splice(idx, 1);
        this.tlb.push(k);
        this.stats.tlb_hits++;
        return true;
      } else {
        this.stats.tlb_misses++;
        if (this.tlb.length >= 4) this.tlb.shift();
        this.tlb.push(k);
        return false;
      }
    },
    takeFrame() {
      const L = this.pfnDb.lists;
      if (L.zero.length) return this.pfnDb.frames[L.zero[0]];
      if (L.free.length) return this.pfnDb.frames[L.free[0]];
      if (!L.stby.length && L.mod.length) this.flushModified();
      if (L.stby.length) {
        const f = this.pfnDb.frames[L.stby[0]];
        this.log.unshift(`Reclaimed oldest standby frame #${f.i} (P${f.p + 1}:${f.pg} evicted)`);
        return f;
      }
      const actFrames = this.pfnDb.frames.filter(x => x.s === 'act');
      const victim = actFrames.sort((a, b) => a.u - b.u)[0];
      this.tlbDrop(victim.p, victim.pg);
      if (victim.d) this.stats.wr++;
      this.log.unshift(`Memory full: stole frame #${victim.i} from P${victim.p + 1}:${victim.pg}`);
      return victim;
    },
    trim(p) {
      let active;
      while ((active = this.pfnDb.frames.filter(f => f.s === 'act' && f.p === p)).length > this.limits[p]) {
        const victim = active.sort((a, b) => a.u - b.u)[0];
        this.pfnDb.moveFrame(victim, victim.d ? 'mod' : 'stby');
        this.log.unshift(`Trimmed P${p + 1}:${victim.pg} from working set to ${victim.d ? 'modified' : 'standby'} list`);
      }
    },
    accessPage(p, pg, isWrite) {
      this.clock++;
      this.trace.push([p, pg, isWrite ? 1 : 0]);
      this.tlbLookup(p, pg);

      let f = this.pfnDb.frames.find(x => x.p === p && x.pg === pg && x.s !== 'free' && x.s !== 'zero');
      let faultType = 'hard';

      if (f && f.s === 'act') {
        faultType = 'hit';
        this.stats.hit++;
        this.log.unshift(`HIT P${p + 1}:${pg} (${isWrite ? 'write' : 'read'})`);
      } else if (f) {
        faultType = 'soft';
        this.stats.soft++;
        const from = f.s;
        this.pfnDb.moveFrame(f, 'act');
        this.log.unshift(`SOFT fault P${p + 1}:${pg}: reattached from ${from} list (no disk read)`);
      } else {
        faultType = 'hard';
        f = this.takeFrame();
        this.pfnDb.moveFrame(f, 'act');
        f.p = p;
        f.pg = pg;
        f.d = 0;
        this.stats.hard++;
        this.stats.rd++;
        this.log.unshift(`HARD fault P${p + 1}:${pg}: read from disk into frame #${f.i}`);
      }

      if (isWrite) f.d = 1;
      f.u = this.clock;
      this.trim(p);
      this.pfnDb.stepZeroPageThread();

      const total = this.stats.hit + this.stats.soft + this.stats.hard;
      this.stats.accesses = total;
      this.stats.fault_rate_pct = total ? Math.round(((this.stats.soft + this.stats.hard) / total) * 100) : 0;
      this.history.push([this.stats.hit, this.stats.soft, this.stats.hard]);

      return { faultType, frame: f };
    },
    flushModified() {
      const mod = [...this.pfnDb.lists.mod];
      mod.forEach(idx => {
        const f = this.pfnDb.frames[idx];
        f.d = 0;
        this.stats.wr++;
        this.pfnDb.moveFrame(f, 'stby');
      });
      if (mod.length) {
        this.log.unshift(`Modified page writer: ${mod.length} dirty page(s) written to pagefile, moved to standby`);
      }
    },
    terminateProcess(p) {
      this.pfnDb.frames.filter(f => f.p === p && f.s !== 'free' && f.s !== 'zero').forEach(f => {
        f.p = -1;
        f.pg = -1;
        f.d = 0;
        this.pfnDb.moveFrame(f, 'free');
      });
      this.tlb = this.tlb.filter(k => Math.floor(k / 100) !== p);
      this.log.unshift(`Process P${p + 1} terminated: all frames returned to Free list`);
    },
    stepAuto() {
      const p = Math.floor(Math.random() * 3);
      const hot = this.hotPages[p];
      if (Math.random() < 0.1) {
        const base = Math.floor(Math.random() * 8);
        this.hotPages[p] = [base, base + 1, base + 2];
      }
      const pg = Math.random() < 0.8 ? hot[Math.floor(Math.random() * 3)] : Math.floor(Math.random() * 10);
      this.accessPage(p, pg, Math.random() < 0.3);
    },
    translateAndAccess(va, p, w) {
      const vpn = va >> 12;
      const off = va & 0xFFF;
      const tlbHit = this.tlb.includes(p * 100 + vpn);
      const res = this.accessPage(p, vpn, w);
      const pa = (res.frame.i << 12) | off;
      const msg = `VA 0x${va.toString(16).toUpperCase()} -> VPN ${vpn}, Offset 0x${off.toString(16).toUpperCase()}. TLB ${tlbHit ? 'HIT' : 'MISS'}, ${res.faultType.toUpperCase()} FAULT. Frame #${res.frame.i} => PA 0x${pa.toString(16).toUpperCase()}.`;
      return { message: msg, fault_type: res.faultType };
    },
    runScenario(id) {
      const configs = [
        { lim: [4, 4, 3], steps: () => {
          const t = [];
          for (let r = 0; r < 6; r++) {
            t.push([0, [0, 1, 2][r % 3], 0], [0, [0, 1, 2][r % 3], 0]);
            t.push([1, [3, 4, 5][r % 3], 0], [1, [3, 4, 5][r % 3], 0]);
            t.push([2, [6, 7][r % 2], 0], [2, [6, 7][r % 2], 0]);
          }
          return t;
        }},
        { lim: [1, 1, 1], steps: () => Array.from({ length: 60 }, (_, i) => [i % 3, Math.floor(i / 3) % 10, 0]) },
        { lim: [4, 4, 3], steps: () => Array.from({ length: 30 }, (_, i) => [0, i % 10, 0]) },
        { lim: [8, 8, 8], steps: () => {
          const t = [];
          for (let k = 0; k < 2; k++) for (let r = 0; r < 8; r++) for (let p = 0; p < 3; p++) t.push([p, r, 0]);
          return t;
        }},
        { lim: [4, 4, 3], steps: () => {
          const t = [];
          for (let i = 0; i < 10; i++) t.push([0, i, 1]);
          t.push(['flush']);
          for (let i = 0; i < 10; i++) t.push([0, i, 0]);
          return t;
        }},
        { lim: [4, 4, 3], steps: () => {
          const t = [];
          for (let i = 0; i < 4; i++) t.push([0, i, 0], [1, i, 0]);
          t.push(['kill', 0]);
          for (let i = 0; i < 4; i++) t.push([2, i, 0]);
          return t;
        }}
      ];
      const cfg = configs[id - 1];
      this.reset(cfg.lim);
      const steps = cfg.steps();
      steps.forEach(st => {
        if (st[0] === 'kill') this.terminateProcess(st[1]);
        else if (st[0] === 'flush') this.flushModified();
        else this.accessPage(st[0], st[1], Boolean(st[2]));
      });
    },
    runLab(workload, customStr) {
      let trace = [];
      if (workload === 'bel') trace = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5];
      else if (workload === 'loop') trace = Array.from({ length: 100 }, (_, i) => i % 10);
      else if (workload === 'ses') trace = this.trace.map(e => e[0] * 100 + e[1]);
      else if (workload === 'cus') trace = customStr.split(/[\s,]+/).map(Number).filter(x => !isNaN(x));
      else {
        let sd = 42;
        const r = () => (sd = (sd * 16807) % 2147483647) / 2147483647;
        let b = 0;
        for (let i = 0; i < 200; i++) {
          if (r() < 0.1) b = Math.floor(r() * 8);
          trace.push(r() < 0.85 ? b + Math.floor(r() * 4) : Math.floor(r() * 16));
        }
      }

      const simAlg = (algName, tr, F) => {
        let fr = [], rf = [], hd = 0, f = 0;
        for (let i = 0; i < tr.length; i++) {
          const k = tr[i], j = fr.indexOf(k);
          if (j > -1) {
            if (algName === 'LRU') { fr.splice(j, 1); fr.push(k); }
            if (algName === 'Clock') rf[j] = 1;
            continue;
          }
          f++;
          if (fr.length < F) { fr.push(k); rf.push(1); continue; }
          if (algName === 'FIFO' || algName === 'LRU') { fr.shift(); fr.push(k); }
          else if (algName === 'Clock') {
            while (rf[hd]) { rf[hd] = 0; hd = (hd + 1) % F; }
            fr[hd] = k; rf[hd] = 1; hd = (hd + 1) % F;
          } else {
            let v = 0, far = -1;
            fr.forEach((x, m) => {
              let n = tr.indexOf(x, i + 1);
              if (n < 0) n = 1e9;
              if (n > far) { far = n; v = m; }
            });
            fr[v] = k;
          }
        }
        return f;
      };

      const frames = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      const results = {
        FIFO: frames.map(f => simAlg('FIFO', trace, f)),
        LRU: frames.map(f => simAlg('LRU', trace, f)),
        Clock: frames.map(f => simAlg('Clock', trace, f)),
        OPT: frames.map(f => simAlg('OPT', trace, f))
      };

      const anomalies = [];
      for (let i = 0; i < frames.length - 1; i++) {
        if (results.FIFO[i + 1] > results.FIFO[i]) {
          anomalies.push({
            from_frames: frames[i],
            to_frames: frames[i + 1],
            faults_before: results.FIFO[i],
            faults_after: results.FIFO[i + 1]
          });
        }
      }

      return {
        workload,
        trace_length: trace.length,
        frame_range: frames,
        results,
        belady_anomalies: anomalies
      };
    },
    runSelfTests() {
      const bel = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5];
      const items = [];
      const sim = (a, tr, f) => this.runLab('cus', tr.join(' ')).results[a][f - 1];

      [
        ['FIFO on Belady String (3 frames)', 9, sim('FIFO', bel, 3)],
        ['FIFO on Belady String (4 frames - Anomaly)', 10, sim('FIFO', bel, 4)],
        ['LRU on Belady String (3 frames)', 10, sim('LRU', bel, 3)],
        ['LRU on Belady String (4 frames)', 8, sim('LRU', bel, 4)],
        ['OPT on Belady String (3 frames)', 7, sim('OPT', bel, 3)],
        ['OPT on Belady String (4 frames)', 6, sim('OPT', bel, 4)]
      ].forEach(([name, exp, act]) => {
        items.push({ name, expected: `${exp} faults`, actual: `${act} faults`, passed: exp === act });
      });

      const passed = items.filter(x => x.passed).length;
      return {
        total_tests: items.length,
        passed_tests: passed,
        failed_tests: items.length - passed,
        success_rate_pct: Math.round((passed / items.length) * 100),
        results: items
      };
    },
    getBaselineComparison() {
      const runBase = (pol) => {
        let fr = [], f = 0, wr = 0;
        const d = {};
        for (const [p, pg, w] of this.trace) {
          const k = p * 100 + pg, idx = fr.indexOf(k);
          if (idx > -1) {
            if (pol === 'LRU') { fr.splice(idx, 1); fr.push(k); }
          } else {
            f++;
            if (fr.length >= 16) {
              const victim = fr.shift();
              if (d[victim]) { wr++; delete d[victim]; }
            }
            fr.push(k);
          }
          if (w) d[k] = 1;
        }
        return { reads: f, writes: wr };
      };
      return {
        access_count: this.trace.length,
        windows_model: { reads: this.stats.rd, writes: this.stats.wr },
        global_fifo: runBase('FIFO'),
        global_lru: runBase('LRU')
      };
    },
    getSnapshot() {
      const isThrashing = (() => {
        const r = this.history.slice(-20);
        return r.length >= 20 && (r[19][2] - r[0][2] >= 10) && !this.pfnDb.lists.free.length && !this.pfnDb.lists.zero.length;
      })();
      return {
        timestamp: this.clock,
        frames: this.pfnDb.frames.map(f => ({ ...f })),
        lists: {
          free: [...this.pfnDb.lists.free],
          zero: [...this.pfnDb.lists.zero],
          stby: [...this.pfnDb.lists.stby],
          mod: [...this.pfnDb.lists.mod]
        },
        working_sets: [0, 1, 2].map(p => {
          const active = this.pfnDb.frames.filter(f => f.s === 'act' && f.p === p).sort((a, b) => a.pg - b.pg);
          const colors = ["#10b981", "#8b5cf6", "#f97316"];
          return {
            process_id: p,
            process_name: `Process P${p + 1}`,
            limit: this.limits[p],
            active_pages: active.map(f => f.pg),
            active_count: active.length,
            color: colors[p]
          };
        }),
        stats: { ...this.stats },
        log: [...this.log],
        tlb: [...this.tlb],
        history: this.history.map(h => [...h]),
        current_process: this.currentProcess,
        write_mode: this.writeMode,
        is_thrashing: isThrashing
      };
    }
  };
}
