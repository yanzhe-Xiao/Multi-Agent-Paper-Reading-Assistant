from __future__ import annotations

import argparse
import copy
import json
import math
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ALLOWED_FRAGMENT_TYPES = {"image", "text", "list", "equation", "code"}
PRIMARY_FIGURE_PATTERN = r"\bFig(?:ure)?\.?\s+\d+\b"
TEXT_CAPTION_TYPES = {"text", "list"}
SUBFIGURE_LABEL_PATTERN = r"\([a-zA-Z]\)"


@dataclass(frozen=True)
class LinearCalibration:
    x_scale: float
    x_offset: float
    y_scale: float
    y_offset: float
    page_width: float
    page_height: float

    def to_pdf_bbox(self, bbox: list[int] | tuple[int, int, int, int]) -> list[float]:
        left = self.x_scale * bbox[0] + self.x_offset
        top = self.y_scale * bbox[1] + self.y_offset
        right = self.x_scale * bbox[2] + self.x_offset
        bottom = self.y_scale * bbox[3] + self.y_offset
        return [
            max(0.0, min(self.page_width, left)),
            max(0.0, min(self.page_height, top)),
            max(0.0, min(self.page_width, right)),
            max(0.0, min(self.page_height, bottom)),
        ]


@dataclass(frozen=True)
class ReconstructionGroup:
    page_idx: int
    start_idx: int
    end_idx: int
    anchor_idx: int
    union_bbox: list[int]
    item_indices: list[int]
    fragment_image_paths: list[str]
    ocr_texts: list[str]


def caption_text(item: dict[str, Any]) -> str:
    parts = item.get("image_caption") or []
    return " ".join(
        part if isinstance(part, str) else str(part.get("content", ""))
        for part in parts
    ).strip()


def item_text(item: dict[str, Any]) -> str:
    return str(item.get("text", "")).strip()


def has_caption(item: dict[str, Any]) -> bool:
    return item.get("type") == "image" and bool(item.get("image_caption"))


def has_primary_figure_caption(item: dict[str, Any]) -> bool:
    if item.get("type") == "image":
        return bool(re.search(PRIMARY_FIGURE_PATTERN, caption_text(item), re.IGNORECASE))
    if item.get("type") in TEXT_CAPTION_TYPES:
        return bool(re.search(PRIMARY_FIGURE_PATTERN, item_text(item), re.IGNORECASE))
    return False


def count_primary_figure_captions(item: dict[str, Any]) -> int:
    if item.get("type") == "image":
        return len(re.findall(PRIMARY_FIGURE_PATTERN, caption_text(item), re.IGNORECASE))
    if item.get("type") in TEXT_CAPTION_TYPES:
        return len(re.findall(PRIMARY_FIGURE_PATTERN, item_text(item), re.IGNORECASE))
    return 0


def is_caption_text_item(item: dict[str, Any]) -> bool:
    if item.get("type") == "image":
        return has_caption(item)
    if item.get("type") in TEXT_CAPTION_TYPES:
        return bool(re.match(rf"^\s*({PRIMARY_FIGURE_PATTERN}[:.]|{SUBFIGURE_LABEL_PATTERN})", item_text(item), re.IGNORECASE))
    return False


def is_unlabeled_image(item: dict[str, Any]) -> bool:
    return item.get("type") == "image" and not item.get("image_caption")


def is_fragment_candidate(item: dict[str, Any]) -> bool:
    return item.get("type") in ALLOWED_FRAGMENT_TYPES and bool(item.get("bbox"))


