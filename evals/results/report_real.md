# FinAgent — Evaluation Report

- **Run at:** 2026-07-23 (real Anthropic run)
- **LLM provider:** `anthropic` — Claude Sonnet 5 (`claude-sonnet-5`) for 21/22 questions; `q07` ran on Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), so this is not a single-model run.
- **Questions:** 22  ·  **Errors:** 0

### Run notes

- **Errors: 0** counts crashed runs (0/22). 5/22 questions had a tool error the agent finished with low confidence: `q10`, `q11`, `q12`, `q22` (RAG) and `q18` (SEC).
- **SEC EDGAR** was served from the committed fixtures (`SEC_EDGAR_MODE=cache`): real filing numbers, reproducible offline. With `SEC_EDGAR_MODE=auto` the tool fetches from `data.sec.gov` and falls back to the fixtures.
- **RAG was not exercised in this run.** `chromadb` was not installed, so `rag_retrieve` raised `ModuleNotFoundError` on every call in the RAG questions (`q10`, `q11`, `q12`, `q22`); the agent reported low confidence instead of answering. To run them end to end: `pip install -e .[rag]`, then `python -m finagent.rag.ingest` with an embedding key.
- **Web search** returned results only in `q13`; in `q10`, `q11` and `q22` it ran as the offline stub.
- **Calculator** was never selected (0/22).
- **Tool-selection "exact"** is moderate (36.4%, 8/22) mainly because (a) on derived values the model computes inline instead of calling `calculator`, and (b) RAG questions fan out to fallback tools because retrieval failed. The first tool chosen was an expected one in 22/22 questions (mean Jaccard 0.674). See README → Known gaps.

## Summary

| Metric | Value |
|---|---|
| Tool-selection accuracy (exact set) | 36.4% |
| Tool-selection mean Jaccard | 0.674 |
| Numerical accuracy (within tolerance) | 100.0% (n=14) |
| Answer-content checks passed | 90.0% (n=10) |
| Avg planner iterations | 1.14 |
| Avg tool calls / question | 1.95 |
| **Reflection trigger rate** | **54.5%** |
| Reflection recall on questions designed to need it | 100.0% (n=5) |
| Avg latency / question | 19.31s |
| Confidence distribution | {"high": 14, "medium": 3, "low": 5} |

## Per-question results

| id | diff | tools used | exp tools | tool | num | txt | refl(exp) | steps | conf | lat |
|---|---|---|---|:--:|:--:|:--:|:--:|:--:|:--:|--:|
| q01_single_aapl_rev | easy | sec_edgar | sec_edgar | ✓ | ✓ | ✓ | ✗(n) | 1 | high | 11.18s |
| q02_single_msft_ni | easy | sec_edgar | sec_edgar | ✓ | ✓ | ✓ | ✗(n) | 1 | high | 10.52s |
| q03_single_aapl_q_rev | easy | sec_edgar | sec_edgar | ✓ | ✓ | – | ✗(n) | 1 | high | 12.19s |
| q04_calc_aapl_rev_growth | medium | sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✗(n) | 1 | high | 9.81s |
| q05_calc_aapl_net_margin | medium | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✓(n) | 2 | high | 20.43s |
| q06_calc_msft_net_margin | medium | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✓(n) | 2 | high | 17.4s |
| q07_compare_net_margin | hard | sec_edgar,sec_edgar,sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | – | ✓ | ✓(y) | 4 | high | 25.05s |
| q08_compare_rev_diff | hard | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✓ | ✓ | ✓(y) | 2 | high | 17.91s |
| q09_calc_aapl_q1_yoy | medium | sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✗(n) | 1 | medium | 10.25s |
| q10_rag_aapl_supply | medium | rag_retrieve,rag_retrieve,web_search | rag_retrieve | ✗ | – | ✗ | ✓(n) | 3 | low | 28.15s |
| q11_rag_msft_cloud | medium | rag_retrieve,sec_edgar,web_search | rag_retrieve | ✗ | – | ✓ | ✓(n) | 3 | low | 33.8s |
| q12_rag_msft_segment | medium | rag_retrieve,rag_retrieve,sec_edgar | rag_retrieve | ✗ | – | ✓ | ✓(n) | 3 | low | 28.38s |
| q13_web_aapl_ai_news | medium | web_search | web_search | ✓ | – | – | ✗(n) | 1 | medium | 37.23s |
| q14_single_aapl_ni | easy | sec_edgar | sec_edgar | ✓ | ✓ | – | ✗(n) | 1 | high | 8.42s |
| q15_single_msft_rev | easy | sec_edgar | sec_edgar | ✓ | ✓ | – | ✗(n) | 1 | high | 9.24s |
| q16_calc_msft_rev_growth | medium | sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✗(n) | 1 | high | 9.27s |
| q17_compare_rev | hard | sec_edgar,sec_edgar | sec_edgar | ✓ | – | ✓ | ✓(y) | 2 | high | 17.09s |
| q18_ambiguous_profitable | hard | sec_edgar,sec_edgar,sec_edgar,sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | – | ✓ | ✓(y) | 5 | low | 41.96s |
| q19_calc_combined_ni | hard | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✓(y) | 2 | high | 18.1s |
| q20_single_msft_q_rev | easy | sec_edgar | sec_edgar | ✓ | ✓ | – | ✗(n) | 1 | high | 10.79s |
| q21_calc_aapl_ni_growth | medium | sec_edgar,sec_edgar | sec_edgar,calculator | ✗ | ✓ | – | ✓(n) | 2 | medium | 22.7s |
| q22_rag_msft_ai_risk | medium | rag_retrieve,web_search,rag_retrieve | rag_retrieve | ✗ | – | ✓ | ✓(n) | 3 | low | 24.99s |

