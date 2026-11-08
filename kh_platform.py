# coding: utf-8
"""开源版的平台工具。支持 Windows 及本 fork 的 Linux 桌面源码运行。

主库的 cli/platform_utils 按操作系统和是否装有 xtquant 打开或关闭各项功能；
开源版没有这些功能，只保留回测内核需要的默认数据目录。
"""
from kh_app_identity import default_duckdb_dir

__all__ = ["default_duckdb_dir"]
