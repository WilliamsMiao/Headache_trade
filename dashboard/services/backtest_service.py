"""
回测服务
管理回测任务的执行和状态
"""
import os
import sys
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dashboard.config import PROJECT_ROOT, LOG_FILES


class BacktestJobManager:
    """回测任务管理器"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
    
    def create_job(self, payload: Dict[str, Any]) -> str:
        """
        创建新的回测任务
        
        Args:
            payload: 回测任务参数
        
        Returns:
            任务ID
        """
        job_id = str(uuid.uuid4())
        with self.lock:
            self.jobs[job_id] = {
                'id': job_id,
                'status': 'queued',
                'ai_feedback': bool(payload.get('ai_feedback', False)),
                'config_name': payload.get('config') or 'default',
            }
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            job_id: 任务ID
        
        Returns:
            任务信息字典，如果不存在则返回None
        """
        with self.lock:
            return self.jobs.get(job_id)
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """
        更新任务状态
        
        Args:
            job_id: 任务ID
            updates: 要更新的字段
        """
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(updates)
    
    def run_job(self, job_id: str, payload: Dict[str, Any]) -> None:
        """
        执行回测任务
        
        Args:
            job_id: 任务ID
            payload: 任务参数
        """
        with self.lock:
            self.jobs[job_id] = {
                'id': job_id,
                'status': 'running',
                'started_at': datetime.utcnow().isoformat() + 'Z',
                'ai_feedback': bool(payload.get('ai_feedback', False)),
                'config_name': payload.get('config') or 'default',
            }
        
        log_path = LOG_FILES.get('backtest')
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            sys.executable,
            os.path.join(PROJECT_ROOT, 'scripts', 'backtest_runner.py'),
            '--days',
            str(payload.get('days', 30))
        ]
        if payload.get('config'):
            cmd += ['--config', str(payload['config'])]
        
        # 支持策略系统参数
        if payload.get('strategy_name'):
            cmd += ['--strategy', str(payload['strategy_name'])]
        if payload.get('strategy_params'):
            import json
            cmd += ['--strategy-params', json.dumps(payload['strategy_params'])]
        
        env = os.environ.copy()
        if payload.get('initial_balance'):
            env['BACKTEST_INITIAL_BALANCE'] = str(payload['initial_balance'])
        if payload.get('leverage'):
            env['BACKTEST_LEVERAGE'] = str(payload['leverage'])
        
        try:
            with log_path.open('a', encoding='utf-8') as lf:
                lf.write(f"\n[{datetime.utcnow().isoformat()}Z] job {job_id} start cmd: {' '.join(cmd)}\n")
                proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, stdout=lf, stderr=lf, text=True)
            
            status = 'completed' if proc.returncode == 0 else 'failed'
            with self.lock:
                self.jobs[job_id] = {
                    **self.jobs.get(job_id, {}),
                    'status': status,
                    'finished_at': datetime.utcnow().isoformat() + 'Z',
                    'message': f'return code {proc.returncode}',
                }
        except Exception as exc:
            with self.lock:
                self.jobs[job_id] = {
                    **self.jobs.get(job_id, {}),
                    'status': 'failed',
                    'finished_at': datetime.utcnow().isoformat() + 'Z',
                    'message': str(exc),
                }


# 全局回测任务管理器实例
backtest_manager = BacktestJobManager()