def has_inline_neighbor_image(items: list[dict[str, Any]], item_idx: int) -> bool:
    item = items[item_idx]
    bbox = item.get("bbox")
    page_idx = item.get("page_idx")
    if not bbox:
        return False

    for neighbor_idx in range(max(0, item_idx - 2), min(len(items), item_idx + 3)):
        if neighbor_idx == item_idx:
            continue
        neighbor = items[neighbor_idx]
        if neighbor.get("page_idx") != page_idx or neighbor.get("type") != "image" or not neighbor.get("bbox"):
            continue
        neighbor_bbox = neighbor["bbox"]
        gap_x = axis_gap(bbox[0], bbox[2], neighbor_bbox[0], neighbor_bbox[2])
        overlap_y = axis_overlap(bbox[1], bbox[3], neighbor_bbox[1], neighbor_bbox[3])
        if gap_x <= 20 and overlap_y >= 8:
            return True
    return False


def is_body_text_block(items: list[dict[str, Any]], item_idx: int) -> bool:
    item = items[item_idx]
    if item.get("type") not in TEXT_CAPTION_TYPES:
        return False
    text = item_text(item)
    if not text:
        return False
    if is_caption_text_item(item):
        return False
    bbox = item.get("bbox") or [0, 0, 0, 0]
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    if has_inline_neighbor_image(items, item_idx):
        return False
    return len(text) > 180 and height >= 30 and width >= 320


def bbox_union(*boxes: list[int] | tuple[int, int, int, int]) -> list[int]:
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def axis_gap(a0: int, a1: int, b0: int, b1: int) -> int:
    if a1 < b0:
        return b0 - a1
    if b1 < a0:
        return a0 - b1
    return 0


def axis_overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


def is_spatially_connected(
    current_bbox: list[int],
    candidate_bbox: list[int],
    candidate_type: str | None = None,
    allow_wide_horizontal_merge: bool = False,
) -> bool:
    gap_x = axis_gap(current_bbox[0], current_bbox[2], candidate_bbox[0], candidate_bbox[2])
    gap_y = axis_gap(current_bbox[1], current_bbox[3], candidate_bbox[1], candidate_bbox[3])
    overlap_x = axis_overlap(current_bbox[0], current_bbox[2], candidate_bbox[0], candidate_bbox[2])
    overlap_y = axis_overlap(current_bbox[1], current_bbox[3], candidate_bbox[1], candidate_bbox[3])

    if gap_x == 0 and gap_y == 0:
        return True
    if gap_y <= 36 and overlap_x >= 12:
        return True
    if gap_x <= 24 and overlap_y >= 12:
        return True
    if candidate_type == "image" and gap_x <= 64 and overlap_y >= 60:
        return True
    if allow_wide_horizontal_merge and candidate_type == "image" and gap_x <= 120 and overlap_y >= 60:
        return True
    if gap_x <= 12 and gap_y <= 12:
        return True
    return False


def is_row_aligned_panel(
    member_bbox: list[int],
    candidate_bbox: list[int],
) -> bool:
    gap_y = axis_gap(member_bbox[1], member_bbox[3], candidate_bbox[1], candidate_bbox[3])
    overlap_x = axis_overlap(member_bbox[0], member_bbox[2], candidate_bbox[0], candidate_bbox[2])
    return gap_y <= 72 and overlap_x >= 80


def is_connected_to_group(
    items: list[dict[str, Any]],
    start_idx: int,
    end_idx: int,
    union_bbox: list[int],
    candidate: dict[str, Any],
    allow_wide_horizontal_merge: bool = False,
) -> bool:
    candidate_bbox = candidate["bbox"]
    if is_spatially_connected(
        union_bbox,
        candidate_bbox,
        candidate.get("type"),
        allow_wide_horizontal_merge=allow_wide_horizontal_merge,
    ):
        return True

    if candidate.get("type") != "image":
        return False

    for idx in range(start_idx, end_idx + 1):
        member = items[idx]
        if member.get("type") != "image" or not member.get("bbox"):
            continue
        if is_row_aligned_panel(member["bbox"], candidate_bbox):
            return True
    return False


