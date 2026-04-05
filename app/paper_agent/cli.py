from __future__ import annotations

"""命令行入口模块。

用于从终端快速调用论文阅读助手，便于本地调试与演示。
"""

import argparse
import json

from .config import PaperAgentConfig
from .runtime import PaperAssistant


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Run the LangGraph paper-reading assistant.")
    parser.add_argument("query", help="The user question to ask the assistant.")
    parser.add_argument("--paper-id", dest="paper_ids", action="append", help="One paper id to include. Repeatable.")
    parser.add_argument(
        "--all-papers",
        action="store_true",
        help="Explicitly include all locally available papers in the current query.",
    )
    parser.add_argument("--thread-id", default="demo-thread", help="Thread id used by the checkpointer.")
    parser.add_argument("--preferences", default="{}", help="JSON object with user preferences.")
    parser.add_argument(
        "--max-model-calls",
        type=int,
        default=None,
        help="Override the per-request model call budget.",
    )
    parser.add_argument(
        "--verbose-progress",
        action="store_true",
        help="Print per-node progress logs during workflow execution.",
    )
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Print tool call records (status/summary/payload) returned by the workflow.",
    )
    return parser


def main() -> None:
    """CLI 主函数：解析参数并调用 PaperAssistant。"""
    parser = build_parser()
    args = parser.parse_args()
    preferences = json.loads(args.preferences)
    config = PaperAgentConfig.from_env()
    if args.max_model_calls is not None:
        config.max_model_calls = max(1, args.max_model_calls)
    if args.verbose_progress:
        config.verbose_progress = True

    assistant = PaperAssistant(config=config)
    # 当显式指定 all-papers 且未传入具体 paper-id 时，使用本地全部论文。
    paper_ids = assistant.available_papers() if args.all_papers and not args.paper_ids else args.paper_ids
    response = assistant.invoke(
        user_query=args.query,
        paper_ids=paper_ids,
        thread_id=args.thread_id,
        user_preferences=preferences,
    )
    print(response.final_answer)

    if args.show_tools:
        tool_results = {name: record.model_dump() for name, record in response.tool_results.items()}
        print("\n=== Tool Results ===")
        print(json.dumps(tool_results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
