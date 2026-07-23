# FinAgent — Project Plan

## 1. Šta ovo treba da bude

Multi-agent sistem za finansijsko istraživanje. Planner LLM dobije pitanje ("Kakva je bila marža Apple-a u poslednja 3 kvartala i kako se poredi sa Microsoftom?") i sam odlučuje koje alate da pozove: SEC EDGAR (10-K/10-Q podaci), web search (vesti, kontekst), Python calculator (finansijski izračuni), RAG retrieval (nad lokalno indeksiranim dokumentima). Rezultat je strukturisan, brojčano tačan odgovor sa citiranim izvorima.

Cilj nije demo koji radi jednom — cilj je repo koji izgleda kao production-grade agentic sistem, sa evaluacijom koja to i dokazuje. Ovo je razlikovni projekat za AI engineering pozicije, treba da izdrži da neko na intervjuu otvori kod i evals i poveruje da je ozbiljno rađeno.

## 2. Zašto ovako (dizajn odluke)

- **LangGraph, ne LangChain agent executor** — treba eksplicitan graf sa granama (planner → tool node → reflect → planner ili finish), ne crna kutija. To je i ono što CV/LinkedIn već tvrde, pa mora da odgovara.
- **Planner bira alate, ne fiksni pipeline** — suština "multi-agent orchestration" tvrdnje. Planner mora realno da ima izbor i da taj izbor bude vidljiv u trace-u.
- **Reflection loop** — posle tool poziva, agent proverava da li ima dovoljno da odgovori ili treba još jedan korak. Ovo direktno pokriva "reflection loops... improved task success rate" iz LinkedIn opisa — mora zaista da postoji, ne samo u tekstu.
- **Structured outputs** — finalni odgovor i intermediate tool pozivi idu kroz Pydantic sheme, ne slobodan tekst. Ovo pokriva "structured outputs to improve numerical accuracy".
- **Eval harness kao prvoklasni deo projekta** — set test pitanja sa poznatim tačnim odgovorima (ili proverljivim brojevima), meri se tool selection accuracy, numerička tačnost, broj koraka. Bez ovoga je "comprehensive LLM evaluation framework" iz LinkedIn opisa laž na CV-ju.

## 3. Arhitektura (high level)

```
User Query
   │
   ▼
┌─────────────┐
│   Planner    │◄────────────────┐
│  (Claude)    │                  │
└──────┬───────┘                  │
       │ odlučuje: koji alat / done?
       ▼                          │
┌─────────────────────────┐       │
│      Tool Router         │      │
├───────────┬─────────────┤       │
│ SEC EDGAR  │ Web Search  │       │
│   Tool     │   Tool      │       │
├───────────┼─────────────┤       │
│ Python Calc│ RAG Retrieve│       │
│   Tool     │   Tool      │       │
└─────┬──────┴──────┬──────┘      │
      │             │             │
      ▼             ▼             │
┌─────────────────────────┐       │
│   Reflection Node        │──────┘
│ (dovoljno info? / retry) │
└───────────┬──────────────┘
            │ done
            ▼
┌─────────────────────────┐
│  Structured Answer       │
│  (Pydantic model +       │
│   citations)             │
└───────────────────────────┘
```

LangGraph state machine, čvorovi: `planner`, `tool_executor`, `reflect`, `finalize`. Uslovne grane iz `planner` i `reflect` (conditional edges).

## 4. Tech stack

- **Orkestracija:** LangGraph (StateGraph, checkpointer za perzistenciju stanja između koraka)
- **LLM:** Anthropic Claude (planner + reflection + finalizacija) preko `anthropic` SDK; opciono OpenAI GPT-4 kao alternativni provider za A/B poređenje u evalu (LinkedIn eksplicitno pominje oba)
- **Alati:**
  - SEC EDGAR — `sec-edgar-api` ili direktan REST poziv na `data.sec.gov` (company facts / submissions endpoint), besplatno, bez key-a, samo treba custom `User-Agent` header
  - Web search — Tavily API (namenjen za LLM agente, ima free tier) ili Anthropic web_search tool preko API-ja
  - Python calculator — sandboxed `exec` sa ograničenim namespace-om (samo `math`, osnovne aritmetičke operacije) ili `simpleeval` biblioteka radi sigurnosti
  - RAG retrieval — ChromaDB kao vector store nad lokalno učitanim finansijskim PDF-ovima (10-K izveštaji), embeddings preko `voyage-3` (Anthropic-preporučeni) ili OpenAI `text-embedding-3-small`
