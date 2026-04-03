import json
import tempfile
import unittest
from pathlib import Path

from figure_reconstruction import detect_reconstruction_groups, reconstruct_content_list


REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CONTENT_LIST = REPO_ROOT / "docs" / "docs_parser" / "caf89a99-eccd-4042-8f87-e3912b1eb2a8" / "156d77aa-b95a-4213-be4d-278219204812_content_list.json"


class FigureReconstructionTest(unittest.TestCase):
    def test_detects_fragmented_figures_in_sample(self) -> None:
        items = json.loads(SAMPLE_CONTENT_LIST.read_text(encoding="utf-8"))
        groups = detect_reconstruction_groups(items)

        self.assertEqual(len(groups), 3)
        self.assertEqual([group.anchor_idx for group in groups], [54, 134, 221])
        self.assertEqual(groups[0].union_bbox, [176, 104, 821, 422])
        self.assertEqual(groups[1].union_bbox, [174, 104, 816, 224])
        self.assertEqual(groups[2].union_bbox, [192, 157, 800, 842])

    def test_rewrites_sample_and_generates_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_json = temp_path / "content_list_optimized.json"
            output_image_dir = temp_path / "reconstructed_images"

            result = reconstruct_content_list(
                content_list_path=SAMPLE_CONTENT_LIST,
                output_json_path=output_json,
                output_image_dir=output_image_dir,
                dpi=200,
                render_mode="auto",
            )

            self.assertEqual(result["reconstructed_count"], 3)
            self.assertTrue(output_json.exists())

            optimized_items = json.loads(output_json.read_text(encoding="utf-8"))
            reconstructed = [item for item in optimized_items if item.get("is_reconstructed_figure")]
            self.assertEqual(len(reconstructed), 3)
            self.assertLess(len(optimized_items), len(json.loads(SAMPLE_CONTENT_LIST.read_text(encoding="utf-8"))))

            figure_numbers = [item["reconstruction"]["span"] for item in reconstructed]
            self.assertEqual(figure_numbers, [[23, 55], [133, 134], [171, 222]])

            for image_path in result["generated_images"]:
                self.assertTrue(Path(image_path).exists(), image_path)


if __name__ == "__main__":
    unittest.main()
