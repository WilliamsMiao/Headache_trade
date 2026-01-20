"""
交易参数配置仓库
负责交易参数的加载、保存、备份和回滚
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dashboard.config import CONFIG_BACKUP_DIR, CURRENT_CONFIG_FILE, PROJECT_ROOT
from dashboard.utils.file_lock import read_with_shared_lock, write_with_exclusive_lock


def load_trading_params() -> Dict[str, Any]:
    """
    加载交易参数
    如果当前配置文件存在则读取，否则返回默认配置
    
    Returns:
        交易参数字典
    """
    if CURRENT_CONFIG_FILE.exists():
        try:
            return read_with_shared_lock(str(CURRENT_CONFIG_FILE))
        except Exception as exc:
            print(f"⚠️ 读取当前配置失败，使用默认: {exc}")
    
    # 返回默认配置（由service层提供）
    return {}


def save_trading_params(new_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    保存交易参数
    保存前会自动备份当前配置
    
    Args:
        new_params: 新的交易参数
    
    Returns:
        保存后的参数（包含updated_at字段）
    """
    # 先备份
    backup_trading_params()
    
    # 确保目录存在
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存新配置
    payload = {**new_params, 'updated_at': datetime.utcnow().isoformat() + 'Z'}
    write_with_exclusive_lock(str(CURRENT_CONFIG_FILE), payload, ensure_ascii=False)
    
    return payload


def backup_trading_params(snapshot: Optional[Dict[str, Any]] = None) -> Path:
    """
    备份交易参数
    
    Args:
        snapshot: 要备份的参数快照，如果为None则备份当前配置
    
    Returns:
        备份文件路径
    """
    CONFIG_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    if snapshot is None:
        snapshot = load_trading_params()
    
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = CONFIG_BACKUP_DIR / f"trading_params_{ts}.json"
    
    with backup_path.open('w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    
    return backup_path


def list_config_history() -> List[Dict[str, Any]]:
    """
    列出所有配置备份历史
    
    Returns:
        配置历史记录列表，按时间倒序排列
    """
    entries = []
    if not CONFIG_BACKUP_DIR.exists():
        return entries
    
    for p in CONFIG_BACKUP_DIR.glob('trading_params_*.json'):
        entries.append({
            'name': p.name,
            'path': str(p.relative_to(PROJECT_ROOT)),
            'timestamp': p.stat().st_mtime,
            'size': p.stat().st_size,
        })
    
    # 按时间倒序排列
    entries.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # 格式化时间戳
    for item in entries:
        item['timestamp'] = datetime.fromtimestamp(item['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
    
    return entries


def rollback_config(name: str) -> Dict[str, Any]:
    """
    回滚到指定的配置备份
    
    Args:
        name: 备份文件名
    
    Returns:
        回滚后的配置参数
    
    Raises:
        FileNotFoundError: 如果备份文件不存在
    """
    target = CONFIG_BACKUP_DIR / name
    if not target.exists():
        raise FileNotFoundError(f"未找到备份: {name}")
    
    # 读取备份配置
    payload = read_with_shared_lock(str(target))
    
    # 保存为当前配置
    write_with_exclusive_lock(str(CURRENT_CONFIG_FILE), payload, ensure_ascii=False)
    
    return payload
