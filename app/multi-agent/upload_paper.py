import json
import re
import os
import traceback
from sqlalchemy.orm import Session
from langchain_text_splitters import MarkdownTextSplitter
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from dotenv import load_dotenv
load_dotenv(override=True)
from app.database.database import get_db_session
from app.database.schemas import PaperSummary, PaperBase, convert_paper_summary_to_base, ImgPathCreate
from app.database.crud import create_image_for_paper
from app.database.crud import create_paper


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


def summarize_paper_to_base(paper_id: str, db: Session, language: str = "Chinese") -> PaperBase:
    """
    调用 build_agent_and_summarize 获取论文摘要，转换为 PaperBase 格式，并保存图片信息到数据库
    
    Args:
        paper_id: 论文ID，用于构建路径和作为返回对象的id字段
        db: 数据库会话对象
        language: 回答语言，默认为中文
    
    Returns:
        PaperBase 对象
    """
    # 构建论文目录路径
    base_dir = f"../../docs/docs_parser/{paper_id}"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paper_dir = os.path.normpath(os.path.join(script_dir, base_dir))
    
    # 构建文件路径
    md_file_path = os.path.join(paper_dir, "full_optimized.md")
    
    if not os.path.exists(md_file_path):
        raise FileNotFoundError(f"Markdown file not found: {md_file_path}")
    
    # 分割 Markdown 文件为 chunks
    print(f"Reading and chunking markdown file: {md_file_path}")
    chunks = chunk_markdown(md_file_path)
    print(f"Markdown split into {len(chunks)} chunks.")
    
    # 调用 Agent 进行总结
    print("Starting agent summarization...")
    paper_summary = build_agent_and_summarize(chunks, language=language)
    
    if paper_summary is None:
        raise ValueError("Agent failed to generate summary")
    
    print(f"Successfully generated summary for paper: {paper_summary.title}")
    
    # 构建完整路径（相对路径）
    relative_path = f"/docs/docs_parser/{paper_id}"
    
    # 转换为 PaperBase 格式
    paper_base = convert_paper_summary_to_base(
        paper_summary=paper_summary,
        paper_id=paper_id,
        paper_path=relative_path
    )
    with get_db_session() as db:
        # 保存 PaperBase 信息到数据库
        create_paper(db, paper_base) # type: ignore


    # 解析图片映射并保存到数据库
    try:
        # 查找 JSON 文件（content_list_optimized.json）
        json_files = [f for f in os.listdir(paper_dir) if f.endswith('_content_list_optimized.json')]
        
        if json_files:
            json_file_path = os.path.join(paper_dir, json_files[0])
            print(f"Parsing figure mapping from: {json_file_path}")
            
            # 解析图片映射
            figure_mapping = parse_figure_mapping(json_file_path)
            print(f"Found {len(figure_mapping)} figure mappings")
            

            
            img_id_counter = 1
            for _, img_path in figure_mapping.items():
                img_create = ImgPathCreate(
                    img_id=img_id_counter,
                    img_path=img_path,
                    is_check=False
                )
                create_image_for_paper(db, paper_id, img_create)
                print(f"Saved image {img_id_counter}: {img_path}")
                img_id_counter += 1
            
            print(f"Successfully saved {img_id_counter - 1} images to database")
        else:
            print(f"No content_list_optimized.json found in {paper_dir}")
            
    except Exception as e:
        print(f"Warning: Failed to save images to database: {e}")
        import traceback
        traceback.print_exc()
    
    return paper_base


def main():
    # 处理 docs/docs_parser 文件夹内的所有论文
    script_dir = os.path.dirname(os.path.abspath(__file__))
    docs_parser_dir = os.path.normpath(os.path.join(script_dir, "../../docs/docs_parser"))
    
    if not os.path.exists(docs_parser_dir):
        print(f"Directory not found: {docs_parser_dir}")
        exit(1)
    
    print(f"Processing papers in: {docs_parser_dir}\n")
    
    # 获取所有子目录（每个子目录代表一篇论文）
    paper_dirs = [d for d in os.listdir(docs_parser_dir) 
                  if os.path.isdir(os.path.join(docs_parser_dir, d))]
    
    print(f"Found {len(paper_dirs)} paper directories\n")
    
    # 创建数据库会话
    from app.database.database import SessionLocal
    db = SessionLocal()
    
    try:
        for paper_id in paper_dirs:
            print("=" * 80)
            print(f"Processing paper: {paper_id}")
            print("=" * 80)
            
            try:
                # 调用函数处理论文
                paper_base = summarize_paper_to_base(
                    paper_id=paper_id,
                    db=db,
                    language="Chinese"
                )
                
                print(f"\n✓ Successfully processed: {paper_base.title}")
                print(f"  - ID: {paper_base.id}")
                print(f"  - Authors: {paper_base.authors}")
                print(f"  - One Sentence: {paper_base.one_sentence}\n")
                
            except Exception as e:
                print(f"\n✗ Failed to process paper {paper_id}: {e}")
                traceback.print_exc()
                print()
        
        print("\n" + "=" * 80)
        print("All papers processed!")
        print("=" * 80)
        
    finally:
        db.close()
        print("\nDatabase session closed.")

