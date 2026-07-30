from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

try:
    from fastembed import TextEmbedding
except ImportError:  # The lexical index remains usable without the optional model.
    TextEmbedding = None


logging.getLogger("pypdf").setLevel(logging.ERROR)

SEMANTIC_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LEXICAL_ROUTE_THRESHOLD = 0.11
RRF_K = 10
SEMANTIC_RRF_WEIGHT = 2.0


GLOSSARY: dict[str, tuple[str, ...]] = {
    "土壤": ("soil",),
    "重金属": ("heavy metal", "metalloid"),
    "污染": ("contamination", "pollution"),
    "修复": ("remediation", "restoration"),
    "生物修复": ("bioremediation",),
    "植物修复": ("phytoremediation",),
    "深层": ("deep soil", "deeper layer"),
    "背景值": ("background value", "natural background"),
    "自然背景": ("natural background", "geochemical background"),
    "机器学习": ("machine learning",),
    "随机森林": ("random forest", "RF"),
    "极端梯度提升": ("XGBoost", "gradient boosting"),
    "支持向量回归": ("support vector regression", "SVR"),
    "神经网络": ("artificial neural network", "ANN"),
    "富集": ("enrichment", "accumulation"),
    "迁移": ("migration", "transport"),
    "喀斯特": ("karst",),
    "竹": ("bamboo",),
    "吸附": ("adsorption",),
    "农田": ("agricultural soil", "cropland"),
    "作物": ("crop",),
    "镉": ("cadmium", "Cd"),
    "铬": ("chromium", "Cr"),
    "铜": ("copper", "Cu"),
    "镍": ("nickel", "Ni"),
    "铅": ("lead", "Pb"),
    "锌": ("zinc", "Zn"),
    "砷": ("arsenic", "As"),
    "汞": ("mercury", "Hg"),
    "有机质": ("organic matter",),
    "酸碱度": ("pH",),
    "风化": ("weathering",),
    "BA值": ("BA value", "weathering degree"),
    "SAF值": ("SAF value", "weathering intensity"),
    "模型输入": ("model input", "input variables"),
    "预测性能": (
        "prediction performance",
        "coefficient of determination",
        "mean absolute error",
        "mean squared error",
    ),
    "评价模型": (
        "model evaluation",
        "coefficient of determination",
        "mean absolute error",
        "mean squared error",
    ),
    "SHAP": ("SHAP", "feature importance"),
    "最佳预测": ("best prediction performance", "best-performing model"),
    "影响因素": ("influencing factors", "most important factor"),
    "定向孔": ("aligned porous structure", "ice templating"),
    "平均孔宽": ("average pore width",),
    "太阳蒸发": ("solar evaporation",),
    "蒸腾": ("transpiration",),
    "对流": ("convection", "convective transport"),
    "扩散": ("diffusion", "diffusion-controlled"),
    "蒸发速率": ("evaporation rate",),
    "临界深度": ("critical depth",),
    "土壤质地": ("soil texture", "sandy soil"),
    "食品安全": ("food safety",),
    "环境可持续性": ("environmental sustainability",),
    "成本": ("cost", "cost effectiveness"),
    "抗性策略": ("resistance strategies", "avoidance", "tolerance"),
    "根滤": ("rhizofiltration", "phytofiltration"),
    "植物过滤": ("phytofiltration", "rhizofiltration"),
    "螯合剂": ("chelating agents", "chelation"),
    "降pH": ("lowering soil pH",),
    "生态风险": ("ecological risks", "leaching"),
    "转基因微生物": (
        "genetically modified microorganisms",
        "horizontal gene transfer",
        "containment",
    ),
    "生物安全": ("biosafety", "containment", "horizontal gene transfer"),
    "亚表层": ("subsoil", "1.5-2.0 m"),
    "近自然背景": ("near-natural background",),
    "富集系数": ("enrichment coefficient", "EC"),
    "半变异函数": ("semi-variogram",),
    "块金比": ("nugget-to-sill ratio", "nugget ratio"),
    "空间自相关": ("spatial autocorrelation",),
    "非喀斯特": ("non-karst",),
    "总体有何差异": (
        "soil HM content",
        "significantly higher",
        "compared to non-karst areas",
    ),
    "中位富集系数": ("median enrichment coefficient", "median EC"),
    "形态和生长优势": (
        "morphological advantages",
        "extensive root system",
        "rapid growth",
    ),
    "毛竹": ("Phyllostachys pubescens",),
    "耐受水平": ("tolerance level",),
    "去除率": ("removal rate",),
    "抗氧化系统": ("antioxidant defense system",),
    "ROS": ("reactive oxygen species", "ROS"),
    "植物螯合肽": ("phytochelatins", "PCs"),
    "游离重金属": ("free heavy metal ions",),
    "伴矿景天": ("Sedum plumbizincicola",),
    "间作": ("intercropping",),
    "吸收和转运": ("uptake", "absorption", "translocation"),
}


