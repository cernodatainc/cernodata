import os
import unittest

class TestSearch(unittest.TestCase):
    def test_search_terms(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        src_dir = os.path.join(repo_root, "src")
        
        print("\n--- SEARCH RESULTS ---")
        for root, dirs, files in os.walk(src_dir):
            if "__pycache__" in root or ".git" in root:
                continue
            for file in files:
                if file.endswith((".py", ".js", ".html", ".css", ".json")):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, repo_root)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            for lno, line in enumerate(f, 1):
                                line_lower = line.lower()
                                if any(w in line_lower for w in ["retry", "rerun", "redoing"]):
                                    print(f"MATCH (retry) {rel_path}:{lno}: {line.strip()[:100]}")
                    except Exception:
                        pass
        print("--- END SEARCH ---")
