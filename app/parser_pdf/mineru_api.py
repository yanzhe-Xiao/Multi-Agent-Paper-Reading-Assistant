import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)
TOKEN = os.getenv("MINERU_API_TOKEN")
URL=os.getenv("MINERU_URL", "https://mineru.net/api/v4/file-urls/batch")
doc_path = Path(__file__).parent.parent.parent / "docs"
print("当前文档目录:", doc_path.resolve())
# 本地待上传文件

# 解析参数
MODEL_VERSION = "vlm"   # 非 HTML 文件可用 pipeline 或 vlm
LANGUAGE = "en"
ENABLE_TABLE = True
ENABLE_FORMULA = True
IS_OCR = True  # 是否开启 OCR，开启后可解析图片中的文本（如表格、公式等），但会增加解析时间

def apply_upload_urls(token: str, file_paths: list[str], model_version: str=MODEL_VERSION, language: str=LANGUAGE, enable_table: bool=ENABLE_TABLE, enable_formula: bool=ENABLE_FORMULA) -> tuple[str, list[str]]:
    """
    申请批量上传链接
    返回: (batch_id, file_urls)
    """
    url = URL
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    files_payload = []
    for fp in file_paths:
        p = Path(fp)
        files_payload.append({
            "name": p.name,
            "data_id": p.stem,     # 可选，你也可以换成业务 ID
            "is_ocr": IS_OCR,      # 也可按文件单独设置
        })

    payload = {
        "files": files_payload,
        "model_version": model_version,
        "language": language,
        "enable_table": enable_table,
        "enable_formula": enable_formula,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("code") != 0:
        raise RuntimeError(f"申请上传链接失败: {result}")

    batch_id = result["data"]["batch_id"]
    file_urls = result["data"]["file_urls"]

    if len(file_urls) != len(file_paths):
        raise RuntimeError(
            f"返回上传链接数量不匹配: files={len(file_paths)}, urls={len(file_urls)}"
        )

    return batch_id, file_urls


def upload_files(file_paths: list[str], file_urls: list[str]) -> None:
    """
    PUT 上传文件到签名 URL
    注意：不要手动设置 Content-Type
    """
    for fp, upload_url in zip(file_paths, file_urls):
        with open(fp, "rb") as f:
            resp = requests.put(upload_url, data=f, timeout=300)
            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"上传失败: file={fp}, status={resp.status_code}, body={resp.text[:500]}"
                )
        print(f"上传成功: {fp}")


def query_batch_result(token: str, batch_id: str) -> dict:
    """
    查询批量解析结果
    """
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("code") != 0:
        raise RuntimeError(f"查询批量结果失败: {result}")

    return result["data"]


def all_finished(extract_result: list[dict]) -> bool:
    unfinished = {"waiting-file", "pending", "running", "converting"}
    return all(item.get("state") not in unfinished for item in extract_result)


def main():
    LOCAL_FILES = [
    str(doc_path / "VLN-PETL.pdf"),
    ]
    # 校验本地文件
    for fp in LOCAL_FILES:
        if not os.path.exists(fp):
            raise FileNotFoundError(fp)

    # 1) 申请上传链接
    batch_id, file_urls = apply_upload_urls(TOKEN, LOCAL_FILES)
    print("batch_id =", batch_id)
    print("拿到上传链接数量 =", len(file_urls))

    # 2) 上传本地文件
    upload_files(LOCAL_FILES, file_urls)

    # 3) 轮询批量解析结果
    while True:
        data = query_batch_result(TOKEN, batch_id)
        results = data.get("extract_result", [])

        print("\n当前状态：")
        for item in results:
            file_name = item.get("file_name")
            state = item.get("state")
            err_msg = item.get("err_msg", "")
            print(f"- {file_name}: {state} {err_msg}")

        if results and all_finished(results):
            print("\n全部任务结束：")
            for item in results:
                file_name = item.get("file_name")
                state = item.get("state")
                zip_url = item.get("full_zip_url", "")
                err_msg = item.get("err_msg", "")
                print(f"\n文件: {file_name}")
                print(f"状态: {state}")
                if state == "done":
                    print(f"结果包: {zip_url}")
                else:
                    print(f"失败原因: {err_msg}")
            break

        time.sleep(5)


if __name__ == "__main__":
    main()