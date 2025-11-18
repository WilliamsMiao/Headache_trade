"""
AI分析模块
包含DeepSeek API调用、市场情绪分析等
"""

import os
import json
import requests
from openai import OpenAI
from typing import Dict, Optional
from datetime import datetime
import traceback


class AIAnalyzer:
    """AI分析器"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = "deepseek-chat"
    
    def analyze_market(self, price_data, technical_analysis: str) -> Optional[Dict]:
        """
        使用DeepSeek分析市场
        
        Args:
            price_data: 价格数据
            technical_analysis: 技术分析文本
        
        Returns:
            dict: 分析结果
        """
        try:
            prompt = self._build_analysis_prompt(price_data, technical_analysis)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的加密货币交易分析师。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            
            result_text = response.choices[0].message.content
            result_json = self._parse_response(result_text)
            
            return result_json
        
        except Exception as e:
            print(f"❌ AI分析失败: {e}")
            traceback.print_exc()
            return None
    
    def _build_analysis_prompt(self, price_data, technical_analysis: str) -> str:
        """构建分析提示词"""
        current_price = price_data['close'].iloc[-1]
        
        prompt = f"""
请分析以下BTC市场数据，给出交易建议：

当前价格: ${current_price:.2f}

技术分析:
{technical_analysis}

请以JSON格式返回分析结果：
{{
    "signal": "buy/sell/hold",
    "confidence": 0-100,
    "reasoning": "分析理由",
    "key_levels": {{
        "support": 价格,
        "resistance": 价格
    }}
}}
"""
        return prompt
    
    def _parse_response(self, text: str) -> Optional[Dict]:
        """解析AI响应"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                return None
        
        except Exception as e:
            print(f"⚠️ 解析AI响应失败: {e}")
            return None


def generate_technical_analysis_text(price_data) -> str:
    """
    生成技术分析文本
    
    Args:
        price_data: 价格数据帧
    
    Returns:
        str: 技术分析文本
    """
    from indicators import calculate_technical_indicators, get_market_trend
    
    indicators = calculate_technical_indicators(price_data)
    trend = get_market_trend(price_data)
    
    current_price = price_data['close'].iloc[-1]
    
    text = f"""
价格: ${current_price:.2f}

趋势分析:
- 趋势: {trend['trend']}
- MA20: ${trend['ma20']:.2f}
- MA50: ${trend['ma50']:.2f}
- MA100: ${trend['ma100']:.2f}

技术指标:
- RSI(14): {indicators['rsi']:.2f}
- MACD: {indicators['macd']:.4f}
- 信号线: {indicators['macd_signal']:.4f}
- ADX: {indicators['adx']:.2f}
- ATR: {indicators['atr']:.2f}

布林带:
- 上轨: ${indicators['bb_upper']:.2f}
- 中轨: ${indicators['bb_middle']:.2f}
- 下轨: ${indicators['bb_lower']:.2f}
- 宽度: {indicators['bb_width']:.4f}

成交量:
- 成交量比率: {indicators['volume_ratio']:.2f}
"""
    
    return text


# =============================================================================
# 市场情绪分析
# =============================================================================

# CryptoOracle API监控状态
sentiment_api_monitor = {
    'consecutive_failures': 0,
    'is_available': True,
    'last_success': datetime.now(),
    'last_reset_date': datetime.now().date(),
}


