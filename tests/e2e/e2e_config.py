#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:8000")
TEST_CLIENT_ID: str = os.environ.get("TEST_CLIENT_ID", "test-hotel-e2e")
TEST_PASSWORD: str = os.environ.get("TEST_PASSWORD", "TestPass@2025!")
