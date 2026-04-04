"""
数据库 CRUD 操作测试
"""
import os
import sys
from dotenv import load_dotenv

# 将项目根目录添加到 Python 路径
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# 在导入任何其他模块之前，先加载 .env 文件
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path, override=True)

# 验证 DATABASE_URL 是否正确加载
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

# print(f"✓ Using database: {DATABASE_URL}")

# 现在可以安全地导入其他模块
from app.database.crud import (
    create_paper,
    get_paper,
    get_papers,
    update_paper,
    delete_paper,
    create_image_for_paper,
    get_images_by_paper_id,
)
from app.database.schemas import PaperCreate, PaperUpdate, ImgPathCreate

from app.database.database import get_db_session


# 使用上下文管理器
# with get_db_session() as db:
#     paper_data = PaperCreate(
#                 id="test_003",
#                 path="/path/to/paper2.pdf",
#                 title="Another Test Paper",
#             )
#     create_paper(db, paper_data)

# with get_db_session() as db:
#     paper = get_paper(db, "test_003")
#     if paper:
#         print("Retrieved Paper:")
#         print(f"  ID: {paper.id}")
#         print(f"  Path: {paper.path}")
#         print(f"  Title: {paper.title}")
#         print(f"  Authors: {paper.authors}")
#         print(f"  One Sentence Summary: {paper.one_sentence}")
#         print(f"  Core Problem: {paper.core_problem}")
#         print(f"  Methodology: {paper.methodology}")
#         print(f"  Experiments: {paper.experiments}")
#         print(f"  Conclusion: {paper.conclusion}")
#     else:
#         print("Paper not found")


# with get_db_session() as db:
#     a = update_paper(db,"test_003", PaperUpdate(
#         one_sentence="This is an updated one-sentence summary."))
#     print("Updated Paper:", a.one_sentence)

with get_db_session() as db:
    delete_paper(db, "test_003")
    print("Paper deleted successfully")