- **Structured outputs:** Pydantic modeli, Claude tool-use / OpenAI function calling za garantovanu shemu
- **Backend/API:** FastAPI da se agent izloži kao servis (i da eval harness i frontend mogu da ga pozivaju)
- **Eval:** custom skripta (nije potreban framework kao DeepEval — jednostavnije je i transparentnije da bude custom, lakše se objašnjava na intervjuu), rezultati u JSON + markdown report, opciono logging u Weights & Biases (već pominje na CV-ju za drugi projekat, konzistentnost dobra)
- **Testing:** pytest za tool-level unit testove
- **Observability:** LangSmith (opciono, besplatan tier) za trace-ove — jako pomaže kad se pokazuje demo

## 5. Struktura repozitorijuma

```
FinAgent/
├── README.md                 # sa dijagramom, primerom, rezultatima evala
├── pyproject.toml / requirements.txt
├── .env.example
├── src/
│   └── finagent/
│       ├── graph.py           # LangGraph definicija (state, čvorovi, grane)
│       ├── state.py           # Pydantic AgentState
│       ├── planner.py         # planner node logika + prompt
│       ├── reflect.py         # reflection node
│       ├── tools/
│       │   ├── sec_edgar.py
│       │   ├── web_search.py
│       │   ├── calculator.py
│       │   └── rag_retrieve.py
│       ├── rag/
│       │   ├── ingest.py      # indeksiranje PDF-ova u ChromaDB
│       │   └── store.py
│       ├── schemas.py         # Pydantic modeli za structured output
│       └── api.py             # FastAPI app
├── data/
│   └── sample_filings/        # par 10-K PDF-ova za RAG demo
├── evals/
│   ├── dataset.json           # test pitanja + ground truth
│   ├── run_eval.py
│   ├── metrics.py             # tool selection accuracy, numerical accuracy, avg steps
│   └── results/                # generated eval reports
├── tests/
│   └── test_tools.py
└── notebooks/
    └── demo.ipynb              # brz vizuelni walkthrough
```

## 6. Faze rada

**Faza 1 — Skelet i state graph**
LangGraph state definicija, prazan graph sa planner → finish, bez pravih alata (mock). Cilj: graf radi end-to-end sa jednim trivijalnim pitanjem.

**Faza 2 — Alati**
Implementirati sva 4 alata pojedinačno, sa unit testovima. Svaki alat mora da radi standalone pre nego što uđe u graf.

**Faza 3 — Planner + tool routing**
Planner LLM sa tool-use šemom bira alat, tool executor ga poziva, rezultat se vraća u state.

**Faza 4 — Reflection loop**
Reflect node ocenjuje da li state ima dovoljno informacija; ako ne, vraća se planneru sa objašnjenjem šta nedostaje (max broj iteracija da se izbegne beskonačna petlja).

**Faza 5 — Structured output**
Finalize node forsira Pydantic shemu (odgovor, brojevi, izvori, confidence).

**Faza 6 — RAG + SEC EDGAR podaci**
Ingest par 10-K dokumenata, testirati retrieval kvalitet.

**Faza 7 — Eval harness**
15-25 test pitanja različite težine (single-tool, multi-tool, treba reflection, treba calculator). Metrike: tool selection accuracy, numerička tačnost (exact/tolerance match), broj koraka do odgovora, latencija.

**Faza 8 — API + polish**
FastAPI endpoint, README sa dijagramom i eval rezultatima, opciono minimalan Streamlit/CLI demo.

## 7. Definicija "gotovo"

- [ ] Graf radi end-to-end sa realnim pitanjima, ne samo happy path
- [ ] Sva 4 alata rade i imaju testove
- [ ] Reflection loop se stvarno aktivira na bar par test pitanja (ne postoji samo u kodu nego se i okine)
- [ ] Eval report postoji, sa brojevima, u repou
- [ ] README objašnjava arhitekturu sa dijagramom i navodi eval rezultate
- [ ] .env.example, nema hardkodovanih ključeva
- [ ] Repo ima bar 1 GitHub Action (lint + test na push)
