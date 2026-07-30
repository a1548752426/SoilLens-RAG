from pathlib import Path
import unittest

from app.indexer import DocumentIndex


ROOT = Path(__file__).resolve().parents[1]


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = DocumentIndex(ROOT)
        cls.index.rebuild()

    def test_all_documents_are_indexed(self):
        stats = self.index.stats()
        self.assertEqual(stats["documents"], 5)
        self.assertEqual(stats["pages"], 70)
        self.assertGreater(stats["chunks"], 100)

    def test_artificial_plant_query_finds_correct_paper(self):
        results = self.index.search(
            "What removal rate did the bioinspired artificial plant achieve for deep soil?",
            top_k=5,
        )
        self.assertTrue(results)
        self.assertIn("Bioinspired Artificial Plant", results[0]["title"])
        self.assertGreaterEqual(results[0]["page"], 1)

    def test_chinese_background_value_query_is_expanded(self):
        results = self.index.search(
            "机器学习如何用于确定土壤重金属自然背景值？",
            top_k=5,
        )
        titles = [result["title"] for result in results[:3]]
        self.assertTrue(
            any("Machine learning-supported determination" in title for title in titles),
            titles,
        )

    def test_source_pages_are_valid(self):
        results = self.index.search("bamboo remediation heavy metal soil", top_k=5)
        self.assertTrue(results)
        for result in results:
            document = self.index.get_document(str(result["document_id"]))
            self.assertIsNotNone(document)
            self.assertGreaterEqual(result["page"], 1)
            self.assertLessEqual(result["page"], document.pages)

    def test_multilingual_semantic_search_finds_unmapped_concept(self):
        status = self.index.retrieval_status()
        self.assertTrue(status["semantic_available"], status)
        results = self.index.search(
            "纳米颗粒通过哪些入口进入植物，哪些颗粒性质会影响吸收？",
            top_k=5,
        )
        self.assertTrue(
            any(
                "Bioremediation of heavy metal" in result["title"]
                and result["page"] == 9
                for result in results
            ),
            [(result["title"], result["page"]) for result in results],
        )
        self.assertTrue(
            any(result["retrieval_method"] == "关键词 + 语义融合" for result in results)
        )

    def test_lexical_fallback_works_without_semantic_model(self):
        fallback = DocumentIndex(ROOT)
        fallback.documents = self.index.documents
        fallback.chunks = self.index.chunks
        fallback.vectorizer = self.index.vectorizer
        fallback.matrix = self.index.matrix
        results = fallback.search("机器学习如何确定土壤重金属背景值？", top_k=3)
        self.assertTrue(results)
        self.assertTrue(
            all(result["retrieval_method"] == "关键词检索" for result in results)
        )


if __name__ == "__main__":
    unittest.main()
