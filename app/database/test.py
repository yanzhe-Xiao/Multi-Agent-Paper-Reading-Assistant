import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openrouter import ChatOpenRouter

load_dotenv(override=True)

model = ChatOpenRouter(
    model=os.getenv("OPENAI_MODEL"),
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

agent = create_agent(
    model=model,
    system_prompt="你是一个论文阅读助手，帮助用户理解论文内容并回答相关问题。",
)

for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "请简要介绍一下Transformer模型的核心思想。"}]},
    stream_mode="messages",
    version="v2",   # 关键
):
    if chunk["type"] != "messages":
        continue

    token, metadata = chunk["data"]

    # 这里一般是 "model"，不是 "agent"
    if metadata.get("langgraph_node") != "model":
        continue

    # 优先从标准 content_blocks 里取文本
    if hasattr(token, "content_blocks") and token.content_blocks:
        for block in token.content_blocks:
            if block.get("type") == "text":
                print(block.get("text", ""), end="", flush=True)

    # 兜底：有些模型/版本可能直接放在 content
    elif hasattr(token, "content") and token.content:
        if isinstance(token.content, str):
            print(token.content, end="", flush=True)