#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具模块测试脚本
测试跨平台文件锁、线程监控、备份管理等功能
"""

import os
import sys
import time
import json
import threading
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from trading_bots.utils import (
        CrossPlatformFileLock,
        safe_read_json,
        safe_write_json,
        ThreadHealthMonitor,
        DataBackupManager,
        ExponentialBackoffRetry,
        validate_json_file
    )
    print("✅ 工具模块导入成功")
except ImportError as e:
    print(f"❌ 工具模块导入失败: {e}")
    sys.exit(1)

# 测试数据目录
TEST_DIR = Path(__file__).parent / 'test_data'
TEST_DIR.mkdir(exist_ok=True)

def test_cross_platform_file_lock():
    """测试跨平台文件锁"""
    print("\n" + "="*60)
    print("测试1: 跨平台文件锁")
    print("="*60)
    
    test_file = TEST_DIR / 'test_lock.json'
    test_data = {'test': 'data', 'value': 123}
    
    # 测试写入
    success = safe_write_json(test_file, test_data, create_backup=False)
    if success:
        print("✅ 文件写入成功")
    else:
        print("❌ 文件写入失败")
        return False
    
    # 测试读取
    read_data = safe_read_json(test_file, default=None)
    if read_data == test_data:
        print("✅ 文件读取成功")
    else:
        print(f"❌ 文件读取失败: 期望 {test_data}, 实际 {read_data}")
        return False
    
    print(f"✅ 测试通过 (操作系统: {sys.platform})")
    return True

def test_backup_manager():
    """测试备份管理器"""
    print("\n" + "="*60)
    print("测试2: 数据备份管理")
    print("="*60)
    
    # 创建测试文件
    test_file = TEST_DIR / 'test_backup.json'
    test_data = {'version': 1, 'data': [1, 2, 3]}
    safe_write_json(test_file, test_data, create_backup=False)
    
    # 创建备份管理器
    backup_mgr = DataBackupManager(TEST_DIR, max_backups=3)
    
    # 创建3个备份
    for i in range(3):
        test_data['version'] = i + 2
        safe_write_json(test_file, test_data, create_backup=False)
        backup_mgr.create_backup(test_file)
        time.sleep(0.1)  # 确保时间戳不同
    
    # 检查备份数量
    backups = list((TEST_DIR / 'backups').glob('test_backup_*.json'))
    if len(backups) == 3:
        print(f"✅ 备份创建成功 ({len(backups)}个)")
    else:
        print(f"❌ 备份数量错误: 期望3个, 实际{len(backups)}个")
        return False
    
    # 修改文件并恢复
    test_data['version'] = 999
    safe_write_json(test_file, test_data, create_backup=False)
    
    backup_mgr.restore_latest_backup(test_file)
    restored_data = safe_read_json(test_file)
    
    if restored_data['version'] == 4:  # 最后一个备份是version 4
        print(f"✅ 备份恢复成功 (版本: {restored_data['version']})")
    else:
        print(f"❌ 备份恢复失败: 期望版本4, 实际版本{restored_data.get('version')}")
        return False
    
    print("✅ 测试通过")
    return True

def test_thread_health_monitor():
    """测试线程健康监控"""
    print("\n" + "="*60)
    print("测试3: 线程健康监控")
    print("="*60)
    
    # 创建一个会崩溃的工作函数
    test_results = {'runs': 0, 'restarts': 0}
    
    def crash_worker():
        """模拟会崩溃的工作线程"""
        test_results['runs'] += 1
        if test_results['runs'] == 1:
            print("   💥 工作线程崩溃（模拟）")
            raise Exception("Simulated crash")
        else:
            print(f"   ✅ 工作线程重启成功 (第{test_results['runs']}次运行)")
            while True:
                time.sleep(1)
    
    # 创建监控器
    monitor = ThreadHealthMonitor(
        target_func=crash_worker,
        thread_name="TestWorker",
        check_interval=2,
        heartbeat_timeout=10
    )
    
    # 启动监控
    monitor.start()
    
    # 等待足够时间让线程崩溃和重启
    time.sleep(5)
    
    # 检查结果
    if test_results['runs'] >= 2:
        print(f"✅ 线程自动重启成功 (运行次数: {test_results['runs']})")
        monitor.stop()
        return True
    else:
        print(f"❌ 线程未能重启 (运行次数: {test_results['runs']})")
        monitor.stop()
        return False

def test_exponential_backoff():
    """测试指数退避重试"""
    print("\n" + "="*60)
    print("测试4: 指数退避重试")
    print("="*60)
    
    # 创建一个会失败2次后成功的函数
    test_state = {'attempts': 0}
    
    def failing_function():
        test_state['attempts'] += 1
        if test_state['attempts'] < 3:
            print(f"   ⚠️ 第{test_state['attempts']}次尝试失败")
            raise Exception("Simulated failure")
        print(f"   ✅ 第{test_state['attempts']}次尝试成功")
        return "success"
    
    # 创建重试管理器
    retry = ExponentialBackoffRetry(max_retries=5, base_delay=0.5, max_delay=5)
    
    try:
        result = retry.execute(failing_function)
        if result == "success" and test_state['attempts'] == 3:
            print(f"✅ 指数退避重试成功 (尝试次数: {test_state['attempts']})")
            return True
        else:
            print(f"❌ 重试结果异常: {result}, 尝试次数: {test_state['attempts']}")
            return False
    except Exception as e:
        print(f"❌ 重试失败: {e}")
        return False

def test_json_validation():
    """测试JSON验证"""
    print("\n" + "="*60)
    print("测试5: JSON文件验证")
    print("="*60)
    
    # 创建测试文件
    test_file = TEST_DIR / 'test_validation.json'
    test_data = {'required_key1': 'value1', 'required_key2': 'value2', 'optional': 'data'}
    safe_write_json(test_file, test_data, create_backup=False)
    
    # 验证必需字段
    is_valid, message = validate_json_file(test_file, required_keys=['required_key1', 'required_key2'])
    if is_valid:
        print(f"✅ JSON验证通过: {message}")
    else:
        print(f"❌ JSON验证失败: {message}")
        return False
    
    # 验证缺失字段
    is_valid, message = validate_json_file(test_file, required_keys=['missing_key'])
    if not is_valid and 'missing_key' in message:
        print(f"✅ 缺失字段检测正常: {message}")
    else:
        print(f"❌ 缺失字段检测异常: {message}")
        return False
    
    print("✅ 测试通过")
    return True

def cleanup_test_data():
    """清理测试数据"""
    import shutil
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
        print("\n🗑️ 测试数据已清理")

def main():
    """运行所有测试"""
    print("\n" + "🧪 工具模块测试开始 ".center(60, "="))
    print(f"操作系统: {sys.platform}")
    print(f"Python版本: {sys.version.split()[0]}")
    
    results = []
    
    # 运行测试
    results.append(("跨平台文件锁", test_cross_platform_file_lock()))
    results.append(("数据备份管理", test_backup_manager()))
    results.append(("线程健康监控", test_thread_health_monitor()))
    results.append(("指数退避重试", test_exponential_backoff()))
    results.append(("JSON文件验证", test_json_validation()))
    
    # 统计结果
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    print("="*60)
    print(f"总计: {passed}/{total} 通过")
    print("="*60)
    
    # 清理测试数据
    cleanup_test_data()
    
    if passed == total:
        print("\n🎉 所有测试通过！工具模块工作正常。")
        return 0
    else:
        print(f"\n⚠️ {total - passed}个测试失败，请检查日志。")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
