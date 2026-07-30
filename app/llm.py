from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .indexer import expand_query


@dataclass(slots=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_environment(cls) -> "LLMConfig":
        if os.getenv("LLM_API_KEY") or os.getenv("LLM_MODEL"):
            return cls(
                api_key=os.getenv("LLM_API_KEY", ""),
                base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
                model=os.getenv("LLM_MODEL", ""),
            )
        if os.getenv("OPENAI_API_KEY"):
            return cls(
                api_key=os.getenv("OPENAI_API_KEY", ""),
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
                model=os.getenv("OPENAI_MODEL", ""),
            )
        if os.getenv("DEEPSEEK_API_KEY"):
            return cls(
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url="https://api.deepseek.com/v1",
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            )
        return cls(api_key="", base_url="", model="")

    @property
    def available(self) -> bool:
        local_endpoint = self.base_url.startswith(("http://127.0.0.1", "http://localhost"))
        return bool(self.base_url and self.model and (self.api_key or local_endpoint))

    def public_status(self) -> dict[str, object]:
        return {
            "available": self.available,
            "model": self.model if self.available else "",
            "mode": "AI 综合回答" if self.available else "本地证据检索",
        }


def generate_answer(
    question: str,
    sources: list[dict[str, object]],
    config: LLMConfig,
) -> str:
    source_text = "\n\n".join(
        f"[S{index}] {source['title']}，PDF 第 {source['page']} 页\n"
        f"{str(source['text'])[:2200]}"
        for index, source in enumerate(sources, start=1)
    )

    system_prompt = (
        "你是严谨的土壤环境科研助手。只能依据用户提供的证据回答，不得使用未给出的事实。"
        "请用简洁中文作答，每个事实性结论后必须标注对应来源编号，如 [S1]。"
        "如果证据不足，明确说“现有文档证据不足”，不要猜测。"
    )
    user_prompt = f"问题：{question}\n\n可用证据：\n{source_text}"
    payload = json.dumps(
        {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key or 'local'}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"模型接口返回 {exc.code}：{detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"无法连接模型接口：{exc}") from exc

    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("模型接口返回格式无法识别。") from exc


def extractive_answer(question: str, sources: list[dict[str, object]]) -> str:
    expanded = expand_query(question).lower()
    terms = {
        term
        for term in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", expanded)
        if term not in {"what", "which", "where", "when", "how", "soil", "the", "and", "with"}
    }
    candidates: list[tuple[float, int, str]] = []

    for source_index, source in enumerate(sources, start=1):
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", str(source["text"]))
        for sentence in sentences:
            cleaned = sentence.strip()
            if not 45 <= len(cleaned) <= 520:
                continue
            lowered = cleaned.lower()
            overlap = sum(1 for term in terms if term in lowered)
            number_bonus = 0.4 if re.search(r"\d", cleaned) else 0.0
            score = overlap + float(source["score"]) * 3 + number_bonus
            candidates.append((score, source_index, cleaned))

    selected: list[tuple[int, str]] = []
    seen: set[str] = set()
    for _, source_index, sentence in sorted(candidates, reverse=True):
        fingerprint = re.sub(r"\W+", "", sentence.lower())[:80]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        selected.append((source_index, sentence))
        if len(selected) >= 3:
            break

    if not selected:
        return "当前为本地证据模式。找到了相关页面，但无法自动提炼句子，请直接查看下方来源。"

    bullets = "\n".join(f"- {sentence} [S{source_index}]" for source_index, sentence in selected)
    return (
        "当前未配置大模型，以下为系统从论文中抽取的最相关原文证据：\n\n"
        f"{bullets}\n\n"
        "配置模型接口后，系统会基于同一批证据生成中文综合回答。"
    )

