import json
import re
import os
import traceback
from pydantic import BaseModel, Field
from langchain_text_splitters import MarkdownTextSplitter
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from dotenv import load_dotenv
load_dotenv(override=True)
class PaperSummary(BaseModel):
    title: str = Field(description="Title of the paper")
    authors: list[str] = Field(description="Authors of the paper, note that this is a list")
    one_sentence_summary: str = Field(description="One-sentence summary of the paper")
    core_problem: str = Field(description="The Core Problem: What is the paper trying to solve?")
    methodology: str = Field(description="Methodology/Approach: How did the authors solve it?")
    experiments: str = Field(description="Key Experiments & Results: What were the major findings?")
    conclusion: str = Field(description="Conclusion: What is the final takeaway?")

def parse_figure_mapping(json_path):
    """
    Parse the optimized JSON to map Figure references to their corresponding image paths.
    Maps multiple figures if present in a single caption.
    """
    figure_mapping = {}
    
    # Regex to capture Figure references, e.g., "Fig. 1", "Figure 2"
    fig_pattern = re.compile(r'(?:[Ff]ig\.|[Ff]igure)\s*(\d+)')
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for item in data:
        if item.get('type') == 'image' and 'img_path' in item:
            img_path = item['img_path']
            captions = item.get('image_caption', [])
            
            for caption in captions:
                matches = fig_pattern.findall(caption)
                for match in matches:
                    fig_key = f"Figure {match}"
                    figure_mapping[fig_key] = img_path
                    
    return figure_mapping

def chunk_markdown(md_path, chunk_size=4000, chunk_overlap=200):
    """
    Split the markdown file into manageable chunks.
    """
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
        
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap
    )
    
    chunks = splitter.split_text(md_content)
    return chunks


def extract_json_object(text: str) -> str:
    """
    Extract a JSON object from a model response that may contain extra text.
    """
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)

    raise ValueError("No valid JSON object found in model response.")



def build_agent_and_summarize(md_chunks,language="Chinese"):
    """
    Summarize paper chunks with structured output.
    Primary path uses LangChain create_agent + ProviderStrategy (v1.2-compatible).
    Fallback paths preserve compatibility across provider routing differences.
    """
    base_url = os.getenv("OPENAI_BASE_URL")
    extra_body = None
    if base_url and "openrouter.ai" in base_url:
        # Route only to providers that support all request params (e.g., json schema).
        # Helps avoid provider mismatch issues in OpenRouter routing.
        extra_body = {"provider": {"require_parameters": True}}

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4-0613"),
        temperature=0.2,
        base_url=base_url,
        api_key=os.getenv("OPENAI_API_KEY"), # type: ignore
        extra_body=extra_body,
    )

    system_prompt = """You are an expert academic paper reading assistant.
Your task is to systematically summarize the content of the paper provided to you in chunks.
Please identify the main contributions, methodology, experiments, and conclusions.
Return your summary strictly conforming to the requested format."""
    
    combined_content = "\\n\\n--- NEXT CHUNK ---\\n\\n".join(md_chunks)
    human_prompt = f"Here is the content of the paper split into chunks:\\n\\n{combined_content}\\n\\nPlease read through all parts and provide a systematic summary as instructed.Please use {language} to answer the question. But sure to return the answer in the structured format as requested, without any additional commentary or text. The Author And Title Fields Must Be Retained As The Content In The Original Document And Do Not Need To Be Translated However Use {language} To Answer The Core Questions Methodology Experiment And Conclusion Fields"
    
    print("Agent is reading and summarizing the paper with structured output...")

    # Primary path: LangChain create_agent + explicit ProviderStrategy (v1.2+)
    # This avoids automatic fallback to ToolStrategy (which can trigger tool_choice).
    try:
        agent = create_agent(
            model=llm,
            tools=[],
            system_prompt=system_prompt,
            response_format=ProviderStrategy(PaperSummary, strict=True),
        )
        result = agent.invoke({"messages": [{"role": "user", "content": human_prompt}]})
        structured = result.get("structured_response") if isinstance(result, dict) else None
        if isinstance(structured, PaperSummary):
            return structured
        if isinstance(structured, dict):
            return PaperSummary(**structured)
    except Exception as agent_error:
        print(f"create_agent path failed, trying model structured output: {agent_error}")
        print(traceback.format_exc())


if __name__ == "__main__":
    # Example usage for the specific paper mentioned in Phase 1
    base_dir = "../../docs/docs_parser/4ffc67ef-8d72-40f9-ba82-23d39052c3db"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paper_dir = os.path.normpath(os.path.join(script_dir, base_dir))
    
    json_file_path = os.path.join(paper_dir, "cc90a819-7d1b-4438-a96f-a20017bb84e8_content_list_optimized.json")
    md_file_path = os.path.join(paper_dir, "full_optimized.md")
    
    if os.path.exists(json_file_path) and os.path.exists(md_file_path):
        fig_map = parse_figure_mapping(json_file_path)
        print("Figure Mappings Found:", len(fig_map))
        
        chunks = chunk_markdown(md_file_path)
        print(f"Markdown split into {len(chunks)} chunks.")
        
        try:
            summary = build_agent_and_summarize(chunks)
            print("\\n=== Structured Paper Summary ===\\n")
            if summary:
                print(f"Title: {summary.title}\\n")
                print(f"Authors: {', '.join(summary.authors)}\\n")
                print(f"One-Sentence Summary: {summary.one_sentence_summary}\\n")
                print(f"Core Problem: {summary.core_problem}\\n")
                print(f"Methodology: {summary.methodology}\\n")
                print(f"Experiments: {summary.experiments}\\n")
                print(f"Conclusion: {summary.conclusion}\\n")
            else:
                print("No structured summary returned.")
        except Exception as e:
            print(f"Error executing agent: {e}")
    else:
        print(f"File not found. Please ensure the paths exist:\\nJSON: {json_file_path}\\nMD: {md_file_path}")
