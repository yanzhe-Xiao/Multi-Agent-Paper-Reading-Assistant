from __future__ import annotations

import argparse
import json

from .runtime import PaperAssistant


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the LangGraph paper-reading assistant.")
    parser.add_argument("query", help="The user question to ask the assistant.")
    parser.add_argument("--paper-id", dest="paper_ids", action="append", help="One paper id to include. Repeatable.")
    parser.add_argument("--thread-id", default="demo-thread", help="Thread id used by the checkpointer.")
    parser.add_argument("--preferences", default="{}", help="JSON object with user preferences.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    preferences = json.loads(args.preferences)
    assistant = PaperAssistant()
    response = assistant.invoke(
        user_query=args.query,
        paper_ids=args.paper_ids,
        thread_id=args.thread_id,
        user_preferences=preferences,
    )
    print(response.final_answer)


if __name__ == "__main__":
    main()
