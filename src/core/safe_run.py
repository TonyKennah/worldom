# src/core/safe_run.py
from __future__ import annotations

"""
Safe launcher for WorldDom.

- Avoids hard (bare) references like `src/utils/asset_manifest.py` that break linting.
- Supports a headless mode useful for CI by setting SDL dummy drivers.
- Tries multiple entry points in `src.core.game`:
    1) a top-level main() function, or
    2) a Game class with a run() method.
- Optionally dumps an asset manifest if `src.utils.asset_manifest` provides a
  `build_manifest()` function or a `get_manifest()` function.

This module is designed to be CI-friendly and to fail gracefully with clear logs.
"""

import argparse
import json
import os
import sys
import traceback
import importlib
from typing import Any, Optional


def _safe_import(module_name: str) -> Optional[Any]:
    """Import a module by name and return it, or None on failure (with a log)."""
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        print(f"[safe_run] Could not import '{module_name}': {exc}")
        return None


def _enable_headless_if_requested(headless: bool) -> None:
    """Set SDL to dummy drivers so Pygame can initialize without a display/audio device."""
    if not headless:
        return
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    print("[safe_run] Headless mode enabled (SDL dummy video/audio drivers).")


def _run_game_entrypoint() -> int:
    """
    Attempt to run the game via known entry points:
      1) src.core.game.main()
      2) src.core.game.Game().run()
    Returns an integer exit code.
    """
    game_mod = _safe_import("src.core.game")
    if game_mod is None:
        print("[safe_run] ERROR: Could not import 'src.core.game'.")
        return 2

    # 1) Prefer a top-level `main()` if present.
    maybe_main = getattr(game_mod, "main", None)
    if callable(maybe_main):
        print("[safe_run] Launching via src.core.game.main()")
        try:
            result = maybe_main()
            return int(result or 0)
        except SystemExit as exc:
            return int(exc.code or 0)
        except Exception:
            traceback.print_exc()
            return 3

    # 2) Fallback: Game().run() if present.
    game_cls = getattr(game_mod, "Game", None)
    if game_cls is not None:
        try:
            game = game_cls()  # type: ignore[call-arg]
            run_fn = getattr(game, "run", None)
            if callable(run_fn):
                print("[safe_run] Launching via src.core.game.Game().run()")
                run_fn()
                return 0
            print("[safe_run] ERROR: Game class found but has no run() method.")
            return 4
        except Exception:
            traceback.print_exc()
            return 5

    print(
        "[safe_run] ERROR: No valid entry point in 'src.core.game'. "
        "Expected a main() function or a Game class with run()."
    )
    return 6


def _dump_asset_manifest(outfile: str) -> int:
    """
    Try to obtain an asset manifest from `src.utils.asset_manifest` if it exposes
    either `build_manifest()` or `get_manifest()`. Writes JSON to `outfile`.
    Returns 0 on success, non-zero otherwise.
    """
    mod = _safe_import("src.utils.asset_manifest")
    if mod is None:
        print(
            "[safe_run] WARNING: 'src.utils.asset_manifest' not found. "
            "Skipping manifest dump."
        )
        return 1

    candidates = ("build_manifest", "get_manifest")
    func = None
    for name in candidates:
        maybe = getattr(mod, name, None)
        if callable(maybe):
            func = maybe
            break

    if func is None:
        print(
            "[safe_run] WARNING: asset manifest module found, but neither "
            "`build_manifest()` nor `get_manifest()` exists. Skipping."
        )
        return 1

    try:
        data = func()  # type: ignore[misc]
    except Exception:
        print("[safe_run] ERROR: Exception while building asset manifest:")
        traceback.print_exc()
        return 2

    try:
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[safe_run] Asset manifest written to '{outfile}'.")
        return 0
    except Exception:
        print(f"[safe_run] ERROR: Could not write manifest to '{outfile}'.")
        traceback.print_exc()
        return 3


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Safe launcher for WorldDom with CI-friendly options."
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use SDL dummy drivers for video and audio (no actual window).",
    )
    parser.add_argument(
        "--dump-asset-manifest",
        metavar="FILE",
        help=(
            "If provided, attempts to import 'src.utils.asset_manifest' and write "
            "a JSON manifest to FILE."
        ),
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="If set, do not launch the game (useful when only dumping manifest).",
    )

    args = parser.parse_args(argv)

    _enable_headless_if_requested(args.headless)

    exit_code = 0
    if args.dump_asset_manifest:
        exit_code = _dump_asset_manifest(args.dump_asset_manifest)

    if not args.no_run:
        # Even if manifest dumping failed, still try to run unless '--no-run'.
        game_code = _run_game_entrypoint()
        # Propagate the worst (non-zero) code if either step failed.
        exit_code = exit_code or game_code

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
