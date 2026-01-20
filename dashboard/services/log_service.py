"""
日志服务
负责日志文件的读取和流式传输
"""
import time
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Generator
from dashboard.config import LOG_FILES


def tail_log(path: Path, limit: int = 200) -> List[str]:
    """
    读取日志文件的最后N行
    
    Args:
        path: 日志文件路径
        limit: 读取行数限制
    
    Returns:
        日志行列表
    """
    if not path.exists():
        return []
    
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    return lines[-limit:]


def log_stream_generator(path: Path, log_type: str, poll_seconds: float = 1.0) -> Generator[str, None, None]:
    """
    生成日志流（Server-Sent Events格式）
    
    Args:
        path: 日志文件路径
        log_type: 日志类型标识
        poll_seconds: 轮询间隔（秒）
    
    Yields:
        SSE格式的日志数据
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        f.seek(0, 2)  # 移动到文件末尾 (os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                payload = json.dumps({
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'level': 'INFO',
                    'source': log_type,
                    'message': line.strip(),
                })
                yield f"data: {payload}\n\n"
            else:
                time.sleep(poll_seconds)


def format_log_entries(lines: List[str], log_type: str) -> List[Dict[str, Any]]:
    """
    格式化日志行为JSON格式
    
    Args:
        lines: 日志行列表
        log_type: 日志类型
    
    Returns:
        格式化的日志条目列表
    """
    entries = []
    for line in lines:
        entries.append({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': 'INFO',
            'source': log_type,
            'message': line.strip(),
        })
    return entries