def detect_reconstruction_groups(items: list[dict[str, Any]]) -> list[ReconstructionGroup]:
    anchor_indices = [idx for idx, item in enumerate(items) if has_primary_figure_caption(item)]
    if not anchor_indices:
        anchor_indices = [idx for idx, item in enumerate(items) if has_caption(item)]
    groups: list[ReconstructionGroup] = []

    for anchor_pos, anchor_idx in enumerate(anchor_indices):
        lower_bound = anchor_indices[anchor_pos - 1] + 1 if anchor_pos > 0 else 0
        upper_bound = anchor_indices[anchor_pos + 1] - 1 if anchor_pos + 1 < len(anchor_indices) else len(items) - 1
        group = _detect_single_group(items, anchor_idx, lower_bound, upper_bound)
        if group is not None:
            groups.append(group)

    return merge_overlapping_groups(groups, items)


def merge_overlapping_groups(
    groups: list[ReconstructionGroup],
    items: list[dict[str, Any]],
) -> list[ReconstructionGroup]:
    if not groups:
        return []

    sorted_groups = sorted(groups, key=lambda group: (group.page_idx, group.start_idx, group.end_idx, group.anchor_idx))
    merged: list[ReconstructionGroup] = []

    for group in sorted_groups:
        if not merged:
            merged.append(group)
            continue

        prev = merged[-1]
        if prev.page_idx != group.page_idx or group.start_idx > prev.end_idx:
            merged.append(group)
            continue

        merged_indices = sorted(set(prev.item_indices) | set(group.item_indices))
        merged_items = [items[idx] for idx in merged_indices]
        merged[-1] = ReconstructionGroup(
            page_idx=prev.page_idx,
            start_idx=min(prev.start_idx, group.start_idx),
            end_idx=max(prev.end_idx, group.end_idx),
            anchor_idx=max(prev.anchor_idx, group.anchor_idx),
            union_bbox=bbox_union(prev.union_bbox, group.union_bbox),
            item_indices=merged_indices,
            fragment_image_paths=[
                item["img_path"]
                for item in merged_items
                if item.get("type") == "image" and item.get("img_path")
            ],
            ocr_texts=[
                item.get("text", "").strip()
                for item in merged_items
                if item.get("type") != "image" and item.get("text", "").strip()
            ],
        )

    return merged


def _detect_single_group(
    items: list[dict[str, Any]],
    anchor_idx: int,
    lower_bound: int,
    upper_bound: int,
) -> ReconstructionGroup | None:
    anchor = items[anchor_idx]
    if not anchor.get("bbox"):
        return None

    page_idx = anchor.get("page_idx")
    anchor_is_text_caption = anchor.get("type") in TEXT_CAPTION_TYPES
    allow_wide_horizontal_merge = count_primary_figure_captions(anchor) >= 2
    start_idx = anchor_idx
    end_idx = anchor_idx
    union = list(anchor["bbox"])
    changed = True
    while changed:
        changed = False
        prev_idx = start_idx - 1
        while prev_idx >= lower_bound:
            candidate = items[prev_idx]
            if candidate.get("page_idx") != page_idx:
                break
            if has_primary_figure_caption(candidate):
                break
            if not is_fragment_candidate(candidate):
                break
            if is_body_text_block(items, prev_idx):
                break
            if not is_connected_to_group(
                items,
                start_idx,
                end_idx,
                union,
                candidate,
                allow_wide_horizontal_merge=allow_wide_horizontal_merge,
            ):
                break
            start_idx = prev_idx
            union = bbox_union(union, candidate["bbox"])
            changed = True
            prev_idx -= 1

        next_idx = end_idx + 1
        while next_idx <= upper_bound:
            candidate = items[next_idx]
            if candidate.get("page_idx") != page_idx:
                break
            if has_primary_figure_caption(candidate):
                break
            if anchor_is_text_caption and not is_caption_text_item(candidate):
                break
            if not is_fragment_candidate(candidate):
                break
            if is_body_text_block(items, next_idx):
                break
            if not is_connected_to_group(
                items,
                start_idx,
                end_idx,
                union,
                candidate,
                allow_wide_horizontal_merge=allow_wide_horizontal_merge,
            ):
                break
            end_idx = next_idx
            union = bbox_union(union, candidate["bbox"])
            changed = True
            next_idx += 1

    item_indices = list(range(start_idx, end_idx + 1))
    image_item_count = sum(1 for idx in item_indices if items[idx].get("type") == "image")
    if image_item_count <= 1:
        return None

    fragment_image_paths = [
        item["img_path"]
        for item in (items[idx] for idx in item_indices)
        if item.get("type") == "image" and item.get("img_path")
    ]
    ocr_texts = [
        item.get("text", "").strip()
        for item in (items[idx] for idx in item_indices)
        if item.get("type") != "image" and item.get("text", "").strip()
    ]
    return ReconstructionGroup(
        page_idx=page_idx,
        start_idx=start_idx,
        end_idx=end_idx,
        anchor_idx=anchor_idx,
        union_bbox=union,
        item_indices=item_indices,
        fragment_image_paths=fragment_image_paths,
        ocr_texts=ocr_texts,
    )


