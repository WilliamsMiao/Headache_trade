"""
文件锁工具函数
提供统一的文件读写锁机制
"""
import fcntl
from typing import Any, Callable, Optional


def with_file_lock(file_path: str, mode: str = 'r', lock_type: int = fcntl.LOCK_SH, 
                   operation: Optional[Callable] = None) -> Any:
    """
    使用文件锁执行文件操作
    
    Args:
        file_path: 文件路径
        mode: 文件打开模式 ('r', 'w', 'a' 等)
        lock_type: 锁类型 (fcntl.LOCK_SH 共享锁, fcntl.LOCK_EX 排他锁)
        operation: 要执行的操作函数，接收文件对象作为参数
    
    Returns:
        操作函数的返回值，如果没有提供操作函数则返回文件内容
    """
    with open(file_path, mode, encoding='utf-8') as f:
        fcntl.flock(f.fileno(), lock_type)
        try:
            if operation:
                return operation(f)
            else:
                if mode.startswith('r'):
                    import json
                    return json.load(f)
                return None
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_with_shared_lock(file_path: str) -> Any:
    """
    使用共享锁读取JSON文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        解析后的JSON数据
    """
    import json
    return with_file_lock(file_path, 'r', fcntl.LOCK_SH, lambda f: json.load(f))


def write_with_exclusive_lock(file_path: str, data: Any, ensure_ascii: bool = False) -> None:
    """
    使用排他锁写入JSON文件
    
    Args:
        file_path: 文件路径
        data: 要写入的数据
        ensure_ascii: 是否确保ASCII编码
    """
    import json
    import os
    
    # 确保目录存在
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # 如果文件不存在，先创建空文件
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            pass
    
    with_file_lock(file_path, 'w', fcntl.LOCK_EX, 
                   lambda f: json.dump(data, f, ensure_ascii=ensure_ascii, indent=2))
