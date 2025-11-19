"""
Headache Trade - 加密货币自动交易系统
"""
from setuptools import setup, find_packages
from pathlib import Path

# 读取README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# 读取依赖
requirements = (this_directory / "requirements.txt").read_text(encoding='utf-8').splitlines()

setup(
    name="headache-trade",
    version="2.0.0",
    author="Headache Trade Team",
    author_email="",
    description="多策略AI驱动的加密货币自动交易系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/WilliamsMiao/Headache_trade",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'headache-backtest=scripts.backtest_cli:main',
            'headache-trade=headache_trade.live.bot:main',
        ],
    },
    include_package_data=True,
    package_data={
        'headache_trade': ['web/templates/*.html'],
    },
)
