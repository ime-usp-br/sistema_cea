"""Smoke tests de acessibilidade e responsividade (TS-NFR-001/002)."""

from __future__ import annotations

import re

from helpers import BASE_URL
from playwright.sync_api import Page, expect


# Cobre: TS-NFR-001
def test_E2E_NFR_001_login_tem_landmarks_rotulos_e_foco(page: Page) -> None:
    page.goto(f"{BASE_URL}/auth/login/")
    expect(page.locator("html")).to_have_attribute("lang", re.compile(r"pt"))
    expect(page.locator("main")).to_be_visible()
    expect(page.locator("h1, h2").first).to_be_visible()
    assert page.locator("form label").count() >= 2
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement && document.activeElement.tagName")
    assert focused in {"A", "BUTTON", "INPUT", "SELECT", "TEXTAREA"}


# Cobre: TS-NFR-002
def test_E2E_NFR_002_login_utilizavel_em_viewport_movel(page: Page) -> None:
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(f"{BASE_URL}/auth/login/")
    expect(page.locator("form")).to_be_visible()
    metrics = page.evaluate(
        "({scroll: document.documentElement.scrollWidth, width: window.innerWidth})"
    )
    assert metrics["scroll"] <= metrics["width"] + 1
