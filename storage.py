import json

from constants import (
    STORAGE_KEY,
    CATEGORIES_KEY,
    FLOORPLAN_KEY,
    DEFAULT_CATEGORIES,
)

_js_window = None
try:
    from js import window as _js_window
except Exception:
    pass


def _ls_get(key):
    if _js_window is not None:
        try:
            return _js_window.localStorage.getItem(key)
        except Exception:
            pass
    return None


def _ls_set(key, val):
    if _js_window is not None:
        try:
            _js_window.localStorage.setItem(key, val)
            return True
        except Exception:
            pass
    return False


def load_categories():
    raw = _ls_get(CATEGORIES_KEY)
    if raw:
        try:
            cats = json.loads(raw)
            if isinstance(cats, list) and len(cats) > 0:
                return cats
        except Exception:
            pass
    return DEFAULT_CATEGORIES[:]


def save_categories(cats):
    _ls_set(CATEGORIES_KEY, json.dumps(cats, ensure_ascii=False))


def load_floorplan():
    raw = _ls_get(FLOORPLAN_KEY)
    if raw:
        try:
            fp = json.loads(raw)
            if isinstance(fp, dict) and "rows" in fp and "cols" in fp:
                return fp
        except Exception:
            pass
    return {"name": "マイ間取り", "rows": 3, "cols": 3, "cell_size": 80, "cells": []}


def save_floorplan(fp):
    _ls_set(FLOORPLAN_KEY, json.dumps(fp, ensure_ascii=False))


def migrate_floorplan_cells(cells):
    changed = False
    for cell in cells:
        if "spots" in cell and "furniture" not in cell:
            old = cell.pop("spots", "")
            cell["furniture"] = [{"name": "その他", "spots": [s.strip() for s in old.split(",") if s.strip()]}] if old.strip() else []
            changed = True
        cell.setdefault("furniture", [])
    return changed


def load_records(page):
    raw = _ls_get(STORAGE_KEY)
    if raw is not None:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    try:
        raw = page.client_storage.get(STORAGE_KEY)
        if raw and isinstance(raw, list):
            return raw
    except Exception:
        pass
    return []


def save_records(page, records):
    raw = json.dumps(records, ensure_ascii=False)
    if _ls_set(STORAGE_KEY, raw):
        return True
    try:
        page.client_storage.set(STORAGE_KEY, records)
        return True
    except Exception:
        return False