@dataclass(slots=True)
class Document:
    id: str
    title: str
    filename: str
    path: str
    pages: int
    source_type: str
    location_label: str

    def public_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("path", None)
        return data


@dataclass(slots=True)
class Chunk:
    document_id: str
    title: str
    filename: str
    page: int
    source_type: str
    location_label: str
    text: str


def _document_title(filename: str) -> str:
    title = Path(filename).stem
    title = re.sub(r"\s*\(科研通-ablesci\.com\)\s*$", "", title, flags=re.I)
    return title.strip()


def _normalize_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text)
    return [piece.strip() for piece in pieces if len(piece.strip()) >= 20]


def _chunk_page(text: str, target_words: int = 170) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    sentences = _split_sentences(normalized)
    if len(sentences) < 2:
        words = normalized.split()
        if len(words) < 25 and re.search(r"[\u4e00-\u9fff]", normalized):
            target_chars = 420
            step = 340
            return [
                normalized[start : start + target_chars]
                for start in range(0, len(normalized), step)
                if len(normalized[start : start + target_chars]) >= 60
            ]
        step = max(1, target_words - 35)
        return [
            " ".join(words[start : start + target_words])
            for start in range(0, len(words), step)
            if len(words[start : start + target_words]) >= 25
        ]

    chunks: list[str] = []
    current: list[str] = []
    word_count = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and word_count + sentence_words > target_words:
            chunks.append(" ".join(current))
            current = current[-2:]
            word_count = sum(len(item.split()) for item in current)
        current.append(sentence)
        word_count += sentence_words

    if current:
        chunk = " ".join(current)
        if len(chunk.split()) >= 20:
            chunks.append(chunk)
    return chunks


