import os
import requests
import zipfile
import tarfile
import shutil
from pathlib import Path
from typing import Optional


def download_and_extract(
    url: str,
    save_dir: Optional[str] = None,
    extract_dir: Optional[str] = None,
    chunk_size: int = 8192,
    delete_after_extract: bool = False
) -> str:
    """
    下载文件并解压
    
    Args:
        url: 下载链接
        save_dir: 文件保存目录，默认为当前脚本所在目录的 downloads 文件夹
        extract_dir: 解压目录，默认为 save_dir 下的文件名（不含扩展名）
        chunk_size: 下载分块大小，默认 8KB
        delete_after_extract: 解压后是否删除压缩包，默认 False
    
    Returns:
        解压后的目录路径
    
    Raises:
        RuntimeError: 下载或解压失败时抛出异常
        FileNotFoundError: 压缩文件不存在
        ValueError: 不支持的压缩格式
    """
    # 设置默认保存目录
    if save_dir is None:
        save_path = Path(__file__).parent.parent / "docs" / "docs_parser"
    else:
        save_path = Path(save_dir)
    
    save_path.mkdir(parents=True, exist_ok=True)
    
    # 提取文件名
    filename = url.split('/')[-1].split('?')[0]
    file_path = save_path / filename
    
    print(f"开始下载：{url}")
    print(f"保存路径：{file_path}")
    
    # 下载文件
    try:
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        
        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        
        with open(file_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # 显示下载进度
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r下载进度：{progress:.2f}%", end='')
        
        print(f"\n下载完成：{file_path}")
        
    except Exception as e:
        raise RuntimeError(f"下载失败：{e}")
    
    # 解压文件
    extracted_path = extract_file(
        file_path=str(file_path),
        extract_dir=extract_dir,
        delete_after=delete_after_extract
    )
    
    return extracted_path


def extract_file(
    file_path: str,
    extract_dir: Optional[str] = None,
    delete_after: bool = False
) -> str:
    """
    解压文件
    
    Args:
        file_path: 压缩文件路径
        extract_dir: 解压目录，默认为文件所在目录下的文件名（不含扩展名）
        delete_after: 解压后是否删除原压缩文件
    
    Returns:
        解压后的目录路径
    """
    fpath = Path(file_path)
    
    if not fpath.exists():
        raise FileNotFoundError(f"压缩文件不存在：{fpath}")
    
    # 确定解压目录
    if extract_dir is None:
        # 去除所有可能的压缩扩展名
        stem = fpath.stem
        for ext in ['.tar', '.gz', '.bz2', '.xz', '.zip', '.rar', '.7z']:
            if stem.endswith(ext):
                stem = stem[:-len(ext)]
        edest = fpath.parent / stem
    else:
        edest = Path(extract_dir)
    
    edest.mkdir(parents=True, exist_ok=True)
    
    print(f"开始解压：{fpath}")
    print(f"解压到：{edest}")
    
    # 根据文件扩展名选择解压方式
    suffix = fpath.suffix.lower()
    full_suffix = fpath.name.lower()
    
    try:
        if suffix == '.zip':
            _extract_zip(fpath, edest)
        elif suffix in ['.tar', '.gz', '.bz2', '.xz'] or full_suffix.endswith('.tar.gz') or full_suffix.endswith('.tar.bz2'):
            _extract_tar(fpath, edest)
        elif suffix in ['.rar', '.7z']:
            print(f"警告：{suffix} 格式需要额外库支持，尝试使用系统工具")
            _extract_with_system(fpath, edest)
        else:
            # 尝试自动检测
            if _is_zip_file(fpath):
                _extract_zip(fpath, edest)
            elif _is_tar_file(fpath):
                _extract_tar(fpath, edest)
            else:
                raise ValueError(f"不支持的压缩格式：{suffix}")
        
        print(f"解压完成：{edest}")
        
        # 删除原压缩文件
        if delete_after:
            fpath.unlink()
            print(f"已删除原压缩文件：{fpath}")
        
        return str(edest)
        
    except Exception as e:
        raise RuntimeError(f"解压失败：{e}")


def _extract_zip(file_path: Path, extract_dir: Path) -> None:
    """解压 ZIP 文件"""
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)


def _extract_tar(file_path: Path, extract_dir: Path) -> None:
    """解压 TAR 系列文件（tar.gz, tar.bz2, tar.xz 等）"""
    mode = 'r:*'  # 自动检测压缩格式
    with tarfile.open(file_path, mode) as tar_ref:
        tar_ref.extractall(extract_dir)


def _extract_with_system(file_path: Path, extract_dir: Path) -> None:
    """使用系统命令解压（用于 rar、7z 等格式）"""
    import subprocess
    
    # 尝试使用 7z 命令
    try:
        subprocess.run(['7z', 'x', str(file_path), f'-o{extract_dir}', '-y'], check=True)
        return
    except subprocess.CalledProcessError:
        pass
    except FileNotFoundError:
        pass
    
    # 尝试使用 unzip 命令（仅限 zip）
    try:
        subprocess.run(['unzip', '-o', str(file_path), '-d', str(extract_dir)], check=True)
        return
    except subprocess.CalledProcessError:
        pass
    except FileNotFoundError:
        pass
    
    raise RuntimeError("无法解压：缺少必要的解压工具，请安装 7z 或相应解压软件")


def _is_zip_file(file_path: Path) -> bool:
    """检测是否为 ZIP 文件"""
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.testzip()
        return True
    except:
        return False


def _is_tar_file(file_path: Path) -> bool:
    """检测是否为 TAR 文件"""
    try:
        with tarfile.open(file_path, 'r:*') as tar_ref:
            pass
        return True
    except:
        return False


# 使用示例
# if __name__ == "__main__":
#     # 示例 1: 下载并解压 ZIP 文件
#     # url = "https://example.com/file.zip"
#     # extracted_path = download_and_extract(url)
#     # print(f"解压到：{extracted_path}")
    
#     # 示例 2: 指定保存和解压目录
#     # extracted_path = download_and_extract(
#     #     url="https://example.com/data.tar.gz",
#     #     save_dir="./my_downloads",
#     #     extract_dir="./my_data",
#     #     delete_after_extract=True
#     # )
    
#     # 示例 3: 仅解压本地文件
#     # extracted_path = extract_file("./downloads/file.zip")
    
#     print("下载解压工具已就绪！")
#     print("使用方法:")
#     print("  from downloader import download_and_extract")
#     print("  result = download_and_extract('https://example.com/file.zip')")
