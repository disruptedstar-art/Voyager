import asyncio
import os
import re
import argparse
import base64
from PIL import Image
from playwright.async_api import async_playwright

# ── CLI ARGUMENTS ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Capture Voyager ArtBlocks offsets")

parser.add_argument("--token-id",      type=int, default=0,
                    help="Voyager edition number, 0-299 (e.g. 64 → project token 434000064)")
parser.add_argument("--contract",      default="0x99a9b7c1116f9ceeb1652de04d5969cce509b069")
parser.add_argument("--chain",         default="1")
parser.add_argument("--offset-start",  type=int, default=0)
parser.add_argument("--offset-end",    type=int, default=100)
parser.add_argument("--offset-step",   type=int, default=1)
parser.add_argument("--offsets",       type=int, nargs="+", default=None,
                    help="Explicit list of offsets — waits for 100%% completion before saving")
parser.add_argument("--from-dir",      default=None,
                    help="Directory of curated offset_XXXXX.png/.jpg/.webp files (e.g. after pruning a "
                         "sweep) — offsets are extracted from the filenames and captured the same "
                         "way as --offsets, saved to the standard Voyager_<id>/<w>_<h>_<dp> output "
                         "dir (or --output-dir if given). Mutually exclusive with --offsets.")
parser.add_argument("--wait",          type=float, default=12.0,
                    help="Max seconds to wait for render in sweep mode; capture happens "
                         "earlier if the artwork reports completion (default: 12)")
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
parser.add_argument("--webp",          action="store_true",
                    help="Convert captured PNGs to WebP and remove the PNG (smaller files)")
parser.add_argument("--webp-quality",  type=int, default=80,
                    help="WebP compression quality 0-100 (default: 80, visually close to "
                         "JPG 90 and noticeably smaller)")

parser.add_argument("--overwrite",     action="store_true",
                    help="Recapture offsets whose output file already exists "
                         "(by default they are skipped, so an interrupted run can be resumed)")
parser.add_argument("--retries",       type=int, default=2,
                    help="Extra attempts per offset after an error before moving on (default: 2)")
parser.add_argument("--nav-timeout",   type=float, default=60.0,
                    help="Max seconds to wait for the page to load (default: 60)")
parser.add_argument("--workers",       type=int, default=1,
                    help="Number of offsets captured in parallel, one browser tab each (default: 1)")

args = parser.parse_args()

if not (0 <= args.token_id <= 299):
    parser.error("--token-id must be a Voyager edition number between 0 and 299")

if args.jpg and args.webp:
    parser.error("--jpg and --webp are mutually exclusive")

if args.offsets is not None and args.from_dir is not None:
    parser.error("--offsets and --from-dir are mutually exclusive")


def extract_offsets_from_dir(directory: str) -> list[int]:
    """Scan `directory` for offset_XXXXX.(png|jpg|jpeg|webp) or
    Voyager_NNN_offset_XXXXX_DPY.(png|jpg|jpeg|webp) files and return the sorted,
    de-duplicated list of offsets found in the filenames."""
    if not os.path.isdir(directory):
        parser.error(f"--from-dir '{directory}' is not a directory")

    pattern = re.compile(r"^(?:Voyager_\d+_)?offset_(\d+)(?:_DP\d+)?\.(png|jpe?g|webp)$",
                         re.IGNORECASE)
    offsets = set()
    for fname in os.listdir(directory):
        m = pattern.match(fname)
        if m:
            offsets.add(int(m.group(1)))

    if not offsets:
        parser.error(f"No offset_XXXXX.png/.jpg/.webp files found in '{directory}'")

    return sorted(offsets)


if args.from_dir is not None:
    args.offsets = extract_offsets_from_dir(args.from_dir)
    print(f"Extracted {len(args.offsets)} offsets from '{args.from_dir}': {args.offsets}")

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


OUT_EXT = "jpg" if args.jpg else "webp" if args.webp else "png"


def output_stem(offset: int) -> str:
    return os.path.join(
        OUTPUT_DIR, f"Voyager_{args.token_id:03d}_offset_{offset:05d}_DP{args.dp}"
    )


def already_captured(offset: int) -> bool:
    return os.path.exists(f"{output_stem(offset)}.{OUT_EXT}")


def convert_png(png_path: str, offset: int):
    """Convert a PNG to JPG/WebP, remove the PNG. Written to a temp file first so an
    interrupted run never leaves a truncated image that would be skipped on resume."""
    out_path = f"{output_stem(offset)}.{OUT_EXT}"
    tmp_path = out_path + ".part"
    with Image.open(png_path) as img:
        rgb = img.convert("RGB")  # drop alpha channel if any
        if args.jpg:
            rgb.save(tmp_path, "JPEG", quality=args.jpg_quality, optimize=True)
        else:
            rgb.save(tmp_path, "WEBP", quality=args.webp_quality, method=6)
    os.replace(tmp_path, out_path)
    os.remove(png_path)
    out_kb = os.path.getsize(out_path) / 1024
    print(f"  [{offset:05d}] ✓ → {out_path} ({out_kb:.0f} KB)")


