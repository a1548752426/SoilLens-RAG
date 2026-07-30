from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .assessment import AssessmentDataset, calculate_assessment, calculate_batch_assessment
from .config import AppSettings
from .evaluator import evaluate_boundary, load_questions, run_evaluation
from .exporter import build_batch_workbook
from .indexer import DocumentIndex
from .llm import LLMConfig, extractive_answer, generate_answer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
SETTINGS = AppSettings.from_environment(PROJECT_ROOT)
INDEX = DocumentIndex(
    SETTINGS.document_dir,
    SETTINGS.cache_dir,
    allowed_extensions={".md", ".txt"} if SETTINGS.is_demo else {".pdf"},
)
ASSESSMENT = AssessmentDataset(
    SETTINGS.sample_file,
    SETTINGS.assessment_source,
    synthetic=SETTINGS.is_demo,
)
EVALUATION_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "questions.json"
EVALUATION_BASELINE_PATH = PROJECT_ROOT / "evaluation" / "baseline.json"
BLIND_QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "blind_questions.json"
BLIND_BASELINE_PATH = PROJECT_ROOT / "evaluation" / "blind_baseline.json"
EVALUATION_DATASETS = {
    "development": {
        "label": "开发回归集",
        "questions": EVALUATION_QUESTIONS_PATH,
        "baseline": EVALUATION_BASELINE_PATH,
    },
    "blind": {
        "label": "独立盲测集",
        "questions": BLIND_QUESTIONS_PATH,
        "baseline": BLIND_BASELINE_PATH,
    },
}
LOCAL_CLIENTS = {"127.0.0.1", "::1"}
LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=3, le=8)
    use_llm: bool = True


class AssessmentRequest(BaseModel):
    sample_id: str | None = None
    concentrations: dict[str, float] | None = None
    name: str | None = None


def is_local_request(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    return client_host in LOCAL_CLIENTS and request.url.hostname in LOCAL_HOSTNAMES


def require_local_client(request: Request) -> None:
    if not SETTINGS.is_demo and not is_local_request(request):
        raise HTTPException(status_code=403, detail="真实样点数据只允许在本机访问。")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(INDEX.rebuild)
    yield


app = FastAPI(
    title="SoilLens 土壤环境文档智能问答",
    version="0.6.0",
    lifespan=lifespan,
)
app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/api/status")
def status() -> dict[str, object]:
    config = LLMConfig.from_environment()
    return {
        "profile": SETTINGS.public_dict(),
        "index": INDEX.stats(),
        "retrieval": INDEX.retrieval_status(),
        "llm": config.public_status(),
    }


@app.get("/api/health")
def health() -> dict[str, object]:
    stats = INDEX.stats()
    index_ready = stats["documents"] > 0 and stats["chunks"] > 0
    return {
        "status": "ok" if index_ready else "starting",
        "version": app.version,
        "profile": SETTINGS.profile,
        "index_ready": index_ready,
        "documents": stats["documents"],
        "semantic_available": INDEX.retrieval_status()["semantic_available"],
    }


@app.get("/api/documents")
def documents() -> dict[str, object]:
    return {"documents": INDEX.list_documents()}


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: str) -> FileResponse:
    document = INDEX.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="未找到该文档。")
    path = Path(document.path).resolve()
    try:
        path.relative_to(SETTINGS.document_dir)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="文档路径不允许访问。") from exc
    media_types = {
        ".pdf": "application/pdf",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }
    media_type = media_types.get(path.suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=403, detail="文档路径不允许访问。")
    return FileResponse(path, media_type=media_type)


@app.get("/api/assessment/config")
def assessment_config(request: Request) -> dict[str, object]:
    try:
        config = ASSESSMENT.config()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if SETTINGS.is_demo:
        config["source"] = {
            "title": "SoilLens 土壤重金属评价演示知识",
            "table": "杭州背景值演示参考表",
            "page": 2,
            "location_label": "节",
            "url": "/api/assessment/source",
        }
    else:
        config["source"]["location_label"] = "页"
    config["profile"] = SETTINGS.profile
    if not SETTINGS.is_demo and not is_local_request(request) and config["dataset_available"]:
        config["dataset_available"] = False
        config["sample_count"] = 0
        config["note"] = "公开访问不会加载真实样点数据，请手动输入待评价浓度。"
    return config


@app.get("/api/assessment/samples")
def assessment_samples(request: Request) -> dict[str, object]:
    if not SETTINGS.is_demo and not is_local_request(request):
        return {"samples": []}
    try:
        return {"samples": ASSESSMENT.list_samples()}
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/assessment")
def assess_sample(payload: AssessmentRequest, request: Request) -> dict[str, object]:
    if payload.sample_id:
        require_local_client(request)
        try:
            sample = ASSESSMENT.get_sample(payload.sample_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if sample is None:
            raise HTTPException(status_code=404, detail="未找到该样点。")
        concentrations = payload.concentrations or sample.concentrations
        name = payload.name or sample.name
        sample_id = sample.sample_id
    else:
        concentrations = payload.concentrations or {}
        name = payload.name or "自定义样点"
        sample_id = None

    try:
        result = calculate_assessment(
            concentrations,
            sample_id=sample_id,
            sample_name=name,
        )
        result["synthetic"] = SETTINGS.is_demo
        if SETTINGS.is_demo:
            result["warnings"].insert(
                0,
                "当前结果使用人工合成演示数据，不可用于科研、监管或场地决策。",
            )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/assessment/source")
def assessment_source() -> FileResponse:
    path = ASSESSMENT.source_pdf_path.resolve()
    allowed_root = (
        SETTINGS.document_dir
        if SETTINGS.is_demo
        else (PROJECT_ROOT / "background_values").resolve()
    )
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="背景值来源路径不允许访问。") from exc
    media_types = {
        ".pdf": "application/pdf",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }
    media_type = media_types.get(path.suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=403, detail="背景值来源路径不允许访问。")
    if not path.exists():
        raise HTTPException(status_code=404, detail="未找到背景值来源文档。")
    return FileResponse(path, media_type=media_type)