## Reflection loop — evidence it actually fired

- **q05_calc_aapl_net_margin** (1 iteration(s)): What was Apple's net profit margin (net income divided by revenue) in FY2025?
    - reflect → *insufficient*: Need Apple's FY2025 total revenue (e.g., Revenues or RevenueFromContractWithCustomerExcludingAssessedTax) to compute net profit margin.
- **q06_calc_msft_net_margin** (1 iteration(s)): What was Microsoft's net profit margin in FY2025?
    - reflect → *insufficient*: Need Microsoft's FY2025 total revenue to compute net profit margin (net income / revenue); only net income has been gathered so far.
- **q07_compare_net_margin** (3 iteration(s)): How did Apple's net profit margin in FY2025 compare with Microsoft's? Which was higher?
    - reflect → *insufficient*: Apple's FY2025 net profit margin requires both net income ($112,010,000,000) and total revenue, which has not been retrieved yet. Additionally, Microsoft's FY2025 net income and revenue are completely missing, making the comparison impossible. Both pieces of data are required to calculate and compare the net profit margins.
    - reflect → *insufficient*: Microsoft's FY2025 net income and revenue have not been retrieved yet. To calculate the net profit margin comparison, we need both Apple's and Microsoft's net profit margins for FY2025. We have Apple's data (Net Income: $112.01B, Revenue: $416.161B), but we need Microsoft's equivalent figures to complete the comparison.
    - reflect → *insufficient*: Microsoft's FY2025 revenue is missing. We have Apple's FY2025 net income ($112,010M) and revenue ($416,161M), allowing us to calculate Apple's net profit margin. However, for Microsoft, we only have net income for FY2025 ($101,832M) but not the corresponding revenue figure, so Microsoft's net profit margin cannot be calculated yet. The comparison cannot be completed without Microsoft's FY2025 revenue.
- **q08_compare_rev_diff** (1 iteration(s)): Which company had higher total revenue in FY2025, Apple or Microsoft, and by how much (in dollars)?
    - reflect → *insufficient*: Microsoft's FY2025 total revenue has not been retrieved, so the comparison and difference cannot be computed yet.
- **q10_rag_aapl_supply** (3 iteration(s)): According to the indexed 10-K filings, what supply-chain risk does Apple highlight?
    - reflect → *insufficient*: The retrieval tool call failed due to a ModuleNotFoundError, so no actual content from Apple's 10-K filings was retrieved. Need to retry the retrieval (or use an alternative method) to get the actual supply-chain risk disclosure text before answering.
    - reflect → *insufficient*: Both retrieval attempts failed due to a module error (chromadb missing), so no actual content from Apple's 10-K regarding supply-chain risk has been retrieved yet. Need a successful retrieval of relevant 10-K text before answering.
    - reflect → *insufficient*: Both the RAG retrieval and web search tools failed to return actual content (module error and offline stub, respectively). No actual data from Apple's 10-K about supply-chain risk has been retrieved yet, so the question cannot be answered.
- **q11_rag_msft_cloud** (3 iteration(s)): Based on the indexed filings, what is driving Microsoft's revenue growth?
    - reflect → *insufficient*: The retrieval tool errored out (chromadb module missing), so no actual filing data was retrieved. There is no information on revenue segments, growth drivers, or supporting figures from Microsoft's filings to answer the question.
    - reflect → *insufficient*: The retrieval tool failed (chromadb error), so no qualitative filing text about revenue growth drivers (e.g., segment breakdown, cloud/Azure commentary, management discussion) was obtained. Only raw total revenue figures were retrieved, which don't explain what is driving growth. Need segment-level revenue data (e.g., Intelligent Cloud, Productivity, More Personal Computing) or MD&A text discussing drivers like Azure/cloud growth, AI services, etc.
    - reflect → *insufficient*: The rag_retrieve tool failed (missing chromadb module) and web_search returned no results (no provider configured). Only raw revenue numbers were obtained; no qualitative MD&A commentary on what is driving the revenue growth (e.g., Azure/cloud, AI services, segment-level drivers, commercial bookings) has been retrieved. Need to either fix the rag_retrieve tool or pull segment-level revenue breakdown (e.g., Intelligent Cloud, Productivity, More Personal Computing) and MD&A narrative text from the actual 10-Q/10-K filings to identify the growth drivers.
