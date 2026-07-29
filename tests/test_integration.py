"""
MCP Tools Smoke Test
====================
Exercises all five MCP tool functions directly (no FastAPI, no MCP server process).

Run from the project root:
    python tests/test_integration.py
"""

import json
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so tool imports resolve correctly
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Change CWD to project root so relative paths inside tools (data/progress/) work
os.chdir(PROJECT_ROOT)

from mcp_server.tools.fetch_url import fetch_url_content          # noqa: E402
from mcp_server.tools.quiz_tools import generate_quiz              # noqa: E402
from mcp_server.tools.progress_tools import save_progress, get_progress  # noqa: E402


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_test(label: str, fn) -> bool:
    """Execute fn(), print PASS/FAIL, return True on success."""
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except AssertionError as exc:
        print(f"  FAIL  {label}")
        print(f"        AssertionError: {exc}")
        return False
    except Exception as exc:
        print(f"  FAIL  {label}")
        print(f"        {type(exc).__name__}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_fetch_url_content() -> None:
    result = fetch_url_content("https://en.wikipedia.org/wiki/Machine_learning")
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}"
    assert len(result) > 0, "Result string is empty"
    assert not result.startswith("Error:"), f"Tool returned an error: {result[:120]}"
    assert "machine learning" in result.lower() or "learning" in result.lower(), \
        "Expected page content not found in result"


def test_generate_quiz() -> None:
    result = generate_quiz(
        "Machine learning is a subset of AI that enables systems to learn from data.",
        3,
        ["multiple_choice"],
    )
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}"

    data = json.loads(result)  # raises json.JSONDecodeError if not valid JSON

    assert "quiz_id" in data,        "Missing 'quiz_id' in quiz dict"
    assert "created_at" in data,     "Missing 'created_at' in quiz dict"
    assert data["num_questions"] == 3, \
        f"Expected num_questions=3, got {data['num_questions']}"
    assert data["question_types"] == ["multiple_choice"], \
        f"Unexpected question_types: {data['question_types']}"
    assert data["status"] == "template", \
        f"Expected status='template', got {data['status']!r}"
    assert isinstance(data["questions"], list), \
        "'questions' should be an empty list"


def test_save_progress() -> None:
    result = save_progress(
        "test_user",
        "quiz_taken",
        {"score": 80, "topic": "ML"},
    )
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}"
    assert not result.startswith("Error:"), f"Tool returned an error: {result}"
    # Confirmation message should name the user and activity
    assert "test_user" in result, f"Expected 'test_user' in result: {result}"
    assert "quiz_taken" in result, f"Expected 'quiz_taken' in result: {result}"


def test_get_progress() -> None:
    result = get_progress("test_user")
    assert isinstance(result, str), f"Expected str, got {type(result).__name__}"
    assert not result.startswith("Error:"),  f"Tool returned an error: {result}"
    assert not result.startswith("No progress"), "No progress found — run test_save_progress first"

    history = json.loads(result)  # raises if not valid JSON
    assert isinstance(history, list), f"Expected list, got {type(history).__name__}"
    assert len(history) > 0, "Progress history is empty"

    # Verify the entry saved in test_save_progress is present
    found = any(
        entry.get("activity_type") == "quiz_taken"
        and entry.get("data", {}).get("topic") == "ML"
        and entry.get("data", {}).get("score") == 80
        for entry in history
    )
    assert found, (
        "Could not find the quiz_taken/ML/80 entry saved by test_save_progress. "
        f"History keys present: {[e.get('activity_type') for e in history]}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n" + "=" * 52)
    print("  MCP Tools Smoke Test")
    print("=" * 52 + "\n")

    suite = [
        ("fetch_url_content  — Wikipedia ML page",     test_fetch_url_content),
        ("generate_quiz      — 3 multiple-choice Qs",  test_generate_quiz),
        ("save_progress      — quiz_taken, score=80",  test_save_progress),
        ("get_progress       — verify saved entry",    test_get_progress),
    ]

    results = [run_test(label, fn) for label, fn in suite]

    passed = sum(results)
    total  = len(results)

    print(f"\n{'=' * 52}")
    print(f"  {passed}/{total} tests passed")
    print("=" * 52 + "\n")

    sys.exit(0 if passed == total else 1)
