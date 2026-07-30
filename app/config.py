from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppSettings:
    profile: str
    project_root: Path
    document_dir: Path
    sample_file: Path
    assessment_source: Path
    cache_dir: Path

    @classmethod
    def from_environment(cls, project_root: Path) -> "AppSettings":
        profile = os.getenv("SOILLENS_PROFILE", "private").strip().lower()
        if profile not in {"private", "demo"}:
            raise RuntimeError("SOILLENS_PROFILE 只能是 private 或 demo。")

        demo_root = project_root / "demo_data"
        default_document_dir = (
            demo_root / "documents" if profile == "demo" else project_root
        )
        default_sample_file = (
            demo_root / "Sample_demo.xlsx"
            if profile == "demo"
            else project_root / "private_data" / "Sample_hms.xlsx"
        )
        default_source = (
            demo_root / "documents" / "土壤重金属评价演示知识.md"
            if profile == "demo"
            else project_root
            / "background_values"
            / "中国城市土壤化学元素的背景值与基准值_成杭新.pdf"
        )

        return cls(
            profile=profile,
            project_root=project_root.resolve(),
            document_dir=Path(
                os.getenv("SOILLENS_DOCUMENT_DIR", str(default_document_dir))
            ).expanduser().resolve(),
            sample_file=Path(
                os.getenv("SOILLENS_SAMPLE_FILE", str(default_sample_file))
            ).expanduser().resolve(),
            assessment_source=Path(
                os.getenv("SOILLENS_ASSESSMENT_SOURCE", str(default_source))
            ).expanduser().resolve(),
            cache_dir=Path(
                os.getenv(
                    "SOILLENS_CACHE_DIR",
                    str(project_root / ".cache"),
                )
            ).expanduser().resolve(),
        )

    @property
    def is_demo(self) -> bool:
        return self.profile == "demo"

    @property
    def profile_label(self) -> str:
        return "公开合成演示模式" if self.is_demo else "本机私有数据模式"

    @property
    def notice(self) -> str:
        if self.is_demo:
            return (
                "当前只使用原创演示文档和人工合成浓度数据，"
                "不包含真实样点或受版权保护的论文原文。"
            )
        return "当前读取本机资料；真实样点接口仅允许从本机浏览器访问。"

    def public_dict(self) -> dict[str, object]:
        return {
            "id": self.profile,
            "label": self.profile_label,
            "public_demo": self.is_demo,
            "synthetic_data": self.is_demo,
            "evaluation_available": not self.is_demo,
            "notice": self.notice,
        }
