#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易机器人工具模块
包含：跨平台文件锁、线程健康监控、数据备份等工具
"""

import sys
import time
import json
import shutil
import threading
from datetime import datetime
from pathlib import Path

# =============================================================================
# 跨平台文件锁（解决Windows兼容性问题）
# =============================================================================

class CrossPlatformFileLock:
    """跨平台文件锁 - 支持Windows和Unix系统"""
    
    def __init__(self, file_obj, exclusive=False):
        """
        Args:
            file_obj: 文件对象
            exclusive: 是否排他锁（True=排他，False=共享）
        """
        self.file_obj = file_obj
        self.exclusive = exclusive
        self.locked = False
        
    def __enter__(self):
        """进入上下文时加锁"""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时释放锁"""
        self.release()
        
    def acquire(self):
        """获取锁"""
        if self.locked:
            return
            
        try:
            if sys.platform == 'win32':
                # Windows系统使用msvcrt
                import msvcrt
                mode = msvcrt.LK_NBLCK if not self.exclusive else msvcrt.LK_LOCK
                msvcrt.locking(self.file_obj.fileno(), mode, 1)
            else:
                # Unix系统使用fcntl
                import fcntl
                mode = fcntl.LOCK_SH if not self.exclusive else fcntl.LOCK_EX
                fcntl.flock(self.file_obj.fileno(), mode)
            
            self.locked = True
        except Exception as e:
            print(f"⚠️ 文件加锁失败（继续执行）: {e}")
            # 不抛出异常，允许程序继续运行
    
    def release(self):
        """释放锁"""
        if not self.locked:
            return
            
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_UN)
            
            self.locked = False
        except Exception as e:
            print(f"⚠️ 文件解锁失败（忽略）: {e}")


def safe_read_json(file_path, default=None):
    """安全读取JSON文件（带文件锁）"""
    try:
        if not Path(file_path).exists():
            return default
        
        with open(file_path, 'r', encoding='utf-8') as f:
            with CrossPlatformFileLock(f, exclusive=False):
                data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ 读取JSON文件失败 ({file_path}): {e}")
        return default


def safe_write_json(file_path, data, create_backup=True):
    """安全写入JSON文件（带文件锁和备份）"""
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建备份（如果文件已存在）
        if create_backup and file_path.exists():
            backup_path = file_path.with_suffix('.json.bak')
            shutil.copy2(file_path, backup_path)
        
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            with CrossPlatformFileLock(f, exclusive=True):
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"❌ 写入JSON文件失败 ({file_path}): {e}")
        return False


# =============================================================================
# 线程健康监控（解决线程崩溃问题）
# =============================================================================

