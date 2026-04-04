import os
import traceback
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy

load_dotenv(override=True)


class S(BaseModel):
    a: str


base_url = os.getenv("OPENAI_BASE_URL")
extra_body = None
if base_url and "openrouter.ai" in base_url:
    extra_body = {"provider": {"require_parameters": True}}

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    temperature=0,
    base_url=base_url,
    api_key=os.getenv("OPENAI_API_KEY"),
    extra_body=extra_body,
)

print("base_url:", base_url)
print("model:", os.getenv("OPENAI_MODEL"))
print("extra_body:", extra_body)

try:
    agent = create_agent(
        model=llm,
        tools=[],
        response_format=ProviderStrategy(S, strict=True),
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "return a=test"}]})
    print("RESULT:", result)
except Exception as e:
    print("ERROR:", e)
    print(traceback.format_exc())
