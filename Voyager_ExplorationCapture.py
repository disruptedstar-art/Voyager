import asyncio
import os
import argparse
import base64
from PIL import Image
from playwright.async_api import async_playwright

# ── CLI ARGUMENTS ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Capture Voyager ArtBlocks offsets")

parser.add_argument("--token-id",      type=int, default=0,
                    help="Voyager edition number, 0-300 (e.g. 64 → project token 434000064)")
parser.add_argument("--contract",      default="0x99a9b7c1116f9ceeb1652de04d5969cce509b069")
parser.add_argument("--chain",         default="1")
parser.add_argument("--offset-start",  type=int, default=0)
parser.add_argument("--offset-end",    type=int, default=100)
parser.add_argument("--offset-step",   type=int, default=1)
parser.add_argument("--offsets",       type=int, nargs="+", default=None,
                    help="Explicit list of offsets — waits for 100%% completion before saving")
parser.add_argument("--wait",          type=float, default=12.0,
                    help="Seconds to wait for render in sweep mode (default: 12)")
parser.add_argument("--timeout",       type=float, default=600.0,
                    help="Max seconds to wait for 100%% completion in explicit mode (default: 600)")
parser.add_argument("--output-dir",    default=None,
                    help="Output directory (default: Voyager_<id>/<width>_<height>_<dp>)")

parser.add_argument("--width",         type=int, default=300, help="Viewport width in px")
parser.add_argument("--height",        type=int, default=450, help="Viewport height in px")

parser.add_argument("--fit-to-screen", action="store_true",
                    help="Append &fitToScreen=true to URLs")
parser.add_argument("--grainy",        action="store_true",
                    help="Append &grainy=true to URLs (speeds up rendering)")
parser.add_argument("--dp",            type=int, default=1,
                    help="Device pixel ratio passed to the artwork as &DP=X (default: 1)")
parser.add_argument("--jpg",           action="store_true",
                    help="Convert captured PNGs to JPG and remove the PNG (smaller files)")
parser.add_argument("--jpg-quality",   type=int, default=90,
                    help="JPG compression quality 1-95 (default: 90)")

args = parser.parse_args()

if not (0 <= args.token_id <= 300):
    parser.error("--token-id must be a Voyager edition number between 0 and 300")

FULL_TOKEN_ID = f"434000{args.token_id:03d}"

OUTPUT_DIR = args.output_dir or os.path.join(
    f"Voyager_{args.token_id:03d}",
    f"{args.width}_{args.height}_{args.dp}"
)
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = f"https://generator.artblocks.io/{args.chain}/{args.contract}/{FULL_TOKEN_ID}"


def build_url(offset: int) -> str:
    params = [f"offset={offset}"]
    if args.fit_to_screen:
        params.append("fitToScreen=true")
    if args.grainy:
        params.append("grainy=true")
    params.append(f"DP={args.dp}")
    return BASE_URL + "?" + "&".join(params)


def png_to_jpg(png_path: str):
    """Convert a PNG to JPG, remove the PNG."""
    jpg_path = os.path.splitext(png_path)[0] + ".jpg"
    with Image.open(png_path) as img:
        rgb = img.convert("RGB")  # drop alpha channel if any
        rgb.save(jpg_path, "JPEG", quality=args.jpg_quality, optimize=True)
    os.remove(png_path)
    png_kb  = 0  # already deleted, size was checked before
    jpg_kb  = os.path.getsize(jpg_path) / 1024
    print(f"     ✓ → {jpg_path} ({jpg_kb:.0f} KB)")


async def capture_and_save(page, offset: int):
    png_path = os.path.join(OUTPUT_DIR, f"offset_{offset:05d}.png")

    saved = await page.evaluate("""() => {
        const canvas = document.querySelector('canvas');
        if (!canvas) return null;
        return canvas.toDataURL('image/png');
    }""")

    if saved:
        data = saved.split(",", 1)[1]
        raw = base64.b64decode(data)
        with open(png_path, "wb") as f:
            f.write(raw)
        png_kb = len(raw) / 1024
        if args.jpg:
            print(f"     ✓ Canvas export → {png_path} ({png_kb:.0f} KB) — converting…")
            png_to_jpg(png_path)
        else:
            print(f"     ✓ Canvas export → {png_path} ({png_kb:.0f} KB)")
    else:
        await page.screenshot(path=png_path, full_page=True)
        print(f"     ✓ Screenshot fallback → {png_path}")
        if args.jpg:
            png_to_jpg(png_path)


async def capture_sweep(page, offset: int):
    """Fixed wait — don't care if render is complete."""
    url = build_url(offset)
    print(f"  → {url}")
    await page.goto(url)
    await page.wait_for_timeout(int(args.wait * 1000))
    await capture_and_save(page, offset)


async def capture_hires(page, offset: int):
    """Wait for the 100% completion line in the browser console."""
    done = asyncio.Event()

    def on_console(msg):
        console_args = msg.args
        # Format: ['%d % (%d s)', '<percent>', '<seconds>']
        if len(console_args) >= 3:
            async def check():
                try:
                    pct  = await console_args[1].json_value()
                    secs = await console_args[2].json_value()
                    print(f"     {pct} % ({secs} s)")
                    if int(pct) == 100 or int(pct) == 99: # sometimes 100 does not appear, do not know why
                        done.set()
                except Exception:
                    pass
            asyncio.create_task(check())

    page.on("console", on_console)

    url = build_url(offset)
    print(f"  → {url}")
    await page.goto(url)

    try:
        await asyncio.wait_for(done.wait(), timeout=args.timeout)
        print(f"     ✓ Render complete")
    except asyncio.TimeoutError:
        print(f"     ⚠ Timeout after {args.timeout}s — saving whatever is rendered")

    page.remove_listener("console", on_console)
    await page.wait_for_timeout(500)
    await capture_and_save(page, offset)


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.offsets is not None:
        offsets = args.offsets
        mode = f"explicit list {offsets} — waiting for 100% completion"
    else:
        offsets = list(range(args.offset_start, args.offset_end + 1, args.offset_step))
        mode = f"sweep {args.offset_start}→{args.offset_end} step {args.offset_step} — fixed {args.wait}s wait"

    flags = []
    if args.fit_to_screen: flags.append("fitToScreen=true")
    if args.grainy:        flags.append("grainy=true")
    flags.append(f"DP={args.dp}")

    fmt = f"JPG (quality {args.jpg_quality})" if args.jpg else "PNG"

    print(f"Voyager #{args.token_id} (token {FULL_TOKEN_ID})")
    print(f"Capturing {len(offsets)} offsets | {mode} | "
          f"{args.width}×{args.height}px | {' '.join(flags)} | {fmt}"
          f" → '{OUTPUT_DIR}/'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )
        page = await context.new_page()

        if args.offsets is not None:
            for offset in offsets:
                await capture_hires(page, offset)
        else:
            for offset in offsets:
                await capture_sweep(page, offset)

        await browser.close()

    print(f"\nDone! {len(offsets)} images saved to '{OUTPUT_DIR}/'")


asyncio.run(main())
