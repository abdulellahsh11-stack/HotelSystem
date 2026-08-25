#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/syntax_check.py — فحص Syntax لكل ملفات Python
الاستخدام: python scripts/syntax_check.py
"""
import ast
import os
import sys


def check_all(root_dir: str = ".") -> bool:
    """يفحص كل ملفات .py ويُعيد True إذا كانت كلها سليمة"""
    all_files = []
    all_ok = True
    errors = []

    for root, dirs, files in os.walk(root_dir):
        # تجاهل المجلدات غير المهمة
        dirs[:] = [
            d for d in dirs
            if d not in {"__pycache__", ".git", "venv", "env", "node_modules", ".venv"}
        ]
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            all_files.append(path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    source = f.read()
                ast.parse(source)
                lines = len(source.splitlines())
                print(f"  ✅ {path} ({lines} سطر)")
            except SyntaxError as e:
                print(f"  ❌ {path} — سطر {e.lineno}: {e.msg}")
                errors.append({"file": path, "line": e.lineno, "msg": e.msg})
                all_ok = False
            except Exception as e:
                print(f"  ⚠️  {path} — {type(e).__name__}: {e}")
                all_ok = False

    print()
    print("=" * 60)
    print(f"  📊 إجمالي الملفات: {len(all_files)}")
    if all_ok:
        print("  ✅ كل الملفات سليمة — جاهز للـ Deploy على Railway")
    else:
        print(f"  ❌ {len(errors)} ملف فيه أخطاء — لا ترفع على Railway")
        for err in errors:
            print(f"     → {err['file']} سطر {err['line']}: {err['msg']}")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print(f"🔍 فحص Syntax — المجلد: {os.path.abspath(root)}")
    print()
    ok = check_all(root)
    sys.exit(0 if ok else 1)
