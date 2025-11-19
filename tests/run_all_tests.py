#!/usr/bin/env python
"""
测试运行器
统一运行所有测试套件
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 测试脚本列表
TEST_SCRIPTS = [
    ("单元测试", "tests/test_core_modules.py"),
    ("策略测试", "tests/test_strategies.py"),
    ("配置系统测试", "tests/test_config_system.py"),
    ("集成测试", "tests/test_integration.py"),
    ("回归测试", "tests/test_regression.py"),
]


def run_test_script(name, script_path):
    """运行单个测试脚本"""
    print("\n" + "="*70)
    print(f"运行: {name}")
    print(f"脚本: {script_path}")
    print("="*70)
    
    script_file = Path(script_path)
    
    if not script_file.exists():
        print(f"[WARN] 测试脚本不存在: {script_path}")
        return None
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_file)],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        # 打印输出
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        success = result.returncode == 0
        
        if success:
            print(f"\n[OK] {name} 通过")
        else:
            print(f"\n[FAIL] {name} 失败 (返回码: {result.returncode})")
        
        return success
    except subprocess.TimeoutExpired:
        print(f"\n[FAIL] {name} 超时")
        return False
    except Exception as e:
        print(f"\n[FAIL] {name} 执行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    start_time = datetime.now()
    
    print("="*70)
    print("Headache Trade 测试套件")
    print("="*70)
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    results = []
    
    for name, script_path in TEST_SCRIPTS:
        result = run_test_script(name, script_path)
        results.append((name, result))
    
    # 总结
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    total = len(results)
    
    for name, result in results:
        if result is True:
            status = "[OK] 通过"
        elif result is False:
            status = "[FAIL] 失败"
        else:
            status = "[WARN] 跳过"
        print(f"   {status} - {name}")
    
    print("\n" + "-"*70)
    print(f"总计: {total} 个测试套件")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"跳过: {skipped}")
    print(f"用时: {duration:.2f}秒")
    print("-"*70)
    
    if failed == 0:
        print("\n[SUCCESS] 所有测试通过!")
        print("[OK] 系统功能验证完成")
        return 0
    else:
        print(f"\n[WARN] {failed} 个测试套件失败")
        print("[FAIL] 需要修复失败的测试")
        return 1


if __name__ == '__main__':
    exit(main())
