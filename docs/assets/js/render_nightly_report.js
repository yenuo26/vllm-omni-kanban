function reportPageRoot() {
  return document.querySelector("[data-nightly-report-page]");
}

function resolveReportAssetUrl(entry) {
  const page = reportPageRoot();
  const base = page?.dataset.nightlyReportBase?.trim();
  const filename = entry?.filename || entry?.url?.split("/").pop() || "";
  if (!filename) {
    throw new Error("Report entry is missing a filename");
  }
  if (base) {
    const baseUrl = new URL(base.endsWith("/") ? base : `${base}/`, window.location.href).href;
    return new URL(filename, baseUrl).href;
  }
  return new URL(entry.url || filename, window.location.href).href;
}

async function fetchReportManifest(src) {
  const url = new URL(src, window.location.href).href;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load report manifest (${response.status})`);
  }
  return response.json();
}

function setReportType(root, type) {
  root.querySelectorAll("[data-report-type]").forEach((button) => {
    const active = button.dataset.reportType === type;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });

  const nightlyView = root.querySelector('[data-report-view="nightly"]');
  const releaseView = root.querySelector('[data-report-view="release"]');
  const isNightly = type === "nightly";

  if (nightlyView) {
    nightlyView.hidden = !isNightly;
  }
  if (releaseView) {
    releaseView.hidden = isNightly;
  }
  root.querySelectorAll("[data-report-log-filter]").forEach((filter) => {
    filter.hidden = !isNightly;
  });
}

function populateLogSelect(select, entries, selectedId) {
  select.innerHTML = "";
  if (!entries.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No reports available";
    select.append(option);
    select.disabled = true;
    return;
  }
  select.disabled = false;
  entries.forEach((entry) => {
    const option = document.createElement("option");
    option.value = entry.id;
    option.textContent = entry.label || entry.date || entry.id;
    if (entry.id === selectedId) {
      option.selected = true;
    }
    select.append(option);
  });
}

function loadReportIntoFrame(root, entry) {
  const frame = root.querySelector("[data-report-frame]");
  const empty = root.querySelector("[data-report-empty]");
  if (!frame) {
    return;
  }
  if (!entry) {
    frame.hidden = true;
    frame.removeAttribute("src");
    if (empty) {
      empty.hidden = false;
      empty.textContent = "暂无 nightly 测试报告。";
    }
    return;
  }
  if (empty) {
    empty.hidden = true;
  }
  frame.hidden = false;
  frame.src = resolveReportAssetUrl(entry);
}

async function initNightlyReportPage() {
  const root = reportPageRoot();
  if (!root) {
    return;
  }

  const manifestSrc = root.dataset.nightlyReportManifest;
  if (!manifestSrc) {
    return;
  }

  let manifest;
  try {
    manifest = await fetchReportManifest(manifestSrc);
  } catch (error) {
    const empty = root.querySelector("[data-report-empty]");
    if (empty) {
      empty.hidden = false;
      empty.textContent = `Failed to load reports: ${error.message}`;
    }
    return;
  }

  root._nightlyReportManifest = manifest;
  const logSelect = root.querySelector("[data-report-log-select]");
  const nightlyEntries = manifest.nightly || [];
  const defaultEntry = nightlyEntries[0] || null;
  if (logSelect) {
    populateLogSelect(logSelect, nightlyEntries, defaultEntry?.id || "");
  }

  setReportType(root, "nightly");
  loadReportIntoFrame(root, defaultEntry);

  root.querySelectorAll("[data-report-type]").forEach((button) => {
    button.addEventListener("click", () => {
      const type = button.dataset.reportType;
      setReportType(root, type);
      if (type === "nightly") {
        const selectedId = logSelect?.value || nightlyEntries[0]?.id;
        const entry = nightlyEntries.find((item) => item.id === selectedId) || nightlyEntries[0] || null;
        loadReportIntoFrame(root, entry);
      }
    });
  });

  logSelect?.addEventListener("change", () => {
    const entry = nightlyEntries.find((item) => item.id === logSelect.value) || null;
    loadReportIntoFrame(root, entry);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initNightlyReportPage();
});
