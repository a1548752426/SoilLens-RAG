import {
  answerQuestion,
  assess,
  assessmentConfig,
  batchAssessment,
  documentMarkdown,
  publicDocuments,
  sampleList,
} from "../../lib/demo-engine";

const profile = {
  id: "demo",
  label: "公开合成演示模式",
  public_demo: true,
  synthetic_data: true,
  evaluation_available: false,
  notice: "当前只使用原创演示文档和人工合成浓度数据，不包含真实样点或受版权保护的论文原文。",
};

function indexStats() {
  const documents = publicDocuments();
  return {
    documents: documents.length,
    pages: documents.reduce((sum, document) => sum + document.pages, 0),
    chunks: documents.reduce((sum, document) => sum + document.pages, 0),
  };
}

export default function handler(req, res) {
  const segments = Array.isArray(req.query.path) ? req.query.path : [];
  const route = segments.join("/");

  if (route === "health" && req.method === "GET") {
    return res.status(200).json({
      status: "ok",
      version: "0.6.0-sites",
      profile: "demo",
      index_ready: true,
      documents: 3,
      semantic_available: false,
    });
  }
  if (route === "status" && req.method === "GET") {
    return res.status(200).json({
      profile,
      index: indexStats(),
      retrieval: {
        mode: "关键词检索",
        semantic_available: false,
        semantic_model: null,
        semantic_cache_hit: false,
        fallback_reason: "生产演示使用轻量级关键词检索。",
      },
      llm: { available: false, model: "", mode: "公开证据检索" },
    });
  }
  if (route === "documents" && req.method === "GET") {
    return res.status(200).json({ documents: publicDocuments() });
  }
  if (route === "rebuild" && req.method === "POST") {
    return res.status(200).json({ ok: true, index: indexStats() });
  }
  if (route === "assessment/config" && req.method === "GET") {
    return res.status(200).json(assessmentConfig);
  }
  if (route === "assessment/samples" && req.method === "GET") {
    return res.status(200).json({ samples: sampleList() });
  }
  if (route === "assessment/batch" && req.method === "GET") {
    return res.status(200).json(batchAssessment());
  }
  if (route === "assessment/batch/export" && req.method === "GET") {
    return res.redirect(307, "/Sample_demo.xlsx");
  }
  if (route === "assessment/source" && req.method === "GET") {
    res.setHeader("Content-Type", "text/markdown; charset=utf-8");
    return res.status(200).send(documentMarkdown("2cf296bd802a"));
  }
  if (route === "assessment" && req.method === "POST") {
    try {
      const payload = req.body || {};
      const selected = payload.sample_id
        ? sampleList().find((sample) => sample.sample_id === String(payload.sample_id))
        : null;
      if (payload.sample_id && !selected) {
        return res.status(404).json({ detail: "未找到该演示样点。" });
      }
      const concentrations = payload.concentrations || selected?.concentrations || {};
      const name = payload.name || selected?.name || "自定义样点";
      return res.status(200).json(assess(
        concentrations,
        selected?.sample_id || null,
        name,
      ));
    } catch (error) {
      return res.status(422).json({ detail: error.message });
    }
  }
  if (route === "ask" && req.method === "POST") {
    const question = String(req.body?.question || "").trim();
    if (question.length < 2) {
      return res.status(422).json({ detail: "问题至少需要 2 个字符。" });
    }
    return res.status(200).json(answerQuestion(question, req.body?.top_k || 5));
  }
  if (route.startsWith("evaluation/")) {
    return res.status(409).json({ detail: "公开演示模式不包含论文原文及页码评测集。" });
  }
  if (
    segments.length === 3
    && segments[0] === "documents"
    && segments[2] === "file"
    && req.method === "GET"
  ) {
    const markdown = documentMarkdown(segments[1]);
    if (!markdown) {
      return res.status(404).json({ detail: "未找到该演示文档。" });
    }
    res.setHeader("Content-Type", "text/markdown; charset=utf-8");
    return res.status(200).send(markdown);
  }
  return res.status(404).json({ detail: "未找到该接口。" });
}
