# Voyager Exploration Capture

`Voyager_ExplorationCapture.py` captures images of **Voyager** (Art Blocks, by DisruptedStar) directly from the official Art Blocks generator. It loads each edition in a headless Chromium browser, varies the `offset` parameter that the artwork reads from its URL, and saves what the canvas draws as PNG, JPG or WebP.

It is designed for exploration at scale: sweep hundreds of offsets quickly at low resolution, keep the ones you like, then re-render only those at high resolution.

---

## Contents

- [Requirements](#requirements)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [The two capture modes](#the-two-capture-modes)
- [Recommended workflow](#recommended-workflow)
- [All options](#all-options)
- [Output files and folders](#output-files-and-folders)
- [Image formats and file size](#image-formats-and-file-size)
- [Resuming an interrupted run](#resuming-an-interrupted-run)
- [Error handling and retries](#error-handling-and-retries)
- [Parallel capture](#parallel-capture)
- [Reading the log](#reading-the-log)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Requirements

- Python 3.9 or later
- [Playwright for Python](https://playwright.dev/python/) with Chromium
- [Pillow](https://python-pillow.org/), with WebP support if you use `--webp` (included in standard wheels)

```bash
pip install playwright pillow
playwright install chromium
```

An internet connection is required: every image is rendered by `generator.artblocks.io`.

---

## Quick start

```bash
# Sweep offsets 0 to 100 of Voyager #64 at 300×450, saved as WebP
python Voyager_ExplorationCapture.py --token-id 64 --webp

# Re-render three chosen offsets at DP 9, waiting for the full render
python Voyager_ExplorationCapture.py --token-id 64 --offsets 12 37 81 --dp 9 --webp
```

Run `python Voyager_ExplorationCapture.py --help` to list every option.

---

## How it works

For each offset, the script:

1. Builds the generator URL of the chosen edition:
   ```
   https://generator.artblocks.io/<chain>/<contract>/434000NNN?offset=X[&fitToScreen=true][&grainy=true]&DP=Y
   ```
   `NNN` is the edition number (`--token-id 64` → token `434000064`).
2. Opens it in a headless Chromium tab with the requested viewport (`--width` × `--height`).
3. Listens to the browser console, where the artwork reports its progress as `<percent> % (<seconds> s)`.
4. Captures as soon as the render reports completion (99 % or 100 %), or when the maximum wait is reached, whichever comes first.
5. Exports the `<canvas>` content losslessly with `canvas.toDataURL()`. If no canvas is found, it falls back to a full-page screenshot.
6. Optionally converts the PNG to JPG or WebP and deletes the PNG.

Resolution is controlled by the artwork itself through `DP`, not by the browser (whose device scale factor stays at 1). With the default 300×450 viewport, the exported images measure:

| DP | Image size |
|---|---|
| 1 | 600 × 900 |
| 3 | 1800 × 2700 |
| 9 | 5400 × 8100 |

i.e. `2 × DP × viewport`.

---

## The two capture modes

| | **Sweep mode** | **Explicit mode** |
|---|---|---|
| Selected by | `--offset-start`, `--offset-end`, `--offset-step` (default) | `--offsets …` or `--from-dir DIR` |
| Purpose | Fast exploration of many offsets | Final, high-resolution renders |
| Maximum wait per offset | `--wait` (default 12 s) | `--timeout` (default 600 s) |
| Progress log | Completion line only | Every progress line from the artwork |

In both modes the script stops waiting as soon as the artwork reports completion, so a large `--wait` or `--timeout` never slows down offsets that finish quickly. If the limit is reached, whatever is on the canvas is saved and the log says so.

### `--from-dir`

`--from-dir DIR` reads the offsets from the filenames of an existing folder, so you never have to type a list. Both naming schemes are recognised:

```
offset_00037.jpg                       (legacy)
Voyager_064_offset_00037_DP1.webp      (current)
```

Extensions `.png`, `.jpg`, `.jpeg` and `.webp` are accepted. `--from-dir` and `--offsets` cannot be used together.

---

## Recommended workflow

1. **Sweep** a wide range at low resolution:
   ```bash
   python Voyager_ExplorationCapture.py --token-id 64 --offset-end 300 --grainy --webp --workers 4
   ```
   Output: `Voyager_064/300_450_1/`
2. **Prune** the folder by hand: delete every image you don't want to keep.
3. **Re-render** the survivors at high resolution, using the pruned folder as the list of offsets:
   ```bash
   python Voyager_ExplorationCapture.py --token-id 64 --from-dir Voyager_064/300_450_1 --dp 9 --webp --workers 2
   ```
   Output: `Voyager_064/300_450_9/`

Because each resolution goes to its own folder, the curated low-resolution folder is left untouched and can be reused for another DP later.

---

## All options

### Artwork selection

| Option | Default | Description |
|---|---|---|
| `--token-id N` | `0` | Voyager edition number, **0 to 299**. Mapped to the Art Blocks token `434000NNN`. |
| `--contract ADDR` | `0x99a9b7c1116f9ceeb1652de04d5969cce509b069` | Art Blocks contract address. |
| `--chain ID` | `1` | Chain ID used in the generator URL (1 = Ethereum mainnet). |

### Offsets

| Option | Default | Description |
|---|---|---|
| `--offset-start N` | `0` | First offset of the sweep. |
| `--offset-end N` | `100` | Last offset of the sweep (inclusive). |
| `--offset-step N` | `1` | Step between offsets in the sweep. |
| `--offsets N [N …]` | — | Explicit list of offsets. Switches to explicit mode. |
| `--from-dir DIR` | — | Take the offsets from the image filenames in `DIR`. Switches to explicit mode. |

### Rendering

| Option | Default | Description |
|---|---|---|
| `--width PX` | `300` | Browser viewport width. |
| `--height PX` | `450` | Browser viewport height. |
| `--dp N` | `1` | Resolution multiplier passed to the artwork as `&DP=N`. |
| `--fit-to-screen` | off | Adds `&fitToScreen=true` to the URL. |
| `--grainy` | off | Adds `&grainy=true` to the URL. Faster rendering, handy for sweeps. |

### Timing

| Option | Default | Description |
|---|---|---|
| `--wait S` | `12` | Sweep mode: maximum seconds to wait for completion. |
| `--timeout S` | `600` | Explicit mode: maximum seconds to wait for completion. |
| `--nav-timeout S` | `60` | Maximum seconds for the generator page itself to load. |

### Output

| Option | Default | Description |
|---|---|---|
| `--output-dir DIR` | `Voyager_NNN/<width>_<height>_<dp>` | Where images are saved. |
| `--jpg` | off | Convert to JPG and delete the PNG. |
| `--jpg-quality Q` | `90` | JPG quality, 1 to 95. |
| `--webp` | off | Convert to WebP and delete the PNG. |
| `--webp-quality Q` | `80` | WebP quality, 0 to 100. |
| `--overwrite` | off | Re-capture offsets whose output file already exists. |

`--jpg` and `--webp` are mutually exclusive. Without either, images are kept as PNG.

### Robustness and speed

| Option | Default | Description |
|---|---|---|
| `--retries N` | `2` | Extra attempts per offset after an error before moving on. |
| `--workers N` | `1` | Number of offsets captured in parallel, one browser tab each. |

---

## Output files and folders

By default images go to:

```
Voyager_<NNN>/<width>_<height>_<dp>/Voyager_<NNN>_offset_<XXXXX>_DP<dp>.<ext>
```

For example, `--token-id 64 --dp 9 --webp` on offset 37 produces:

```
Voyager_064/300_450_9/Voyager_064_offset_00037_DP9.webp
```

- `NNN` is the edition number, zero-padded to 3 digits.
- `XXXXX` is the offset, zero-padded to 5 digits, so files sort correctly.
- `DP` is not padded (`DP1`, `DP9`, `DP12`).

The full name is self-describing: a file copied anywhere still says which edition, offset and resolution it is.

---

## Image formats and file size

Capture is always lossless PNG first; `--jpg` or `--webp` then re-encodes it.

Measured on Voyager images (size relative to the same image as PNG):

| Image size | JPG q90 | WebP q80 |
|---|---|---|
| 600×900 | 23 % | 17 % |
| 1800×2700 | 22 % | 14 % |
| 5400×8100 | 16 % | 6 % |

Quality numbers are not comparable between formats: WebP 80 is visually close to JPG 90 while being noticeably smaller, especially at high DP. If fine grain matters, check a full-size render and raise `--webp-quality` to 85 or 90.

Alpha is dropped when converting to JPG or WebP.

---

## Resuming an interrupted run

Before starting, the script checks which output files already exist in the selected format and skips those offsets:

```
Skipping 142 offsets already captured (use --overwrite to redo them)
```

So after a crash, a closed laptop or Ctrl-C, simply run **the same command again**. Files are written to a temporary `.part` file and renamed only when complete, so an interrupted run never leaves a truncated image that would wrongly count as done.

Use `--overwrite` to force every offset to be captured again.

Only the current naming scheme (`Voyager_NNN_offset_XXXXX_DPY`) is checked. Legacy `offset_XXXXX` files are not recognised as already captured.

---

## Error handling and retries

A single failure no longer stops the run. When loading or capturing an offset fails (page load timeout, browser tab crash, network error):

1. The error is logged with its attempt number.
2. The tab is closed and a fresh one is opened.
3. The offset is retried, up to `--retries` extra times.
4. If every attempt fails, the offset is recorded and the script moves on.

At the end, failed offsets are listed:

```
Done! 98/100 images saved to 'Voyager_064/300_450_1/'
⚠ 2 offsets failed: 17 63
  Re-run the same command to retry them (captured offsets are skipped).
```

Thanks to resume, re-running the same command retries only those offsets.

---

## Parallel capture

`--workers N` opens N browser tabs, each pulling the next offset from a shared queue.

- **Sweeps** benefit most: with `--grainy` and small viewports, 4 to 8 workers usually work well.
- **High-resolution renders** are CPU and GPU heavy; several at once can slow each one down. Start with 2 or 3 and watch render times in the log.

Each log line is prefixed with its offset, e.g. `[00037]`, so interleaved output stays readable.

---

## Reading the log

Example (timings and sizes are illustrative):

```
Voyager #64 (token 434000064)
Capturing 3 offsets | explicit list [12, 37, 81] — waiting for 100% completion | 300×450px | DP=9 | WebP (quality 80) → 'Voyager_064/300_450_9/'
3 offsets to capture with 1 worker(s)

  [00012] → https://generator.artblocks.io/1/0x99a9…b069/434000064?offset=12&DP=9
  [00012] 25 % (14 s)
  [00012] 100 % (52 s)
  [00012] ✓ Render complete after 52.3s
  [00012] ✓ Canvas export → Voyager_064/300_450_9/Voyager_064_offset_00012_DP9.png (31250 KB)
  [00012] ✓ → Voyager_064/300_450_9/Voyager_064_offset_00012_DP9.webp (2810 KB)
```

| Symbol | Meaning |
|---|---|
| `→` | Page requested, or converted file written |
| `✓ Render complete after Xs` | The artwork reported completion |
| `⚠ Not complete after Xs` | Maximum wait reached; the current canvas was saved anyway |
| `✓ Canvas export` | Lossless export of the canvas |
| `✓ Screenshot fallback` | No canvas found; a page screenshot was saved instead |
| `✗ Attempt i/n failed` | An error occurred; the offset will be retried or recorded as failed |

---

## Examples

```bash
# Every 5th offset from 0 to 500, quick grainy preview
python Voyager_ExplorationCapture.py --token-id 31 --offset-end 500 --offset-step 5 --grainy --webp --workers 6

# A slow-rendering edition: allow up to 30 s per offset in the sweep
python Voyager_ExplorationCapture.py --token-id 138 --offset-end 50 --wait 30 --jpg

# Landscape viewport
python Voyager_ExplorationCapture.py --token-id 41 --fit-to-screen --width 450 --height 300 --offsets 7 34 --dp 1 --webp

# High-res from a curated folder, into a custom output folder
python Voyager_ExplorationCapture.py --token-id 41 --from-dir Voyager_041/300_450_1 --dp 9 --webp --output-dir prints/041

# Redo everything in a folder, ignoring existing files
python Voyager_ExplorationCapture.py --token-id 64 --from-dir Voyager_064/300_450_1 --dp 3 --overwrite
```

---

## Troubleshooting

**`--token-id must be a Voyager edition number between 0 and 299`**
Editions are numbered from 0, so the last one is #299.

**Every render ends with `⚠ Not complete after …`**
The maximum wait is too short for this edition or DP. Raise `--wait` (sweep) or `--timeout` (explicit), or reduce `--workers` so renders don't compete for the CPU.

**`✗ Attempt … failed: Timeout 60000ms exceeded`**
The generator page itself didn't load in time. Check your connection or raise `--nav-timeout`.

**`✓ Screenshot fallback` instead of `Canvas export`**
No `<canvas>` was found on the page. The screenshot is limited to the viewport size and is not affected by `DP`.

**Nothing happens: `Nothing to do — all offsets already captured.`**
All output files already exist. Use `--overwrite`, or a different `--dp`, `--output-dir` or format.

**`--webp` fails with an encoder error**
Your Pillow build lacks WebP support. Check with `python -c "from PIL import features; print(features.check('webp'))"` and reinstall Pillow from the standard wheels if it prints `False`.
