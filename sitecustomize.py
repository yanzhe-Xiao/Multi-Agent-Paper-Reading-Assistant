"""项目级 Python 启动钩子。

Python 启动时若能找到本文件，会自动导入它。
这里统一启用流式输出，覆盖直接运行脚本等场景。
"""

from app.stream_output import enable_stream_output

enable_stream_output()