@app.get("/api/assessment/batch")
def batch_assessment(request: Request) -> dict[str, object]:
    require_local_client(request)
    try:
        samples = ASSESSMENT.list_samples()
        result = calculate_batch_assessment(samples)
        if SETTINGS.is_demo:
            result["note"] = (
                "批量结果基于人工合成演示数据生成，仅用于功能展示，"
                "不可用于科研、监管或场地决策。"
            )
        return result
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/assessment/batch/export")
def export_batch_assessment(request: Request) -> Response:
    require_local_client(request)
    try:
        samples = ASSESSMENT.list_samples()
        batch = calculate_batch_assessment(samples, include_details=True)
        if SETTINGS.is_demo:
            batch["note"] = (
                "批量结果基于人工合成演示数据生成，仅用于功能展示，"
                "不可用于科研、监管或场地决策。"
            )
        content = build_batch_workbook(batch)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="SoilLens_batch_assessment.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/rebuild")
async def rebuild() -> dict[str, object]:
    stats = await asyncio.to_thread(INDEX.rebuild)
    return {"ok": True, "index": stats}


@app.get("/api/evaluation/config")
def evaluation_config() -> dict[str, object]:
    if SETTINGS.is_demo:
        raise HTTPException(
            status_code=409,
            detail="公开演示模式不包含论文原文及其页码评测集。",
        )
    try:
        datasets = {}
        for dataset_id, paths in EVALUATION_DATASETS.items():
            questions = load_questions(paths["questions"])
            datasets[dataset_id] = {
                "label": paths["label"],
                "question_count": len(questions),
                "answerable_count": sum(
                    question.answerable for question in questions
                ),
                "unanswerable_count": sum(
                    not question.answerable for question in questions
                ),
            }
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"无法读取评测配置：{exc}") from exc
    return {
        "datasets": datasets,
        "default_dataset": "blind",
        "note": "评测仅使用公开论文的问题、正确文档与页码，不读取私有样点 Excel。",
    }


@app.post("/api/evaluation/run")
async def evaluate_retrieval(dataset: str = "blind") -> dict[str, object]:
    if SETTINGS.is_demo:
        raise HTTPException(
            status_code=409,
            detail="公开演示模式不包含论文原文及其页码评测集。",
        )
    selected = EVALUATION_DATASETS.get(dataset)
    if selected is None:
        raise HTTPException(status_code=422, detail="未知评测集。")
    try:
        questions = load_questions(selected["questions"])
        baseline = json.loads(selected["baseline"].read_text(encoding="utf-8"))
        current = await asyncio.to_thread(run_evaluation, INDEX, questions)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"评测运行失败：{exc}") from exc
    return {
        "dataset": dataset,
        "dataset_label": selected["label"],
        "baseline": baseline,
        "current": current,
        "note": (
            "这是冻结后的独立盲测结果；首次运行后未通过修改题目或逐题添加关键词调分。"
            if dataset == "blind"
            else "这是开发回归集结果，可用于日常检索调试，不代表未见问题上的泛化性能。"
        ),
    }


@app.post("/api/ask")
async def ask(request: AskRequest) -> dict[str, object]:
    question = request.question.strip()
    sources = await asyncio.to_thread(INDEX.search, question, request.top_k)
    boundary = evaluate_boundary(question, sources)
    if not boundary.accepted:
        return {
            "answer": f"我不能根据当前知识库回答这个问题。{boundary.message}",
            "mode": "本地证据检索",
            "sources": [],
            "warning": f"{boundary.label}：{boundary.message}",
            "boundary": boundary.public_dict(),
        }

    config = LLMConfig.from_environment()
    warning = ""
    retrieval_mode = str(sources[0].get("retrieval_method", "关键词检索"))
    if request.use_llm and config.available:
        try:
            answer = await asyncio.to_thread(generate_answer, question, sources, config)
            mode = f"AI 综合回答 · {config.model} · {retrieval_mode}"
        except RuntimeError as exc:
            answer = extractive_answer(question, sources)
            mode = retrieval_mode
            warning = f"模型调用失败，已自动回退到本地证据模式：{exc}"
    else:
        answer = extractive_answer(question, sources)
        mode = retrieval_mode
        if request.use_llm and not config.available:
            warning = "尚未配置模型接口，当前返回最相关原文证据。"

    public_sources = []
    for index, source in enumerate(sources, start=1):
        source_type = str(source.get("source_type", "pdf"))
        location_label = str(source.get("location_label", "页"))
        fragment = f"#page={source['page']}" if source_type == "pdf" else ""
        public_sources.append(
            {
                "marker": f"S{index}",
                "document_id": source["document_id"],
                "title": source["title"],
                "page": source["page"],
                "source_type": source_type,
                "location_label": location_label,
                "score": source["score"],
                "lexical_score": source.get("lexical_score"),
                "semantic_score": source.get("semantic_score"),
                "query_semantic_score": source.get("query_semantic_score"),
                "retrieval_method": source.get("retrieval_method"),
                "excerpt": source["text"],
                "url": f"/api/documents/{source['document_id']}/file{fragment}",
            }
        )

    return {
        "answer": answer,
        "mode": mode,
        "sources": public_sources,
        "warning": warning,
        "boundary": boundary.public_dict(),
    }
