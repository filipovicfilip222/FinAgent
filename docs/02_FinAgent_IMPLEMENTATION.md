# FinAgent — Implementation Spec

Ovo je detaljna specifikacija koju Claude Cowork treba da prati kad piše kod. Nije pseudokod za copy-paste, nego kontrakt: šta svaki fajl mora da radi, koje su granice odgovornosti, i šta je "gotovo" za taj deo.

## 1. `state.py` — AgentState

```python
from pydantic import BaseModel, Field
from typing import Literal

class ToolCall(BaseModel):
    tool: Literal["sec_edgar", "web_search", "calculator", "rag_retrieve"]
    input: dict
    output: str
    step_index: int

class AgentState(BaseModel):
    query: str
    plan: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reflection_notes: list[str] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 6
    final_answer: "FinalAnswer | None" = None
    done: bool = False
```

`iteration` se increment-uje na svaki povratak u planner. `max_iterations` je hard stop — ako se dostigne, graf ide direktno na finalize sa najboljim dostupnim podacima i flag-om da odgovor može biti nepotpun. Ovo je bitno da eval ne visi u petlji.

## 2. `schemas.py` — structured output

```python
class Citation(BaseModel):
    source: str          # npr. "SEC EDGAR 10-K AAPL Q3 2025" ili URL
    detail: str           # šta konkretno iz izvora je korišćeno

class FinalAnswer(BaseModel):
    answer: str
    key_numbers: dict[str, float] = Field(default_factory=dict)
    citations: list[Citation]
    confidence: Literal["high", "medium", "low"]
    caveats: str | None = None
```

`confidence` je nizak ako je `max_iterations` dostignut ili ako je bar jedan tool poziv vratio grešku bez zamene. Ovo mora da bude realna logika, ne uvek "high".

## 3. `planner.py`

Planner dobija: originalni query, dosadašnje tool_calls (kompaktan summary, ne sirovi output ako je predugačak), i reflection_notes ako postoje. Vraća JSON (Claude tool-use) sa:
```
{"action": "call_tool", "tool": "...", "input": {...}, "reasoning": "..."}
```
ili
```
{"action": "finish", "reasoning": "..."}
```

**Sistemski prompt planner-a mora eksplicitno da:**
- nabroji sva 4 alata sa po jednom rečenicom kad se koji koristi (SEC EDGAR za zvanične finansijske brojeve iz filing-a; web_search za novosti/kontekst van filing-a; calculator za bilo koji izračun sa više od jedne cifre — planner ne sme sam da računa u glavi; rag_retrieve za pitanja o sadržaju lokalno indeksiranih dokumenata)
- kaže planneru da NE zove calculator ako već ima gotov broj iz alata — samo za derivate (marže, rast, poređenja)
- traži `reasoning` polje uvek — to je ono što se posle pokazuje u eval izveštaju kao "zašto je agent odabrao ovaj alat", korisno za debug i za demo

## 4. `reflect.py`

Reflect node se zove posle svakog tool poziva. Dobija state, vraća:
```
{"sufficient": bool, "missing": "kratak opis šta nedostaje ili null"}
```
Ako `sufficient=False`, `missing` se dodaje u `reflection_notes` i state se vraća planneru. Bitno: reflect prompt mora imati konkretan primer kad NIJE dovoljno (npr. "imamo Apple maržu ali pitanje traži poređenje sa Microsoftom, a Microsoft podaci nisu povučeni") — bez primera model ima tendenciju da uvek kaže "dovoljno" da bi završio brže.

## 5. Tool specifikacije

### `tools/sec_edgar.py`
- Endpoint: `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json` za konkretne finansijske stavke (npr. `Revenues`, `NetIncomeLoss`, `GrossProfit`)
- Treba mapa ticker → CIK (može statički dict za par velikih firmi: AAPL, MSFT, GOOGL, AMZN, META — dovoljno za demo/eval, ne mora univerzalno)
- Obavezan `User-Agent` header sa email adresom (SEC to zahteva, inače baca 403)
- Vraća najnovijih N kvartala/godina za traženi concept, kao čist string koji planner/reflect mogu da čitaju

### `tools/web_search.py`
- Tavily API (`tavily-python` paket) ili Anthropic web_search preko API-ja — Cowork treba da proveri koji je lakše integrisati sa postojećim Anthropic klijentom (verovatno Anthropic web_search je jednostavnije jer nema drugi API key)
- Vraća top 3-5 rezultata, svaki sa naslovom, kratkim izvodom, URL-om (URL ide u citations)

