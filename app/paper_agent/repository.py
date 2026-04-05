from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable

from .config import PaperAgentConfig
from .schemas import FigureAsset, RetrievedChunk

try:
    from app.database.crud import get_image_by_paper_and_img_id, get_images_by_paper_id, get_paper
    from app.database.database import get_db_session
except Exception:
    get_db_session = None
    get_paper = None
    get_images_by_paper_id = None
    get_image_by_paper_and_img_id = None


WORD_RE = re.compile(r"[A-Za-z0-9_]+")
FIGURE_REF_RE = re.compile(r"(?:fig(?:ure)?\.?)[\s:-]*(\d+)", re.IGNORECASE)


class PaperRepository:
    def __init__(self, config: PaperAgentConfig):
        self.config = config
        self.docs_root = config.docs_root or (Path(__file__).resolve().parents[2] / "docs" / "docs_parser")

    def resolve_paper_dir(self, paper_id: str) -> Path:
        paper_dir = self.docs_root / paper_id
        if not paper_dir.exists():
            raise FileNotFoundError(f"Paper directory not found for {paper_id}: {paper_dir}")
        return paper_dir

    def list_paper_ids(self) -> list[str]:
        if not self.docs_root.exists():
            return []
        return sorted(path.name for path in self.docs_root.iterdir() if path.is_dir())

    def load_markdown(self, paper_id: str) -> str:
        path = self.resolve_paper_dir(paper_id) / "full_optimized.md"
        return path.read_text(encoding="utf-8")

    def load_paper_title(self, paper_id: str) -> str | None:
        paper = self.load_paper_record(paper_id)
        if paper is not None and getattr(paper, "title", None):
            return str(paper.title)

        markdown = self.load_markdown(paper_id)
        for line in markdown.splitlines():
            cleaned = line.strip()
            if cleaned.startswith("# "):
                return cleaned.removeprefix("# ").strip()
            if cleaned:
                return cleaned[:160]
        return None

    def load_paper_record(self, paper_id: str):
        if get_db_session is None or get_paper is None:
            return None
        try:
            with get_db_session() as db:
                return get_paper(db, paper_id)
        except Exception:
            return None

    def chunk_markdown(self, paper_id: str) -> list[RetrievedChunk]:
        text = self.load_markdown(paper_id)
        return list(
            self._build_chunks(
                paper_id=paper_id,
                text=text,
                source_path=str(self.resolve_paper_dir(paper_id) / "full_optimized.md"),
                title=self.load_paper_title(paper_id),
            )
        )

    def retrieve_chunks(self, query: str, paper_ids: list[str], top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or self.config.retrieval_top_k
        candidates: list[RetrievedChunk] = []
        for paper_id in paper_ids:
            candidates.extend(self.chunk_markdown(paper_id))

        query_terms = self._tokenize(query)
        if not query_terms:
            return candidates[:top_k]

        for chunk in candidates:
            chunk.score = self._score_chunk(chunk.content, query_terms)

        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    def compare_papers(self, query: str, paper_ids: list[str], top_k_per_paper: int = 2) -> dict[str, list[RetrievedChunk]]:
        comparisons: dict[str, list[RetrievedChunk]] = {}
        for paper_id in paper_ids:
            comparisons[paper_id] = self.retrieve_chunks(
                query=query,
                paper_ids=[paper_id],
                top_k=top_k_per_paper,
            )
        return comparisons

    def build_figure_map(self, paper_id: str) -> list[FigureAsset]:
        assets = self.list_figures(paper_id)
        return sorted(assets, key=lambda item: item.img_id)

    def list_figures(self, paper_id: str) -> list[FigureAsset]:
        db_assets = self._list_figures_from_db(paper_id)
        if db_assets:
            return db_assets
        return self._list_figures_from_json(paper_id)

    def get_figure(self, paper_id: str, img_id: int) -> FigureAsset | None:
        if get_db_session is not None and get_image_by_paper_and_img_id is not None:
            try:
                with get_db_session() as db:
                    row = get_image_by_paper_and_img_id(db, paper_id, img_id)
                if row is not None:
                    return self._row_to_asset(paper_id, row)
            except Exception:
                pass

        for asset in self._list_figures_from_json(paper_id):
            if asset.img_id == img_id:
                return asset
        return None

    def _list_figures_from_db(self, paper_id: str) -> list[FigureAsset]:
        if get_db_session is None or get_images_by_paper_id is None:
            return []
        try:
            with get_db_session() as db:
                rows = get_images_by_paper_id(db, paper_id)
            return [self._row_to_asset(paper_id, row) for row in rows]
        except Exception:
            return []

    def _row_to_asset(self, paper_id: str, row) -> FigureAsset:
        paper_dir = self.resolve_paper_dir(paper_id)
        img_path = str(row.img_path)
        absolute_path = str((paper_dir / img_path).resolve())
        return FigureAsset(
            paper_id=paper_id,
            img_id=int(row.img_id),
            img_path=img_path,
            absolute_path=absolute_path,
            is_checked=bool(getattr(row, "is_check", False)),
        )

    def _list_figures_from_json(self, paper_id: str) -> list[FigureAsset]:
        paper_dir = self.resolve_paper_dir(paper_id)
        json_paths = sorted(paper_dir.glob("*_content_list_optimized.json"))
        if not json_paths:
            return []

        items = json.loads(json_paths[0].read_text(encoding="utf-8"))
        figures: list[FigureAsset] = []
        seen_pairs: set[tuple[int, str]] = set()
        fallback_img_id = 1

        for item in items:
            if item.get("type") != "image" or "img_path" not in item:
                continue

            img_path = str(item["img_path"])
            caption_list = item.get("image_caption") or []
            caption = " ".join(part for part in caption_list if part).strip() or None
            figure_ids = self._extract_figure_ids_from_captions(caption_list)
            if not figure_ids:
                while (fallback_img_id, img_path) in seen_pairs:
                    fallback_img_id += 1
                figure_ids = [fallback_img_id]
                fallback_img_id += 1

            for figure_id in figure_ids:
                pair = (figure_id, img_path)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                figures.append(
                    FigureAsset(
                        paper_id=paper_id,
                        img_id=figure_id,
                        img_path=img_path,
                        absolute_path=str((paper_dir / img_path).resolve()),
                        caption=caption,
                        page_idx=item.get("page_idx"),
                    )
                )
        return sorted(figures, key=lambda item: item.img_id)

    def _extract_figure_ids_from_captions(self, captions: list[str]) -> list[int]:
        figure_ids: list[int] = []
        for caption in captions:
            for match in FIGURE_REF_RE.findall(caption or ""):
                if match.isdigit():
                    figure_ids.append(int(match))
        return self._unique_ints(figure_ids)

    def _build_chunks(
        self,
        paper_id: str,
        text: str,
        source_path: str,
        title: str | None,
    ) -> Iterable[RetrievedChunk]:
        normalized = text.replace("\r\n", "\n")
        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]

        buffer = ""
        chunk_index = 0
        for paragraph in paragraphs:
            candidate = paragraph if not buffer else f"{buffer}\n\n{paragraph}"
            if len(candidate) <= self.config.chunk_size:
                buffer = candidate
                continue

            if buffer:
                yield RetrievedChunk(
                    paper_id=paper_id,
                    chunk_id=f"{paper_id}-chunk-{chunk_index}",
                    content=buffer,
                    source_path=source_path,
                    title=title,
                )
                chunk_index += 1

            if len(paragraph) <= self.config.chunk_size:
                buffer = paragraph
                continue

            start = 0
            step = max(1, self.config.chunk_size - self.config.chunk_overlap)
            while start < len(paragraph):
                end = start + self.config.chunk_size
                piece = paragraph[start:end]
                yield RetrievedChunk(
                    paper_id=paper_id,
                    chunk_id=f"{paper_id}-chunk-{chunk_index}",
                    content=piece,
                    source_path=source_path,
                    title=title,
                )
                chunk_index += 1
                start += step
            buffer = ""

        if buffer:
            yield RetrievedChunk(
                paper_id=paper_id,
                chunk_id=f"{paper_id}-chunk-{chunk_index}",
                content=buffer,
                source_path=source_path,
                title=title,
            )

    def _score_chunk(self, content: str, query_terms: list[str]) -> float:
        if not content.strip():
            return 0.0
        tokens = self._tokenize(content)
        if not tokens:
            return 0.0

        frequencies: dict[str, int] = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1

        score = 0.0
        for term in query_terms:
            term_count = frequencies.get(term, 0)
            if term_count:
                score += 1.0 + math.log1p(term_count)

        if "figure" in query_terms or "fig" in query_terms:
            score += 0.2 * content.lower().count("figure")

        return score

    def _tokenize(self, text: str) -> list[str]:
        ascii_terms = [token.lower() for token in WORD_RE.findall(text)]
        chinese_terms = [char for char in text if "\u4e00" <= char <= "\u9fff"]
        return ascii_terms + chinese_terms

    def _unique_ints(self, values: list[int]) -> list[int]:
        seen: set[int] = set()
        result: list[int] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
