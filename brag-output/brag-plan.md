# Ghost Bills: brag plan

## Answers

- **What is it?** A local app that reads your bank statement (CSV) and finds the
  "ghost" subscriptions that quietly cost you money.
- **Who is it for?** Anyone who pays for things they forgot about, and doesn't want to hand a
  money app their bank login.
- **What sets it apart?** It runs 100% on the laptop. Python finds every ghost and does every
  sum, Gemma (local, via Ollama) only writes the words, and a checker blocks anything
  Gemma invents.
- **Most impressive claim:** −$466.76 a year found in one statement, and every number comes
  with proof from that statement.
- **Visual hook:** the red-ink total counting up on ledger paper, double underlined.
- **Real UI to show:** import dialog → 4 ghost-type cards and total → proof list → Gemma text
  passing the grounding check → cancel email → "I cancelled it" → gravestone.
- **Tone:** `default`, played as Penny's account book: warm, playful, clean. The humour comes
  from the project itself (ghosts, a graveyard for cancelled plans, a séance-voiced AI).
- **Share caption:** "I found $466.76 a year haunting my bank statement, and my bank data never
  left my laptop."

## Angle

The user asked for a clear end-to-end demo plus why it was made, so this is longer than a
launch teaser: **about 41 s** instead of 20 s, every cut on a beat. Structure: hook → why →
the 5 real steps → outro.

## Visual identity (straight from the app)

The app's real stylesheet (`frontend/src/styles/tokens.css` + `index.css`), real fonts
(IM Fell English, EB Garamond, Courier Prime, bundled) and real mascots (the v3 set).
Ruled ledger paper with the red margin line, rubber stamps, red ink for money lost, green for
money saved. Scenes are the app's own markup and classes, animated over time.

## Data

All numbers and text are the real demo output: invented merchants (Moonbeam Music,
CloudCrate, PixelPal Pro, EchoTunes), today = 2026-10-27, Gemma 3 4B's saved text for
Moonbeam Music. One illustrative item: the rejected Gemma draft in step 4. It is labelled
"draft", and its rejection reason is the checker's real message. No real people, accounts or URLs.

## Music

96 BPM (beat 0.625 s, bar 2.5 s), D minor, Dm–B♭–F–C. Soft pad, plucked bass, quiet kick and
hats, all generated on one beat grid from frame 0. Effects in key on the same grid: a soft
paper "thump" on stamps and cuts, a quiet bell on reveals, and tiny clicks on simulated presses.
The last bar resolves on D, with a fade out.

## Storyboard (all times on beats)

| # | Time | Scene | On screen |
|---|---|---|---|
| 1 | 0.00–3.75 | **Hook** | Red total counts up to **−$466.76 per year**, double underlined. "Forgotten subscriptions, haunting one bank statement." Four ghosts peek in. |
| 2 | 3.75–8.75 | **Why** | "Most money apps want your bank login." gets struck through in red ink → "Ghost Bills never leaves your laptop." Lock pill + stamps: GEMMA RUNS LOCALLY · NO BANK LOGIN · WORKS WITH WI-FI OFF. |
| 3 | 8.75–13.75 | **Step 1: Import** | "Export a CSV from your bank. Ghost Bills guesses the columns." The real import dialog: column mapping, 5 real rows, a simulated click on IMPORT, "701 charges read". |
| 4 | 13.75–20.00 | **Step 2: Code finds** | "Plain Python finds four kinds of ghost." The 4 type cards stamp in on beats and the total adds up: $36.00 → $155.00 → $334.88 → $466.76. "Not flagged: coffee shop · rent · gym +2%." |
| 5 | 20.00–25.00 | **Step 3: Proof** | "Every ghost comes with proof from your own statement." Moonbeam Music detail; proof lines land one by one next to the real CSV lines (−9.99 → −12.99). |
| 6 | 25.00–31.25 | **Step 4: Gemma, checked** | "Gemma writes the words on your laptop. A checker blocks anything it invents." A draft with a link gets a REJECTED stamp; the real Gemma line passes with the "Gemma · local" badge. |
| 7 | 31.25–36.25 | **Step 5: You decide** | "You decide. It never sends anything for you." The cancel email types in, a click on COPY EMAIL, then I CANCELLED IT; a gravestone settles into "Laid to Rest", and Saved so far +$36.00. |
| 8 | 36.25–41.25 | **Outro** | Penny + **Ghost *Bills***. "AI explains, code finds, you decide." "Gemma 3 on Ollama · runs 100% on your laptop." |

Transitions: old content out (0.25 s), then new content in, dipping through the paper. No
muddy crossfades.

**Poster:** the settled end of scene 4 (−$466.76 with all four cards), baked as frame 0.
