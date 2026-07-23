# FinAgent — Evaluation Report

- **Run at:** 2026-07-23 14:34 UTC
- **LLM provider:** `mock`
- **Questions:** 22  ·  **Errors:** 0

## Summary

| Metric | Value |
|---|---|
| Tool-selection accuracy (exact set) | 31.8% |
| Tool-selection mean Jaccard | 0.545 |
| Numerical accuracy (within tolerance) | 0.0% (n=14) |
| Answer-content checks passed | 70.0% (n=10) |
| Avg planner iterations | 0.23 |
| Avg tool calls / question | 1.23 |
| **Reflection trigger rate** | **22.7%** |
| Reflection recall on questions designed to need it | 100.0% (n=5) |
| Avg latency / question | 0.03s |
| Confidence distribution | {"high": 22} |

## Per-question results

| id | diff | tools used | exp tools | tool | num | txt | refl(exp) | steps | conf | lat |
|---|---|---|---|:--:|:--:|:--:|:--:|:--:|:--:|--:|
| q01_single_aapl_rev | easy | sec_edgar | sec_edgar | ✓ | ✗ | ✓ | ✗(n) | 1 | high | 0.05s |
| q02_single_msft_ni | easy | sec_edgar | sec_edgar | ✓ | ✗ | ✓ | ✗(n) | 1 | high | 0.04s |
| q03_single_aapl_q_rev | easy | sec_edgar | sec_edgar | ✓ | ✗ | – | ✗(n) | 1 | high | 0.04s |
| q04_calc_aapl_rev_growth | medium | sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✗(n) | 1 | high | 0.04s |
| q05_calc_aapl_net_margin | medium | sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✗(n) | 1 | high | 0.03s |
| q06_calc_msft_net_margin | medium | sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✗(n) | 1 | high | 0.03s |
| q07_compare_net_margin | hard | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | – | ✓ | ✓(y) | 2 | high | 0.05s |
| q08_compare_rev_diff | hard | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✗ | ✓ | ✓(y) | 2 | high | 0.04s |
| q09_calc_aapl_q1_yoy | medium | sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✗(n) | 1 | high | 0.03s |
| q10_rag_aapl_supply | medium | sec_edgar | rag_retrieve | ✗ | – | ✗ | ✗(n) | 1 | high | 0.03s |
| q11_rag_msft_cloud | medium | sec_edgar | rag_retrieve | ✗ | – | ✗ | ✗(n) | 1 | high | 0.03s |
| q12_rag_msft_segment | medium | sec_edgar | rag_retrieve | ✗ | – | ✗ | ✗(n) | 1 | high | 0.03s |
| q13_web_aapl_ai_news | medium | sec_edgar | web_search | ✗ | – | – | ✗(n) | 1 | high | 0.02s |
| q14_single_aapl_ni | easy | sec_edgar | sec_edgar | ✓ | ✗ | – | ✗(n) | 1 | high | 0.02s |
| q15_single_msft_rev | easy | sec_edgar | sec_edgar | ✓ | ✗ | – | ✗(n) | 1 | high | 0.03s |
| q16_calc_msft_rev_growth | medium | sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✗(n) | 1 | high | 0.02s |
| q17_compare_rev | hard | sec_edgar,sec_edgar | sec_edgar | ✓ | – | ✓ | ✓(y) | 2 | high | 0.03s |
| q18_ambiguous_profitable | hard | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | – | ✓ | ✓(y) | 2 | high | 0.03s |
| q19_calc_combined_ni | hard | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✓(y) | 2 | high | 0.03s |
| q20_single_msft_q_rev | easy | sec_edgar | sec_edgar | ✓ | ✗ | – | ✗(n) | 1 | high | 0.02s |
| q21_calc_aapl_ni_growth | medium | sec_edgar | sec_edgar,calculator | ✗ | ✗ | – | ✗(n) | 1 | high | 0.02s |
| q22_rag_msft_ai_risk | medium | sec_edgar | rag_retrieve | ✗ | – | ✓ | ✗(n) | 1 | high | 0.03s |

## Reflection loop — evidence it actually fired

- **q07_compare_net_margin** (1 iteration(s)): How did Apple's net profit margin in FY2025 compare with Microsoft's? Which was higher?
    - reflect → *insufficient*: Comparison requested but no data yet for MSFT.
- **q08_compare_rev_diff** (1 iteration(s)): Which company had higher total revenue in FY2025, Apple or Microsoft, and by how much (in dollars)?
    - reflect → *insufficient*: Comparison requested but no data yet for MSFT.
- **q17_compare_rev** (1 iteration(s)): Compare Apple's and Microsoft's most recent annual revenue.
    - reflect → *insufficient*: Comparison requested but no data yet for MSFT.
- **q18_ambiguous_profitable** (1 iteration(s)): Is Apple or Microsoft more profitable, and by how much?
    - reflect → *insufficient*: Comparison requested but no data yet for MSFT.
- **q19_calc_combined_ni** (1 iteration(s)): What was the combined FY2025 net income of Apple and Microsoft together?
    - reflect → *insufficient*: Comparison requested but no data yet for MSFT.

## Example answer (full)

**Q (q07_compare_net_margin):** How did Apple's net profit margin in FY2025 compare with Microsoft's? Which was higher?

```json
{
  "answer": "[mock] Answer to: \"How did Apple's net profit margin in FY2025 compare with Microsoft's? Which was higher?\". Used tools: sec_edgar, sec_edgar.",
  "key_numbers": {},
  "confidence": "high",
  "tools_used": [
    "sec_edgar",
    "sec_edgar"
  ]
}
```