class ThreadHealthMonitor:
    """线程健康监控器 - 自动检测并重启崩溃的线程"""
    
    def __init__(self, target_func, thread_name="Worker", check_interval=30, heartbeat_timeout=120):
        """
        Args:
            target_func: 要监控的线程函数
            thread_name: 线程名称
            check_interval: 检查间隔（秒）
            heartbeat_timeout: 心跳超时时间（秒）
        """
        self.target_func = target_func
        self.thread_name = thread_name
        self.check_interval = check_interval
        self.heartbeat_timeout = heartbeat_timeout
        
        self.worker_thread = None
        self.last_heartbeat = time.time()
        self.is_monitoring = False
        self.monitor_thread = None
        self.restart_count = 0
        self.max_restarts = 10  # 最大重启次数
        
    def start(self):
        """启动监控"""
        if self.is_monitoring:
            print(f"⚠️ 线程监控器已在运行: {self.thread_name}")
            return
        
        # 启动工作线程
        self._start_worker_thread()
        
        # 启动监控线程
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        print(f"✅ 线程健康监控已启动: {self.thread_name}")
    
    def stop(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print(f"⏹️ 线程健康监控已停止: {self.thread_name}")
    
    def heartbeat(self):
        """更新心跳（工作线程应定期调用此方法）"""
        self.last_heartbeat = time.time()
    
    def _start_worker_thread(self):
        """启动工作线程"""
        self.worker_thread = threading.Thread(target=self.target_func, daemon=True)
        self.worker_thread.start()
        self.last_heartbeat = time.time()
        print(f"🔄 工作线程已启动: {self.thread_name}")
    
    def _monitor_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                time.sleep(self.check_interval)
                
                # 检查线程是否存活
                if not self.worker_thread or not self.worker_thread.is_alive():
                    print(f"🚨 检测到线程已死亡: {self.thread_name}")
                    self._restart_worker_thread("线程已死亡")
                    continue
                
                # 检查心跳超时
                time_since_heartbeat = time.time() - self.last_heartbeat
                if time_since_heartbeat > self.heartbeat_timeout:
                    print(f"⚠️ 检测到心跳超时: {self.thread_name} (超时 {time_since_heartbeat:.0f}秒)")
                    self._restart_worker_thread("心跳超时")
                    continue
                
            except Exception as e:
                print(f"❌ 线程监控异常: {e}")
                time.sleep(self.check_interval)
    
    def _restart_worker_thread(self, reason):
        """重启工作线程"""
        self.restart_count += 1
        
        if self.restart_count > self.max_restarts:
            print(f"❌ 线程重启次数超过限制({self.max_restarts})，停止监控: {self.thread_name}")
            self.is_monitoring = False
            return
        
        print(f"🔄 正在重启工作线程 (原因: {reason}, 第{self.restart_count}次重启)...")
        
        # 尝试停止旧线程
        if self.worker_thread and self.worker_thread.is_alive():
            try:
                self.worker_thread.join(timeout=5)
            except:
                pass
        
        # 启动新线程
        self._start_worker_thread()


# =============================================================================
# 数据备份和恢复
# =============================================================================

class DataBackupManager:
    """数据备份管理器"""
    
    def __init__(self, data_dir, max_backups=10):
        """
        Args:
            data_dir: 数据目录
            max_backups: 保留最大备份数量
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = self.data_dir / 'backups'
        self.max_backups = max_backups
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, file_path):
        """创建备份"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return False
            
            # 生成备份文件名（带时间戳）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
            backup_path = self.backup_dir / backup_name
            
            # 复制文件
            shutil.copy2(file_path, backup_path)
            print(f"✅ 备份已创建: {backup_name}")
            
            # 清理旧备份
            self._cleanup_old_backups(file_path.stem)
            
            return True
        except Exception as e:
            print(f"❌ 创建备份失败: {e}")
            return False
    
    def restore_latest_backup(self, file_path):
        """恢复最新备份"""
        try:
            file_path = Path(file_path)
            
            # 查找最新备份
            backups = sorted(self.backup_dir.glob(f"{file_path.stem}_*{file_path.suffix}"), 
                           key=lambda p: p.stat().st_mtime, reverse=True)
            
            if not backups:
                print(f"⚠️ 未找到备份文件: {file_path.stem}")
                return False
            
            latest_backup = backups[0]
            shutil.copy2(latest_backup, file_path)
            print(f"✅ 已从备份恢复: {latest_backup.name}")
            
            return True
        except Exception as e:
            print(f"❌ 恢复备份失败: {e}")
            return False
    
    def _cleanup_old_backups(self, file_stem):
        """清理旧备份（保留最新N个）"""
        try:
            backups = sorted(self.backup_dir.glob(f"{file_stem}_*"), 
                           key=lambda p: p.stat().st_mtime, reverse=True)
            
            # 删除超出限制的备份
            for backup in backups[self.max_backups:]:
                backup.unlink()
                print(f"🗑️ 已删除旧备份: {backup.name}")
        except Exception as e:
            print(f"⚠️ 清理旧备份失败: {e}")


# =============================================================================
# API重试机制（指数退避）
# =============================================================================

class ExponentialBackoffRetry:
    """指数退避重试机制"""
    
    def __init__(self, max_retries=5, base_delay=1, max_delay=60):
        """
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def execute(self, func, *args, **kwargs):
        """执行函数（带重试）"""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"❌ 重试{self.max_retries}次后仍失败: {e}")
                    raise
                
                # 计算延迟时间（指数增长）
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                print(f"⚠️ 第{attempt + 1}次尝试失败，{delay}秒后重试: {e}")
                time.sleep(delay)
        
        return None


# =============================================================================
# 数据完整性验证
# =============================================================================

def validate_json_file(file_path, required_keys=None):
    """验证JSON文件完整性"""
    try:
        data = safe_read_json(file_path)
        if data is None:
            return False, "文件不存在或无法读取"
        
        if required_keys:
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return False, f"缺少必需字段: {', '.join(missing_keys)}"
        
        return True, "验证通过"
    except Exception as e:
        return False, f"验证失败: {e}"