def _read_text_sections(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8-sig").strip()
    if not content:
        return []
    if path.suffix.lower() == ".md":
        sections: list[str] = []
        current: list[str] = []
        for line in content.splitlines():
            if re.match(r"^#{1,3}\s+\S", line) and current:
                section = "\n".join(current).strip()
                if section:
                    sections.append(section)
                current = [line]
            else:
                current.append(line)
        section = "\n".join(current).strip()
        if section:
            sections.append(section)
        return sections
    return [
        section.strip()
        for section in re.split(r"\n\s*\n+", content)
        if section.strip()
    ]


def expand_query(question: str) -> str:
    additions: list[str] = []
    for chinese, english_terms in GLOSSARY.items():
        if chinese in question:
            additions.extend(english_terms)
    return " ".join([question, *additions]).strip()


class DocumentIndex:
    def __init__(
        self,
        document_dir: Path,
        cache_dir: Path | None = None,
        allowed_extensions: set[str] | None = None,
    ):
        self.document_dir = document_dir
        self.cache_dir = cache_dir or (document_dir / ".cache")
        self.allowed_extensions = {
            extension.lower()
            for extension in (allowed_extensions or {".pdf"})
        }
        self.documents: dict[str, Document] = {}
        self.chunks: list[Chunk] = []
        self.vectorizer: FeatureUnion | None = None
        self.matrix = None
        self.semantic_model = None
        self.semantic_matrix: np.ndarray | None = None
        self.semantic_error = ""
        self.semantic_cache_hit = False
        self._lock = threading.RLock()

    def _semantic_fingerprint(self, chunks: list[Chunk]) -> str:
        digest = hashlib.sha256(SEMANTIC_MODEL_NAME.encode("utf-8"))
        for chunk in chunks:
            digest.update(chunk.document_id.encode("utf-8"))
            digest.update(str(chunk.page).encode("ascii"))
            digest.update(chunk.text.encode("utf-8"))
        return digest.hexdigest()

    def _build_semantic_index(
        self,
        chunks: list[Chunk],
    ) -> tuple[object | None, np.ndarray | None, bool, str]:
        if os.getenv("SOILLENS_DISABLE_SEMANTIC", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            return None, None, False, "已通过环境变量禁用语义检索。"
        if TextEmbedding is None:
            return None, None, False, "未安装 fastembed，已使用关键词检索。"

        cache_dir = self.cache_dir / "fastembed"
        cache_dir.mkdir(parents=True, exist_ok=True)
        matrix_path = self.cache_dir / "semantic-index.npz"
        fingerprint = self._semantic_fingerprint(chunks)

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"The model .* now uses mean pooling.*",
                    category=UserWarning,
                )
                model = TextEmbedding(
                    model_name=SEMANTIC_MODEL_NAME,
                    cache_dir=str(cache_dir),
                    threads=max(1, min(4, os.cpu_count() or 1)),
                )

            cache_hit = False
            semantic_matrix: np.ndarray | None = None
            if matrix_path.exists():
                with np.load(matrix_path, allow_pickle=False) as cached:
                    cached_fingerprint = str(cached["fingerprint"].item())
                    cached_matrix = np.asarray(cached["matrix"], dtype=np.float32)
                if (
                    cached_fingerprint == fingerprint
                    and cached_matrix.shape[0] == len(chunks)
                ):
                    semantic_matrix = cached_matrix
                    cache_hit = True

            if semantic_matrix is None:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r"The model .* now uses mean pooling.*",
                        category=UserWarning,
                    )
                    semantic_matrix = np.asarray(
                        list(
                            model.embed(
                                [chunk.text for chunk in chunks],
                                batch_size=64,
                            )
                        ),
                        dtype=np.float32,
                    )
                norms = np.linalg.norm(semantic_matrix, axis=1, keepdims=True)
                semantic_matrix = semantic_matrix / np.clip(norms, 1e-9, None)
                np.savez_compressed(
                    matrix_path,
                    fingerprint=np.asarray(fingerprint),
                    matrix=semantic_matrix,
                )

            return model, semantic_matrix, cache_hit, ""
        except Exception as exc:  # Network/model failures must not block lexical RAG.
            logging.getLogger(__name__).warning("Semantic index unavailable: %s", exc)
            return None, None, False, str(exc)

    def rebuild(self) -> dict[str, int]:
        documents: dict[str, Document] = {}
        chunks: list[Chunk] = []

        supported_paths = [
            path
            for path in self.document_dir.iterdir()
            if path.is_file() and path.suffix.lower() in self.allowed_extensions
        ] if self.document_dir.exists() else []
        for document_path in sorted(supported_paths, key=lambda p: p.name.lower()):
            doc_id = hashlib.sha1(document_path.name.encode("utf-8")).hexdigest()[:12]
            source_type = "pdf" if document_path.suffix.lower() == ".pdf" else "text"
            if source_type == "pdf":
                reader = PdfReader(str(document_path))
                sections = [page.extract_text() or "" for page in reader.pages]
                location_label = "页"
            else:
                sections = _read_text_sections(document_path)
                location_label = "节"
            document = Document(
                id=doc_id,
                title=_document_title(document_path.name),
                filename=document_path.name,
                path=str(document_path.resolve()),
                pages=len(sections),
                source_type=source_type,
                location_label=location_label,
            )
            documents[doc_id] = document

            for page_number, section_text in enumerate(sections, start=1):
                for text in _chunk_page(section_text):
                    chunks.append(
                        Chunk(
                            document_id=doc_id,
                            title=document.title,
                            filename=document.filename,
                            page=page_number,
                            source_type=source_type,
                            location_label=location_label,
                            text=text,
                        )
                    )

        if not chunks:
            raise RuntimeError("没有从知识库文档中提取到可检索文字。")

        vectorizer = FeatureUnion(
            [
                (
                    "words",
                    TfidfVectorizer(
                        lowercase=True,
                        stop_words="english",
                        ngram_range=(1, 2),
                        sublinear_tf=True,
                    ),
                ),
                (
                    "characters",
                    TfidfVectorizer(
                        lowercase=True,
                        analyzer="char_wb",
                        ngram_range=(3, 5),
                        sublinear_tf=True,
                    ),
                ),
            ],
            transformer_weights={"words": 0.72, "characters": 0.28},
        )
        matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])
        semantic_model, semantic_matrix, semantic_cache_hit, semantic_error = (
            self._build_semantic_index(chunks)
        )

        with self._lock:
            self.documents = documents
            self.chunks = chunks
            self.vectorizer = vectorizer
            self.matrix = matrix
            self.semantic_model = semantic_model
            self.semantic_matrix = semantic_matrix
            self.semantic_cache_hit = semantic_cache_hit
            self.semantic_error = semantic_error

        return self.stats()

    def stats(self) -> dict[str, int]:
        return {
            "documents": len(self.documents),
            "pages": sum(document.pages for document in self.documents.values()),
            "chunks": len(self.chunks),
        }

    def retrieval_status(self) -> dict[str, object]:
        return {
            "mode": (
                "关键词 + 多语种语义混合检索"
                if self.semantic_model is not None and self.semantic_matrix is not None
                else "关键词检索"
            ),
            "semantic_available": (
                self.semantic_model is not None and self.semantic_matrix is not None
            ),
            "semantic_model": (
                SEMANTIC_MODEL_NAME
                if self.semantic_model is not None and self.semantic_matrix is not None
                else None
            ),
            "semantic_cache_hit": self.semantic_cache_hit,
            "fallback_reason": self.semantic_error,
        }

    def list_documents(self) -> list[dict[str, object]]:
        return [
            document.public_dict()
            for document in sorted(self.documents.values(), key=lambda item: item.title.lower())
        ]

    def get_document(self, document_id: str) -> Document | None:
        return self.documents.get(document_id)

    def search(self, question: str, top_k: int = 5) -> list[dict[str, object]]:
        with self._lock:
            if self.vectorizer is None or self.matrix is None:
                raise RuntimeError("文档索引尚未构建。")
            query = self.vectorizer.transform([expand_query(question)])
            lexical_scores = (self.matrix @ query.T).toarray().ravel()
            semantic_scores: np.ndarray | None = None
            if self.semantic_model is not None and self.semantic_matrix is not None:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r"The model .* now uses mean pooling.*",
                        category=UserWarning,
                    )
                    semantic_query = np.asarray(
                        list(self.semantic_model.query_embed([question]))[0],
                        dtype=np.float32,
                    )
                semantic_query = semantic_query / max(
                    float(np.linalg.norm(semantic_query)),
                    1e-9,
                )
                semantic_scores = self.semantic_matrix @ semantic_query

        lexical_max = float(np.max(lexical_scores)) if lexical_scores.size else 0.0
        semantic_max = (
            float(np.max(semantic_scores))
            if semantic_scores is not None and semantic_scores.size
            else None
        )
        retrieval_method = "关键词检索"
        ranking_scores = lexical_scores
        if semantic_scores is not None and lexical_max < LEXICAL_ROUTE_THRESHOLD:
            lexical_ranks = np.empty(len(lexical_scores), dtype=np.int32)
            lexical_ranks[np.argsort(lexical_scores)[::-1]] = np.arange(
                1,
                len(lexical_scores) + 1,
            )
            semantic_ranks = np.empty(len(semantic_scores), dtype=np.int32)
            semantic_ranks[np.argsort(semantic_scores)[::-1]] = np.arange(
                1,
                len(semantic_scores) + 1,
            )
            lexical_rrf = np.where(
                lexical_scores > 0,
                1.0 / (RRF_K + lexical_ranks),
                0.0,
            )
            ranking_scores = lexical_rrf + (
                SEMANTIC_RRF_WEIGHT / (RRF_K + semantic_ranks)
            )
            retrieval_method = "关键词 + 语义融合"

        ranking = np.argsort(ranking_scores)[::-1]
        results: list[dict[str, object]] = []
        seen_pages: set[tuple[str, int]] = set()

        for index in ranking:
            ranking_score = float(ranking_scores[index])
            if ranking_score <= 0:
                continue
            chunk = self.chunks[int(index)]
            page_key = (chunk.document_id, chunk.page)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            lexical_score = float(lexical_scores[index])
            semantic_score = (
                float(semantic_scores[index])
                if semantic_scores is not None
                else None
            )
            results.append(
                {
                    "document_id": chunk.document_id,
                    "title": chunk.title,
                    "filename": chunk.filename,
                    "page": chunk.page,
                    "source_type": chunk.source_type,
                    "location_label": chunk.location_label,
                    "score": round(
                        semantic_score if semantic_score is not None else lexical_score,
                        4,
                    ),
                    "lexical_score": round(lexical_score, 4),
                    "semantic_score": (
                        round(semantic_score, 4)
                        if semantic_score is not None
                        else None
                    ),
                    "query_semantic_score": (
                        round(semantic_max, 4)
                        if semantic_max is not None
                        else None
                    ),
                    "retrieval_method": retrieval_method,
                    "text": chunk.text,
                }
            )
            if len(results) >= top_k:
                break
        return results