def get_sentiment_indicators() -> Optional[Dict]:
    """
    获取市场情绪指标
    
    Returns:
        dict: 情绪指标数据
    """
    global sentiment_api_monitor
    
    # 每日重置
    current_date = datetime.now().date()
    if sentiment_api_monitor['last_reset_date'] != current_date:
        sentiment_api_monitor['consecutive_failures'] = 0
        sentiment_api_monitor['is_available'] = True
        sentiment_api_monitor['last_reset_date'] = current_date
        print("🔄 情绪API监控已每日重置")
    
    # 检查API是否可用
    if not sentiment_api_monitor['is_available']:
        time_since_success = (datetime.now() - sentiment_api_monitor['last_success']).total_seconds()
        
        # 超过1小时自动重试
        if time_since_success > 3600:
            sentiment_api_monitor['is_available'] = True
            sentiment_api_monitor['consecutive_failures'] = 0
            print("🔄 情绪API自动恢复重试")
        else:
            print("⚠️ 情绪API暂时不可用，跳过本次调用")
            return None
    
    # 使用指数退避重试
    from utils import ExponentialBackoffRetry
    retry_manager = ExponentialBackoffRetry(max_retries=3, base_delay=1, max_delay=5)
    
    api_url = os.getenv('CRYPTO_ORACLE_API_URL', '')
    api_key = os.getenv('CRYPTO_ORACLE_API_KEY', '')
    
    if not api_url or not api_key:
        print("⚠️ 情绪API配置缺失")
        return None
    
    try:
        result = retry_manager.execute(_fetch_sentiment_data, api_url, api_key)
        
        if result:
            sentiment_api_monitor['consecutive_failures'] = 0
            sentiment_api_monitor['last_success'] = datetime.now()
            sentiment_api_monitor['is_available'] = True
            return result
        else:
            _handle_sentiment_api_failure()
            return None
    
    except Exception as e:
        print(f"❌ 获取情绪指标失败: {e}")
        _handle_sentiment_api_failure()
        return None


def _fetch_sentiment_data(api_url: str, api_key: str) -> Optional[Dict]:
    """
    实际获取情绪数据的函数
    
    Args:
        api_url: API地址
        api_key: API密钥
    
    Returns:
        dict: 情绪数据
    """
    headers = {'Authorization': f'Bearer {api_key}'}
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'fear_greed_index': data.get('fear_greed_index', 50),
                'sentiment_score': data.get('sentiment_score', 0),
                'social_volume': data.get('social_volume', 0),
            }
        else:
            print(f"⚠️ 情绪API返回错误: {response.status_code}")
            return None
    
    except requests.exceptions.Timeout:
        print("⚠️ 情绪API请求超时")
        return None
    except Exception as e:
        print(f"⚠️ 情绪API请求异常: {e}")
        return None


def _handle_sentiment_api_failure():
    """处理情绪API失败"""
    global sentiment_api_monitor
    
    sentiment_api_monitor['consecutive_failures'] += 1
    
    # 连续失败10次后暂时停用
    if sentiment_api_monitor['consecutive_failures'] >= 10:
        sentiment_api_monitor['is_available'] = False
        print(f"⚠️ 情绪API连续失败{sentiment_api_monitor['consecutive_failures']}次，暂时停用")


def check_sentiment_api_health() -> Dict:
    """
    检查情绪API健康状态
    
    Returns:
        dict: 健康状态信息
    """
    global sentiment_api_monitor
    
    return {
        'is_available': sentiment_api_monitor['is_available'],
        'consecutive_failures': sentiment_api_monitor['consecutive_failures'],
        'last_success': sentiment_api_monitor['last_success'].isoformat(),
        'last_reset_date': sentiment_api_monitor['last_reset_date'].isoformat(),
    }


def create_fallback_signal(price_data) -> Dict:
    """
    创建后备信号（当AI分析失败时）
    
    Args:
        price_data: 价格数据
    
    Returns:
        dict: 后备信号
    """
    from indicators import generate_trend_king_signal
    
    # 使用纯技术指标生成信号
    signal = generate_trend_king_signal(price_data)
    
    # 降低置信度
    signal['confidence'] = min(signal['confidence'], 70)
    signal['source'] = 'fallback'
    
    return signal


def safe_json_parse(json_str: str) -> Optional[Dict]:
    """
    安全解析JSON字符串
    
    Args:
        json_str: JSON字符串
    
    Returns:
        dict: 解析结果
    """
    try:
        # 清理字符串
        json_str = json_str.strip()
        
        # 尝试提取JSON部分
        import re
        json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            return json.loads(json_str)
        else:
            return json.loads(json_str)
    
    except Exception as e:
        print(f"⚠️ JSON解析失败: {e}")
        return None
