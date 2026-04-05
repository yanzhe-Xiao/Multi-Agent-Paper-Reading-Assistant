from __future__ import annotations

"""统一的流式输出工具。

目标：让项目中的标准输出尽可能按“流式”方式刷出，而不是一次性缓冲后再显示。
默认会把 `print(...)` 替换为流式版本；可通过环境变量关闭。
"""

import builtins
import os
import sys
import threading
import time
from typing import Any, TextIO

_ORIGINAL_PRINT = builtins.print
_PATCHED = False
_LOCK = threading.Lock()


def _as_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _as_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _as_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


# 全局开关与行为参数（可在 .env 或系统环境中配置）
STREAM_OUTPUT_ENABLED = _as_bool("APP_STREAM_OUTPUT", True)
STREAM_OUTPUT_CHUNK_SIZE = max(1, _as_int("APP_STREAM_CHUNK_SIZE", 48))
STREAM_OUTPUT_DELAY_SECONDS = max(0.0, _as_float("APP_STREAM_DELAY_SECONDS", 0.0))
STREAM_STDOUT_ONLY = _as_bool("APP_STREAM_STDOUT_ONLY", False)


def stream_write(
    text: str,
    *,
    file: TextIO | None = None,
    chunk_size: int | None = None,
    delay_seconds: float | None = None,
    flush: bool = True,
) -> None:
    """将文本按分块方式写入输出流。"""
    output = file or sys.stdout
    size = max(1, int(chunk_size or STREAM_OUTPUT_CHUNK_SIZE))
    delay = max(0.0, float(STREAM_OUTPUT_DELAY_SECONDS if delay_seconds is None else delay_seconds))

    if not text:
        if flush:
            output.flush()
        return

    with _LOCK:
        for index in range(0, len(text), size):
            output.write(text[index : index + size])
            if flush:
                output.flush()
            if delay > 0.0:
                time.sleep(delay)


def stream_print(
    *values: Any,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = True,
    chunk_size: int | None = None,
    delay_seconds: float | None = None,
) -> None:
    """流式 print：兼容原生 print 参数，并逐块刷新输出。"""
    output = file or sys.stdout

    # 对齐内建 print 的参数语义：sep/end 允许为 None（表示使用默认值）。
    if sep is None:
        sep = " "
    if end is None:
        end = "\n"
    if not isinstance(sep, str):
        raise TypeError(f"sep must be None or a string, not {type(sep).__name__}")
    if not isinstance(end, str):
        raise TypeError(f"end must be None or a string, not {type(end).__name__}")

    if (not STREAM_OUTPUT_ENABLED) or (STREAM_STDOUT_ONLY and output not in {sys.stdout, sys.__stdout__}):
        _ORIGINAL_PRINT(*values, sep=sep, end=end, file=output, flush=flush)
        return

    rendered = sep.join(str(item) for item in values) + end
    stream_write(
        rendered,
        file=output,
        chunk_size=chunk_size,
        delay_seconds=delay_seconds,
        flush=flush,
    )


def enable_stream_output(force: bool = False) -> bool:
    """启用全局流式 print（替换 builtins.print）。"""
    global _PATCHED

    if _PATCHED:
        return True

    if not (force or STREAM_OUTPUT_ENABLED):
        return False

    builtins.print = stream_print
    _PATCHED = True
    return True


def disable_stream_output() -> None:
    """恢复原始 print。"""
    global _PATCHED
    if not _PATCHED:
        return
    builtins.print = _ORIGINAL_PRINT
    _PATCHED = False
