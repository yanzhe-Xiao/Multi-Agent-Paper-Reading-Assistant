from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from .figure_reconstruction import detect_reconstruction_groups, reconstruct_content_list
except ImportError:
    from figure_reconstruction import detect_reconstruction_groups, reconstruct_content_list


TEXT_LIKE_TYPES = {"text", "list", "equation", "code"}


def split_markdown_blocks(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return re.split(r"\n\s*\n", stripped)


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def is_text_like(item: dict[str, Any]) -> bool:
    return item.get("type") in TEXT_LIKE_TYPES and bool(item.get("text", "").strip())


def caption_text(item: dict[str, Any]) -> str:
    parts = item.get("image_caption") or []
    return " ".join(
        part if isinstance(part, str) else str(part.get("content", ""))
        for part in parts
    ).strip()


def build_replacement_block(item: dict[str, Any]) -> str:
    image_line = f"![]({item['img_path']})"
    caption = caption_text(item)
    if caption:
        return f"{image_line}  \n{caption}"
    return image_line


def find_block_for_item(blocks: list[str], item: dict[str, Any], start_at: int) -> int | None:
    if item.get("type") == "image" and item.get("img_path"):
        image_path = item["img_path"]
        for idx in range(start_at, len(blocks)):
            if image_path in blocks[idx]:
                return idx
        return None

    if is_text_like(item):
        target = normalize_text(item["text"])
        if not target:
            return None
        for idx in range(start_at, len(blocks)):
            candidate = normalize_text(blocks[idx])
            if candidate == target or candidate.startswith(target) or target.startswith(candidate):
                return idx
        return None

    return None


def reconstruction_group_key(group: Any) -> tuple[int | None, int, int]:
    return (getattr(group, "page_idx", None), getattr(group, "start_idx"), getattr(group, "end_idx"))


def reconstructed_item_key(item: dict[str, Any]) -> tuple[int | None, int, int] | None:
    reconstruction = item.get("reconstruction") or {}
    span = reconstruction.get("span")
    if not isinstance(span, list) or len(span) != 2:
        return None
    return (reconstruction.get("page_idx", item.get("page_idx")), span[0], span[1])


def build_reconstructed_item_maps(
    reconstructed_items: list[dict[str, Any]],
) -> tuple[dict[tuple[int | None, int, int], dict[str, Any]], dict[tuple[int | None, int], dict[str, Any]]]:
    by_span: dict[tuple[int | None, int, int], dict[str, Any]] = {}
    by_anchor: dict[tuple[int | None, int], dict[str, Any]] = {}
    for item in reconstructed_items:
        span_key = reconstructed_item_key(item)
        if span_key is not None:
            by_span[span_key] = item

        reconstruction = item.get("reconstruction") or {}
        anchor_index = reconstruction.get("anchor_index")
        page_idx = reconstruction.get("page_idx", item.get("page_idx"))
        if anchor_index is not None:
            by_anchor[(page_idx, anchor_index)] = item
    return by_span, by_anchor


def replace_fragmented_figures_in_markdown(
    full_md_path: str | Path,
    original_content_list_path: str | Path,
    optimized_content_list_path: str | Path | None = None,
    output_md_path: str | Path | None = None,
) -> dict[str, Any]:
    full_md_path = Path(full_md_path)
    original_content_list_path = Path(original_content_list_path)

    if optimized_content_list_path is None:
        optimized_content_list_path = original_content_list_path.with_name(
            f"{original_content_list_path.stem}_optimized.json"
        )
    optimized_content_list_path = Path(optimized_content_list_path)

    if output_md_path is None:
        output_md_path = full_md_path.with_name(f"{full_md_path.stem}_optimized.md")
    output_md_path = Path(output_md_path)

    if not optimized_content_list_path.exists():
        reconstruct_content_list(original_content_list_path, output_json_path=optimized_content_list_path)

    original_items = json.loads(original_content_list_path.read_text(encoding="utf-8"))
    optimized_items = json.loads(optimized_content_list_path.read_text(encoding="utf-8"))
    groups = detect_reconstruction_groups(original_items)
    reconstructed_items = [item for item in optimized_items if item.get("is_reconstructed_figure")]
    reconstructed_by_span, reconstructed_by_anchor = build_reconstructed_item_maps(reconstructed_items)

    markdown_text = full_md_path.read_text(encoding="utf-8")
    blocks = split_markdown_blocks(markdown_text)

    replacements: list[tuple[int, int, str, dict[str, Any]]] = []
    search_cursor = 0
    used_img_paths: set[str] = set()
    for group in groups:
        new_item = reconstructed_by_span.get(reconstruction_group_key(group))
        if new_item is None:
            new_item = reconstructed_by_anchor.get((group.page_idx, group.anchor_idx))
        if new_item is None:
            raise ValueError(
                f"Unable to match reconstructed item for figure span {group.start_idx}-{group.end_idx} on page {group.page_idx}."
            )
        if new_item["img_path"] in used_img_paths:
            raise ValueError(
                f"Reconstructed item {new_item['img_path']} was matched more than once while rewriting Markdown."
            )

        start_block = None
        end_block = None
        local_cursor = search_cursor
        for item_idx in group.item_indices:
            item = original_items[item_idx]
            match_idx = find_block_for_item(blocks, item, local_cursor)
            if match_idx is None:
                continue
            if start_block is None:
                start_block = match_idx
            end_block = match_idx
            local_cursor = match_idx + 1

        if start_block is None or end_block is None:
            raise ValueError(
                f"Unable to locate markdown block range for figure span {group.start_idx}-{group.end_idx}."
            )

        replacements.append((start_block, end_block, build_replacement_block(new_item), new_item))
        used_img_paths.add(new_item["img_path"])
        search_cursor = end_block + 1

    rewritten_blocks: list[str] = []
    cursor = 0
    replacement_summaries = []
    for start_block, end_block, new_block, new_item in replacements:
        rewritten_blocks.extend(blocks[cursor:start_block])
        rewritten_blocks.append(new_block)
        replacement_summaries.append(
            {
                "block_span": [start_block, end_block],
                "new_img_path": new_item["img_path"],
                "caption": caption_text(new_item),
            }
        )
        cursor = end_block + 1
    rewritten_blocks.extend(blocks[cursor:])

    output_md_path.write_text("\n\n".join(rewritten_blocks).strip() + "\n", encoding="utf-8")
    return {
        "input_markdown_path": str(full_md_path),
        "output_markdown_path": str(output_md_path),
        "replacement_count": len(replacements),
        "replacements": replacement_summaries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replace fragmented figure blocks in full.md.")
    parser.add_argument("full_md_path", help="Path to the source full.md file.")
    parser.add_argument("content_list_path", help="Path to the original MinerU content_list.json file.")
    parser.add_argument("--optimized-json", dest="optimized_content_list_path", help="Path to the optimized content_list JSON.")
    parser.add_argument("--output-md", dest="output_md_path", help="Path to write the rewritten Markdown.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = replace_fragmented_figures_in_markdown(
        full_md_path=args.full_md_path,
        original_content_list_path=args.content_list_path,
        optimized_content_list_path=args.optimized_content_list_path,
        output_md_path=args.output_md_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
