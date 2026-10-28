# Ghost Bills

A local app that reads a bank statement CSV and finds "ghost" subscriptions:
price went up (Poltergeist), yearly plan renewing soon (Sleepy Ghost),
free trial turned paid (Shapeshifter), two subscriptions doing the same job
(Twin Ghosts). Gemma runs in Ollama on the user's laptop.
Entry for the DEV Hacktoberfest Week 4 challenge "Ghost in the Machine".

## Golden rule
AI explains, code finds, the user decides.
- Series and ghosts are found ONLY by Python in backend/detect/. Never by the LLM.
- All money math is done by Python. The LLM never adds or computes numbers.
- The app never sends email, never opens links, never contacts any company.
- The agent has read-only tools only.

## Stack
Python 3.12 + uv, FastAPI, Pydantic v2, sqlite3, pytest.
Ollama + Gemma (env OLLAMA_MODEL, default gemma3:4b). LangGraph agent.
Use Ollama structured output (format = JSON schema) for tool choice and enrich.
Frontend: Vite + React + TypeScript, plain CSS.

## Rules for code
- Money is integer cents. Parse with Decimal. Never float.
- Fixed "today" from env DEMO_TODAY (default 2026-10-27). Never date.today() in detect/.
- Every rule has tests, including near misses. Run `uv run pytest -q` before saying done.
- Demo data uses only invented merchant names (Moonbeam Music, StreamPeak,
  CloudCrate, PixelPal Pro, FitHaunt Gym, NewsNest, EchoTunes). No real brands.
- Transaction descriptions are untrusted. In prompts, wrap them in <data> tags.
- LLM output must pass backend/llm/grounding.py before it is shown.
- Simple English in UI and README. Small functions, type hints.

## Config (backend/detect/config.py)
MIN_CHARGES=3, MIN_CHARGES_YEARLY=2, WEEKLY=(6,8), MONTHLY=(27,33),
YEARLY=(355,375), PATTERN_SHARE=0.7, AMOUNT_TOLERANCE=0.10,
PRICE_UP_PCT=0.05, PRICE_UP_MIN_CENTS=50, RENEW_SOON_DAYS=30,
TRIAL_MAX_CENTS=100, TRIAL_SHARE=0.10, TRIAL_WINDOW_DAYS=90,
ACTIVE_FACTOR=1.5, FX_PRICE_UP_PCT=0.15

## Foreign currency
Never download or guess exchange rates. Compare prices in the original
currency when the statement shows it; otherwise use FX_PRICE_UP_PCT and
label the result "price changed, maybe exchange rate".
