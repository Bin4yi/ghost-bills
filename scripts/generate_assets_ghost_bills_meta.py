#!/usr/bin/env python3
"""
Ghost Bills - mascot and UI asset generator (Meta Model API, Muse Image)
=======================================================================

Same pictures as generate_assets_ghost_bills.py, made with Meta's
Muse Image model instead of OpenAI.

Important differences from the OpenAI version:
  * Muse Image costs a flat $0.01 per image, so this script makes several
    versions of each picture (--variants, default 4). You pick the best one.
  * Muse Image always returns an OPAQUE image (no transparent background).
    So mascots are drawn on a flat magenta background, and this script cuts
    the background out on your laptop:
       - with rembg (open-source background remover) if it is installed,
       - otherwise with a simple magenta colour key (good enough for
         flat cartoon art with thick outlines).
  * Penny's poses are edits of the base Penny image (reference image), so
    she stays the same cat.

Quick start
-----------
  pip install openai pillow            # required
  pip install "rembg[cpu]"             # optional, cleaner cut-outs
  export MODEL_API_KEY="..."           # from https://dev.meta.ai -> API keys

  python generate_assets_ghost_bills_meta.py --dry-run
  python generate_assets_ghost_bills_meta.py --only penny_base --variants 6
  python generate_assets_ghost_bills_meta.py            # everything
  python generate_assets_ghost_bills_meta.py --pick penny_base=3   # choose version 3

Files go to assets_ghost_bills_meta/:
  <name>_v1.png ... <name>_vN.png   all versions, mascots ALREADY TRANSPARENT
  raw/<name>_vN.png                  the untouched originals from Meta
  <name>.png                         the chosen one (transparent PNG)
  <name>_256.webp etc.               small copies for the web page

Note for your DEV post: these pictures are only decoration. The app's real
work runs on open models (Gemma). Say this honestly in the write-up.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-image-1.0"
PRICE_PER_IMAGE = 0.01          # flat price from Meta's docs (Oct 2026)
DEFAULT_VARIANTS = 4
AUTO_PICK = 3                   # version used as <name>.png until you --pick
DEFAULT_BUDGET_USD = 5.00       # a safety cap; raise it with --budget
OUT_DIR = Path("assets_ghost_bills_meta")
LOG_FILE = OUT_DIR / "cost_log.json"
KEY_COLOR = (255, 0, 255)       # magenta background we ask for

# One shared style line keeps all mascots looking like one family.
STYLE = (
    "Cute spooky mascot sticker, original character design, flat vector "
    "illustration with soft cel shading, thick clean dark-purple outline, "
    "limited palette of moonlight white, deep purple, lantern orange and "
    "ghostly mint green, friendly rounded shapes, big expressive eyes, "
    "centered, full body, no text, no letters, no logos, no watermark, "
    "plain flat solid magenta (#FF00FF) background, nothing else in the background."
)


@dataclass
class Asset:
    name: str
    prompt: str
    size: str = "1024x1024"      # sets the aspect ratio only
    transparent: bool = True     # True = cut out the magenta background
    reference: str | None = None # edit this asset's chosen image instead
    thumbs: tuple[int, ...] = (256, 128)


# ---------------------------------------------------------------------------
# The asset list (same pictures as the OpenAI script)
# ---------------------------------------------------------------------------

ASSETS: list[Asset] = [
    # --- Penny: our guide mascot. Base first, poses are edits of it. ---
    Asset(
        "penny_base",
        "A small round black cat with big moon-yellow eyes, holding a glowing "
        "orange lantern in one paw and a tiny open ledger book under the other "
        "arm, calm clever smile, a little dark-purple scarf. " + STYLE,
    ),
    Asset(
        "penny_happy",
        "Same black cat character, same colors, scarf, lantern and ledger. "
        "Pose: cheerful, eyes smiling, holding up a shiny coin. Meaning: "
        "'money saved'. Keep the plain flat solid magenta (#FF00FF) background, no text.",
        reference="penny_base",
    ),
    Asset(
        "penny_alarm",
        "Same black cat character, same colors, scarf, lantern and ledger. "
        "Pose: alarmed, fur puffed up, tail straight up, wide eyes, pointing "
        "at the ledger. Meaning: 'ghost found'. Keep the plain flat solid magenta (#FF00FF) background, no text.",
        reference="penny_base",
    ),
    Asset(
        "penny_thinking",
        "Same black cat character, same colors, scarf, lantern and ledger. "
        "Pose: thinking, paw under chin, reading the ledger, lantern on the "
        "ground. Meaning: 'checking your bills'. Keep the plain flat solid magenta (#FF00FF) background, no text.",
        reference="penny_base",
    ),
    Asset(
        "penny_question",
        "Same black cat character, same colors, scarf, lantern and ledger. "
        "Pose: head tilted, one paw raised as if asking a polite question, "
        "curious friendly eyes, a small question-mark shape made of glowing "
        "lantern light above her head (a simple shape, not a letter). "
        "Meaning: 'I am not sure, can you help?'. Keep the plain flat solid "
        "magenta (#FF00FF) background, no text.",
        reference="penny_base",
    ),
    Asset(
        "penny_seance",
        "Same black cat character, same colors and scarf. Pose: sitting "
        "calmly with eyes half closed like a fortune teller holding a seance, "
        "both paws resting on a small glowing crystal ball, the lantern beside "
        "her, a few faint wisps of mint-green spirit smoke rising. Keep the "
        "plain flat solid magenta (#FF00FF) background, no text.",
        reference="penny_base",
    ),
    # --- Seance props. ---
    Asset(
        "seance_candles",
        "Three cute cream-white wax candles of different heights standing "
        "together, warm orange flames, a little melted wax dripping, soft "
        "glow around each flame, flat vector illustration with soft cel "
        "shading, thick clean dark-purple outline, centered, no text, no "
        "letters, plain flat solid magenta (#FF00FF) background, nothing else "
        "in the background.",
        thumbs=(256, 128),
    ),
    # --- One ghost per ghost type (matches the detection rules). ---
    Asset(
        "ghost_sleepy",
        "A sleepy little ghost in a nightcap hugging a big wall calendar with "
        "one day circled, eyes closed, snoring bubbles made of shapes only. "
        "Meaning: a yearly plan that will wake up and charge you soon. " + STYLE,
    ),
    Asset(
        "ghost_poltergeist",
        "A mischievous poltergeist ghost with glowing orange eyes throwing a "
        "glowing price tag that shows only an upward arrow symbol, small coins "
        "flying around it. Meaning: a price that went up quietly. Still cute, "
        "not scary for kids. " + STYLE,
    ),
    Asset(
        "ghost_shapeshifter",
        "A sly ghost pulling off a mask shaped like a cute wrapped gift box, "
        "revealing a grinning face underneath that holds a coin. Meaning: a "
        "free trial that turned into a paid plan. No letters on the box. " + STYLE,
    ),
    Asset(
        "ghost_twins",
        "Two identical small ghosts side by side sharing one pair of "
        "headphones, both holding a coin, looking a bit guilty. Meaning: two "
        "subscriptions that do the same job. " + STYLE,
    ),
    # --- The Graveyard (cancelled ghosts rest here). ---
    Asset(
        "gravestone",
        "A single cute rounded gravestone, soft lavender-grey stone with a "
        "few cracks and a little moss, a tiny sleeping ghost curled up "
        "peacefully on top, a small orange marigold at its base, the front of "
        "the stone left completely blank and smooth for text added later, "
        "flat vector, thick clean dark-purple outline, no text, no letters, "
        "no symbols on the stone, plain flat solid magenta (#FF00FF) background.",
        thumbs=(256, 128),
    ),
    Asset(
        "graveyard_strip",
        "Very wide, short scene for the bottom of a web page: a calm, cozy "
        "graveyard at night seen from the side, a row of empty rounded "
        "gravestones with blank fronts, soft mint-green fog, orange marigolds "
        "and small candles, a crescent moon, deep purple sky, peaceful and "
        "cute rather than scary, flat vector style, no text, no letters, no "
        "characters.",
        size="1536x512",
        transparent=False,
        thumbs=(1024, 768),
    ),
    # --- UI pictures. ---
    Asset(
        "logo_mark",
        "Simple app icon mark: a glowing orange lantern with a small ghost "
        "shape inside it holding a coin, bold and readable at small size, flat "
        "vector, dark-purple outline, no text, plain flat solid magenta (#FF00FF) background.",
        thumbs=(256, 128, 64, 32),
    ),
    Asset(
        "bg_haunted_ledger",
        "Wide dark background illustration: a cozy haunted study at night, an "
        "old open ledger book on a desk, a few coins, soft mint-green fog on "
        "the floor, faint floating ghost lights, deep purple and navy tones, "
        "low contrast so text on top stays readable, flat vector style, no "
        "text, no characters in the center.",
        size="1536x1024",
        transparent=False,
        thumbs=(768,),
    ),
    Asset(
        "cover_dev_post",
        "Wide cover illustration for a blog post: a small black cat with a "
        "glowing orange lantern on the left, shining light on cute ghosts "
        "hiding inside a giant open wallet (one sleepy ghost with a calendar, "
        "one ghost throwing a price tag, two twin ghosts sharing headphones), "
        "coins on the ground, and two small gravestones with marigolds in the "
        "background, dark purple night, mint fog, flat vector style, "
        "clean empty space on the right half for a title, no text, no letters.",
        size="1536x1024",
        transparent=False,
        thumbs=(1000,),
    ),
]


# ---------------------------------------------------------------------------
# Cost log
# ---------------------------------------------------------------------------

def load_log() -> dict:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return {"total_usd": 0.0, "calls": [], "picked": {}}


def save_log(log: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, indent=2))


# ---------------------------------------------------------------------------
# Background removal (all local, no network)
# ---------------------------------------------------------------------------

def cut_out(png_bytes: bytes):
    """Return a transparent RGBA PIL image."""
    from PIL import Image

    try:
        from rembg import remove  # open-source; downloads its model once
        return Image.open(io.BytesIO(remove(png_bytes))).convert("RGBA")
    except ImportError:
        pass
    # Fallback: magenta colour key with a soft edge.
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    px = img.load()
    kr, kg, kb = KEY_COLOR
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            dist = abs(r - kr) + abs(g - kg) + abs(b - kb)
            if dist < 90:
                px[x, y] = (r, g, b, 0)
            elif dist < 180:  # soft edge, and remove the pink tint
                alpha = int(255 * (dist - 90) / 90)
                px[x, y] = (r, min(g + (255 - alpha) // 3, 255), b, alpha)
    return img


def make_thumbs(path: Path, sizes: tuple[int, ...]) -> None:
    from PIL import Image

    img = Image.open(path)
    for width in sizes:
        copy = img.copy()
        h = max(1, round(copy.height * width / copy.width))
        copy.resize((width, h), Image.LANCZOS).save(
            path.with_name(f"{path.stem}_{width}.webp"), "WEBP", quality=88
        )


def corners_clear(img) -> bool:
    """True if all 4 corners are fully transparent (background removed)."""
    w, h = img.size
    pts = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]
    return all(img.getpixel(p)[3] == 0 for p in pts)


def save_version(asset: Asset, raw: bytes, index: int) -> Path:
    """Save one version. Transparent assets are cut out right away;
    the untouched original goes to raw/ in case you need it."""
    from PIL import Image

    raw_dir = OUT_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{asset.name}_v{index}.png").write_bytes(raw)
    out = OUT_DIR / f"{asset.name}_v{index}.png"
    if asset.transparent:
        img = cut_out(raw)
        if not corners_clear(img):
            print(f"    ! v{index}: background not fully removed "
                  f"(the model may have ignored the magenta background). "
                  f"Try another version or install rembg.")
        img.save(out, "PNG")
    else:
        Image.open(io.BytesIO(raw)).convert("RGB").save(out, "PNG")
    return out


def finalize(asset: Asset, version_path: Path) -> Path:
    """Copy a chosen version to <name>.png (+ small copies)."""
    from PIL import Image

    out = OUT_DIR / f"{asset.name}.png"
    img = Image.open(version_path)
    img = img.convert("RGBA") if asset.transparent else img.convert("RGB")
    img.save(out, "PNG")
    make_thumbs(out, asset.thumbs)
    return out


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def make_client():
    from openai import OpenAI

    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("Set MODEL_API_KEY first (create one at https://dev.meta.ai -> API keys).")
    return OpenAI(base_url=BASE_URL, api_key=key)  # SDK does not read MODEL_API_KEY itself


def call_api(client, asset: Asset, n: int, low_reasoning: bool):
    common = dict(
        model=MODEL,
        prompt=asset.prompt,
        size=asset.size,
        n=n,
        response_format="b64_json",
        extra_body={
            "output_format": "png",
            "reasoning_strength": "low" if low_reasoning else "high",
            # No web/image search: we want original characters, not look-alikes.
            "tool_enablement": {"enable_image_search": False,
                                "enable_web_search": False,
                                "enable_shell": False},
        },
    )
    if asset.reference:
        ref = OUT_DIR / f"{asset.reference}.png"
        if not ref.exists():
            raise FileNotFoundError(
                f"'{asset.name}' needs '{asset.reference}.png' first. "
                f"Make it and pick a version with --pick {asset.reference}=N."
            )
        # Send the chosen base on its key colour, so edits keep the same background.
        flat = io.BytesIO()
        from PIL import Image
        base = Image.open(ref).convert("RGBA")
        bg = Image.new("RGBA", base.size, KEY_COLOR + (255,))
        bg.alpha_composite(base)
        bg.convert("RGB").save(flat, "PNG")
        flat.seek(0)
        flat.name = "reference.png"
        result = client.images.edit(image=flat, **common)
    else:
        result = client.images.generate(**common)
    return [d.b64_json for d in result.data if getattr(d, "b64_json", None)]


def call_with_retry(client, asset, n, low_reasoning, tries=3):
    import openai

    for attempt in range(1, tries + 1):
        try:
            return call_api(client, asset, n, low_reasoning)
        except openai.BadRequestError as err:
            print(f"    ! request refused ({getattr(err, 'code', '?')}): {err}")
            return []
        except (openai.RateLimitError, openai.APIConnectionError,
                openai.InternalServerError) as err:
            wait = 10 * attempt
            print(f"    ! temporary error, retry {attempt}/{tries} in {wait}s: {err}")
            time.sleep(wait)
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Make Ghost Bills assets with Meta Muse Image.")
    p.add_argument("--variants", type=int, default=DEFAULT_VARIANTS,
                   help="versions per picture, 1-10 (default 4)")
    p.add_argument("--only", nargs="*", default=None, help="make only these asset names")
    p.add_argument("--force", action="store_true", help="remake even if versions exist")
    p.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD,
                   help="safety cap in USD for all runs together (default 5)")
    p.add_argument("--fast", action="store_true", help="reasoning_strength=low (quicker drafts)")
    p.add_argument("--pick", nargs="*", default=None, metavar="NAME=N",
                   help="choose version N as the final image, e.g. --pick penny_base=3")
    p.add_argument("--dry-run", action="store_true", help="show the plan, call nothing")
    args = p.parse_args()

    by_name = {a.name: a for a in ASSETS}
    log = load_log()

    # --- Pick mode: finalize chosen versions, no API calls. ---
    if args.pick:
        for item in args.pick:
            name, _, num = item.partition("=")
            if name not in by_name or not num.isdigit():
                sys.exit(f"Bad --pick value: {item} (use name=N)")
            src = OUT_DIR / f"{name}_v{num}.png"
            if not src.exists():
                sys.exit(f"Missing {src}")
            out = finalize(by_name[name], src)
            log["picked"][name] = int(num)
            save_log(log)
            print(f"picked {src.name} -> {out}")
        return

    n = max(1, min(10, args.variants))
    todo = ASSETS
    if args.only:
        unknown = set(args.only) - set(by_name)
        if unknown:
            sys.exit(f"Unknown asset name(s): {', '.join(sorted(unknown))}")
        todo = [a for a in ASSETS if a.name in args.only]
    if not args.force:
        todo = [a for a in todo if not (OUT_DIR / f"{a.name}_v1.png").exists()]

    spent = log["total_usd"]
    print(f"Model: {MODEL} | {n} version(s) each | folder: {OUT_DIR}/")
    print(f"Already spent: ${spent:.2f} of ${args.budget:.2f} cap")
    print(f"To make: {len(todo)} picture(s) x {n} = {len(todo) * n} images, "
          f"max ${len(todo) * n * PRICE_PER_IMAGE:.2f}\n")
    for a in todo:
        kind = f"edit of {a.reference}" if a.reference else "new"
        cut = "cut-out" if a.transparent else "opaque"
        print(f"  - {a.name:<22} {a.size:<10} {cut:<8} {kind}")
    if args.dry_run or not todo:
        print("\nNothing called." if args.dry_run else "\nAll pictures already have versions.")
        return

    client = make_client()
    for a in todo:
        if spent + n * PRICE_PER_IMAGE > args.budget:
            print(f"\nSTOP: next picture could pass the ${args.budget:.2f} cap. Use --budget.")
            break
        if a.reference and not (OUT_DIR / f"{a.reference}.png").exists():
            print(f"\n> {a.name}: skipped. First run --pick {a.reference}=N to choose the base.")
            continue
        print(f"\n> {a.name}")
        t0 = time.time()
        images = call_with_retry(client, a, n, args.fast)
        if not images:
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for i, b64 in enumerate(images, start=1):
            save_version(a, base64.b64decode(b64), i)
        cost = len(images) * PRICE_PER_IMAGE  # billed only for returned images
        spent += cost
        log["total_usd"] = round(spent, 4)
        log["calls"].append({"asset": a.name, "images": len(images), "usd": cost,
                             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        save_log(log)
        print(f"    saved {len(images)} version(s) | ${cost:.2f} | "
              f"{time.time() - t0:.0f}s | total ${spent:.2f}")
        # Auto-pick version 3 (v1 if fewer came back) so later steps (and the
        # app) have a file; change it any time with --pick name=N.
        if a.name not in log["picked"]:
            pick = AUTO_PICK if len(images) >= AUTO_PICK else 1
            finalize(a, OUT_DIR / f"{a.name}_v{pick}.png")
            log["picked"][a.name] = pick
            save_log(log)
            print(f"    using v{pick} for now -> {a.name}.png (change with --pick {a.name}=N)")

    print(f"\nDone. Total spent: ${spent:.2f}. Look at the _vN files and choose with --pick.")


if __name__ == "__main__":
    main()