- **q12_rag_msft_segment** (3 iteration(s)): Which segment led Microsoft's growth in FY2025 according to the indexed filing text?
    - reflect → *insufficient*: The retrieval tool call errored out (ModuleNotFoundError), so no actual filing data on Microsoft's FY2025 segment revenue/growth was retrieved. Need to successfully query the indexed filing text to identify segment performance (e.g., Intelligent Cloud, Productivity and Business Processes, More Personal Computing) and their growth rates before answering.
    - reflect → *insufficient*: Both retrieval attempts failed due to a module error (chromadb not found), so no actual filing text or segment data was retrieved. Need to successfully query the indexed filing to find Microsoft's segment revenue growth data for FY2025 before determining which segment led growth.
    - reflect → *insufficient*: All retrieval attempts failed (chromadb module missing, invalid SEC concept). No actual segment revenue or growth data for Microsoft FY2025 has been obtained, so the question cannot be answered yet. Need a successful retrieval of the indexed filing text or segment financial data (e.g., Intelligent Cloud, Productivity and Business Processes, More Personal Computing revenue figures and growth rates) before determining which segment led growth.
- **q17_compare_rev** (1 iteration(s)): Compare Apple's and Microsoft's most recent annual revenue.
    - reflect → *insufficient*: Microsoft's most recent annual revenue has not been retrieved yet, so the comparison with Apple's FY2025 revenue cannot be made.
- **q18_ambiguous_profitable** (4 iteration(s)): Is Apple or Microsoft more profitable, and by how much?
    - reflect → *insufficient*: The tool call failed with an error, so no data on Apple's or Microsoft's net income, margins, or any profitability metrics has been retrieved. Need successful retrieval of financial data (e.g., net income, revenue, profit margins) for both AAPL and MSFT to compare profitability.
    - reflect → *insufficient*: Microsoft's net income (and ideally revenue for both companies to assess margin/profitability comparison) has not been retrieved yet.
    - reflect → *insufficient*: Have net income figures for both companies, but "profitability" typically requires margin comparison (net income relative to revenue), not just absolute net income. Need revenue figures for AAPL and MSFT (FY2025) to compute and compare profit margins, or clarify if question only wants net income comparison. Should retrieve revenue data to compute margins for a more accurate answer.
    - reflect → *insufficient*: Need Microsoft's revenue (annual, FY2025) to compute and compare net profit margins between Apple and Microsoft.
- **q19_calc_combined_ni** (1 iteration(s)): What was the combined FY2025 net income of Apple and Microsoft together?
    - reflect → *insufficient*: Microsoft's FY2025 net income has not been retrieved yet, so the combined total cannot be computed.
- **q21_calc_aapl_ni_growth** (1 iteration(s)): By what percent did Apple's net income change from FY2024 to FY2025?
    - reflect → *insufficient*: FY2024 full-year net income figure has not been retrieved; only FY2025 annual net income (112,010,000,000) and some quarterly figures are available. Need FY2024 annual net income to compute the percent change.
- **q22_rag_msft_ai_risk** (3 iteration(s)): What capital-related risk does Microsoft mention regarding AI and datacenters in its filing?
    - reflect → *insufficient*: The retrieval tool call failed with an error (chromadb module missing), so no actual filing content was retrieved. Need a successful retrieval of Microsoft's filing text regarding AI/datacenter capital risk before answering.
    - reflect → *insufficient*: Both retrieval attempts failed (module error and offline search stub returned no data). No actual content from Microsoft's filing about AI/datacenter capital risk was retrieved. Need to try an alternative retrieval method or source to get the actual risk factor text before answering.
    - reflect → *insufficient*: All retrieval attempts failed (module errors and offline search stub returned no data). No actual content from Microsoft's filing about AI/datacenter capital risk has been retrieved yet. Need a working retrieval method (e.g., fix chromadb dependency or alternate search) to get the actual risk factor text before answering.

## Example answer (full)

**Q (q05_calc_aapl_net_margin):** What was Apple's net profit margin (net income divided by revenue) in FY2025?

```json
{
  "answer": "Apple's FY2025 (fiscal year ended September 27, 2025) net income was $112.010 billion on total revenue of $416.161 billion, per its 10-K filed October 31, 2025. This yields a net profit margin of approximately 26.9% (112,010/416,161 \u2248 26.92%).",
  "key_numbers": {
    "aapl_net_income_fy2025_usd": 112010000000.0,
    "aapl_revenue_fy2025_usd": 416161000000.0,
    "aapl_net_profit_margin_fy2025_pct": 26.92
  },
  "confidence": "high",
  "tools_used": [
    "sec_edgar",
    "sec_edgar"
  ]
}
```
