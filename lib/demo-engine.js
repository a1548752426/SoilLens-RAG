import documents from "../demo_data/documents.json";
import samples from "../demo_data/samples.json";

export const METALS = ["As", "Cd", "Cr", "Mn", "Ni", "Cu", "Pb", "Zn"];
export const BACKGROUND = {
  As: 5.0,
  Cd: 0.11,
  Cr: 57.0,
  Mn: 465.0,
  Ni: 26.0,
  Cu: 16.0,
  Pb: 21.0,
  Zn: 68.0,
};

const DOMAIN_TERMS = [
  "土壤", "重金属", "污染", "背景值", "修复", "植物", "机器学习",
  "空间", "样点", "浓度", "cf", "igeo", "pli", "镉", "铅", "锌",
  "砷", "铬", "铜", "镍", "锰",
];

const BLOCK_RULES = [
  ["secret_exfiltration", "敏感信息请求", /提示词|api.?key|密钥|密码|token|系统指令/i],
  ["unrelated_coding", "无关编程请求", /写.*(?:c\s*语言|python|java|代码|程序)|快速排序|编程/i],
  ["financial_advice", "金融建议", /股票|基金|买入|卖出|投资建议|涨停/i],
  ["real_time_info", "实时外部信息", /今天.*新闻|实时|天气|外卖|订单|账户余额|模型额度/i],
  ["hallucination_instruction", "诱导编造", /编造|伪造|虚假引用|随便给.*页码/i],
];

function cleanText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[#*()[\]{}，。！？、：；“”‘’]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function queryTokens(question) {
  const normalized = cleanText(question);
  const tokens = normalized.match(/[a-z][a-z0-9.-]*|[\u4e00-\u9fff]+/g) || [];
  const expanded = [];
  for (const token of tokens) {
    if (/^[\u4e00-\u9fff]+$/.test(token) && token.length > 2) {
      for (let index = 0; index < token.length - 1; index += 1) {
        expanded.push(token.slice(index, index + 2));
      }
    } else if (token.length >= 2) {
      expanded.push(token);
    }
  }
  return [...new Set(expanded)];
}

export function publicDocuments() {
  return documents.map((document) => ({
    id: document.id,
    title: document.title,
    filename: document.filename,
    pages: document.sections.length,
    source_type: "text",
    location_label: "节",
  }));
}

export function documentMarkdown(documentId) {
  const document = documents.find((item) => item.id === documentId);
  return document ? document.sections.join("\n\n") : null;
}

