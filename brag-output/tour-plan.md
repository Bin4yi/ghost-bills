# Ghost Bills: tour video plan

**Goal:** teach a new user what Ghost Bills does, why it exists and how to use it, end to end,
in plain words. Length 3:28 (the request asked for a maximum of 3–4 minutes).

**Voice:** Kokoro (`af_heart`, speed 0.95), open-source text-to-speech running locally via
`kokoro-onnx`. The request asked for Ollama's `phonon`, but phonon needs Apple Silicon (MLX)
and does not run on this Windows laptop, so Kokoro was picked as the local, open-model
stand-in. The narration lines are in `work/script.json`, so they can be re-voiced with phonon on a Mac
(`ollama run phonon "<line>" > <id>.wav`, one file per line) without changing anything else.

**Visuals:** the real app, recorded in headless Chrome from a copy of the demo data
(`work/rec.mjs`): home, import dialog with the real `demo.csv`, Moonbeam Music detail, the
answered exchange-rate question, the graveyard after "I cancelled it", a real Ask Penny answer
from Gemma 3 4B, and séance mode. A camera glides to whatever the voice is talking about, with
a pumpkin spotlight, a cursor that does the clicks, a step label, subtitles and a progress
bar. Halloween frame: night background, moon, bats, pumpkins, the app's séance candles and
the graveyard strip from the art set.

**Story (34 lines):**

1. What it is: finds the subscriptions you forgot ("ghosts").
2. Why: small charges add up; many apps want your bank login, Ghost Bills does not; it all
   runs on your laptop, even the AI.
3. Setup: `ollama pull gemma3:4b`, `uv sync`, `uv run python -m scripts.dev`, open the app.
4. Step 1: import a CSV; the columns are found for you.
5. Step 2: code finds the 4 kinds of ghost (Poltergeist, Sleepy Ghost, Shapeshifter, Twin
   Ghosts) and the yearly total; normal shopping isn't flagged.
6. Step 3: open a ghost; the proof is from your statement, found by code, not AI.
7. Step 4: Gemma explains in simple words; a checker blocks invented numbers or links;
   Penny asks when unsure and remembers the answer.
8. Step 5: copy the cancel email, send it yourself (the app never sends anything), click
   "I cancelled it", and see the graveyard and Saved so far.
9. Extras: upcoming charges, Ask Penny, séance mode.
10. Outro: code finds, AI explains, you decide.

**Audio:** voice track plus a quiet D-minor music box, pad and wind, ducked under the voice;
the mix is at −16 LUFS.

**Fixes made to the app while preparing this** (found while recording, all with tests):
cancel emails must be written by the user ("Please cancel my…"); Gemma's names only use the
merchant's own words; twin ghosts keep both names; Ask Penny fills in a category the small
model forgot ("how much on music?").
