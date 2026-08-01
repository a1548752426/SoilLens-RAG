const elements = {
  form: document.querySelector("#questionForm"),
  input: document.querySelector("#questionInput"),
  askButton: document.querySelector("#askButton"),
  useLlm: document.querySelector("#useLlm"),
  modeBadge: document.querySelector("#modeBadge"),
  profileNotice: document.querySelector("#profileNotice"),
  privacyNote: document.querySelector("#privacyNote"),
  heroLabel: document.querySelector("#heroLabel"),
  heroDescription: document.querySelector("#heroDescription"),
  libraryStats: document.querySelector("#libraryStats"),
  documentList: document.querySelector("#documentList"),
  rebuildButton: document.querySelector("#rebuildButton"),
  resultPanel: document.querySelector("#resultPanel"),
  emptyState: document.querySelector("#emptyState"),
  resultQuestion: document.querySelector("#resultQuestion"),
  resultMode: document.querySelector("#resultMode"),
  warningBox: document.querySelector("#warningBox"),
  answerBox: document.querySelector("#answerBox"),
  sourceCount: document.querySelector("#sourceCount"),
  sourceList: document.querySelector("#sourceList"),
  qaView: document.querySelector("#qaView"),
  assessmentView: document.querySelector("#assessmentView"),
  batchView: document.querySelector("#batchView"),
  evaluationView: document.querySelector("#evaluationView"),
  sampleSelect: document.querySelector("#sampleSelect"),
  customNameField: document.querySelector("#customNameField"),
  customSampleName: document.querySelector("#customSampleName"),
  sampleCount: document.querySelector("#sampleCount"),
  metalInputs: document.querySelector("#metalInputs"),
  datasetNote: document.querySelector("#datasetNote"),
  backgroundSourceLink: document.querySelector("#backgroundSourceLink"),
  assessButton: document.querySelector("#assessButton"),
  assessmentResult: document.querySelector("#assessmentResult"),
  assessmentTitle: document.querySelector("#assessmentTitle"),
  assessmentScope: document.querySelector("#assessmentScope"),
  summaryCards: document.querySelector("#summaryCards"),
  assessmentWarnings: document.querySelector("#assessmentWarnings"),
  assessmentRows: document.querySelector("#assessmentRows"),
  formulaList: document.querySelector("#formulaList"),
  resultSourceLink: document.querySelector("#resultSourceLink"),
  batchRefreshButton: document.querySelector("#batchRefreshButton"),
  batchLoading: document.querySelector("#batchLoading"),
  batchDashboard: document.querySelector("#batchDashboard"),
  batchScope: document.querySelector("#batchScope"),
  batchSummaryCards: document.querySelector("#batchSummaryCards"),
  batchNote: document.querySelector("#batchNote"),
  pliDistributionChart: document.querySelector("#pliDistributionChart"),
  metalExceedanceChart: document.querySelector("#metalExceedanceChart"),
  topSamplesChart: document.querySelector("#topSamplesChart"),
  batchSearchInput: document.querySelector("#batchSearchInput"),
  batchGradeFilter: document.querySelector("#batchGradeFilter"),
  batchVisibleCount: document.querySelector("#batchVisibleCount"),
  batchRows: document.querySelector("#batchRows"),
  evaluationRunButton: document.querySelector("#evaluationRunButton"),
  evaluationDataset: document.querySelector("#evaluationDataset"),
  evaluationLoading: document.querySelector("#evaluationLoading"),
  evaluationDashboard: document.querySelector("#evaluationDashboard"),
  evaluationScope: document.querySelector("#evaluationScope"),
  evaluationSummaryCards: document.querySelector("#evaluationSummaryCards"),
  evaluationNote: document.querySelector("#evaluationNote"),
  evaluationComparison: document.querySelector("#evaluationComparison"),
  evaluationDocumentChart: document.querySelector("#evaluationDocumentChart"),
  evaluationFilter: document.querySelector("#evaluationFilter"),
  evaluationVisibleCount: document.querySelector("#evaluationVisibleCount"),
  evaluationRows: document.querySelector("#evaluationRows"),
};

