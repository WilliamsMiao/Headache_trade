"""
消息传递机制
支持技能间通信和事件驱动
"""

import queue
import threading
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from datetime import datetime
from collections import defaultdict


class MessageType(Enum):
    """消息类型"""
    MARKET_DATA = "market_data"
    MARKET_ANALYSIS = "market_analysis"
    STRATEGY_SIGNAL = "strategy_signal"
    RISK_ASSESSMENT = "risk_assessment"
    TRADE_EXECUTION = "trade_execution"
    EXECUTION_RESULT = "execution_result"
    ERROR = "error"
    WARNING = "warning"
    EVENT = "event"


class Message:
    """消息对象"""
    
    def __init__(
        self,
        msg_type: MessageType,
        sender: str,
        payload: Dict[str, Any],
        timestamp: Optional[datetime] = None
    ):
        self.msg_type = msg_type
        self.sender = sender
        self.payload = payload
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.msg_type.value,
            'sender': self.sender,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat()
        }


class MessageBus:
    """消息总线 - 单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._subscribers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._message_queue: queue.Queue = queue.Queue(maxsize=1000)
        self._lock = threading.RLock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._message_history: List[Message] = []
        self._max_history = 1000
        
        self._initialized = True
    
    def subscribe(self, msg_type: MessageType, callback: Callable[[Message], None]) -> None:
        """订阅消息类型"""
        with self._lock:
            if callback not in self._subscribers[msg_type]:
                self._subscribers[msg_type].append(callback)
    
    def unsubscribe(self, msg_type: MessageType, callback: Callable[[Message], None]) -> None:
        """取消订阅"""
        with self._lock:
            if callback in self._subscribers[msg_type]:
                self._subscribers[msg_type].remove(callback)
    
    def publish(self, message: Message) -> bool:
        """发布消息"""
        try:
            with self._lock:
                # 添加到历史记录
                self._message_history.append(message)
                if len(self._message_history) > self._max_history:
                    self._message_history = self._message_history[-self._max_history:]
            
            # 同步通知订阅者
            self._notify_subscribers(message)
            
            # 异步处理（如果需要）
            try:
                self._message_queue.put_nowait(message)
            except queue.Full:
                # 队列满时丢弃最旧的消息
                try:
                    self._message_queue.get_nowait()
                    self._message_queue.put_nowait(message)
                except queue.Empty:
                    pass
            
            return True
        except Exception as e:
            print(f"⚠️ 发布消息失败: {e}")
            return False
    
    def publish_simple(
        self,
        msg_type: MessageType,
        sender: str,
        payload: Dict[str, Any]
    ) -> bool:
        """发布简单消息（便捷方法）"""
        message = Message(msg_type, sender, payload)
        return self.publish(message)
    
    def _notify_subscribers(self, message: Message) -> None:
        """通知订阅者"""
        with self._lock:
            callbacks = self._subscribers[message.msg_type].copy()
        
        for callback in callbacks:
            try:
                callback(message)
            except Exception as e:
                print(f"⚠️ 消息回调执行失败: {e}")
    
    def start_worker(self) -> None:
        """启动工作线程（用于异步消息处理）"""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop_worker(self) -> None:
        """停止工作线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
    
    def _worker_loop(self) -> None:
        """工作线程循环"""
        while self._running:
            try:
                message = self._message_queue.get(timeout=1.0)
                # 这里可以添加异步处理逻辑
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ 消息处理错误: {e}")
    
    def get_recent_messages(
        self,
        msg_type: Optional[MessageType] = None,
        count: int = 10
    ) -> List[Message]:
        """获取最近的消息"""
        with self._lock:
            if msg_type:
                filtered = [m for m in self._message_history if m.msg_type == msg_type]
            else:
                filtered = self._message_history
            
            return filtered[-count:] if filtered else []
    
    def clear_history(self) -> None:
        """清空消息历史"""
        with self._lock:
            self._message_history = []
