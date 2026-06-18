# Test Report

<p class="dashboard-intro">
Browse nightly Buildkite and local test reports. Use the tabs to switch report type and the date selector to pick a nightly run.
</p>

<section
  class="omni-report-page"
  data-nightly-report-page
  data-nightly-report-manifest="../../assets/nightly_reports/manifest.json"
  data-nightly-report-base="../../assets/nightly_reports/"
  markdown="1"
>

<div class="omni-section">
  <div class="omni-report-toolbar">
    <div class="omni-report-type-toggle" role="tablist" aria-label="Report type">
      <button type="button" class="omni-report-type-btn is-active" data-report-type="nightly" role="tab" aria-selected="true">Nightly</button>
      <button type="button" class="omni-report-type-btn" data-report-type="release" role="tab" aria-selected="false">Release</button>
    </div>
    <label class="omni-report-log-filter" data-report-log-filter>
      <span class="omni-report-log-filter__label">日期</span>
      <select class="omni-report-log-filter__select" data-report-log-select aria-label="Select nightly report date"></select>
    </label>
  </div>
</div>

<div class="omni-report-panel" data-report-view="nightly">
  <div class="omni-empty-state" data-report-empty hidden>Loading report…</div>
  <iframe
    class="omni-report-frame"
    data-report-frame
    title="Nightly test report"
    hidden
  ></iframe>
</div>

<div class="omni-report-panel omni-report-panel--empty" data-report-view="release" hidden>
  <div class="omni-empty-state">暂无内容</div>
</div>

</section>
