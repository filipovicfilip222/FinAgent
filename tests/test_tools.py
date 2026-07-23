"""Unit tests for the four tools + the registry.

These run fully offline: calculator is pure, SEC reads committed fixtures
(SEC_EDGAR_MODE=cache), web search is stubbed, and RAG chunking is pure.
"""

import pytest

from finagent.rag.store import chunk_text
from finagent.tools import run_tool
from finagent.tools.calculator import CalculatorError, calculate, evaluate


# --------------------------------------------------------------------------- #
# calculator
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "expr,expected",
    [
        ("2 + 3 * 4", 14),
        ("(120000 - 100000) / 100000 * 100", 20.0),
        ("2 ** 10", 1024),
        ("-5 + 2", -3),
        ("10 % 3", 1),
        ("7 // 2", 3),
        ("416161 / 112010 * 100", pytest.approx(371.54, abs=0.1)),
    ],
)
def test_calculator_arithmetic(expr, expected):
    assert evaluate(expr) == expected


def test_calculator_echoes_expression():
    assert calculate({"expression": "(120000 - 100000) / 100000 * 100"}) == \
        "(120000 - 100000) / 100000 * 100 = 20"


@pytest.mark.parametrize(
    "bad",
    [
        "__import__('os').system('ls')",  # code execution attempt
        "os.getcwd()",                     # attribute/name
        "print(1)",                        # function call
        "a + 1",                           # bare name
        "[i for i in range(3)]",           # comprehension
        "1 if True else 2",                # ternary
        "lambda: 1",                       # lambda
    ],
)
def test_calculator_rejects_non_arithmetic(bad):
    with pytest.raises(CalculatorError):
        evaluate(bad)


def test_calculator_division_by_zero_and_limits():
    with pytest.raises(CalculatorError):
        evaluate("1 / 0")
    with pytest.raises(CalculatorError):
        evaluate("2 ** 100000")  # exponent guard
    with pytest.raises(CalculatorError):
        evaluate("")


# --------------------------------------------------------------------------- #
# sec_edgar (served from committed fixtures)
# --------------------------------------------------------------------------- #
def test_sec_edgar_apple_revenue_from_fixture():
    out = run_tool("sec_edgar", {"ticker": "AAPL", "concept": "Revenues", "n": 4})
    text, ok = out
    assert ok
    # Alias resolved to the real tag, and both a recent quarter and the FY figure show up.
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in text
    assert "416,161,000,000" in text          # FY2025 annual
    assert "143,756,000,000" in text          # most recent quarter
    assert "[source: cache]" in text


def test_sec_edgar_unknown_ticker_is_graceful():
    text, ok = run_tool("sec_edgar", {"ticker": "TSLA", "concept": "Revenues"})
    assert ok  # tool returns a message, does not raise
    assert "Unknown ticker" in text


def test_sec_edgar_net_income_alias():
    text, ok = run_tool("sec_edgar", {"ticker": "MSFT", "concept": "NetIncomeLoss", "n": 2})
    assert ok
    assert "NetIncomeLoss" in text
    assert "101,832,000,000" in text  # MSFT FY2025 net income


# --------------------------------------------------------------------------- #
# web_search (stub provider)
# --------------------------------------------------------------------------- #
def test_web_search_stub():
    text, ok = run_tool("web_search", {"query": "latest Apple earnings news"})
    assert ok
    assert "stub" in text.lower()


# --------------------------------------------------------------------------- #
# rag chunking (pure)
# --------------------------------------------------------------------------- #
def test_chunk_text_windows_and_overlap():
    words = " ".join(str(i) for i in range(1000))
    chunks = chunk_text(words, chunk_size=500, overlap=50)
    # step = 450 -> windows start at 0, 450, 900 => 3 chunks
    assert len(chunks) == 3
    assert len(chunks[0].split()) == 500
    assert chunks[-1].split()[0] == "900"  # last window starts at word 900
    # overlap: last 50 words of chunk0 equal first 50 of chunk1
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]


def test_chunk_text_empty_and_validation():
    assert chunk_text("") == []
    with pytest.raises(ValueError):
        chunk_text("a b c", chunk_size=10, overlap=10)


# --------------------------------------------------------------------------- #
# registry dispatch + graceful failure
# --------------------------------------------------------------------------- #
def test_run_tool_unknown_and_error_paths():
    text, ok = run_tool("does_not_exist", {})
    assert not ok and "not available" in text

    text, ok = run_tool("calculator", {"expression": "a + 1"})
    assert not ok  # tool raised -> registry reports ok=False
