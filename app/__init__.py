"""应用包初始化。"""

from .stream_output import enable_stream_output

# 包加载时默认启用全局流式输出（可通过 APP_STREAM_OUTPUT=false 关闭）。
enable_stream_output()
