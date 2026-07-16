# Voyager
Series of scripts to be used to extract the best of your Voyager iterations (artblocks collection)
Voyager Capture

Exploration & High-Resolution Export Tool

Automate browsing, rendering, and saving of any Voyager edition across a range of offsets — from quick thumbnail sweeps to fully completed high-resolution exports.

⸻

📦 Installation

1. Python

Python 3.8 or later is required.

Check your version:

python --version

If Python is not installed:
https://www.python.org/downloads/

ℹ On macOS, you may need to use python3 and pip3.

⸻

2. Required Libraries

Install dependencies:

pip install playwright Pillow

Then install Chromium for Playwright:

playwright install chromium

ℹ Run these commands only once.
Pillow is only required if using --jpg, but installing it upfront avoids errors.

⸻

3. Verify Setup

Run:

python -c "from playwright.sync_api import sync_playwright; from PIL import Image; print('OK')"

You should see:

OK

⸻

🧠 The Script

Save the script as:

Voyager_ExplorationCapture.py

All captured images will be written into automatically created subfolders.

⸻

📁 Output Structure

Default structure:

Voyager_064/
  ├── 300_450_1/
  └── 900_1350_3/

* Format: width_height_dp
* Edition numbers are zero-padded:
    * 7 → Voyager_007

⸻

⚙️ Modes of Operation

🎨 Exploration Sweep

* Renders a range of offsets
* Fast, approximate renders
* Ideal for discovering interesting offsets

🖼 High-Resolution Mode

* Uses explicit offset list (--offsets)
* Waits for 100% render completion
* Designed for final outputs

The script automatically selects the mode:

* --offsets → High-resolution mode
* otherwise → Exploration sweep

⸻

🔧 All Options

Token / Edition

Option	Default	Description
--token-id	0	Voyager edition (0–300), mapped internally

⸻

Exploration Sweep

Option	Default	Description
--offset-start	1	First offset
--offset-end	100	Last offset (inclusive)
--offset-step	1	Step size
--wait	12	Seconds per frame (you must adapt it depending on your computer performances)

⸻

High-Resolution Mode

Option	Default	Description
--offsets	—	Explicit offsets list
--from-dir - Extract the remaining offsets in an exploration directory (after deleteing unwanted offsets)
--timeout	600s	Max wait for full render

⸻

Display & Resolution

Option	Default	Description
--width	300	Viewport width
--height	450	Viewport height
--fit-to-screen	off	Scale artwork to viewport
--dp	1	Resolution multiplier

⸻

Rendering

Option	Default	Description
--grainy	off	Skip grain pass (faster)

⸻

Output Format

Option	Default	Description
--jpg	off	Convert PNG → JPG
--jpg-quality	90	JPEG quality (1–95)
--output-dir	auto	Custom output folder

⸻

🚀 Usage Examples

1. Quick Exploration (Edition 64)

adapt the --wait setting to your computer performances

python Voyager_ExplorationCapture.py --token-id 64 --grainy --wait 15 --jpg --offset-start 1 --offset-end 100

→ ~100 images in:

Voyager_064/300_450_1/

For the rare "Close encounter" that allow all objects to appear, I usually run 500 iterations...

⸻

2a. High-Resolution Export from Exploration Directory

After a sweep, prune the exploration directory down to the offsets you actually like (just delete the ones you don't want).
Point the script at that directory with --from-dir: it reads the remaining offset_XXXXX.png/.jpg filenames, extracts the offsets, and re-captures only those in high quality — waiting for each render to hit 100% completion instead of using a fixed wait time.

python Voyager_ExplorationCapture.py --token-id 64 --from-dir Voyager_064/300_450_1 --dp 3 --jpg --jpg-quality 85

→ Output:

Voyager_064/300_450_3/

Note: the output directory is derived from --width/--height/--dp (or --output-dir if you pass one) — it's independent from --from-dir, so your curated exploration directory is never touched or overwritten. --from-dir and --offsets are mutually exclusive.

⸻

2b. High-Resolution Export from Offsets

python Voyager_ExplorationCapture.py --token-id 64 --offsets 31 109 113 --dp 3 --jpg --jpg-quality 85

→ Output:

Voyager_064/300_450_3/

⸻
3. Quick Exploration (Edition 64) for specific display size

adapt the --wait setting to your computer performances

python Voyager_ExplorationCapture.py --token-id 64 --grainy --wait 15 --jpg --fit-to-screen --width 400 --height 400 --offset-start 1 --offset-end 100

→ ~100 images in:

Voyager_064/400_400_1/

Adapt the ration to your setting, and for exploration keep it around 400 pixels (16:9 could be 480:270)

⸻

4. High-Resolution Export for specific display size

python Voyager_ExplorationCapture.py --token-id 64 --offsets 22 26 --fit-to-screen --width 400 --height 400 --dp 3 --jpg --jpg-quality 85

→ Output:

Voyager_064/400_400_3/

Keept the viewport size around 400 pixels and just increase dp...

⸻

5. Custom Output Folder

python Voyager_ExplorationCapture.py --token-id 64 --offsets 12 55 --output-dir ~/Desktop/my_voyager

⸻

🧭 Typical Workflow

1. Run a coarse sweep (grainy, JPG)
2. Identify interesting offsets
3. Export favourites in high resolution:
    * --offsets
    * --dp 3 (or higher for high resolution prints)

⸻

💡 Tips & Notes

* Voyager has 301 editions (0–300) — each with distinct character
* Offsets define starting points in the generative process
* Timeout saves partial render if needed

Image Quality

* JPG (85–90): excellent for most uses
* PNG: recommended for print / lossless (large file size)

Performance

* High-resolution renders can take 60–120 seconds (or much larger for large DP, proceed step by step, until you find the good resolution)
* The script reuses a single browser instance (faster)

Batch

* I usually run the script during night or doing something else, so the rendering time is not very important...

⸻

✨ Conceptual Note

This tool is designed to explore the generative space of Voyager:

* offsets → navigation in latent space
* resolution → scale of emergence
* sweep vs explicit → exploration vs selection

It is both:

* a technical utility
* and a way to interact with the artwork
