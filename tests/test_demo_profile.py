from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from app.assessment import AssessmentDataset, calculate_assessment, calculate_batch_assessment
from app.config import AppSettings
from app.indexer import DocumentIndex


ROOT = Path(__file__).resolve().parents[1]


class DemoProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(
            os.environ,
            {
                "SOILLENS_PROFILE": "demo",
                "SOILLENS_DISABLE_SEMANTIC": "1",
            },
            clear=False,
        ):
            cls.settings = AppSettings.from_environment(ROOT)
            cls.index = DocumentIndex(
                cls.settings.document_dir,
                cls.settings.cache_dir,
                allowed_extensions={".md", ".txt"},
            )
            cls.index.rebuild()
        cls.dataset = AssessmentDataset(
            cls.settings.sample_file,
            cls.settings.assessment_source,
            synthetic=True,
        )

    def test_demo_paths_are_isolated_from_private_data(self):
        self.assertTrue(self.settings.is_demo)
        self.assertEqual(self.settings.document_dir, (ROOT / "demo_data" / "documents").resolve())
        self.assertEqual(self.settings.sample_file, (ROOT / "demo_data" / "Sample_demo.xlsx").resolve())
        self.assertNotIn("private_data", str(self.settings.sample_file))
        self.assertFalse(self.settings.public_dict()["evaluation_available"])

    def test_original_demo_documents_are_indexed_as_sections(self):
        stats = self.index.stats()
        self.assertEqual(stats["documents"], 3)
        self.assertEqual(stats["pages"], 16)
        self.assertGreaterEqual(stats["chunks"], 16)
        self.assertTrue(
            all(
                document["source_type"] == "text"
                and document["location_label"] == "节"
                for document in self.index.list_documents()
            )
        )

    def test_demo_questions_retrieve_the_expected_original_material(self):
        cases = [
            ("综合污染指数 PLI 如何计算？", "土壤重金属评价演示知识"),
            ("植物修复有哪些基本路径？", "植物修复演示知识"),
            ("空间交叉验证如何避免信息泄漏？", "机器学习背景值演示知识"),
        ]
        for question, expected_title in cases:
            with self.subTest(question=question):
                results = self.index.search(question, top_k=3)
                self.assertTrue(results)
                self.assertEqual(results[0]["title"], expected_title)

    def test_demo_workbook_is_synthetic_and_supports_partial_metals(self):
        config = self.dataset.config()
        self.assertTrue(config["synthetic"])
        self.assertEqual(config["sample_count"], 12)
        self.assertIn("人工合成", config["note"])
        partial = self.dataset.get_sample("DEMO-011")
        self.assertIsNotNone(partial)
        self.assertEqual(set(partial.concentrations), {"As", "Pb"})
        result = calculate_assessment(
            partial.concentrations,
            sample_id=partial.sample_id,
            sample_name=partial.name,
        )
        self.assertEqual(result["summary"]["metal_count"], 2)

    def test_demo_batch_contains_only_demo_ids(self):
        samples = self.dataset.list_samples()
        self.assertTrue(all(sample["sample_id"].startswith("DEMO-") for sample in samples))
        batch = calculate_batch_assessment(samples)
        self.assertEqual(batch["summary"]["sample_count"], 12)
        self.assertEqual(batch["summary"]["metal_count"], 8)

    def test_docker_distribution_excludes_private_and_pdf_sources(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertNotIn("COPY . ", dockerfile)
        self.assertIn("demo_data ./demo_data", dockerfile)
        self.assertIn("private_data/", dockerignore)
        self.assertIn("background_values/", dockerignore)
        self.assertIn("/*.pdf", dockerignore)


if __name__ == "__main__":
    unittest.main()
