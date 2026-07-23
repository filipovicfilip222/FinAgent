Radimo na projektu FinAgent — multi-agent sistem za finansijsko istraživanje, LangGraph + Anthropic Claude + OpenAI, sa SEC EDGAR, web search, Python calculator i RAG alatima. Ovo ide na CV/GitHub kao portfolio projekat za AI engineering pozicije, treba da bude realno production-quality, ne demo-toy.

Priložio sam dva dokumenta:
1. FinAgent_PLAN.md — arhitektura, tech stack, faze rada, definicija "gotovo"
2. FinAgent_IMPLEMENTATION.md — tačna specifikacija svakog fajla, šeme, tool kontrakti, eval dizajn

Prati ih tačno kao spec, ne kao inspiraciju. Ako nešto u spec-u nije jasno ili misliš da postoji bolje rešenje, stani i pitaj me pre nego što odstupiš, ne donosi tihe izmene arhitekture.

Radi u fazama iz plan dokumenta (Faza 1 → 8), redom. Posle svake faze:
- pokreni ono što je napisano i pokaži mi da radi (test output, primer poziva)
- ne prelazi na sledeću fazu dok prethodna realno ne radi

Zahtevi koji nisu pregovarački:
- Reflection loop mora stvarno da se okine na bar nekoliko eval pitanja, ne sme postojati samo u kodu a da se nikad ne aktivira — proveri ovo eksplicitno u eval izveštaju
- Calculator tool ne sme koristiti goli Python `eval()` — sandboxed rešenje kao što je opisano u spec-u
- Eval dataset treba 15-25 pitanja različite težine, uključujući namerno dvosmisleno pitanje koje bi trebalo da okine reflection
- Nema hardkodovanih API ključeva nigde, samo `.env` + `.env.example`
- README na kraju mora imati dijagram arhitekture, primer poziva sa realnim outputom, eval tabelu i sekciju "Design decisions"

Kad završiš sve faze, daj mi kratak summary: šta radi, šta ne radi ili je pojednostavljeno u odnosu na spec (i zašto), i koje su sledeće razumne nadogradnje da ih ja mogu da pomenem na intervjuu kao "future work".

Radna okolina: Python, koristi `pyproject.toml` ili `requirements.txt`, standardni layout iz IMPLEMENTATION.md dokumenta (src/finagent/...). GitHub repo je prazan (filipovicfilip222-alt/FinAgent), pa se gradi od nule.