def reconstruct_content_list(
    content_list_path: str | Path,
    output_json_path: str | Path | None = None,
    output_image_dir: str | Path | None = None,
    dpi: int = 200,
    render_mode: str = "auto",
) -> dict[str, Any]:
    content_list_path = Path(content_list_path)
    content_dir = content_list_path.parent
    items = json.loads(content_list_path.read_text(encoding="utf-8"))
    groups = detect_reconstruction_groups(items)

    if output_json_path is None:
        output_json_path = content_list_path.with_name(f"{content_list_path.stem}_optimized.json")
    else:
        output_json_path = Path(output_json_path)

    if output_image_dir is None:
        output_image_dir = content_dir / "reconstructed_images"
    else:
        output_image_dir = Path(output_image_dir)
    output_image_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = infer_pdf_path(content_list_path)
    layout_path = infer_layout_path(content_list_path)
    calibrations = build_page_calibrations(items, layout_path) if layout_path and layout_path.exists() else {}

    rewritten_items: list[dict[str, Any]] = []
    cursor = 0
    generated_images: list[str] = []
    group_by_start = {group.start_idx: group for group in groups}
    covered_indices = {idx for group in groups for idx in group.item_indices}

    while cursor < len(items):
        group = group_by_start.get(cursor)
        if group is not None:
            merged_item, image_path = build_reconstructed_item(
                group=group,
                items=items,
                content_dir=content_dir,
                output_image_dir=output_image_dir,
                pdf_path=pdf_path,
                calibration=calibrations.get(group.page_idx),
                dpi=dpi,
                render_mode=render_mode,
            )
            rewritten_items.append(merged_item)
            generated_images.append(str(image_path))
            cursor = group.end_idx + 1
            continue

        if cursor not in covered_indices:
            rewritten_items.append(copy.deepcopy(items[cursor]))
        cursor += 1

    output_json_path.write_text(json.dumps(rewritten_items, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "input_json_path": str(content_list_path),
        "output_json_path": str(output_json_path),
        "output_image_dir": str(output_image_dir),
        "reconstructed_count": len(groups),
        "generated_images": generated_images,
        "groups": [group.__dict__ for group in groups],
    }


def build_reconstructed_item(
    group: ReconstructionGroup,
    items: list[dict[str, Any]],
    content_dir: Path,
    output_image_dir: Path,
    pdf_path: Path | None,
    calibration: LinearCalibration | None,
    dpi: int,
    render_mode: str,
) -> tuple[dict[str, Any], Path]:
    caption_parts = collect_caption_parts(group, items)
    image_footnotes = collect_image_footnotes(group, items)
    base_image_item = next(
        (copy.deepcopy(items[idx]) for idx in group.item_indices if items[idx].get("type") == "image"),
        None,
    )
    if base_image_item is None:
        base_image_item = {"type": "image", "image_caption": [], "image_footnote": [], "page_idx": group.page_idx}

    anchor = base_image_item
    anchor["image_caption"] = caption_parts
    anchor["image_footnote"] = image_footnotes

    figure_number = extract_figure_number(caption_parts)
    file_stem = f"page_{group.page_idx + 1:02d}_figure_{figure_number or group.anchor_idx}"
    output_path = output_image_dir / f"{file_stem}.png"

    render_source = render_reconstructed_figure(
        group=group,
        items=items,
        content_dir=content_dir,
        output_path=output_path,
        pdf_path=pdf_path,
        calibration=calibration,
        dpi=dpi,
        render_mode=render_mode,
    )

    anchor["bbox"] = group.union_bbox
    try:
        img_path = output_path.relative_to(content_dir)
    except ValueError:
        img_path = output_path.resolve()
    anchor["img_path"] = str(img_path).replace("\\", "/")
    anchor["is_reconstructed_figure"] = True
    anchor["reconstruction"] = {
        "anchor_index": group.anchor_idx,
        "span": [group.start_idx, group.end_idx],
        "page_idx": group.page_idx,
        "fragment_count": len(group.fragment_image_paths),
        "fragment_img_paths": group.fragment_image_paths,
        "ocr_texts": group.ocr_texts,
        "render_source": render_source,
    }
    return anchor, output_path


def collect_caption_parts(group: ReconstructionGroup, items: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()
    for idx in group.item_indices:
        item = items[idx]
        if item.get("type") == "image":
            for part in item.get("image_caption") or []:
                text = str(part if isinstance(part, str) else part.get("content", "")).strip()
                if text and text not in seen:
                    parts.append(text)
                    seen.add(text)
        elif is_caption_text_item(item):
            text = item_text(item)
            if text and text not in seen:
                parts.append(text)
                seen.add(text)
    return parts


def collect_image_footnotes(group: ReconstructionGroup, items: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()
    for idx in group.item_indices:
        item = items[idx]
        if item.get("type") != "image":
            continue
        for part in item.get("image_footnote") or []:
            text = str(part if isinstance(part, str) else part.get("content", "")).strip()
            if text and text not in seen:
                parts.append(text)
                seen.add(text)
    return parts


def render_reconstructed_figure(
    group: ReconstructionGroup,
    items: list[dict[str, Any]],
    content_dir: Path,
    output_path: Path,
    pdf_path: Path | None,
    calibration: LinearCalibration | None,
    dpi: int,
    render_mode: str,
) -> str:
    render_mode = render_mode.lower()
    if render_mode not in {"auto", "pdf", "composite"}:
        raise ValueError(f"Unsupported render_mode: {render_mode}")

    if render_mode in {"auto", "pdf"} and pdf_path and calibration:
        try:
            render_pdf_crop(
                pdf_path=pdf_path,
                output_path=output_path,
                page_idx=group.page_idx,
                content_bbox=group.union_bbox,
                calibration=calibration,
                dpi=dpi,
            )
            return "pdf_crop"
        except Exception:
            if render_mode == "pdf":
                raise

    render_fragment_composite(
        group=group,
        items=items,
        content_dir=content_dir,
        output_path=output_path,
    )
    return "fragment_composite"


def render_pdf_crop(
    pdf_path: Path,
    output_path: Path,
    page_idx: int,
    content_bbox: list[int],
    calibration: LinearCalibration,
    dpi: int,
) -> None:
    pdftoppm = shutil.which("pdftoppm.exe") or shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm is not available in PATH.")

    pdf_bbox = calibration.to_pdf_bbox(content_bbox)
    padding_points = 4
    pdf_bbox = [
        max(0.0, pdf_bbox[0] - padding_points),
        max(0.0, pdf_bbox[1] - padding_points),
        min(calibration.page_width, pdf_bbox[2] + padding_points),
        min(calibration.page_height, pdf_bbox[3] + padding_points),
    ]

    crop_x = max(0, int(math.floor(pdf_bbox[0] * dpi / 72.0)))
    crop_y = max(0, int(math.floor(pdf_bbox[1] * dpi / 72.0)))
    crop_w = max(1, int(math.ceil((pdf_bbox[2] - pdf_bbox[0]) * dpi / 72.0)))
    crop_h = max(1, int(math.ceil((pdf_bbox[3] - pdf_bbox[1]) * dpi / 72.0)))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_prefix = output_path.with_suffix("")
    command = [
        pdftoppm,
        "-f",
        str(page_idx + 1),
        "-l",
        str(page_idx + 1),
        "-singlefile",
        "-png",
        "-r",
        str(dpi),
        "-x",
        str(crop_x),
        "-y",
        str(crop_y),
        "-W",
        str(crop_w),
        "-H",
        str(crop_h),
        str(pdf_path),
        str(output_prefix),
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def render_fragment_composite(
    group: ReconstructionGroup,
    items: list[dict[str, Any]],
    content_dir: Path,
    output_path: Path,
) -> None:
    union = group.union_bbox
    width = max(1, int(math.ceil(union[2] - union[0])))
    height = max(1, int(math.ceil(union[3] - union[1])))
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for idx in group.item_indices:
        item = items[idx]
        bbox = item.get("bbox")
        if not bbox:
            continue
        local_bbox = [
            int(round(bbox[0] - union[0])),
            int(round(bbox[1] - union[1])),
            int(round(bbox[2] - union[0])),
            int(round(bbox[3] - union[1])),
        ]
        if item.get("type") == "image" and item.get("img_path"):
            render_image_fragment(canvas, content_dir, item["img_path"], local_bbox)
            continue
        render_text_fragment(draw, item.get("text", "").strip(), local_bbox, font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def render_image_fragment(canvas: Image.Image, content_dir: Path, img_path: str, local_bbox: list[int]) -> None:
    source_path = content_dir / img_path
    if not source_path.exists():
        return
    width = max(1, local_bbox[2] - local_bbox[0])
    height = max(1, local_bbox[3] - local_bbox[1])
    with Image.open(source_path) as fragment:
        prepared = fragment.convert("RGB").resize((width, height))
        canvas.paste(prepared, (local_bbox[0], local_bbox[1]))


def render_text_fragment(draw: ImageDraw.ImageDraw, text: str, local_bbox: list[int], font: ImageFont.ImageFont) -> None:
    if not text:
        return
    width = max(1, local_bbox[2] - local_bbox[0])
    avg_char_width = max(6, font.getbbox("A")[2])
    wrap_width = max(1, width // avg_char_width)
    wrapped = textwrap.fill(text, width=wrap_width)
    draw.multiline_text((local_bbox[0], local_bbox[1]), wrapped, font=font, fill="black", spacing=2)


def infer_pdf_path(content_list_path: Path) -> Path | None:
    if content_list_path.name.endswith("_content_list.json"):
        stem = content_list_path.name.removesuffix("_content_list.json")
        pdf_path = content_list_path.with_name(f"{stem}_origin.pdf")
        if pdf_path.exists():
            return pdf_path
    return None


def infer_layout_path(content_list_path: Path) -> Path | None:
    layout_path = content_list_path.with_name("layout.json")
    return layout_path if layout_path.exists() else None


def build_page_calibrations(
    content_items: list[dict[str, Any]],
    layout_path: Path,
) -> dict[int, LinearCalibration]:
    layout_pages = json.loads(layout_path.read_text(encoding="utf-8")).get("pdf_info", [])
    content_by_page: dict[int, list[dict[str, Any]]] = {}
    for item in content_items:
        content_by_page.setdefault(item.get("page_idx"), []).append(item)

    calibrations: dict[int, LinearCalibration] = {}
    for page_idx, layout_page in enumerate(layout_pages):
        content_page = [item for item in content_by_page.get(page_idx, []) if normalized_content_type(item)]
        layout_blocks = [block for block in layout_page.get("para_blocks", []) if normalized_layout_type(block)]
        if not content_page or not layout_blocks:
            continue

        matched_pairs = []
        content_ptr = 0
        layout_ptr = 0
        page_mismatch = False
        while content_ptr < len(content_page) and layout_ptr < len(layout_blocks):
            content_type = normalized_content_type(content_page[content_ptr])
            layout_type = normalized_layout_type(layout_blocks[layout_ptr])
            if content_type != layout_type:
                page_mismatch = True
                break
            matched_pairs.append((content_page[content_ptr]["bbox"], layout_blocks[layout_ptr]["bbox"]))
            content_ptr += 1
            layout_ptr += 1

        if page_mismatch or len(matched_pairs) < 2:
            continue

        page_size = layout_page.get("page_size", [612, 792])
        calibrations[page_idx] = fit_calibration(matched_pairs, page_size=page_size)

    return calibrations


def normalized_content_type(item: dict[str, Any]) -> str | None:
    item_type = item.get("type")
    if item_type == "page_number":
        return None
    if item_type in {"text", "aside_text", "page_footnote", "list", "equation", "code"}:
        return "text"
    return item_type


def normalized_layout_type(item: dict[str, Any]) -> str | None:
    item_type = item.get("type")
    if item_type in {
        "text",
        "title",
        "page_footnote",
        "page_aside_text",
        "list",
        "equation_interline",
        "interline_equation",
        "algorithm",
    }:
        return "text"
    return item_type


def fit_calibration(
    matched_pairs: list[tuple[list[int], list[int]]],
    page_size: list[int] | tuple[int, int],
) -> LinearCalibration:
    x_points: list[tuple[float, float]] = []
    y_points: list[tuple[float, float]] = []
    for content_bbox, layout_bbox in matched_pairs:
        x_points.extend([(content_bbox[0], layout_bbox[0]), (content_bbox[2], layout_bbox[2])])
        y_points.extend([(content_bbox[1], layout_bbox[1]), (content_bbox[3], layout_bbox[3])])

    x_scale, x_offset = fit_axis(x_points)
    y_scale, y_offset = fit_axis(y_points)
    return LinearCalibration(
        x_scale=x_scale,
        x_offset=x_offset,
        y_scale=y_scale,
        y_offset=y_offset,
        page_width=page_size[0],
        page_height=page_size[1],
    )


def fit_axis(points: list[tuple[float, float]]) -> tuple[float, float]:
    count = len(points)
    sum_x = sum(point[0] for point in points)
    sum_y = sum(point[1] for point in points)
    sum_xx = sum(point[0] * point[0] for point in points)
    sum_xy = sum(point[0] * point[1] for point in points)
    denominator = count * sum_xx - sum_x * sum_x
    if denominator == 0:
        raise ValueError("Cannot fit calibration with zero denominator.")
    scale = (count * sum_xy - sum_x * sum_y) / denominator
    offset = (sum_y - scale * sum_x) / count
    return scale, offset


def extract_figure_number(caption_items: list[Any]) -> str | None:
    caption = " ".join(str(item) if isinstance(item, str) else str(item.get("content", "")) for item in caption_items).strip()
    match = re.search(PRIMARY_FIGURE_PATTERN, caption, re.IGNORECASE)
    if not match:
        return None
    parts = match.group(0).split()
    return parts[1].rstrip(".")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconstruct fragmented MinerU figures.")
    parser.add_argument("content_list_path", help="Path to the MinerU content_list.json file.")
    parser.add_argument("--output-json", dest="output_json_path", help="Path to write the optimized JSON.")
    parser.add_argument("--output-image-dir", dest="output_image_dir", help="Directory for reconstructed figure images.")
    parser.add_argument("--dpi", type=int, default=200, help="DPI used for PDF crop rendering.")
    parser.add_argument(
        "--render-mode",
        choices=["auto", "pdf", "composite"],
        default="auto",
        help="How to render reconstructed figures.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = reconstruct_content_list(
        content_list_path=args.content_list_path,
        output_json_path=args.output_json_path,
        output_image_dir=args.output_image_dir,
        dpi=args.dpi,
        render_mode=args.render_mode,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
