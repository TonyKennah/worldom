# tests/test_globe_smoke.py
import os
import numpy as np
from src.globe_renderer import render_map_as_globe

def test_globe_two_frames(tmp_path, monkeypatch):
    # tiny synthetic terrain (two types)
    data = [["ocean", "grass"] * 4] * 8  # 8x8
    # set output dir under tmp so CI never collides
    monkeypatch.chdir(tmp_path)
    frames = list(render_map_as_globe(data, map_seed=123))
    assert len(frames)  # progressed
    # confirm at least one PNG present
    out_dir = tmp_path / "image" / "globe_frames"
    pngs = list(out_dir.glob("*.png"))
    assert pngs, "No frames written"