let assessmentConfig = null;
let assessmentSamples = [];
let batchData = null;
let batchLoaded = false;
let batchCharts = [];
let evaluationData = null;
let evaluationLoaded = false;
let evaluationCharts = [];
let appProfile = { id: "private", public_demo: false };

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatAnswer(value) {
  return escapeHtml(value).replace(/\[(S\d+)\]/g, '<span class="citation-token">[$1]</span>');
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `请求失败：${response.status}`);
  }
  return data;
}

function renderDocuments(documents) {
  elements.documentList.innerHTML = documents
    .map(
      (document, index) => `
        <article class="document-item">
          <div class="document-number">${String(index + 1).padStart(2, "0")}</div>
          <div>
            <strong title="${escapeHtml(document.title)}">${escapeHtml(document.title)}</strong>
            <span>${document.pages} ${escapeHtml(document.location_label || "页")}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

async function loadStatus() {
  const [status, library] = await Promise.all([
    requestJson("/api/status"),
    requestJson("/api/documents"),
  ]);
  appProfile = status.profile || appProfile;
  const locationLabel = appProfile.public_demo ? "节" : "页";
  const libraryLabel = appProfile.public_demo ? "篇演示文档" : "篇论文";
  elements.libraryStats.textContent =
    `${status.index.documents} ${libraryLabel} · ${status.index.pages} ${locationLabel} · ${status.index.chunks} 个证据片段`;
  const modelMode = status.llm.available
    ? `${status.llm.model} · ${status.retrieval.mode}`
    : status.retrieval.mode;
  elements.modeBadge.textContent = `● ${appProfile.label || "本机模式"} · ${modelMode}`;
  elements.useLlm.checked = Boolean(status.llm.available);
  elements.useLlm.disabled = !status.llm.available;
  if (appProfile.public_demo) {
    elements.profileNotice.textContent = appProfile.notice;
    elements.profileNotice.classList.remove("hidden");
    elements.privacyNote.lastChild.textContent = " 仅使用原创演示材料和合成数据";
    elements.heroLabel.textContent = "公开安全演示 · 原创知识材料";
    elements.heroDescription.textContent =
      "系统先检索演示文档，再回答问题；每条来源都可回到对应文档章节。";
    const demoSuggestions = [
      "综合污染指数 PLI 如何计算？",
      "植物修复有哪些基本路径？",
      "强化植物修复可能带来哪些二次风险？",
      "空间交叉验证如何避免信息泄漏？",
    ];
    document.querySelectorAll(".suggestions button").forEach((button, index) => {
      button.textContent = demoSuggestions[index] || button.textContent;
    });
    const evaluationTab = document.querySelector('[data-view="evaluation"]');
    if (evaluationTab) evaluationTab.classList.add("hidden");
  }
  renderDocuments(library.documents);
}

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (Math.abs(number) >= 100) return number.toFixed(1);
  if (Math.abs(number) >= 10) return number.toFixed(2);
  return number.toFixed(digits);
}

function formatPercent(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function currentSample() {
  if (elements.sampleSelect.value === "__custom__") return null;
  return assessmentSamples.find(
    (sample) => String(sample.sample_id) === String(elements.sampleSelect.value),
  );
}

function renderMetalInputs(sample) {
  if (!assessmentConfig || !sample) return;
  elements.metalInputs.innerHTML = assessmentConfig.available_metals
    .map(
      (metal) => `
        <label class="metal-field">
          <span>${escapeHtml(metal)}</span>
          <div>
            <input
              data-metal="${escapeHtml(metal)}"
              type="number"
              min="0"
              step="any"
              value="${escapeHtml(sample.concentrations[metal] ?? "")}"
              aria-label="${escapeHtml(metal)} 浓度"
            />
            <small>mg/kg</small>
          </div>
          <em>背景 ${formatNumber(assessmentConfig.background_values[metal])}</em>
        </label>
      `,
    )
    .join("");
}

function renderAssessmentModeNote(sample) {
  elements.datasetNote.textContent = sample
    ? assessmentConfig.note
    : assessmentConfig.synthetic
      ? "自定义样点只按已填写的元素计算；公开演示中的已有样点均为合成数据。"
      : "自定义样点只按已填写的元素计算；输入内容不会写入或修改私有 Excel。";
}

async function loadAssessmentData() {
  const [config, sampleData] = await Promise.all([
    requestJson("/api/assessment/config"),
    requestJson("/api/assessment/samples"),
  ]);
  assessmentConfig = config;
  assessmentSamples = sampleData.samples;
  elements.sampleCount.textContent = config.dataset_available
    ? `${config.sample_count} 个${config.synthetic ? "合成演示" : "私有"}样点`
    : "手动输入模式";
  elements.backgroundSourceLink.href = config.source.url;
  elements.backgroundSourceLink.textContent =
    `查看背景值来源：${config.source.table}，第 ${config.source.page} ${config.source.location_label || "页"} ↗`;
  elements.resultSourceLink.href = config.source.url;
  elements.resultSourceLink.textContent =
    `《${config.source.title}》${config.source.table}，第 ${config.source.page} ${config.source.location_label || "页"}`;
  elements.sampleSelect.disabled = false;
  const privateOptions = assessmentSamples
    .map(
      (sample) =>
        `<option value="${escapeHtml(sample.sample_id)}">${escapeHtml(sample.sample_id)} · ${escapeHtml(sample.name)}</option>`,
    )
    .join("");
  elements.sampleSelect.innerHTML =
    `<option value="__custom__">＋ 自定义样点（可只填部分元素）</option>${privateOptions}`;
  elements.customNameField.classList.remove("hidden");
  renderMetalInputs({ sample_id: "", name: "自定义样点", concentrations: {} });
  renderAssessmentModeNote(null);
}

function gradeClass(grade) {
  if (grade.includes("极高") || grade.includes("极强")) return "grade grade-high";
  if (grade.includes("较高") || grade.includes("强污染")) return "grade grade-elevated";
  if (grade.includes("中等") || grade.includes("中度")) return "grade grade-medium";
  return "grade grade-low";
}

function renderAssessment(result) {
  const summary = result.summary;
  const sampleLabel = [result.sample.sample_id, result.sample.name].filter(Boolean).join(" · ");
  elements.assessmentTitle.textContent = sampleLabel || "自定义样点";
  elements.assessmentScope.textContent = `${summary.metal_count} 种金属`;
  elements.summaryCards.innerHTML = `
    <article class="summary-card summary-primary">
      <span>综合污染指数 PLI</span>
      <strong>${formatNumber(summary.pli)}</strong>
      <em>${escapeHtml(summary.pli_grade)}</em>
    </article>
    <article class="summary-card">
      <span>超过背景值</span>
      <strong>${summary.exceeded_count}/${summary.metal_count}</strong>
      <em>种元素</em>
    </article>
    <article class="summary-card">
      <span>最高 CF</span>
      <strong>${escapeHtml(summary.max_cf_metal)}</strong>
      <em>${formatNumber(summary.max_cf)} 倍背景值</em>
    </article>
    <article class="summary-card">
      <span>最高 Igeo</span>
      <strong>${escapeHtml(summary.max_igeo_metal || "—")}</strong>
      <em>${formatNumber(summary.max_igeo)}</em>
    </article>
  `;
  elements.assessmentWarnings.innerHTML = result.warnings
    .map((warning) => `<div class="warning">${escapeHtml(warning)}</div>`)
    .join("");
  elements.assessmentRows.innerHTML = result.results
    .map(
      (row) => `
        <tr>
          <td><strong>${escapeHtml(row.metal)}</strong>${row.exceeded ? '<span class="exceeded-dot" title="超过背景值"></span>' : ""}</td>
          <td>${formatNumber(row.concentration)}</td>
          <td>${formatNumber(row.background)}</td>
          <td>${formatNumber(row.cf)}</td>
          <td><span class="${gradeClass(row.cf_grade)}">${escapeHtml(row.cf_grade)}</span></td>
          <td>${formatNumber(row.igeo)}</td>
          <td><span class="${gradeClass(row.igeo_grade)}">${escapeHtml(row.igeo_grade)}</span></td>
        </tr>
      `,
    )
    .join("");
  elements.formulaList.innerHTML = Object.values(result.method)
    .map((formula) => `<code>${escapeHtml(formula)}</code>`)
    .join("");
  elements.assessmentResult.classList.remove("hidden");
  elements.assessmentResult.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runAssessment() {
  const sample = currentSample();
  const customName = elements.customSampleName.value.trim() || "自定义样点";
  const concentrations = {};
  elements.metalInputs.querySelectorAll("input[data-metal]").forEach((input) => {
    if (input.value.trim() !== "") concentrations[input.dataset.metal] = Number(input.value);
  });
  elements.assessButton.disabled = true;
  elements.assessButton.firstElementChild.textContent = "正在计算…";
  try {
    const result = await requestJson("/api/assessment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sample_id: sample?.sample_id || null,
        name: sample?.name || customName,
        concentrations,
      }),
    });
    renderAssessment(result);
  } catch (error) {
    window.alert(error.message);
  } finally {
    elements.assessButton.disabled = false;
    elements.assessButton.firstElementChild.textContent = "开始评价";
  }
}

function renderBatchSummary(data) {
  const summary = data.summary;
  elements.batchScope.textContent = `${summary.sample_count} 个样点 · ${summary.metal_count} 种金属`;
  elements.batchNote.textContent = data.note;
  elements.batchSummaryCards.innerHTML = `
    <article class="summary-card summary-primary">
      <span>批量评价样点</span>
      <strong>${summary.sample_count}</strong>
      <em>${summary.metal_count} 种金属参与计算</em>
    </article>
    <article class="summary-card">
      <span>PLI &gt; 1</span>
      <strong>${summary.polluted_count}</strong>
      <em>占全部样点 ${formatPercent(summary.polluted_rate)}</em>
    </article>
    <article class="summary-card">
      <span>最高 PLI 样点</span>
      <strong>${formatNumber(summary.max_pli)}</strong>
      <em title="${escapeHtml(summary.max_pli_sample_name)}">${escapeHtml(summary.max_pli_sample_id)} · ${escapeHtml(summary.max_pli_sample_name)}</em>
    </article>
    <article class="summary-card">
      <span>超背景率最高元素</span>
      <strong>${escapeHtml(summary.highest_exceedance_metal)}</strong>
      <em>${formatPercent(summary.highest_exceedance_rate)} 的样点超过背景值</em>
    </article>
  `;
}

function createChart(element, option) {
  if (!window.echarts) throw new Error("本地图表组件未加载。");
  const chart = window.echarts.init(element, null, { renderer: "svg" });
  chart.setOption(option);
  batchCharts.push(chart);
  return chart;
}

function renderBatchCharts(data) {
  batchCharts.forEach((chart) => chart.dispose());
  batchCharts = [];

  const commonText = {
    color: "#53635a",
    fontFamily: 'Inter, "Microsoft YaHei", sans-serif',
  };
  const distribution = Object.entries(data.pli_grade_distribution).map(([name, value]) => ({
    name,
    value,
  }));
  createChart(elements.pliDistributionChart, {
    color: ["#7FAF8B", "#D6B15E", "#C8734D"],
    tooltip: { trigger: "item", formatter: "{b}<br/>{c} 个样点（{d}%）" },
    legend: { bottom: 0, textStyle: { ...commonText, fontSize: 11 } },
    series: [
      {
        type: "pie",
        radius: ["48%", "70%"],
        center: ["50%", "43%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "#fffdf8", borderWidth: 4, borderRadius: 6 },
        label: { formatter: "{c}", color: "#183126", fontWeight: 700 },
        data: distribution,
      },
    ],
  });

  createChart(elements.metalExceedanceChart, {
    color: ["#3D8A68"],
    grid: { left: 48, right: 20, top: 18, bottom: 38 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value) => `${Number(value).toFixed(1)}%`,
    },
    xAxis: {
      type: "category",
      data: data.metal_summary.map((row) => row.metal),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#cfd6cd" } },
      axisLabel: { ...commonText, fontSize: 11 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { ...commonText, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#e8ebe4" } },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 34,
        itemStyle: { borderRadius: [6, 6, 0, 0] },
        data: data.metal_summary.map((row) => Number((row.exceeded_rate * 100).toFixed(2))),
      },
    ],
  });

  const topSamples = [...data.top_samples].reverse();
  createChart(elements.topSamplesChart, {
    color: ["#C88D42"],
    grid: { left: 150, right: 36, top: 12, bottom: 32 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items) => {
        const item = items[0];
        const sample = topSamples[item.dataIndex];
        return `${escapeHtml(sample.sample_id)} · ${escapeHtml(sample.name)}<br/>PLI：${formatNumber(sample.pli)}`;
      },
    },
    xAxis: {
      type: "value",
      axisLabel: { ...commonText },
      splitLine: { lineStyle: { color: "#e8ebe4" } },
    },
    yAxis: {
      type: "category",
      data: topSamples.map((row) => `${row.sample_id} · ${row.name}`),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        ...commonText,
        width: 125,
        overflow: "truncate",
        fontSize: 11,
      },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 22,
        itemStyle: { borderRadius: [0, 5, 5, 0] },
        data: topSamples.map((row) => Number(row.pli.toFixed(4))),
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "#9B6650", type: "dashed" },
          label: { formatter: "PLI = 1", color: "#7a5b4b" },
          data: [{ xAxis: 1 }],
        },
      },
    ],
  });
}

function renderBatchRows() {
  if (!batchData) return;
  const query = elements.batchSearchInput.value.trim().toLowerCase();
  const filter = elements.batchGradeFilter.value;
  const filtered = batchData.samples.filter((row) => {
    const matchesQuery =
      !query ||
      String(row.sample_id).toLowerCase().includes(query) ||
      String(row.name).toLowerCase().includes(query);
    const matchesGrade =
      filter === "all" ||
      (filter === "polluted" && row.pli > 1) ||
      (filter === "clean" && row.pli <= 1);
    return matchesQuery && matchesGrade;
  });
  elements.batchVisibleCount.textContent = `显示 ${filtered.length}/${batchData.samples.length} 个样点`;
  elements.batchRows.innerHTML = filtered
    .map((row) => {
      const rank = batchData.samples.findIndex((sample) => sample.sample_id === row.sample_id) + 1;
      const statusClass = row.pli > 1 ? "grade grade-elevated" : "grade grade-low";
      return `
        <tr>
          <td><span class="rank-number">${rank}</span></td>
          <td>
            <strong>${escapeHtml(row.sample_id)} · ${escapeHtml(row.name)}</strong>
          </td>
          <td><strong>${formatNumber(row.pli)}</strong></td>
          <td><span class="${statusClass}">${escapeHtml(row.pli_grade)}</span></td>
          <td>${row.exceeded_count}/${row.metal_count}</td>
          <td>${escapeHtml(row.max_cf_metal)} · ${formatNumber(row.max_cf)}</td>
          <td><button class="detail-button" data-sample-id="${escapeHtml(row.sample_id)}">查看详情</button></td>
        </tr>
      `;
    })
    .join("");
}

function renderBatchDashboard(data) {
  renderBatchSummary(data);
  renderBatchRows();
  elements.batchLoading.classList.add("hidden");
  elements.batchDashboard.classList.remove("hidden");
  requestAnimationFrame(() => renderBatchCharts(data));
}

function shortPaperTitle(title) {
  if (title.startsWith("Bioinspired")) return "仿生人工植物";
  if (title.startsWith("Bioremediation")) return "农田生物修复";
  if (title.startsWith("Characteristics")) return "喀斯特县域";
  if (title.startsWith("Machine learning")) return "机器学习背景值";
  if (title.startsWith("Research on the role")) return "竹类修复";
  return title;
}

function percentagePointDelta(current, baseline) {
  const delta = (Number(current) - Number(baseline)) * 100;
  if (Math.abs(delta) < 0.05) return "持平";
  return `${delta > 0 ? "+" : ""}${delta.toFixed(1)} 个百分点`;
}

function renderEvaluationSummary(data) {
  const current = data.current.summary;
  const baseline = data.baseline.summary;
  elements.evaluationScope.textContent =
    `${data.dataset_label} · ${current.question_count} 题 · Recall@${current.top_k}`;
  elements.evaluationNote.textContent = data.note;
  const metrics = [
    ["正确页码命中率", "page_hit_at_k"],
    ["正常问题接受率", "answerable_acceptance_rate"],
    ["越界问题拒答率", "unanswerable_rejection_rate"],
    ["边界判断准确率", "scope_boundary_accuracy"],
  ];
  elements.evaluationSummaryCards.innerHTML = metrics
    .map(
      ([label, key], index) => `
        <article class="summary-card ${index === 1 ? "summary-primary" : ""}">
          <span>${label}</span>
          <strong>${formatPercent(current[key])}</strong>
          <em>基线 ${formatPercent(baseline[key])}</em>
        </article>
      `,
    )
    .join("");
  elements.evaluationComparison.innerHTML = metrics
    .concat([
      ["文档命中率", "document_recall_at_k"],
      ["综合通过率", "overall_pass_rate"],
    ])
    .map(
      ([label, key]) => `
        <div class="metric-row">
          <span>${label}</span>
          <div>
            <small>${formatPercent(baseline[key])}</small>
            <b aria-hidden="true">→</b>
            <strong>${formatPercent(current[key])}</strong>
          </div>
          <em>${percentagePointDelta(current[key], baseline[key])}</em>
        </div>
      `,
    )
    .join("");
}

function renderEvaluationChart(data) {
  evaluationCharts.forEach((chart) => chart.dispose());
  evaluationCharts = [];
  if (!window.echarts) throw new Error("本地图表组件未加载。");
  const baselineByTitle = Object.fromEntries(
    data.baseline.per_document.map((row) => [row.title, row.page_hit_at_k]),
  );
  const rows = data.current.per_document;
  const chart = window.echarts.init(elements.evaluationDocumentChart, null, {
    renderer: "svg",
  });
  chart.setOption({
    color: ["#C9BBA0", "#3D8A68"],
    grid: { left: 112, right: 24, top: 22, bottom: 42 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value) => `${Number(value).toFixed(0)}%`,
    },
    legend: {
      bottom: 0,
      data: ["优化前", "当前"],
      textStyle: { color: "#53635a", fontSize: 11 },
    },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { color: "#53635a", formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#e8ebe4" } },
    },
    yAxis: {
      type: "category",
      data: rows.map((row) => shortPaperTitle(row.title)),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: "#53635a", fontSize: 11 },
    },
    series: [
      {
        name: "优化前",
        type: "bar",
        barMaxWidth: 17,
        data: rows.map((row) =>
          Number(((baselineByTitle[row.title] || 0) * 100).toFixed(1)),
        ),
      },
      {
        name: "当前",
        type: "bar",
        barMaxWidth: 17,
        itemStyle: { borderRadius: [0, 4, 4, 0] },
        data: rows.map((row) => Number((row.page_hit_at_k * 100).toFixed(1))),
      },
    ],
  });
  evaluationCharts.push(chart);
}

function renderEvaluationRows() {
  if (!evaluationData) return;
  const filter = elements.evaluationFilter.value;
  const cases = evaluationData.current.cases.filter((row) => {
    if (filter === "failed") return !row.passed;
    if (filter === "passed") return row.passed;
    if (filter === "answerable") return row.answerable;
    if (filter === "unanswerable") return !row.answerable;
    return true;
  });
  elements.evaluationVisibleCount.textContent =
    `显示 ${cases.length}/${evaluationData.current.cases.length} 题`;
  elements.evaluationRows.innerHTML = cases
    .map((row) => {
      const expected = row.answerable
        ? `<a href="${escapeHtml(row.expected_url)}" target="_blank" rel="noreferrer">
             ${escapeHtml(shortPaperTitle(row.expected_title))} · PDF 第 ${row.expected_pages.join("/")} 页 ↗
           </a>`
        : '<span class="muted-text">应拒绝作答</span>';
      const topResult = row.top_url
        ? `<a href="${escapeHtml(row.top_url)}" target="_blank" rel="noreferrer">
             ${escapeHtml(shortPaperTitle(row.top_title))} · PDF 第 ${row.top_page} 页 ↗
           </a>
           <small>
             ${escapeHtml(row.retrieval_method || "关键词检索")}
             · 语义${row.top_semantic_score === null ? "—" : `${(row.top_semantic_score * 100).toFixed(1)}%`}
             · 关键词 ${(row.top_lexical_score * 100).toFixed(1)}%
           </small>`
        : '<span class="muted-text">没有检索结果</span>';
      const detail = row.answerable
        ? `${row.decision.label} · 文档${row.document_hit ? "✓" : "×"} · 页码${row.page_hit ? "✓" : "×"}`
        : row.predicted_answerable
          ? "未拒答"
          : `已拒答 · ${row.decision.label}`;
      return `
        <tr>
          <td><strong>${escapeHtml(row.id)}</strong><small>${escapeHtml(row.category)}</small></td>
          <td>${escapeHtml(row.question)}</td>
          <td>${expected}</td>
          <td>${topResult}</td>
          <td>
            <span class="grade ${row.passed ? "grade-low" : "grade-high"}">
              ${row.passed ? "通过" : "失败"}
            </span>
            <small>${detail}</small>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderEvaluationDashboard(data) {
  renderEvaluationSummary(data);
  renderEvaluationRows();
  elements.evaluationLoading.classList.add("hidden");
  elements.evaluationDashboard.classList.remove("hidden");
  requestAnimationFrame(() => renderEvaluationChart(data));
}

async function loadEvaluationData(force = false) {
  if (evaluationLoaded && !force) {
    evaluationCharts.forEach((chart) => chart.resize());
    return;
  }
  elements.evaluationLoading.classList.remove("hidden");
  elements.evaluationDashboard.classList.add("hidden");
  elements.evaluationRunButton.disabled = true;
  elements.evaluationRunButton.textContent = "评测中…";
  try {
    const dataset = encodeURIComponent(elements.evaluationDataset.value);
    evaluationData = await requestJson(`/api/evaluation/run?dataset=${dataset}`, {
      method: "POST",
      headers: { "Cache-Control": "no-cache" },
    });
    evaluationLoaded = true;
    renderEvaluationDashboard(evaluationData);
  } catch (error) {
    elements.evaluationLoading.innerHTML =
      `<p>评测失败：${escapeHtml(error.message)}</p>`;
  } finally {
    elements.evaluationRunButton.disabled = false;
    elements.evaluationRunButton.textContent = "重新运行评测";
  }
}

async function loadBatchData(force = false) {
  if (batchLoaded && !force) {
    batchCharts.forEach((chart) => chart.resize());
    return;
  }
  elements.batchLoading.classList.remove("hidden");
  elements.batchDashboard.classList.add("hidden");
  elements.batchRefreshButton.disabled = true;
  elements.batchRefreshButton.textContent = "计算中…";
  try {
    batchData = await requestJson("/api/assessment/batch", {
      headers: { "Cache-Control": "no-cache" },
    });
    batchLoaded = true;
    renderBatchDashboard(batchData);
  } catch (error) {
    elements.batchLoading.innerHTML = `<p>批量分析失败：${escapeHtml(error.message)}</p>`;
  } finally {
    elements.batchRefreshButton.disabled = false;
    elements.batchRefreshButton.textContent = "重新计算";
  }
}

function setWorkspaceView(viewName) {
  document.querySelectorAll(".workspace-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.view === viewName);
  });
  elements.qaView.classList.toggle("hidden", viewName !== "qa");
  elements.assessmentView.classList.toggle("hidden", viewName !== "assessment");
  elements.batchView.classList.toggle("hidden", viewName !== "batch");
  elements.evaluationView.classList.toggle("hidden", viewName !== "evaluation");
  if (viewName === "batch") {
    loadBatchData().catch((error) => window.alert(error.message));
    setTimeout(() => batchCharts.forEach((chart) => chart.resize()), 0);
  }
  if (viewName === "evaluation") {
    loadEvaluationData().catch((error) => window.alert(error.message));
    setTimeout(() => evaluationCharts.forEach((chart) => chart.resize()), 0);
  }
}

async function openBatchSampleDetail(sampleId) {
  setWorkspaceView("assessment");
  elements.sampleSelect.value = String(sampleId);
  elements.sampleSelect.dispatchEvent(new Event("change"));
  await runAssessment();
}

function renderSources(sources) {
  elements.sourceCount.textContent = `${sources.length} 条证据`;
  elements.sourceList.innerHTML = sources
    .map(
      (source) => `
        <article class="source-card">
          <div class="source-topline">
            <div class="source-title">
              <span class="source-marker">${escapeHtml(source.marker)}</span>
              <div>
                <strong>${escapeHtml(source.title)}</strong>
                <span>
                  第 ${source.page} ${escapeHtml(source.location_label || "页")} · ${escapeHtml(source.retrieval_method || "关键词检索")}
                  · ${source.semantic_score === null || source.semantic_score === undefined
                    ? `关键词 ${(source.lexical_score * 100).toFixed(1)}%`
                    : `语义 ${(source.semantic_score * 100).toFixed(1)}%`}
                </span>
              </div>
            </div>
            <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">打开原文 ↗</a>
          </div>
          <p>${escapeHtml(source.excerpt)}</p>
        </article>
      `,
    )
    .join("");
}

async function askQuestion(question) {
  elements.askButton.disabled = true;
  elements.askButton.firstElementChild.textContent = "正在检索…";
  try {
    const result = await requestJson("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        top_k: 5,
        use_llm: elements.useLlm.checked,
      }),
    });
    elements.emptyState.classList.add("hidden");
    elements.resultPanel.classList.remove("hidden");
    elements.resultQuestion.textContent = question;
    elements.resultMode.textContent = result.mode;
    elements.answerBox.innerHTML = formatAnswer(result.answer);
    if (result.warning) {
      elements.warningBox.textContent = result.warning;
      elements.warningBox.classList.remove("hidden");
    } else {
      elements.warningBox.classList.add("hidden");
    }
    renderSources(result.sources);
    elements.resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    window.alert(error.message);
  } finally {
    elements.askButton.disabled = false;
    elements.askButton.firstElementChild.textContent = "检索并回答";
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = elements.input.value.trim();
  if (question) askQuestion(question);
});

