#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易仪表板测试脚本
用于验证仪表板功能是否正常
"""

import requests
import time
import json
from datetime import datetime

def test_dashboard():
    """测试仪表板各个接口"""
    base_url = "http://localhost:5000"
    
    print("🧪 开始测试交易仪表板...")
    print("=" * 50)
    
    # 测试接口列表
    endpoints = [
        ("/", "主页面"),
        ("/api/dashboard", "仪表板数据"),
        ("/api/models", "模型数据"),
        ("/api/crypto-prices", "加密货币价格"),
        ("/api/positions", "持仓信息"),
        ("/api/trades", "交易历史"),
        ("/api/signals", "交易信号"),
        ("/api/technical-analysis", "技术分析")
    ]
    
    results = []
    
    for endpoint, description in endpoints:
        try:
            print(f"🔍 测试 {description} ({endpoint})...")
            
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                if endpoint == "/":
                    print(f"✅ {description}: 页面加载成功")
                else:
                    data = response.json()
                    print(f"✅ {description}: 数据获取成功")
                    if isinstance(data, dict) and 'error' in data:
                        print(f"⚠️  警告: {data['error']}")
                results.append((endpoint, True, "成功"))
            else:
                print(f"❌ {description}: HTTP {response.status_code}")
                results.append((endpoint, False, f"HTTP {response.status_code}"))
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {description}: 连接失败 - 请确保仪表板正在运行")
            results.append((endpoint, False, "连接失败"))
        except requests.exceptions.Timeout:
            print(f"❌ {description}: 请求超时")
            results.append((endpoint, False, "请求超时"))
        except Exception as e:
            print(f"❌ {description}: 错误 - {str(e)}")
            results.append((endpoint, False, str(e)))
        
        time.sleep(0.5)  # 避免请求过快
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    
    success_count = 0
    for endpoint, success, message in results:
        status = "✅" if success else "❌"
        print(f"{status} {endpoint}: {message}")
        if success:
            success_count += 1
    
    print(f"\n🎯 测试完成: {success_count}/{len(results)} 个接口正常")
    
    if success_count == len(results):
        print("🎉 所有测试通过！仪表板运行正常")
    elif success_count > len(results) // 2:
        print("⚠️  大部分功能正常，请检查失败的接口")
    else:
        print("❌ 多个接口异常，请检查仪表板配置")
    
    return success_count == len(results)

def test_data_format():
    """测试数据格式"""
    print("\n🔍 测试数据格式...")
    
    try:
        response = requests.get("http://localhost:5000/api/dashboard", timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # 检查必要字段
            required_fields = ['models', 'crypto_prices', 'performance_history']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"❌ 缺少必要字段: {missing_fields}")
                return False
            
            # 检查模型数据
            if 'DeepSeek Chat V3.1' in data['models']:
                model = data['models']['DeepSeek Chat V3.1']
                model_fields = ['name', 'icon', 'account_value', 'change_percent']
                missing_model_fields = [field for field in model_fields if field not in model]
                
                if missing_model_fields:
                    print(f"❌ 模型数据缺少字段: {missing_model_fields}")
                    return False
            
            print("✅ 数据格式验证通过")
            return True
        else:
            print(f"❌ 无法获取数据: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 数据格式测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 交易仪表板测试工具")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 等待用户确认
    input("请确保仪表板正在运行 (http://localhost:5000)，然后按 Enter 继续...")
    
    # 执行测试
    api_test_passed = test_dashboard()
    format_test_passed = test_data_format()
    
    print("\n" + "=" * 50)
    if api_test_passed and format_test_passed:
        print("🎉 所有测试通过！您的交易仪表板运行完美！")
        print("🌐 访问地址: http://localhost:5000")
    else:
        print("⚠️  部分测试失败，请检查配置和日志")
        print("💡 提示: 确保交易服务正常运行且 API 密钥正确")
