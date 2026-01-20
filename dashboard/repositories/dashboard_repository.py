"""
Dashboard数据仓库
负责读取dashboard_data.json文件
"""
import os
from typing import Optional, Dict, Any
from dashboard.config import DASHBOARD_DATA_FILE
from dashboard.utils.file_lock import read_with_shared_lock


def load_dashboard_data() -> Optional[Dict[str, Any]]:
    """
    从JSON文件读取Dashboard数据
    
    Returns:
        Dashboard数据字典，如果文件不存在或读取失败则返回None
    """
    try:
        if not os.path.exists(DASHBOARD_DATA_FILE):
            print("⚠️ Dashboard数据文件不存在，使用默认数据")
            return None
        
        data = read_with_shared_lock(DASHBOARD_DATA_FILE)
        return data
    except Exception as e:
        print(f"❌ 读取Dashboard数据失败: {e}")
        return None
