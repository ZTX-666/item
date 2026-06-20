"""
从本机测试能否连接「公司 MySQL」（你 → 公司）。

不读取 wacli 数据，仅测网络与账号。

环境变量:
  MYSQL_TEST_HOST  必填
  MYSQL_TEST_PORT  默认 3306
  MYSQL_TEST_USER  必填
  MYSQL_TEST_PASS  必填
  MYSQL_TEST_DB    可选，不填则只测登录

  python test_company_mysql.py
"""

from __future__ import annotations

import os
import socket
import sys


def main() -> int:
    host = os.environ.get("MYSQL_TEST_HOST", "").strip()
    port = int(os.environ.get("MYSQL_TEST_PORT", "3306"))
    user = os.environ.get("MYSQL_TEST_USER", "").strip()
    password = os.environ.get("MYSQL_TEST_PASS", "")
    database = os.environ.get("MYSQL_TEST_DB", "").strip()

    if not host or not user:
        print("FAIL: set MYSQL_TEST_HOST and MYSQL_TEST_USER (and MYSQL_TEST_PASS)")
        return 1

    print(f"--- TCP {host}:{port} ---")
    try:
        with socket.create_connection((host, port), timeout=10):
            print("OK: TCP connect succeeded")
    except OSError as e:
        print(f"FAIL: TCP — {e}")
        print("     Check VPN, firewall, or ask IT for correct host/port.")
        return 2

    try:
        import pymysql
    except ImportError:
        print("WARN: pymysql not installed. Run: pip install pymysql")
        print("      TCP OK — MySQL login not tested.")
        return 0

    print(f"--- MySQL login as {user} ---")
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database or None,
            connect_timeout=15,
            read_timeout=15,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            ver = cur.fetchone()[0]
            print(f"OK: MySQL version {ver}")
            if database:
                cur.execute("SELECT DATABASE()")
                print(f"OK: current database {cur.fetchone()[0]}")
        conn.close()
        print("")
        print("结论: 你本机可以连公司 MySQL。")
        print("      HiAgent 应用同一 host 做「连接测试」也应使用此地址（非 127.0.0.1）。")
        print("      下一步: 把 wacli 数据同步到该公司库，而不是暴露本机 SQLite。")
        return 0
    except Exception as e:
        print(f"FAIL: MySQL — {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