export function searchDocuments(question, topK = 5) {
  const tokens = queryTokens(question);
  const candidates = [];
  for (const document of documents) {
    document.sections.forEach((section, sectionIndex) => {
      const normalized = cleanText(section);
      let score = 0;
      for (const token of tokens) {
        if (normalized.includes(token)) {
          score += token.length > 3 ? 2 : 1;
        }
      }
      if (score > 0) {
        candidates.push({
          document_id: document.id,
          title: document.title,
          filename: document.filename,
          page: sectionIndex + 1,
          source_type: "text",
          location_label: "节",
          score,
          text: section.replace(/^#{1,3}\s*/m, "").replace(/\n+/g, " ").trim(),
        });
      }
    });
  }
  return candidates
    .sort((left, right) => right.score - left.score)
    .slice(0, Math.max(3, Math.min(8, Number(topK) || 5)));
}

function boundaryDecision(question, results) {
  for (const [code, label, pattern] of BLOCK_RULES) {
    if (pattern.test(question)) {
      return {
        accepted: false,
        code,
        label,
        message: "该请求超出土壤环境知识库与污染评价的业务边界。",
      };
    }
  }
  const normalized = cleanText(question);
  const inDomain = DOMAIN_TERMS.some((term) => normalized.includes(term));
  if (!inDomain || !results.length) {
    return {
      accepted: false,
      code: "insufficient_evidence",
      label: "证据相关度不足",
      message: "当前原创演示知识库没有足够证据支持回答。",
    };
  }
  return {
    accepted: true,
    code: "within_scope",
    label: "知识库范围内",
    message: "问题属于土壤环境演示知识库范围。",
  };
}

export function answerQuestion(question, topK = 5) {
  const results = searchDocuments(question, topK);
  const boundary = boundaryDecision(question, results);
  if (!boundary.accepted) {
    return {
      answer: `我不能根据当前知识库回答这个问题。${boundary.message}`,
      mode: "公开演示 · 本地证据检索",
      sources: [],
      warning: `${boundary.label}：${boundary.message}`,
      boundary,
    };
  }
  const sources = results.map((result, index) => ({
    marker: `S${index + 1}`,
    document_id: result.document_id,
    title: result.title,
    page: result.page,
    source_type: "text",
    location_label: "节",
    score: Number((result.score / 10).toFixed(4)),
    lexical_score: Number(Math.min(1, result.score / 10).toFixed(4)),
    semantic_score: null,
    query_semantic_score: null,
    retrieval_method: "关键词检索",
    excerpt: result.text.slice(0, 420),
    url: `/api/documents/${result.document_id}/file`,
  }));
  const answer = sources
    .slice(0, 3)
    .map((source) => `${source.excerpt} [${source.marker}]`)
    .join("\n\n");
  return {
    answer,
    mode: "公开演示 · 关键词证据检索",
    sources,
    warning: "当前未配置生成模型，返回最相关的原创演示材料。",
    boundary,
  };
}

function classifyCf(value) {
  if (value < 1) return "低污染";
  if (value < 3) return "中等污染";
  if (value < 6) return "较高污染";
  return "极高污染";
}

function classifyIgeo(value) {
  if (value === null) return "无法计算";
  if (value < 0) return "无污染";
  if (value < 1) return "无污染至中度污染";
  if (value < 2) return "中度污染";
  if (value < 3) return "中度至强污染";
  if (value < 4) return "强污染";
  if (value < 5) return "强至极强污染";
  return "极强污染";
}

export function assess(concentrations, sampleId = null, sampleName = "自定义样点") {
  const available = {};
  for (const metal of METALS) {
    if (concentrations?.[metal] === null || concentrations?.[metal] === undefined) continue;
    const value = Number(concentrations[metal]);
    if (!Number.isFinite(value) || value < 0) {
      throw new Error(`${metal} 浓度必须是大于或等于 0 的有限数值。`);
    }
    available[metal] = value;
  }
  if (!Object.keys(available).length) {
    throw new Error("至少需要输入一种重金属浓度。");
  }
  const results = METALS.filter((metal) => metal in available).map((metal) => {
    const concentration = available[metal];
    const background = BACKGROUND[metal];
    const cf = concentration / background;
    const igeo = concentration > 0
      ? Math.log2(concentration / (1.5 * background))
      : null;
    return {
      metal,
      concentration,
      background,
      cf,
      cf_grade: classifyCf(cf),
      igeo,
      igeo_grade: classifyIgeo(igeo),
      exceeded: concentration > background,
    };
  });
  const factors = results.map((row) => row.cf);
  const pli = factors.some((value) => value === 0)
    ? 0
    : Math.exp(factors.reduce((sum, value) => sum + Math.log(value), 0) / factors.length);
  const maxCf = [...results].sort((a, b) => b.cf - a.cf)[0];
  const withIgeo = results.filter((row) => row.igeo !== null).sort((a, b) => b.igeo - a.igeo);
  const missing = METALS.filter((metal) => !(metal in available));
  const warnings = [
    "当前结果使用人工合成演示数据，不可用于科研、监管或场地决策。",
  ];
  if (missing.length) {
    warnings.push(`当前数据未提供 ${missing.join("、")}，PLI 按现有 ${results.length} 种金属计算。`);
  }
  warnings.push("本结果表示相对背景值的富集程度，不等同于用地风险筛选结论。");
  return {
    synthetic: true,
    sample: { sample_id: sampleId, name: sampleName, concentrations: available },
    summary: {
      pli,
      pli_grade: Math.abs(pli - 1) < 1e-9 ? "背景水平" : pli < 1 ? "整体未污染" : "整体污染",
      metal_count: results.length,
      exceeded_count: results.filter((row) => row.exceeded).length,
      max_cf_metal: maxCf.metal,
      max_cf: maxCf.cf,
      max_igeo_metal: withIgeo[0]?.metal || null,
      max_igeo: withIgeo[0]?.igeo ?? null,
    },
    results,
    metals: results.map((row) => row.metal),
    warnings,
    method: {
      cf: "CF = C / B",
      igeo: "Igeo = log2[C / (1.5 × B)]",
      pli: `PLI = (CF₁ × CF₂ × … × CFₙ)^(1/n)，本次 n = ${results.length}`,
    },
  };
}

export function sampleList() {
  return samples;
}

export function batchAssessment() {
  const assessed = samples.map((sample) => assess(
    sample.concentrations,
    sample.sample_id,
    sample.name,
  ));
  const sampleRows = assessed.map((item) => ({
    sample_id: item.sample.sample_id,
    name: item.sample.name,
    ...item.summary,
  })).sort((left, right) => right.pli - left.pli);
  const metalSummary = METALS.map((metal) => {
    const rows = assessed.flatMap((item) => item.results).filter((row) => row.metal === metal);
    const exceededCount = rows.filter((row) => row.exceeded).length;
    const igeoValues = rows.map((row) => row.igeo).filter((value) => value !== null);
    return {
      metal,
      background: BACKGROUND[metal],
      sample_count: rows.length,
      exceeded_count: exceededCount,
      exceeded_rate: exceededCount / rows.length,
      mean_cf: rows.reduce((sum, row) => sum + row.cf, 0) / rows.length,
      max_cf: Math.max(...rows.map((row) => row.cf)),
      max_igeo: Math.max(...igeoValues),
      igeo_polluted_count: igeoValues.filter((value) => value >= 0).length,
    };
  });
  const pliValues = sampleRows.map((row) => row.pli);
  const polluted = sampleRows.filter((row) => row.pli > 1);
  const sortedPli = [...pliValues].sort((a, b) => a - b);
  const median = (sortedPli[5] + sortedPli[6]) / 2;
  const highest = [...metalSummary].sort((a, b) => b.exceeded_rate - a.exceeded_rate)[0];
  return {
    summary: {
      sample_count: sampleRows.length,
      metal_count: metalSummary.length,
      polluted_count: polluted.length,
      polluted_rate: polluted.length / sampleRows.length,
      mean_pli: pliValues.reduce((sum, value) => sum + value, 0) / pliValues.length,
      median_pli: median,
      max_pli: sampleRows[0].pli,
      max_pli_sample_id: sampleRows[0].sample_id,
      max_pli_sample_name: sampleRows[0].name,
      highest_exceedance_metal: highest.metal,
      highest_exceedance_rate: highest.exceeded_rate,
    },
    pli_grade_distribution: {
      "整体未污染": sampleRows.filter((row) => row.pli < 1).length,
      "背景水平": sampleRows.filter((row) => Math.abs(row.pli - 1) < 1e-9).length,
      "整体污染": sampleRows.filter((row) => row.pli > 1).length,
    },
    metal_summary: metalSummary,
    samples: sampleRows,
    top_samples: sampleRows.slice(0, 10),
    note: "批量结果基于人工合成演示数据生成，仅用于功能展示，不可用于科研、监管或场地决策。",
  };
}

export const assessmentConfig = {
  dataset_available: true,
  synthetic: true,
  sample_count: samples.length,
  available_metals: METALS,
  missing_metals: [],
  background_values: BACKGROUND,
  unit: "mg/kg",
  source: {
    title: "SoilLens 土壤重金属评价演示知识",
    table: "杭州背景值演示参考表",
    page: 2,
    location_label: "节",
    url: "/api/assessment/source",
  },
  formulas: {
    cf: "CF = C / B",
    igeo: "Igeo = log2[C / (1.5 × B)]",
    pli: "PLI = (CF₁ × CF₂ × … × CFₙ)^(1/n)",
  },
  note: "所有浓度均为人工合成，仅用于功能演示，不可用于科研或监管结论。",
  profile: "demo",
};
