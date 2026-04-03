"""
下载并解压工具使用示例
"""
from app.parser_pdf.downloader import download_and_extract, extract_file

# 示例 1: 下载并解压一个 ZIP 文件
def example1():
    """从 URL 下载并解压"""
    url = "https://cdn-mineru.openxlab.org.cn/pdf/2026-04-03/caf89a99-eccd-4042-8f87-e3912b1eb2a8.zip"
    
    try:
        # 基本用法：自动保存到 downloads 目录，自动解压到同名文件夹
        result_path = download_and_extract(url)
        print(f"下载并解压完成：{result_path}")
    except Exception as e:
        print(f"操作失败：{e}")


# 示例 2: 自定义保存和解压目录
def example2():
    """指定保存路径和解压路径"""
    url = "https://example.com/dataset.tar.gz"
    
    try:
        result_path = download_and_extract(
            url=url,
            save_dir="./my_downloads",      # 自定义保存目录
            extract_dir="./data/dataset",   # 自定义解压目录
            delete_after_extract=True       # 解压后删除压缩包
        )
        print(f"文件已解压到：{result_path}")
    except Exception as e:
        print(f"操作失败：{e}")


# 示例 3: 仅解压本地已有压缩文件
def example3():
    """解压本地文件"""
    compressed_file = "./downloads/file.zip"
    
    try:
        result_path = extract_file(
            file_path=compressed_file,
            extract_dir="./output/data",  # 可选，不指定则解压到同名文件夹
            delete_after=False            # 保留原压缩文件
        )
        print(f"解压完成：{result_path}")
    except Exception as e:
        print(f"解压失败：{e}")


# 示例 4: 处理论文数据集下载（实际场景）
def download_paper_dataset():
    """下载论文相关的数据集"""
    # 假设这是一个论文数据集的下载链接
    dataset_url = "https://github.com/example/paper-dataset/archive/main.zip"
    
    try:
        print("开始下载论文数据集...")
        dataset_path = download_and_extract(
            dataset_url,
            save_dir="./datasets",
            extract_dir="./datasets/paper_data",
            chunk_size=16384,  # 增大下载块大小提高速度
            delete_after_extract=True
        )
        print(f"数据集已准备就绪：{dataset_path}")
        
        # 接下来可以读取和处理数据
        # process_dataset(dataset_path)
        
    except Exception as e:
        print(f"数据集下载失败：{e}")


if __name__ == "__main__":
    # 选择一个示例运行
    print("=== 下载解压工具示例 ===\n")
    
    # 取消注释以下任一行来运行对应的示例
    
    # 示例 1: 基本下载解压
    example1()
    
    # 示例 2: 自定义路径
    # example2()
    
    # 示例 3: 解压本地文件
    # example3()
    
    # 示例 4: 论文数据集下载
    # download_paper_dataset()
    
    print("\n提示：修改代码中的 URL 为你的实际下载链接后运行")
    print("使用方法:")
    print("  python example_usage.py")
