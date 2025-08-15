# c:/game/worldom/map_io.py
"""
Simple (de)serialization helpers for Map (seed + grid).
"""
from __future__ import annotations
import json
from typing import Any, Dict, List
import pygame

from worldom.map import Map  # adjust import if your package structure differs

def save_map(map_obj: Map, path: str) -> None:
    data: Dict[str, Any] = {
        "width": map_obj.width,
        "height": map_obj.height,
        "seed": map_obj.seed,
        "tiles": map_obj.data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def load_map(path: str) -> Map:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    m = Map(int(payload["width"]), int(payload["height"]), int(payload["seed"]))
    m.data = [[str(t) for t in row] for row in payload["tiles"]]  # normalize/validate strings
    m._create_lod_surface()
    return m
