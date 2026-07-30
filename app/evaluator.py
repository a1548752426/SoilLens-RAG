from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from .indexer import DocumentIndex


DEFAULT_TOP_K = 5
DEFAULT_CONFIDENCE_THRESHOLD = 0.06
SEMANTIC_CONFIDENCE_THRESHOLD = 0.58


@dataclass(frozen=True, slots=True)
class BoundaryRule:
    code: str
    label: str
    message: str
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class BoundaryDecision:
    accepted: bool
    code: str
    label: str
    message: str

    def public_dict(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "code": self.code,
            "label": self.label,
            "message": self.message,
        }


BOUNDARY_RULES = (
    BoundaryRule(
        code="secret_exfiltration",
        label="敏感信息请求",
        message="该请求试图获取系统提示词、密码或密钥，超出文献助手允许范围。",
        pattern=re.compile(
            r"系统提示词|管理员密码|api\s*密钥|api\s*key|访问令牌|access\s*token",
            re.I,
        ),
    ),
    BoundaryRule(
        code="hallucination_instruction",
        label="诱导编造",
        message="该请求要求脱离证据或伪造来源，系统只允许基于已收录论文回答。",
        pattern=re.compile(
            r"忽略.{0,12}(?:文档|论文|规则)|即使.{0,16}(?:没有|无).{0,12}证据|"
            r"编造|虚假页码|伪造(?:结论|来源|引用)",
            re.I,
        ),
    ),
    BoundaryRule(
        code="unrelated_coding",
        label="无关编程任务",
        message="当前助手只回答土壤重金属文献问题，不执行通用编程任务。",
        pattern=re.compile(
            r"\bc\s*语言\b|c\+\+|用\s*(?:java|python|go)\s*(?:写|实现)|"
            r"快速排序|写.{0,8}(?:代码|程序)|code\s+(?:a|the)|write\s+code",
            re.I,
        ),
    ),
    BoundaryRule(
        code="external_system",
        label="外部系统请求",
        message="当前助手不能充当外卖客服，也不能查询模型账户、额度或其他外部系统。",
        pattern=re.compile(
            r"外卖.{0,8}客服|客服账号|模型.{0,8}额度|剩余.{0,6}额度|"
            r"查询.{0,12}(?:账号|账户|订单)",
            re.I,
        ),
    ),
    BoundaryRule(
        code="real_time",
        label="实时信息请求",
        message="当前知识库是固定论文集合，不包含实时新闻、案件、处罚或行情。",
        pattern=re.compile(
            r"(?:今天|当前|实时|最新).{0,16}(?:新闻|案件|处罚|天气|行情)|"
            r"(?:新闻|案件|处罚).{0,16}(?:今天|实时|最新)",
            re.I,
        ),
    ),
    BoundaryRule(
        code="financial_advice",
        label="金融建议",
        message="股票预测和投资建议不属于土壤文献知识库范围。",
        pattern=re.compile(
            r"股票|股价|买入|卖出|涨停|投资建议|应该买多少",
            re.I,
        ),
    ),
    BoundaryRule(
        code="unsupported_domain",
        label="知识库范围外",
        message="该主题不在当前五篇土壤重金属论文的证据范围内。",
        pattern=re.compile(
            r"\b(?:transformer|bert|gpt[-\s]?4)\b|行政区|监管罚款|罚款金额|"
            r"月球|lunar|每亩|元以下|患者|临床试验|血铅|治疗方案|"
            r"clinical\s+trial|patient",
            re.I,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class EvaluationQuestion:
    id: str
    question: str
    answerable: bool
    expected_title: str | None
    expected_pages: tuple[int, ...]
    category: str
    boundary_type: str


def load_questions(path: Path) -> list[EvaluationQuestion]:
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("评测集必须是非空 JSON 数组。")

    questions: list[EvaluationQuestion] = []
    seen_ids: set[str] = set()
    for raw in raw_items:
        question = EvaluationQuestion(
            id=str(raw["id"]).strip(),
            question=str(raw["question"]).strip(),
            answerable=bool(raw["answerable"]),
            expected_title=(
                str(raw["expected_title"]).strip() if raw.get("expected_title") else None
            ),
            expected_pages=tuple(int(page) for page in raw.get("expected_pages", [])),
            category=str(raw["category"]).strip(),
            boundary_type=str(
                raw.get(
                    "boundary_type",
                    "in_scope" if raw["answerable"] else "knowledge_scope",
                )
            ).strip(),
        )
        if not question.id or question.id in seen_ids:
            raise ValueError(f"评测题 ID 缺失或重复：{question.id!r}")
        if not question.question:
            raise ValueError(f"评测题 {question.id} 缺少问题文本。")
        if question.answerable and (
            not question.expected_title or not question.expected_pages
        ):
            raise ValueError(f"可回答题 {question.id} 缺少正确文档或页码。")
        if not question.answerable and (
            question.expected_title is not None or question.expected_pages
        ):
            raise ValueError(f"无答案题 {question.id} 不应设置正确文档或页码。")
        seen_ids.add(question.id)
        questions.append(question)
    return questions


def evaluate_boundary(
    question: str,
    results: list[dict[str, object]],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> BoundaryDecision:
    for rule in BOUNDARY_RULES:
        if rule.pattern.search(question):
            return BoundaryDecision(
                accepted=False,
                code=rule.code,
                label=rule.label,
                message=rule.message,
            )
    if not results:
        return BoundaryDecision(
            accepted=False,
            code="no_evidence",
            label="未检索到证据",
            message="当前论文库没有检索到与该问题相关的证据。",
        )
    top_result = results[0]
    retrieval_method = str(top_result.get("retrieval_method", "关键词检索"))
    if retrieval_method == "关键词 + 语义融合":
        semantic_score = top_result.get(
            "query_semantic_score",
            top_result.get("semantic_score"),
        )
        lexical_score = top_result.get("lexical_score", 0.0)
        confident = (
            (
                semantic_score is not None
                and float(semantic_score) >= SEMANTIC_CONFIDENCE_THRESHOLD
            )
            or float(lexical_score or 0.0) >= threshold
        )
    else:
        lexical_score = top_result.get("lexical_score", top_result.get("score", 0.0))
        confident = float(lexical_score or 0.0) >= threshold
    if not confident:
        return BoundaryDecision(
            accepted=False,
            code="low_relevance",
            label="证据相关度不足",
            message="检索到了弱相关内容，但关键词或语义相关度不足以支持可靠回答。",
        )
    return BoundaryDecision(
        accepted=True,
        code="within_scope",
        label="知识库范围内",
        message="问题位于当前论文库范围内，并检索到达到可信标准的证据。",
    )


def is_confident(
    question: str,
    results: list[dict[str, object]],
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> bool:
    return evaluate_boundary(question, results, threshold).accepted


def _round_metric(value: float) -> float:
    return round(float(value), 4)


def _mean_or_zero(values: list[float]) -> float:
    return _round_metric(mean(values)) if values else 0.0


def validate_questions(
    index: DocumentIndex,
    questions: list[EvaluationQuestion],
) -> None:
    documents_by_title = {document.title: document for document in index.documents.values()}
    for question in questions:
        if not question.answerable:
            continue
        document = documents_by_title.get(question.expected_title or "")
        if document is None:
            raise ValueError(
                f"评测题 {question.id} 的正确文档不在当前文档库："
                f"{question.expected_title}"
            )
        invalid_pages = [
            page
            for page in question.expected_pages
            if page < 1 or page > document.pages
        ]
        if invalid_pages:
            raise ValueError(
                f"评测题 {question.id} 包含无效页码：{invalid_pages}"
            )


def run_evaluation(
    index: DocumentIndex,
    questions: list[EvaluationQuestion],
    *,
    top_k: int = DEFAULT_TOP_K,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    validate_questions(index, questions)
    documents_by_title = {document.title: document for document in index.documents.values()}

    cases: list[dict[str, Any]] = []
    answerable_cases: list[dict[str, Any]] = []
    unanswerable_cases: list[dict[str, Any]] = []
    per_document: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for question in questions:
        results = index.search(question.question, top_k=top_k)
        top_result = results[0] if results else None
        boundary_decision = evaluate_boundary(
            question.question,
            results,
            confidence_threshold,
        )
        predicted_answerable = boundary_decision.accepted
        document_rank: int | None = None
        page_rank: int | None = None

        if question.answerable:
            for rank, result in enumerate(results, start=1):
                if result["title"] == question.expected_title and document_rank is None:
                    document_rank = rank
                if (
                    result["title"] == question.expected_title
                    and int(result["page"]) in question.expected_pages
                    and page_rank is None
                ):
                    page_rank = rank

        document_hit = document_rank is not None
        page_hit = page_rank is not None
        passed = (
            page_hit and predicted_answerable
            if question.answerable
            else not predicted_answerable
        )
        expected_document = (
            documents_by_title.get(question.expected_title or "")
            if question.answerable
            else None
        )

        case = {
            "id": question.id,
            "question": question.question,
            "category": question.category,
            "boundary_type": question.boundary_type,
            "answerable": question.answerable,
            "expected_title": question.expected_title,
            "expected_pages": list(question.expected_pages),
            "expected_url": (
                f"/api/documents/{expected_document.id}/file"
                f"#page={question.expected_pages[0]}"
                if expected_document
                else None
            ),
            "top_title": top_result["title"] if top_result else None,
            "top_page": int(top_result["page"]) if top_result else None,
            "top_score": float(top_result["score"]) if top_result else 0.0,
            "top_lexical_score": (
                float(top_result.get("lexical_score", 0.0))
                if top_result
                else 0.0
            ),
            "top_semantic_score": (
                float(top_result["semantic_score"])
                if top_result and top_result.get("semantic_score") is not None
                else None
            ),
            "query_semantic_score": (
                float(top_result["query_semantic_score"])
                if top_result
                and top_result.get("query_semantic_score") is not None
                else None
            ),
            "retrieval_method": (
                str(top_result.get("retrieval_method", "关键词检索"))
                if top_result
                else None
            ),
            "top_url": (
                f"/api/documents/{top_result['document_id']}/file"
                f"#page={top_result['page']}"
                if top_result
                else None
            ),
            "predicted_answerable": predicted_answerable,
            "decision": boundary_decision.public_dict(),
            "document_hit": document_hit,
            "page_hit": page_hit,
            "document_rank": document_rank,
            "page_rank": page_rank,
            "passed": passed,
        }
        cases.append(case)
        if question.answerable:
            answerable_cases.append(case)
            per_document[question.expected_title or ""].append(case)
        else:
            unanswerable_cases.append(case)

    document_hits = sum(bool(case["document_hit"]) for case in answerable_cases)
    page_hits = sum(bool(case["page_hit"]) for case in answerable_cases)
    accepted = sum(bool(case["predicted_answerable"]) for case in answerable_cases)
    rejected = sum(not bool(case["predicted_answerable"]) for case in unanswerable_cases)
    passed = sum(bool(case["passed"]) for case in cases)
    correctly_bounded = sum(
        bool(case["predicted_answerable"]) == bool(case["answerable"])
        for case in cases
    )
    reciprocal_ranks = [
        1 / int(case["document_rank"]) if case["document_rank"] else 0.0
        for case in answerable_cases
    ]

    document_breakdown = []
    for title in sorted(per_document):
        document_cases = per_document[title]
        document_breakdown.append(
            {
                "title": title,
                "question_count": len(document_cases),
                "document_recall_at_k": _round_metric(
                    sum(bool(case["document_hit"]) for case in document_cases)
                    / len(document_cases)
                ),
                "page_hit_at_k": _round_metric(
                    sum(bool(case["page_hit"]) for case in document_cases)
                    / len(document_cases)
                ),
            }
        )

    boundary_breakdown = []
    for boundary_type in sorted(
        {str(case["boundary_type"]) for case in unanswerable_cases}
    ):
        boundary_cases = [
            case
            for case in unanswerable_cases
            if case["boundary_type"] == boundary_type
        ]
        boundary_breakdown.append(
            {
                "boundary_type": boundary_type,
                "question_count": len(boundary_cases),
                "rejected_count": sum(
                    not bool(case["predicted_answerable"])
                    for case in boundary_cases
                ),
                "rejection_rate": _round_metric(
                    sum(
                        not bool(case["predicted_answerable"])
                        for case in boundary_cases
                    )
                    / len(boundary_cases)
                ),
            }
        )

    return {
        "summary": {
            "question_count": len(cases),
            "answerable_count": len(answerable_cases),
            "unanswerable_count": len(unanswerable_cases),
            "top_k": top_k,
            "confidence_threshold": confidence_threshold,
            "document_recall_at_k": _round_metric(
                document_hits / len(answerable_cases)
            ),
            "page_hit_at_k": _round_metric(page_hits / len(answerable_cases)),
            "answerable_acceptance_rate": _round_metric(
                accepted / len(answerable_cases)
            ),
            "mrr_document": _mean_or_zero(reciprocal_ranks),
            "unanswerable_rejection_rate": _round_metric(
                rejected / len(unanswerable_cases)
            ),
            "scope_boundary_accuracy": _round_metric(
                correctly_bounded / len(cases)
            ),
            "overall_pass_rate": _round_metric(passed / len(cases)),
            "mean_top_score_answerable": _mean_or_zero(
                [float(case["top_score"]) for case in answerable_cases]
            ),
            "mean_top_score_unanswerable": _mean_or_zero(
                [float(case["top_score"]) for case in unanswerable_cases]
            ),
        },
        "per_document": document_breakdown,
        "boundary_breakdown": boundary_breakdown,
        "cases": cases,
    }
