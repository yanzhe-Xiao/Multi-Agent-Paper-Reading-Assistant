import tempfile
import unittest
from pathlib import Path

from app.parser_pdf.full_markdown_figure_rewriter import replace_fragmented_figures_in_markdown


REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = REPO_ROOT / "docs" / "docs_parser" / "caf89a99-eccd-4042-8f87-e3912b1eb2a8"
FULL_MD = DOC_DIR / "full.md"
CONTENT_LIST = DOC_DIR / "156d77aa-b95a-4213-be4d-278219204812_content_list.json"
OPTIMIZED_JSON = DOC_DIR / "156d77aa-b95a-4213-be4d-278219204812_content_list_optimized.json"


class FullMarkdownFigureRewriterTest(unittest.TestCase):
    def test_rewrites_fragmented_figures_in_full_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_md = Path(temp_dir) / "full_optimized.md"
            result = replace_fragmented_figures_in_markdown(
                full_md_path=FULL_MD,
                original_content_list_path=CONTENT_LIST,
                optimized_content_list_path=OPTIMIZED_JSON,
                output_md_path=output_md,
            )

            self.assertEqual(result["replacement_count"], 3)
            text = output_md.read_text(encoding="utf-8")

            self.assertIn("![](reconstructed_images/page_03_figure_2.png)", text)
            self.assertIn("![](reconstructed_images/page_09_figure_4.png)", text)
            self.assertIn("![](reconstructed_images/page_16_figure_7.png)", text)

            self.assertNotIn("![](images/236256fd86ffdd57e1f50644c07a3572cf5880ca30593a1da2b3192f24163493.jpg)", text)
            self.assertNotIn("![](images/c82915c8fc030dda3b23c3dd4d683ec09a268bac63b4c4384697843255fbf741.jpg)", text)
            self.assertNotIn("![](images/fba7228b2e72c7c7aad51e8256c966caf13ba149cc83dee7bf522b5bd17b1cd9.jpg)", text)

            self.assertNotIn("There's a fork ahead, and at the end of the hallway to the front right", text)
            self.assertNotIn("A painting is hanging in the center of the wall.", text)


if __name__ == "__main__":
    unittest.main()