### `tools/calculator.py`
- NE sme da koristi goli `eval()`. Koristiti `simpleeval` paket (whitelist operacija) ili napisati mini AST-based evaluator koji dozvoljava samo `+ - * / ** ()` i brojeve
- Input: string izraz, npr. `"(120000 - 100000) / 100000 * 100"`
- Output: broj + isti taj string nazad (radi transparentnosti u trace-u)

### `tools/rag_retrieve.py`
- ChromaDB persistent client, kolekcija `filings`
- `ingest.py` čita PDF-ove iz `data/sample_filings/`, chunk-uje (npr. 500 tokena, 50 overlap), embed-uje, upisuje sa metadata (company, filing_type, date)
- Retrieval: top-k (k=4) similarity search, vraća chunk tekst + metadata kao citation source

## 6. `graph.py` — LangGraph wiring

Čvorovi: `planner`, `tool_executor`, `reflect`, `finalize`.

Grane:
- `planner` → conditional: ako `action == "call_tool"` idi na `tool_executor`; ako `finish` idi na `finalize`; ako `iteration >= max_iterations` idi na `finalize` (force)
- `tool_executor` → `reflect`
- `reflect` → conditional: ako `sufficient` idi na `finalize`; inače nazad na `planner` (uz increment iteration)
- `finalize` → END

Koristiti `StateGraph(AgentState)`, kompajlirati sa `MemorySaver` checkpointer-om (omogućava da se state inspektuje posle svakog koraka — korisno i za eval i za LangSmith trace).

## 7. `evals/dataset.json` — struktura

```json
[
  {
    "id": "q1_single_tool",
    "query": "Koliki je bio Apple-ov prihod (Revenues) u poslednjem raspoloživom kvartalu?",
    "expected_tools": ["sec_edgar"],
    "expected_answer_contains": null,
    "expected_number": null,
    "tolerance_pct": 5,
    "difficulty": "easy"
  },
  {
    "id": "q5_multi_tool_calc",
    "query": "Kolika je bila procentualna promena Apple-ove neto dobiti između poslednja dva raspoloživa kvartala?",
    "expected_tools": ["sec_edgar", "calculator"],
    "difficulty": "medium"
  }
]
```
Cowork treba da napravi 15-25 ovakvih pitanja, raspon: single-tool (lako), multi-tool bez calculator-a, multi-tool sa calculator-om, pitanja koja zahtevaju RAG (nešto specifično iz demo PDF-a), i namerno dvosmisleno pitanje koje bi trebalo da okine reflection loop (traži poređenje dve firme ali prvi tool poziv pokrije samo jednu).

## 8. `evals/metrics.py`

- **Tool selection accuracy** — set(tools_used) vs set(expected_tools), Jaccard ili exact match, izveštava se posebno
- **Numerical accuracy** — ako `expected_number` postoji, proveri da li je finalni `key_numbers` u okviru `tolerance_pct`
- **Avg steps to answer** — prosečan broj planner iteracija
- **Reflection trigger rate** — % pitanja gde je reflect vratio `sufficient=False` bar jednom (dokaz da mehanizam realno radi, ne samo postoji u kodu)

`run_eval.py` prolazi kroz dataset, poziva graph.invoke po pitanju, agregira metrike, piše `evals/results/report_<timestamp>.md` sa tabelom po pitanju + summary na vrhu.

## 9. `api.py` — FastAPI

Jedan endpoint `POST /query` sa body `{"query": str}`, vraća `FinalAnswer` JSON. Dodati i `GET /health`. Ovo nije za production load, samo da postoji čist interfejs za demo/frontend kasnije.

## 10. README zahtevi

README mora da sadrži: kratak opis, arhitekturni dijagram (ascii ili mermaid), primer poziva sa realnim outputom (copy iz eval rezultata ili ručnog testa), tabelu sa eval metrikama, uputstvo za pokretanje (`pip install`, `.env` setup, `python -m finagent.api`), i eksplicitnu sekciju "Design decisions" koja objašnjava zašto LangGraph a ne obican agent loop, zašto reflection, zašto structured output — ovo je ono što na intervjuu pokazuje da je razumevanje stvarno, ne kopipejst tutorijala.

## 11. Redosled u kom Cowork treba da radi

Sledi fazni redosled iz plan dokumenta (Faza 1-8). Posle svake faze, pokrenuti postojeće testove/graf ručno pre nego što se ide dalje — ne pisati sve fajlove odjednom pa tek onda debug-ovati sve zajedno.
