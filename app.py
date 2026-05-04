#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hotel SaaS — app.py
Entry point for Railway/Render deployment
Loads: unified_server.py + main_admin.py + main.py automatically
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_server import main

if __name__ == "__main__":
    main()
