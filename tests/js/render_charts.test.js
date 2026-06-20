const assert = require("node:assert/strict");
const test = require("node:test");

global.document = { body: {}, addEventListener: () => {} };
global.getComputedStyle = () => ({ getPropertyValue: () => "" });

const {
  buildOmniChartOption,
  compareNullableNumber,
  selectDefaultVisibleSeriesKeys,
} = require("../../docs/assets/js/render_charts.js");

function series(key, meta) {
  return {
    __omniSeriesKey: key,
    data: [{ meta }],
  };
}

function record(name, maxConcurrency, inputLen, metricValue) {
  return {
    config_key: name,
    scenario: name,
    test_name: name,
    dataset_name: "random",
    max_concurrency: maxConcurrency,
    num_prompts: 10,
    random_input_len: inputLen,
    random_output_len: 100,
    mean_ttft_ms: metricValue,
    sort_timestamp: "2026-06-01T00:00:00",
    date: "2026-06-01 00:00:00",
  };
}

function colorBySeriesKey(option) {
  return Object.fromEntries(
    option.series
      .filter((item) => item.type === "line")
      .map((item) => [item.__omniSeriesKey, item.color]),
  );
}

test("nullable number comparison keeps missing values stable and last", () => {
  assert.equal(compareNullableNumber(null, null), 0);
  assert.equal(compareNullableNumber(null, 1), 1);
  assert.equal(compareNullableNumber(1, null), -1);
  assert.equal(compareNullableNumber(1, 2, "asc"), -1);
  assert.equal(compareNullableNumber(1, 2, "desc"), 1);
});

test("key scenario selection covers long sequence, high throughput, and low latency", () => {
  const selected = selectDefaultVisibleSeriesKeys(
    [
      series("long", { max_concurrency: 8, random_input_len: 2500 }),
      series("high", { max_concurrency: 32, random_input_len: 100 }),
      series("low", { max_concurrency: 1, random_input_len: 100 }),
      series("missing-a", { random_input_len: 100 }),
      series("missing-b", { random_input_len: 100 }),
    ],
    3,
  );

  assert.deepEqual([...selected], ["long", "high", "low"]);
});

test("series colors stay stable between key scenarios and all series views", () => {
  const metricGroup = { metrics: ["mean_ttft_ms"] };
  const groupFields = ["scenario"];
  const records = [
    record("long", 8, 2500, 10),
    record("middle", 16, 100, 20),
    record("high", 32, 100, 30),
    record("low", 1, 100, 40),
  ];
  const allOption = buildOmniChartOption(metricGroup, records, groupFields, true);
  const visibleKeys = new Set([
    "mean_ttft_ms::long",
    "mean_ttft_ms::high",
    "mean_ttft_ms::low",
  ]);
  const keyOption = buildOmniChartOption(metricGroup, records, groupFields, true, visibleKeys);
  const allColors = colorBySeriesKey(allOption);
  const keyColors = colorBySeriesKey(keyOption);

  visibleKeys.forEach((key) => {
    assert.equal(keyColors[key], allColors[key]);
  });
});
