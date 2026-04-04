from typing import Any

import yaml

import mineru_api,downloader,figure_reconstruction,full_markdown_figure_rewriter
from dotenv import load_dotenv
import os
from pathlib import Path


load_dotenv(override=True)
config_yaml = os.getenv("YAML_PATH")
# 解析参数
def load_config(config_path: str = "default.yaml") -> dict:
    """
    读取 YAML 配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config
config = load_config(config_path=config_yaml or "default.yaml")
docs_path = config.get("docs_path")
docs_parser_path = config.get("docs_parser_path")
os.makedirs(docs_path,exist_ok=True) # type: ignore
os.makedirs(docs_parser_path,exist_ok=True) # type: ignore
print("解析文档路径:",docs_path)
model_version=config.get("MODEL_VERSION")

import re
def match(target_filename,text):
    pattern = rf'(\S*{re.escape(target_filename)})'   # \S+ 匹配一个或多个非空白字符（路径通常不含空格）

    match = re.search(pattern, text)
    if match:
        file_path = match.group(1)
        return file_path
    else:
        return None

def find_target_file(partial_file:str,filepath:str):
    path = Path(filepath)
    all_files = [f.name for f in path.iterdir() if f.is_file()]
    files_only = None
    for file in all_files:
        files_only = match(partial_file,file)
        if files_only:
            break
    if files_only:
        return path / files_only
    return
def reconstruct_figures(
    content_list_path: str | Path,
    dpi: int = 200,
    render_mode: str = "auto"
) -> dict[str, Any]:
    """
    重建碎片化的图表
    
    Args:
        content_list_path: content_list.json 文件路径
        output_dir: 输出目录
        dpi: 渲染 DPI
        render_mode: 渲染模式 (auto/pdf/composite)
    
    Returns:
        重建结果字典
    """
    
    result = figure_reconstruction.reconstruct_content_list(
        content_list_path=content_list_path,
        dpi=dpi,
        render_mode=render_mode,
    )
    
    print(f"✅ 图表重建完成：{result['reconstructed_count']} 个图表")
    return result

def parser(pdf_name: str, **kwargs):
    """解析指定路径下的 PDF 文件，并将结果保存到同一目录下的 markdown 文件中。

    Args:
        pdf_name (str): PDF 的名称。
        **kwargs: 可选的解析参数，包括：
            - model_version (str): 模型版本，默认为 config 中的 MODEL_VERSION
            - language (str): 语言设置，默认为 config 中的 LANGUAGE
            - enable_table (bool): 是否启用表格，默认为 config 中的 ENABLE_TABLE
            - enable_formula (bool): 是否启用公式，默认为 config 中的 ENABLE_FORMULA
            - is_ocr (bool): 是否开启 OCR，默认为 config 中的 IS_OCR
    
    Examples:
        # 使用默认配置
        parser("paper.pdf")
        
        # 自定义部分参数
        parser("paper.pdf", model_version="vlm", enable_table=False)
        
        # 自定义所有参数
        parser("paper.pdf", model_version="pipeline", language="zh", 
               enable_table=True, enable_formula=False, is_ocr=True)
    """
    # 从 config 中获取默认值
    default_params = {
        'model_version': config.get('MODEL_VERSION'),
        'language': config.get('LANGUAGE'),
        'enable_table': config.get('ENABLE_TABLE'),
        'enable_formula': config.get('ENABLE_FORMULA'),
        'is_ocr': config.get('IS_OCR')
    }
    
    # 更新为用户提供的参数
    default_params.update(kwargs)
    
    # 解包参数
    model_version = default_params['model_version']
    language = default_params['language']
    enable_table = default_params['enable_table']
    enable_formula = default_params['enable_formula']
    is_ocr = default_params['is_ocr']
    
    print(f"解析参数：model_version={model_version}, language={language}, "
          f"enable_table={enable_table}, enable_formula={enable_formula}, is_ocr={is_ocr}")
    
    path = Path(docs_path) / pdf_name  # type: ignore
    if not path.is_file():
        print(f"文件 {path} 不存在，请检查路径是否正确。")
        return

    # 1. 获取 PDF 文件的下载链接
    try:
        file_url = mineru_api.get(str(path),model_version,language,enable_table,enable_formula,is_ocr) # type: ignore
        print(f"获取文件 URL 成功：{file_url}")
    except Exception as e:
        print(f"获取文件 URL 失败：{e}")
        return

    # # 2. 下载并解压 PDF 文件（如果是压缩包）
    try:
        extracted_path = downloader.download_and_extract(file_url, save_dir=docs_parser_path) # type: ignore
        print(f"下载并解压完成：{extracted_path}")
    except Exception as e:
        print(f"下载或解压失败：{e}")
        return

    # 3. 进行图像重建
    
    try:
        # extracted_path = "docs\docs_parser\d0b15a92-53f3-452f-a942-49102389c4fa"
        content_list_file = find_target_file("_content_list.json",extracted_path)
        if not content_list_file:
            print("解压失败，找不到指定文件")
            return
        reconstruct_figures(content_list_file)
        print("图像重建完成")
    except Exception as e:
        print(f"图像重建失败：{e}")
        return

    # 4. 重写 Markdown 文件中的图像链接
    try:
        full_md = find_target_file("full.md",extracted_path)
        if not full_md:
            print("解压失败，找不到指定文件")
            return
        full_markdown_figure_rewriter.replace_fragmented_figures_in_markdown(full_md,content_list_file)
        print("Markdown 图像链接重写完成")
    except Exception as e:
        print(f"Markdown 图像链接重写失败：{e}")
        return

if __name__ == "__main__":
    parser("Dual.pdf")