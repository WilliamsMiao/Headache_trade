#!/usr/bin/env python
"""
配置系统测试脚本
测试YAML配置加载器和配置迁移功能
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from headache_trade.utils.config_loader import ConfigLoader, load_config, get_config


def test_yaml_loading():
    """测试YAML配置加载"""
    print("="*70)
    print("测试1: YAML配置加载")
    print("="*70)
    
    config_path = Path("config/config.yaml")
    
    if not config_path.exists():
        print(f"[FAIL] 配置文件不存在: {config_path}")
        return False
    
    try:
        config = load_config(config_path)
        print(f"[OK] YAML配置加载成功")
        print(f"   配置节数量: {len(config)}")
        print(f"   主要配置节: {', '.join(config.keys())}")
        return True
    except Exception as e:
        print(f"[FAIL] YAML配置加载失败: {e}")
        return False


def test_env_var_replacement():
    """测试环境变量替换"""
    print("\n" + "="*70)
    print("测试2: 环境变量替换")
    print("="*70)
    
    # 设置测试环境变量
    os.environ['TEST_API_KEY'] = 'test_key_12345'
    
    # 创建测试配置
    test_config_path = Path("config/config_test_env.yaml")
    test_config_content = """
test:
  api_key: ${TEST_API_KEY}
  api_secret: ${TEST_API_SECRET:default_secret}
  missing: ${MISSING_VAR}
"""
    
    test_config_path.write_text(test_config_content, encoding='utf-8')
    
    try:
        loader = ConfigLoader()
        config = loader.load(test_config_path)
        
        api_key = config['test']['api_key']
        api_secret = config['test']['api_secret']
        missing = config['test']['missing']
        
        print(f"[OK] 环境变量替换测试:")
        print(f"   api_key = {api_key} (预期: test_key_12345)")
        print(f"   api_secret = {api_secret} (预期: default_secret)")
        print(f"   missing = {missing} (预期: ${{MISSING_VAR}})")
        
        # 清理
        test_config_path.unlink()
        
        success = (api_key == 'test_key_12345' and 
                  api_secret == 'default_secret')
        
        return success
    except Exception as e:
        print(f"[FAIL] 环境变量替换失败: {e}")
        test_config_path.unlink(missing_ok=True)
        return False


def test_config_inheritance():
    """测试配置继承"""
    print("\n" + "="*70)
    print("测试3: 配置继承")
    print("="*70)
    
    config_path = Path("config/config.yaml")
    test_config_path = Path("config/config.test.yaml")
    
    if not config_path.exists() or not test_config_path.exists():
        print(f"[FAIL] 配置文件不存在")
        return False
    
    try:
        # 加载基础配置
        base_loader = ConfigLoader()
        base_config = base_loader.load(config_path)
        
        # 加载测试配置(继承基础配置)
        test_loader = ConfigLoader()
        test_config = test_loader.load(test_config_path, base_config=base_config)
        
        print(f"[OK] 配置继承测试:")
        print(f"   基础配置 - testnet: {base_config.get('exchange', {}).get('testnet')}")
        print(f"   测试配置 - testnet: {test_config.get('exchange', {}).get('testnet')}")
        print(f"   测试配置 - symbol: {test_config.get('trading', {}).get('symbol')}")
        
        # 验证继承和覆盖
        success = (base_config['exchange']['testnet'] == False and
                  test_config['exchange']['testnet'] == True and
                  test_config['trading']['symbol'] == base_config['trading']['symbol'])
        
        return success
    except Exception as e:
        print(f"[FAIL] 配置继承失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_nested_config():
    """测试嵌套配置获取"""
    print("\n" + "="*70)
    print("测试4: 嵌套配置获取")
    print("="*70)
    
    config_path = Path("config/config.yaml")
    
    try:
        config = load_config(config_path)
        loader = ConfigLoader()
        loader.config = config
        
        # 测试点号路径访问
        symbol = loader.get('trading.symbol')
        testnet = loader.get('exchange.testnet')
        log_level = loader.get('logging.level')
        missing = loader.get('non.existent.path', 'default_value')
        
        print(f"[OK] 嵌套配置获取:")
        print(f"   trading.symbol = {symbol}")
        print(f"   exchange.testnet = {testnet}")
        print(f"   logging.level = {log_level}")
        print(f"   non.existent.path = {missing} (使用默认值)")
        
        success = (symbol is not None and 
                  testnet is not None and 
                  missing == 'default_value')
        
        return success
    except Exception as e:
        print(f"[FAIL] 嵌套配置获取失败: {e}")
        return False


def test_json_compatibility():
    """测试JSON格式兼容性"""
    print("\n" + "="*70)
    print("测试5: JSON格式兼容性")
    print("="*70)
    
    json_config_path = Path("config/trading_config.json")
    
    if not json_config_path.exists():
        print(f"[WARN] JSON配置文件不存在，跳过测试")
        return True
    
    try:
        config = load_config(json_config_path)
        print(f"[OK] JSON配置加载成功")
        print(f"   配置节数量: {len(config)}")
        print(f"   主要配置节: {', '.join(config.keys())}")
        return True
    except Exception as e:
        print(f"[FAIL] JSON配置加载失败: {e}")
        return False


def test_config_migration():
    """测试配置迁移"""
    print("\n" + "="*70)
    print("测试6: 配置迁移")
    print("="*70)
    
    json_config = Path("config/config_example.json")
    
    if not json_config.exists():
        print(f"[WARN] 示例配置文件不存在，跳过测试")
        return True
    
    try:
        # 运行迁移脚本
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/migrate_config.py", 
             str(json_config), "-o", "config/config_migrated.yaml"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"[OK] 配置迁移成功")
            print(result.stdout)
            
            # 验证迁移后的文件可以加载
            migrated_config = load_config("config/config_migrated.yaml")
            print(f"   迁移后配置节: {', '.join(migrated_config.keys())}")
            
            # 清理
            Path("config/config_migrated.yaml").unlink(missing_ok=True)
            return True
        else:
            print(f"[FAIL] 配置迁移失败")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"[FAIL] 配置迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("配置系统测试")
    print("="*70 + "\n")
    
    tests = [
        ("YAML配置加载", test_yaml_loading),
        ("环境变量替换", test_env_var_replacement),
        ("配置继承", test_config_inheritance),
        ("嵌套配置获取", test_get_nested_config),
        ("JSON兼容性", test_json_compatibility),
        ("配置迁移", test_config_migration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[FAIL] 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*70)
    print("测试总结")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "[OK] 通过" if success else "[FAIL] 失败"
        print(f"   {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过!")
        return 0
    else:
        print(f"\n[WARN] {total - passed} 个测试失败")
        return 1


if __name__ == '__main__':
    exit(main())
