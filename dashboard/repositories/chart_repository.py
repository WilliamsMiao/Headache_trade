"""
图表历史数据仓库
负责读取和保存chart_history.json文件
"""
import os
from typing import List, Dict, Any
from datetime import datetime
from dashboard.config import CHART_HISTORY_FILE
from dashboard.utils.file_lock import read_with_shared_lock, write_with_exclusive_lock


def load_chart_history() -> List[Dict[str, Any]]:
    """
    从JSON文件读取图表历史数据
    
    Returns:
        图表历史数据点列表
    """
    try:
        if not os.path.exists(CHART_HISTORY_FILE):
            print("⚠️ 图表历史文件不存在，创建新文件")
            return []
        
        data = read_with_shared_lock(CHART_HISTORY_FILE)
        return data.get('chart_points', [])
    except Exception as e:
        print(f"❌ 读取图表历史失败: {e}")
        return []


def save_chart_history(chart_points: List[Dict[str, Any]]) -> None:
    """
    保存图表历史数据到JSON文件
    
    Args:
        chart_points: 图表数据点列表
    """
    try:
        # 确保数据按时间顺序排列（旧到新）
        sorted_points = sorted(chart_points, key=lambda x: x.get('timestamp', ''))
        
        data = {
            'chart_points': sorted_points,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_points': len(sorted_points)
        }
        
        write_with_exclusive_lock(CHART_HISTORY_FILE, data, ensure_ascii=False)
        
        print(f"✅ 图表历史已保存: {len(sorted_points)} 个数据点 (已按时间排序)")
    except Exception as e:
        print(f"❌ 保存图表历史失败: {e}")
