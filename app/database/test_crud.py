"""
数据库 CRUD 操作测试
"""
import os
import sys
from dotenv import load_dotenv

# 在导入任何其他模块之前，先加载 .env 文件
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=env_path, override=True)

# 验证 DATABASE_URL 是否正确加载
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

print(f"✓ Using database: {DATABASE_URL}")

# 现在可以安全地导入其他模块
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
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

# 创建测试引擎（使用从 .env 加载的 DATABASE_URL）
engine = create_engine(DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话"""
    # 创建会话
    db = TestingSessionLocal()
    try:
        # 清理测试数据（删除所有测试相关的记录）
        db.execute(text("DELETE FROM img_path WHERE paper_id LIKE 'test_%'"))
        db.execute(text("DELETE FROM paper WHERE id LIKE 'test_%'"))
        db.commit()
        
        yield db
    finally:
        # 清理测试数据
        db.execute(text("DELETE FROM img_path WHERE paper_id LIKE 'test_%'"))
        db.execute(text("DELETE FROM paper WHERE id LIKE 'test_%'"))
        db.commit()
        db.close()


class TestPaperCRUD:
    """测试 Paper 的 CRUD 操作"""

    def test_create_paper(self, db_session):
        """测试创建论文"""
        paper_data = PaperCreate(
            id="test_001",
            path="/path/to/paper.pdf",
            title="Test Paper Title",
            authors="Author A, Author B",
            one_sentence="This is a test paper.",
            core_problem="What is the problem?",
            methodology="How to solve it?",
            experiments="Experimental results.",
            conclusion="Final conclusion.",
        )
        
        created_paper = create_paper(db_session, paper_data)
        
        assert created_paper.id == "test_001"
        assert created_paper.path == "/path/to/paper.pdf"
        assert created_paper.title == "Test Paper Title"
        assert created_paper.authors == "Author A, Author B"
        assert created_paper.one_sentence == "This is a test paper."
        assert created_paper.core_problem == "What is the problem?"
        assert created_paper.methodology == "How to solve it?"
        assert created_paper.experiments == "Experimental results."
        assert created_paper.conclusion == "Final conclusion."

    def test_get_paper(self, db_session):
        """测试获取单个论文"""
        # 先创建一篇论文
        paper_data = PaperCreate(
            id="test_002",
            path="/path/to/paper2.pdf",
            title="Another Test Paper",
        )
        create_paper(db_session, paper_data)
        
        # 获取论文
        retrieved_paper = get_paper(db_session, "test_002")
        
        assert retrieved_paper is not None
        assert retrieved_paper.id == "test_002"
        assert retrieved_paper.title == "Another Test Paper"

    def test_get_paper_not_found(self, db_session):
        """测试获取不存在的论文"""
        retrieved_paper = get_paper(db_session, "nonexistent_id")
        assert retrieved_paper is None

    def test_get_papers(self, db_session):
        """测试获取论文列表"""
        # 创建多篇论文
        for i in range(5):
            paper_data = PaperCreate(
                id=f"test_{i:03d}",
                path=f"/path/to/paper{i}.pdf",
                title=f"Paper {i}",
            )
            create_paper(db_session, paper_data)
        
        # 获取所有论文
        papers = get_papers(db_session, skip=0, limit=10)
        assert len(papers) == 5
        
        # 测试分页
        papers_page1 = get_papers(db_session, skip=0, limit=2)
        assert len(papers_page1) == 2
        
        papers_page2 = get_papers(db_session, skip=2, limit=2)
        assert len(papers_page2) == 2

    def test_update_paper(self, db_session):
        """测试更新论文"""
        # 先创建一篇论文
        paper_data = PaperCreate(
            id="test_003",
            path="/path/to/original.pdf",
            title="Original Title",
            authors="Original Author",
        )
        create_paper(db_session, paper_data)
        
        # 更新论文
        update_data = PaperUpdate(
            title="Updated Title",
            authors="Updated Author",
        )
        updated_paper = update_paper(db_session, "test_003", update_data)
        
        assert updated_paper is not None
        assert updated_paper.title == "Updated Title"
        assert updated_paper.authors == "Updated Author"
        assert updated_paper.path == "/path/to/original.pdf"  # 未更新的字段保持不变

    def test_update_paper_partial(self, db_session):
        """测试部分更新论文"""
        # 先创建一篇论文
        paper_data = PaperCreate(
            id="test_004",
            path="/path/to/paper4.pdf",
            title="Test Title",
            one_sentence="Original sentence.",
        )
        create_paper(db_session, paper_data)
        
        # 只更新一个字段
        update_data = PaperUpdate(conclusion="New conclusion.")
        updated_paper = update_paper(db_session, "test_004", update_data)
        
        assert updated_paper is not None
        assert updated_paper.conclusion == "New conclusion."
        assert updated_paper.title == "Test Title"  # 未更新的字段保持不变
        assert updated_paper.one_sentence == "Original sentence."

    def test_update_paper_not_found(self, db_session):
        """测试更新不存在的论文"""
        update_data = PaperUpdate(title="New Title")
        updated_paper = update_paper(db_session, "nonexistent_id", update_data)
        assert updated_paper is None

    def test_delete_paper(self, db_session):
        """测试删除论文"""
        # 先创建一篇论文
        paper_data = PaperCreate(
            id="test_005",
            path="/path/to/paper5.pdf",
            title="To Be Deleted",
        )
        create_paper(db_session, paper_data)
        
        # 验证论文存在
        paper = get_paper(db_session, "test_005")
        assert paper is not None
        
        # 删除论文
        deleted_paper = delete_paper(db_session, "test_005")
        assert deleted_paper is not None
        assert deleted_paper.id == "test_005"
        
        # 验证论文已被删除
        paper_after_delete = get_paper(db_session, "test_005")
        assert paper_after_delete is None

    def test_delete_paper_not_found(self, db_session):
        """测试删除不存在的论文"""
        deleted_paper = delete_paper(db_session, "nonexistent_id")
        assert deleted_paper is None

    def test_create_paper_with_optional_fields_none(self, db_session):
        """测试创建论文时可选字段为 None"""
        paper_data = PaperCreate(
            id="test_006",
            path="/path/to/minimal.pdf",
        )
        
        created_paper = create_paper(db_session, paper_data)
        
        assert created_paper.id == "test_006"
        assert created_paper.path == "/path/to/minimal.pdf"
        assert created_paper.title is None
        assert created_paper.authors is None


class TestImageCRUD:
    """测试 Image 的 CRUD 操作"""

    def test_create_image_for_paper(self, db_session):
        """测试为论文创建图片"""
        # 先创建一篇论文
        paper_data = PaperCreate(
            id="test_img_001",
            path="/path/to/paper_with_images.pdf",
            title="Paper with Images",
        )
        create_paper(db_session, paper_data)
        
        # 创建图片
        image_data = ImgPathCreate(
            img_id=1,
            img_path="/images/fig1.png",
        )
        created_image = create_image_for_paper(db_session, "test_img_001", image_data)
        
        assert created_image.paper_id == "test_img_001"
        assert created_image.img_id == 1
        assert created_image.img_path == "/images/fig1.png"

    def test_create_multiple_images_for_paper(self, db_session):
        """测试为同一篇论文创建多个图片"""
        # 先创建一篇论文
        paper_data = PaperCreate(
            id="test_img_002",
            path="/path/to/multi_image_paper.pdf",
            title="Multi-Image Paper",
        )
        create_paper(db_session, paper_data)
        
        # 创建多个图片
        for i in range(3):
            image_data = ImgPathCreate(
                img_id=i + 1,
                img_path=f"/images/fig{i+1}.png",
            )
            create_image_for_paper(db_session, "test_img_002", image_data)
        
        # 获取所有图片
        images = get_images_by_paper_id(db_session, "test_img_002")
        assert len(images) == 3
        
        # 验证图片顺序
        for idx, img in enumerate(images):
            assert img.img_id == idx + 1
            assert img.img_path == f"/images/fig{idx+1}.png"

    def test_get_images_by_paper_id(self, db_session):
        """测试根据论文 ID 获取图片列表"""
        # 先创建一篇论文和图片
        paper_data = PaperCreate(
            id="test_img_003",
            path="/path/to/paper3.pdf",
            title="Paper 3",
        )
        create_paper(db_session, paper_data)
        
        image_data = ImgPathCreate(img_id=1, img_path="/images/test.png")
        create_image_for_paper(db_session, "test_img_003", image_data)
        
        # 获取图片
        images = get_images_by_paper_id(db_session, "test_img_003")
        assert len(images) == 1
        assert images[0].img_path == "/images/test.png"

    def test_get_images_empty_result(self, db_session):
        """测试获取不存在论文的图片列表"""
        images = get_images_by_paper_id(db_session, "nonexistent_id")
        assert len(images) == 0

    def test_create_image_for_nonexistent_paper(self, db_session):
        """测试为不存在的论文创建图片"""
        # 注意：SQLite 默认不强制外键约束，所以这个操作可能不会失败
        # 在实际生产环境中（如 PostgreSQL/MySQL），这会抛出 IntegrityError
        image_data = ImgPathCreate(img_id=1, img_path="/images/orphan.png")
        
        # 在 SQLite 中，这个操作可能会成功，但 paper_id 会指向不存在的记录
        # 我们只验证它能被创建，实际的外键约束需要在生产数据库中测试
        try:
            created_image = create_image_for_paper(db_session, "nonexistent_paper", image_data)
            # 如果成功创建，验证数据
            assert created_image.paper_id == "nonexistent_paper"
            assert created_image.img_id == 1
        except Exception as e:
            # 如果数据库配置了外键约束，应该会抛出异常
            assert "FOREIGN KEY" in str(e) or "IntegrityError" in str(type(e).__name__)


class TestPaperWithImagesIntegration:
    """测试论文和图片的关联操作"""

    def test_cascade_delete(self, db_session):
        """测试级联删除：删除论文时自动删除相关图片"""
        # 创建论文和图片
        paper_data = PaperCreate(
            id="test_cascade_001",
            path="/path/to/cascade_test.pdf",
            title="Cascade Test",
        )
        create_paper(db_session, paper_data)
        
        for i in range(3):
            image_data = ImgPathCreate(
                img_id=i + 1,
                img_path=f"/images/cascade_fig{i+1}.png",
            )
            create_image_for_paper(db_session, "test_cascade_001", image_data)
        
        # 验证图片已创建
        images_before = get_images_by_paper_id(db_session, "test_cascade_001")
        assert len(images_before) == 3
        
        # 删除论文
        delete_paper(db_session, "test_cascade_001")
        
        # 验证图片也被删除（级联删除）
        images_after = get_images_by_paper_id(db_session, "test_cascade_001")
        assert len(images_after) == 0

    def test_paper_with_multiple_images_workflow(self, db_session):
        """测试完整的论文和多图片工作流"""
        # 1. 创建论文
        paper_data = PaperCreate(
            id="test_workflow_001",
            path="/path/to/workflow.pdf",
            title="Workflow Test Paper",
            authors="Test Author",
            one_sentence="A complete workflow test.",
        )
        created_paper = create_paper(db_session, paper_data)
        assert created_paper.id == "test_workflow_001"
        
        # 2. 添加多张图片
        for i in range(5):
            image_data = ImgPathCreate(
                img_id=i + 1,
                img_path=f"/images/workflow_fig{i+1}.png",
            )
            create_image_for_paper(db_session, "test_workflow_001", image_data)
        
        # 3. 验证图片数量
        images = get_images_by_paper_id(db_session, "test_workflow_001")
        assert len(images) == 5
        
        # 4. 更新论文信息
        update_data = PaperUpdate(
            conclusion="Workflow test completed successfully."
        )
        updated_paper = update_paper(db_session, "test_workflow_001", update_data)
        assert updated_paper.conclusion == "Workflow test completed successfully."
        
        # 5. 再次验证图片仍然存在
        images_after_update = get_images_by_paper_id(db_session, "test_workflow_001")
        assert len(images_after_update) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
