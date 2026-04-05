from pathlib import Path

from app.paper_agent.config import PaperAgentConfig
from app.paper_agent.repository import PaperRepository


SAMPLE_PAPER_ID = "4ffc67ef-8d72-40f9-ba82-23d39052c3db"


def build_repository() -> PaperRepository:
    docs_root = Path(__file__).resolve().parents[1] / "docs" / "docs_parser"
    return PaperRepository(PaperAgentConfig(docs_root=docs_root))


def test_list_paper_ids_returns_local_parsed_papers():
    repository = build_repository()

    paper_ids = repository.list_paper_ids()

    assert SAMPLE_PAPER_ID in paper_ids
    assert len(paper_ids) >= 1


def test_retrieve_chunks_returns_ranked_results():
    repository = build_repository()

    chunks = repository.retrieve_chunks(
        query="coarse map navigation",
        paper_ids=[SAMPLE_PAPER_ID],
        top_k=3,
    )

    assert len(chunks) == 3
    assert all(chunk.paper_id == SAMPLE_PAPER_ID for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)


def test_list_figures_returns_integer_indexed_assets():
    repository = build_repository()

    figures = repository.list_figures(SAMPLE_PAPER_ID)

    assert figures
    assert figures[0].img_id == 1
    assert figures[0].absolute_path.endswith((".png", ".jpg", ".jpeg"))


def test_get_specific_figure_by_id_uses_integer_lookup():
    repository = build_repository()

    figure = repository.get_figure(SAMPLE_PAPER_ID, 1)

    assert figure is not None
    assert figure.img_id == 1
