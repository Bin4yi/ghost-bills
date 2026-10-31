# Ghost Bills: tour video plan (v3, animated Auth0 diagrams)

**Goal:** teach a new user what Ghost Bills does, why it exists, how to use it,
and how the agents send an email safely with Auth0. Plain words, 3:29 long.

**Voice:** Kokoro (`af_heart`, speed 0.95), open-source text-to-speech running
locally (Ollama's `phonon` needs Apple Silicon, so it can't run on this Windows
laptop). The narration lines are in `work/script.json`.

**Visuals:**
- The real app, recorded in headless Chrome from demo data (`work/rec.mjs`).
- The logged-in agent screens (Send with Gmail, "Confirm by logging in again",
  the token inspector and the "What Penny did" timeline) recorded from the real
  UI against a test tenant (`work/rec_agents.mjs`, fake Auth0, demo data).
- Four colorful animated diagrams (one color per actor: you mint, Penny orange,
  Courier coral, Auth0 violet, Google blue):
  - How the pieces fit: laptop / Auth0 / Google zones, arrows draw on.
  - Delegation: passes fly You → Auth0 → Penny → Auth0 → Courier, each pass
    shows its claims, then the chain you → Penny → Courier.
  - Three locks: padlocks click shut one by one.
  - After you confirm: a Google token flies from Token Vault to Courier to Gmail,
    one email reaches the company, the token is thrown away.
- A camera that glides to what the voice explains, a spotlight, cursor clicks,
  step labels, subtitles and a progress bar, in a Halloween night frame.

**Story (32 lines):**
1. What it is, and why: forgotten subscriptions add up; everything runs on your laptop.
2. Step 1: import a CSV. Step 2: code finds the 4 kinds of ghost and the total.
3. Step 3: open a ghost, see the proof (code, not AI); Gemma explains; Penny asks when unsure.
4. Step 4: Ghost Bills writes the cancel email.
5. **Auth0 section:**
   - Three agents: Penny (chat and plans, read-only), Ledger (local, never online),
     Courier (the only one that can send).
   - Token exchange: your login token → Penny's token (act: Penny, read:ghosts,
     5 minutes) → Courier's token (act: Courier ← Penny, send:cancel_email, 5 minutes).
   - Three locks: Penny can only read; only Courier's token reaches the send step;
     you confirm each send with a fresh login (one-time, 2 minutes).
   - Send with Gmail and "Confirm by logging in again", in the real UI.
   - Token Vault → a short Google token (gmail.send only) → Gmail sends one email
     → the token is thrown away. Leaves the laptop: only that email.
   - The token inspector, Stop all agents, and the "What Penny did" timeline.
6. Laid to rest; wrap-up.

**YouTube chapters (every chapter is at least 10 seconds):**

```
0:00 What is Ghost Bills?
0:10 Why I made it
0:22 Step 1: Import your bank CSV
0:35 Step 2: Code finds the 4 kinds of ghost
1:07 Step 3: Proof, Gemma and the cancel email
1:32 How the pieces fit: Penny, Ledger, Courier
1:50 Delegation with Auth0 token exchange
2:19 Three locks
2:29 Confirm by logging in again, Token Vault
2:55 Token inspector, Stop all agents, audit log
3:11 Laid to rest, and wrap-up
```

**Audio:** voice track plus a quiet D-minor music box, pad and wind, ducked
under the voice; the mix is at −16 LUFS.
