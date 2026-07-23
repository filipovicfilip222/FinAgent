"""Generate condensed sample 10-K excerpt PDFs for the RAG demo.

These are *abbreviated, paraphrased* excerpts: the headline figures are the real
FY2025 numbers from each company's SEC filing (and match the SEC EDGAR fixtures),
while the narrative sections are shortened summaries of the risk-factor and MD&A
themes those companies actually disclose. They exist so the RAG pipeline has real,
queryable filing-style text to index. Drop any real 10-K PDF into data/sample_filings/
and `python -m finagent.rag.ingest` will index it the same way.

Run: python scripts/make_sample_filings.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parents[1] / "data" / "sample_filings"


def _build(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, title=title)
    flow = [Paragraph(title, styles["Title"]),
            Paragraph("Condensed sample excerpt for RAG demo — headline figures are from the "
                      "cited SEC filing; narrative is abbreviated/paraphrased.", styles["Italic"]),
            Spacer(1, 12)]
    for heading, body in sections:
        flow.append(Paragraph(heading, styles["Heading2"]))
        for para in body.strip().split("\n\n"):
            flow.append(Paragraph(para.strip(), styles["BodyText"]))
            flow.append(Spacer(1, 6))
    doc.build(flow)
    print("wrote", path)


APPLE = [
    ("Item 1. Business",
     """Apple Inc. designs, manufactures and markets smartphones, personal computers, tablets,
     wearables and accessories, and sells a variety of related services. The Company's products
     include iPhone, Mac, iPad, and Wearables, Home and Accessories. The Services segment includes
     advertising, AppleCare, cloud services, digital content and payment services.

     For fiscal year 2025 (ended September 27, 2025), total net sales were $416.2 billion and net
     income was $112.0 billion. iPhone remained the Company's largest product category, while the
     Services business continued to grow and reached a new all-time revenue high."""),
    ("Item 1A. Risk Factors",
     """The Company's business is subject to a variety of risks. A substantial portion of the
     Company's manufacturing is performed by outsourcing partners located primarily in Asia,
     including China, India and Vietnam, and a disruption to these operations or to the supply of
     key components could materially harm results. The Company depends heavily on the iPhone, and a
     decline in iPhone demand could disproportionately affect revenue.

     The markets for the Company's products and services are highly competitive and characterized by
     rapid technological change. The Company is exposed to foreign-exchange risk because a majority of
     net sales occur outside the United States, and a strengthening U.S. dollar can reduce reported
     revenue. Legal and regulatory developments concerning the App Store and digital-market
     regulation could require changes to business practices."""),
    ("Item 7. Management's Discussion and Analysis",
     """Total net sales increased year over year, driven by growth in Services and higher iPhone
     revenue. Products gross margin benefited from a favorable mix and cost efficiencies, while
     Services gross margin remained substantially higher than Products gross margin. The Company
     returned capital to shareholders through dividends and share repurchases and continued to invest
     in research and development, including silicon and artificial-intelligence capabilities."""),
]

MICROSOFT = [
    ("Item 1. Business",
     """Microsoft Corporation develops and supports software, services, devices and solutions.
     The Company reports in three segments: Productivity and Business Processes (including Microsoft
     365 and LinkedIn), Intelligent Cloud (including Azure and server products), and More Personal
     Computing (including Windows, devices, gaming and search).

     For fiscal year 2025 (ended June 30, 2025), total revenue was $281.7 billion and net income was
     $101.8 billion. Growth was led by the Intelligent Cloud segment, with Azure and other cloud
     services the largest contributor to revenue growth."""),
    ("Item 1A. Risk Factors",
     """The Company faces intense competition across all markets, including from companies investing
     heavily in artificial intelligence and cloud computing. Significant investment in datacenters and
     AI infrastructure increases capital expenditures and depreciation, and demand may not materialize
     as anticipated. Cybersecurity threats to the Company's products and cloud services are persistent
     and evolving, and a significant breach could damage reputation and results.

     The Company is subject to increasing regulatory scrutiny worldwide, including competition,
     privacy and AI-related regulation. Acquisitions, including in gaming, carry integration and
     regulatory risk."""),
    ("Item 7. Management's Discussion and Analysis",
     """Revenue increased year over year, led by Intelligent Cloud and driven by growth in Azure.
     Operating margins reflected continued investment in cloud and AI capacity, including elevated
     capital expenditures for datacenters and AI accelerators. The Company continued to return capital
     to shareholders while prioritizing investment in its cloud and AI platform."""),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _build(OUT / "AAPL_10-K_2025.pdf", "Apple Inc. — Form 10-K (FY2025) — Sample Excerpt", APPLE)
    _build(OUT / "MSFT_10-K_2025.pdf", "Microsoft Corporation — Form 10-K (FY2025) — Sample Excerpt",
           MICROSOFT)


if __name__ == "__main__":
    main()