document.querySelectorAll(".suggestions button").forEach((button) => {
  button.addEventListener("click", () => {
    elements.input.value = button.textContent.trim();
    elements.input.focus();
  });
});

elements.rebuildButton.addEventListener("click", async () => {
  elements.rebuildButton.disabled = true;
  elements.libraryStats.textContent = "正在重新建立索引…";
  try {
    await requestJson("/api/rebuild", { method: "POST" });
    await loadStatus();
  } catch (error) {
    window.alert(error.message);
  } finally {
    elements.rebuildButton.disabled = false;
  }
});

document.querySelectorAll(".workspace-tab").forEach((button) => {
  button.addEventListener("click", () => {
    setWorkspaceView(button.dataset.view);
  });
});

elements.sampleSelect.addEventListener("change", () => {
  const sample = currentSample();
  elements.customNameField.classList.toggle("hidden", Boolean(sample));
  renderMetalInputs(sample || { sample_id: "", name: "自定义样点", concentrations: {} });
  renderAssessmentModeNote(sample);
  elements.assessmentResult.classList.add("hidden");
});
elements.assessButton.addEventListener("click", runAssessment);
elements.batchRefreshButton.addEventListener("click", () => loadBatchData(true));
elements.batchSearchInput.addEventListener("input", renderBatchRows);
elements.batchGradeFilter.addEventListener("change", renderBatchRows);
elements.batchRows.addEventListener("click", (event) => {
  const button = event.target.closest(".detail-button");
  if (button) openBatchSampleDetail(button.dataset.sampleId);
});
elements.evaluationRunButton.addEventListener("click", () => loadEvaluationData(true));
elements.evaluationDataset.addEventListener("change", () => loadEvaluationData(true));
elements.evaluationFilter.addEventListener("change", renderEvaluationRows);
window.addEventListener("resize", () => {
  batchCharts.forEach((chart) => chart.resize());
  evaluationCharts.forEach((chart) => chart.resize());
});

Promise.all([loadStatus(), loadAssessmentData()]).catch((error) => {
  elements.libraryStats.textContent = `加载失败：${error.message}`;
  elements.modeBadge.textContent = "服务异常";
});
