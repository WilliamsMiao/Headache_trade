"""
钉钉机器人通知模块
用于发送交易提醒到钉钉群
"""

import requests
import hmac
import hashlib
import base64
import time
import urllib.parse
from typing import Optional, Dict
import json
from datetime import datetime


class DingDingNotifier:
    """钉钉机器人通知器"""
    
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        """
        初始化钉钉通知器
        
        Args:
            webhook_url: 钉钉机器人 webhook 地址
            secret: 安全设置中的加签密钥（可选）
        """
        self.webhook_url = webhook_url
        self.secret = secret
        self.enabled = bool(webhook_url)
    
    def _get_sign(self, timestamp: str) -> str:
        """生成签名"""
        if not self.secret:
            return None
        
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign
    
    def _build_url(self) -> str:
        """构建带签名的 URL"""
        timestamp = str(round(time.time() * 1000))
        sign = self._get_sign(timestamp)
        
        if sign:
            return f'{self.webhook_url}&timestamp={timestamp}&sign={sign}'
        return self.webhook_url
    
    def send_text(self, content: str, at_all: bool = False, at_mobiles: list = None) -> bool:
        """
        发送文本消息
        
        Args:
            content: 消息内容
            at_all: 是否@所有人
            at_mobiles: @指定人的手机号列表
        """
        if not self.enabled:
            return False
        
        message = {
            "msgtype": "text",
            "text": {
                "content": content
            },
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all
            }
        }
        
        return self._send(message)
    
    def send_markdown(self, title: str, text: str, at_all: bool = False, at_mobiles: list = None) -> bool:
        """
        发送 Markdown 消息
        
        Args:
            title: 消息标题
            text: Markdown 格式的消息内容
            at_all: 是否@所有人
            at_mobiles: @指定人的手机号列表
        """
        if not self.enabled:
            return False
        
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text
            },
            "at": {
                "atMobiles": at_mobiles or [],
                "isAtAll": at_all
            }
        }
        
        return self._send(message)
    
    def _send(self, message: dict) -> bool:
        """发送消息"""
        try:
            url = self._build_url()
            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(message),
                timeout=5
            )
            
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                print(f"钉钉消息发送失败: {result.get('errmsg')}")
                return False
        
        except Exception as e:
            print(f"钉钉消息发送异常: {str(e)}")
            return False
    
    def notify_trade_open(self, trade_info: Dict) -> bool:
        """通知开仓"""
        side = trade_info.get('side', 'unknown').upper()
        side_emoji = "🟢" if side == 'LONG' else "🔴"
        
        title = f"{side_emoji} 开仓通知 - {side}"
        
        text = f"""### {side_emoji} 开仓通知 - {side}

**策略**: {trade_info.get('strategy', 'N/A')}

**入场价格**: ${trade_info.get('entry_price', 0):.2f}

**仓位大小**: {trade_info.get('size', 0):.4f}

**仓位价值**: ${trade_info.get('position_value', 0):,.2f}

**止损价格**: ${trade_info.get('stop_loss', 0):.2f}

**止盈价格**: ${trade_info.get('take_profit', 0):.2f}

**信号置信度**: {trade_info.get('confidence', 0):.1f}%

**入场原因**: {trade_info.get('reason', 'N/A')}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> 交易机器人已自动开仓，请密切关注市场变化
"""
        
        return self.send_markdown(title, text)
    
    def notify_trade_close(self, trade_info: Dict) -> bool:
        """通知平仓"""
        pnl = trade_info.get('net_pnl', 0)
        pnl_emoji = "💰" if pnl > 0 else "📉"
        result = "盈利" if pnl > 0 else "亏损"
        
        title = f"{pnl_emoji} 平仓通知 - {result}"
        
        return_pct = trade_info.get('return_pct', 0)
        hold_hours = trade_info.get('hold_hours', 0)
        
        text = f"""### {pnl_emoji} 平仓通知 - {result}

**策略**: {trade_info.get('strategy', 'N/A')}

**入场价格**: ${trade_info.get('entry_price', 0):.2f}

**出场价格**: ${trade_info.get('exit_price', 0):.2f}

**盈亏金额**: <font color={'#10b981' if pnl >= 0 else '#ef4444'}>${pnl:,.2f}</font>

**收益率**: <font color={'#10b981' if return_pct >= 0 else '#ef4444'}>{return_pct:+.2f}%</font>

**持仓时长**: {hold_hours:.1f} 小时

**退出原因**: {trade_info.get('exit_reason', 'N/A')}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> 交易已完成，{'恭喜盈利！' if pnl > 0 else '保持冷静，继续执行策略'}
"""
        
        return self.send_markdown(title, text)
    
    def notify_strategy_switch(self, from_strategy: str, to_strategy: str, reason: str, market_state: str) -> bool:
        """通知策略切换"""
        title = "🔄 策略切换通知"
        
        text = f"""### 🔄 策略切换通知

**原策略**: {from_strategy}

**新策略**: {to_strategy}

**市场状态**: {market_state}

**切换原因**: {reason}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> 系统已自动切换策略以适应市场变化
"""
        
        return self.send_markdown(title, text)
    
    def notify_risk_warning(self, warning_type: str, message: str, severity: str = 'medium') -> bool:
        """通知风险警告"""
        severity_config = {
            'low': {'emoji': 'ℹ️', 'color': '#3b82f6'},
            'medium': {'emoji': '⚠️', 'color': '#f59e0b'},
            'high': {'emoji': '🚫', 'color': '#ef4444'},
            'critical': {'emoji': '🆘', 'color': '#dc2626'}
        }
        
        config = severity_config.get(severity, severity_config['medium'])
        title = f"{config['emoji']} 风险警告 - {warning_type}"
        
        text = f"""### {config['emoji']} 风险警告

**警告类型**: {warning_type}

**严重程度**: <font color='{config['color']}'>{severity.upper()}</font>

**详细信息**: {message}

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> ⚠️ 请立即检查系统状态，必要时采取应对措施
"""
        
        at_all = (severity in ['high', 'critical'])
        return self.send_markdown(title, text, at_all=at_all)
    
    def notify_daily_summary(self, summary: Dict) -> bool:
        """发送每日交易摘要"""
        title = "📊 每日交易摘要"
        
        equity = summary.get('current_equity', 0)
        total_pnl = summary.get('total_pnl', 0)
        today_pnl = summary.get('today_pnl', 0)
        total_trades = summary.get('total_trades', 0)
        today_trades = summary.get('today_trades', 0)
        win_rate = summary.get('win_rate', 0)
        max_drawdown = summary.get('max_drawdown', 0)
        
        text = f"""### 📊 每日交易摘要

#### 💰 资金状况
- **当前权益**: ${equity:,.2f}
- **累计盈亏**: <font color={'#10b981' if total_pnl >= 0 else '#ef4444'}>${total_pnl:+,.2f}</font>
- **今日盈亏**: <font color={'#10b981' if today_pnl >= 0 else '#ef4444'}>${today_pnl:+,.2f}</font>

#### 📈 交易统计
- **累计交易**: {total_trades} 笔
- **今日交易**: {today_trades} 笔
- **整体胜率**: {win_rate:.1f}%

#### ⚠️ 风险指标
- **最大回撤**: {max_drawdown:.2f}%

#### 🎯 策略表现
"""
        
        # 添加策略表现
        if 'strategies' in summary:
            for strategy in summary['strategies']:
                text += f"- **{strategy['name']}**: {strategy['trades']}笔 | 胜率{strategy['win_rate']:.1f}% | 盈亏${strategy['pnl']:+,.2f}\n"
        
        text += f"""
---
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

> 每日汇总报告，祝您交易顺利！
"""
        
        return self.send_markdown(title, text)
    
    def notify_system_start(self) -> bool:
        """通知系统启动"""
        title = "🚀 交易系统启动"
        
        text = f"""### 🚀 交易系统启动

**状态**: 运行中 ✅

**启动时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> 交易机器人已启动，开始监控市场
"""
        
        return self.send_markdown(title, text)
    
    def notify_system_stop(self, reason: str = "手动停止") -> bool:
        """通知系统停止"""
        title = "🛑 交易系统停止"
        
        text = f"""### 🛑 交易系统停止

**状态**: 已停止 ⏸️

**停止原因**: {reason}

**停止时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> 交易机器人已停止运行
"""
        
        return self.send_markdown(title, text)
    
    def test_connection(self) -> bool:
        """测试连接"""
        if not self.enabled:
            print("钉钉通知未启用")
            return False
        
        title = "🔔 测试通知"
        text = f"""### 🔔 测试通知

这是一条测试消息，用于验证钉钉机器人配置是否正确。

**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
> 如果您看到这条消息，说明配置成功！
"""
        
        result = self.send_markdown(title, text)
        
        if result:
            print("✅ 钉钉通知测试成功")
        else:
            print("❌ 钉钉通知测试失败")
        
        return result


# 便捷函数
def create_notifier_from_config(config: Dict) -> Optional[DingDingNotifier]:
    """从配置创建通知器"""
    
    dingding_config = config.get('dingding', {})
    
    if not dingding_config.get('enabled', False):
        print("钉钉通知未启用")
        return None
    
    webhook_url = dingding_config.get('webhook_url')
    secret = dingding_config.get('secret')
    
    if not webhook_url:
        print("⚠️ 钉钉通知已启用但未配置 webhook_url")
        return None
    
    notifier = DingDingNotifier(webhook_url, secret)
    print("✅ 钉钉通知器初始化成功")
    
    return notifier


if __name__ == '__main__':
    # 测试代码
    print("\n钉钉机器人通知模块测试\n")
    print("请在 config.json 中配置钉钉机器人信息：")
    print("""
{
    "dingding": {
        "enabled": true,
        "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
        "secret": "YOUR_SECRET"
    }
}
    """)
    
    # 尝试加载配置
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        notifier = create_notifier_from_config(config)
        
        if notifier:
            print("\n开始测试...")
            notifier.test_connection()
    
    except FileNotFoundError:
        print("\n⚠️ 未找到 config.json 文件")
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
