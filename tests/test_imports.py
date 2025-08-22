*** a/tests/test_imports.py
--- b/tests/test_imports.py
@@
-import os, sys
-os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
-os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
-os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
-
-sys.path.insert(0, str((__file__).replace("tests/test_imports.py", "src")))
-import importlib, pkgutil
-
-failures = []
-for m in pkgutil.walk_packages([str((__file__).replace("tests/test_imports.py", "src"))], prefix=""):
-    name = m.name
-    try:
-        importlib.import_module(name)
-    except Exception as e:
-        failures.append((name, repr(e)))
-
-assert not failures, f"Import failures: {failures}"
+from __future__ import annotations
+import os
+import sys
+from pathlib import Path
+import importlib
+
+# --- Make pygame headless-friendly during import ---
+os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
+os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
+os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
+
+# Optional: tell sitecustomize (if present) to do nothing under tests.
+# Safe even if sitecustomize is absent.
+os.environ.setdefault("WORLD_DOM_SKIP_SITECUSTOMIZE", "1")
+
+# --- Point imports at our src layout ---
+ROOT = Path(__file__).resolve().parents[1]
+SRC = ROOT / "src"
+sys.path.insert(0, str(SRC))
+
+def _iter_module_names(base: Path) -> list[str]:
+    """
+    Find all importable modules under `base` by scanning *.py files.
+    Produces dotted names relative to `base`. __init__.py files are skipped;
+    importing submodules will import their packages as needed.
+    """
+    names: set[str] = set()
+    for py in base.rglob("*.py"):
+        if py.name == "__init__.py":
+            continue
+        rel = py.relative_to(base).with_suffix("")
+        # Build dotted module name like "core.map" or "utils.settings"
+        names.add(".".join(rel.parts))
+    # Deterministic order
+    return sorted(names)
+
+def test_import_all_modules_headless():
+    failures: list[tuple[str, str]] = []
+    for modname in _iter_module_names(SRC):
+        try:
+            importlib.import_module(modname)
+        except Exception as e:
+            failures.append((modname, f"{type(e).__name__}: {e}"))
+    if failures:
+        # Pretty print failures to help pinpoint the culprit quickly
+        lines = ["Import failures ({}):".format(len(failures))]
+        lines += [f" - {name}: {err}" for name, err in failures]
+        raise AssertionError("\n".join(lines))