async def capture_and_save(page, offset: int):
    png_path = f"{output_stem(offset)}.png"
    tmp_path = png_path + ".part"

    saved = await page.evaluate("""() => {
        const canvas = document.querySelector('canvas');
        if (!canvas) return null;
        return canvas.toDataURL('image/png');
    }""")

    if saved:
        data = saved.split(",", 1)[1]
        raw = base64.b64decode(data)
        with open(tmp_path, "wb") as f:
            f.write(raw)
        os.replace(tmp_path, png_path)
        png_kb = len(raw) / 1024
        print(f"  [{offset:05d}] ✓ Canvas export → {png_path} ({png_kb:.0f} KB)")
    else:
        await page.screenshot(path=tmp_path, full_page=True, type="png")
        os.replace(tmp_path, png_path)
        print(f"  [{offset:05d}] ✓ Screenshot fallback → {png_path}")

    if args.jpg or args.webp:
        convert_png(png_path, offset)


async def render_and_capture(page, offset: int, max_wait: float, show_progress: bool):
    """Load the offset and capture as soon as the artwork reports completion in the
    browser console, or after `max_wait` seconds, whichever comes first."""
    done = asyncio.Event()

    def on_console(msg):
        console_args = msg.args
        # Format: ['%d % (%d s)', '<percent>', '<seconds>']
        if len(console_args) >= 3:
            async def check():
                try:
                    pct  = await console_args[1].json_value()
                    secs = await console_args[2].json_value()
                    if show_progress:
                        print(f"  [{offset:05d}] {pct} % ({secs} s)")
                    if int(pct) == 100 or int(pct) == 99:
                        done.set()
                except Exception:
                    pass
            asyncio.create_task(check())

    page.on("console", on_console)
    try:
        url = build_url(offset)
        print(f"  [{offset:05d}] → {url}")
        await page.goto(url, timeout=args.nav_timeout * 1000)
        start = asyncio.get_running_loop().time()

        try:
            await asyncio.wait_for(done.wait(), timeout=max_wait)
            elapsed = asyncio.get_running_loop().time() - start
            print(f"  [{offset:05d}] ✓ Render complete after {elapsed:.1f}s")
        except asyncio.TimeoutError:
            print(f"  [{offset:05d}] ⚠ Not complete after {max_wait}s — saving whatever is rendered")
    finally:
        page.remove_listener("console", on_console)

    await page.wait_for_timeout(500)
    await capture_and_save(page, offset)


async def capture_sweep(page, offset: int):
    """Capture when the render completes, or after --wait seconds at most."""
    await render_and_capture(page, offset, args.wait, show_progress=False)


async def capture_hires(page, offset: int):
    """Capture when the render completes, or after --timeout seconds at most."""
    await render_and_capture(page, offset, args.timeout, show_progress=True)


async def new_page(browser):
    context = await browser.new_context(
        viewport={"width": args.width, "height": args.height},
        device_scale_factor=1,
    )
    return context, await context.new_page()


async def worker(browser, queue: asyncio.Queue, capture, failed: list):
    """Pull offsets from the queue until empty. Each offset gets 1 + --retries attempts;
    after a failure the page is recreated (it may have crashed) and the next offset
    is processed instead of aborting the whole run."""
    context, page = await new_page(browser)
    while True:
        try:
            offset = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        attempts = args.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                await capture(page, offset)
                break
            except Exception as e:
                reason = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
                print(f"  [{offset:05d}] ✗ Attempt {attempt}/{attempts} failed: {reason}")
                try:
                    await context.close()
                except Exception:
                    pass
                context, page = await new_page(browser)
        else:
            failed.append(offset)
    await context.close()


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.offsets is not None:
        offsets = args.offsets
        mode = f"explicit list {offsets} — waiting for 100% completion"
        capture = capture_hires
    else:
        offsets = list(range(args.offset_start, args.offset_end + 1, args.offset_step))
        mode = f"sweep {args.offset_start}→{args.offset_end} step {args.offset_step} — capture on completion, max {args.wait}s"
        capture = capture_sweep

    flags = []
    if args.fit_to_screen: flags.append("fitToScreen=true")
    if args.grainy:        flags.append("grainy=true")
    flags.append(f"DP={args.dp}")

    if args.jpg:
        fmt = f"JPG (quality {args.jpg_quality})"
    elif args.webp:
        fmt = f"WebP (quality {args.webp_quality})"
    else:
        fmt = "PNG"

    print(f"Voyager #{args.token_id} (token {FULL_TOKEN_ID})")
    print(f"Capturing {len(offsets)} offsets | {mode} | "
          f"{args.width}×{args.height}px | {' '.join(flags)} | {fmt}"
          f" → '{OUTPUT_DIR}/'")

    if args.overwrite:
        todo = offsets
    else:
        todo = [o for o in offsets if not already_captured(o)]
        skipped = len(offsets) - len(todo)
        if skipped:
            print(f"Skipping {skipped} offsets already captured (use --overwrite to redo them)")

    if not todo:
        print("\nNothing to do — all offsets already captured.")
        return

    queue = asyncio.Queue()
    for o in todo:
        queue.put_nowait(o)
    n_workers = max(1, min(args.workers, len(todo)))
    print(f"{len(todo)} offsets to capture with {n_workers} worker(s)\n")

    failed = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        await asyncio.gather(*(worker(browser, queue, capture, failed)
                               for _ in range(n_workers)))
        await browser.close()

    print(f"\nDone! {len(todo) - len(failed)}/{len(todo)} images saved to '{OUTPUT_DIR}/'")
    if failed:
        failed.sort()
        print(f"⚠ {len(failed)} offsets failed: {' '.join(map(str, failed))}")
        print("  Re-run the same command to retry them (captured offsets are skipped).")


asyncio.run(main())
