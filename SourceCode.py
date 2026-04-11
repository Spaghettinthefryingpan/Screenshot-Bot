from cProfile import label
import customtkinter as ctk
from threading import Thread
import pyautogui
import time
import numpy as np
import cv2
from PIL import Image, ImageTk
import os
import logging
from typing import Optional, Tuple, List

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

screen_width, screen_height = pyautogui.size()

# ---------- DEFAULT SETTINGS ----------
SETTINGS = {
    "max_shots": 300,
    "overlap_check_height": 350,
    "diff_threshold": 4,
    "slice_height": 2000,
    "same_image_threshold": 2,
}

OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "shots")
FINAL_IMAGE = os.path.join(os.path.dirname(__file__), "comic_clean.png")

running = False

# ---------- UI HELPERS ----------
def update_preview():
    try:
        if region_toggle.get():
            x = int(x_entry.get())
            y = int(y_entry.get())
            w = int(w_entry.get())
            h = int(h_entry.get())

            if x < 0 or y < 0 or w <= 0 or h <= 0:
                update_status("Invalid preview region")
                return

            region = (x, y, w, h)
            img = take_screenshot(region)
        else:
            img = take_screenshot()

        if img is None:
            update_status("Preview failed")
            return

        # Resize preview to fit UI
        img = img.resize((320, 200))

        img_tk = ImageTk.PhotoImage(img)
        preview_label.configure(image=img_tk, text="")
        preview_label.image = img_tk  # prevent garbage collection

        update_status("Preview updated")

    except Exception as e:
        update_status(f"Preview error: {e}")

def update_status(msg):
    status_label.configure(text=msg)
    logger.info(msg)
    app.update()

def update_progress(val):
    progress.set(val)
    app.update()

# ---------- IMAGE PROCESSING HELPERS ----------
def take_screenshot(region: Optional[Tuple] = None):
    """Take a screenshot of the full screen or a region."""
    try:
        if region:
            return pyautogui.screenshot(region=region)
        return pyautogui.screenshot()
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None

def images_similar(img1, img2, threshold: int) -> bool:
    """Check if two images are similar within threshold."""
    try:
        arr1 = np.array(img1).astype("int16")
        arr2 = np.array(img2).astype("int16")
        return np.mean(np.abs(arr1 - arr2)) < threshold
    except Exception as e:
        logger.error(f"Similarity check failed: {e}")
        return False

def find_overlap(img1, img2, check_height: int) -> int:
    """Find the best overlap offset between two images."""
    try:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        h = check_height
        crop1 = gray1[-h:]
        crop2 = gray2[:h]

        best_offset = 0
        best_score = float('inf')

        for offset in range(h):
            part1 = crop1[offset:]
            part2 = crop2[:h-offset]

            if part1.shape != part2.shape:
                continue

            diff = np.mean((part1 - part2) ** 2)

            if diff < best_score:
                best_score = diff
                best_offset = offset

        return best_offset
    except Exception as e:
        logger.error(f"Overlap detection failed: {e}")
        return 0

def stitch_images(files: List[str], check_height: int) -> Optional[str]:
    """Stitch multiple images together with overlap detection."""
    try:
        images = [cv2.imread(f) for f in files if os.path.exists(f)]

        if not images:
            logger.warning("No valid images to stitch")
            return None

        # Ensure all images have the same width
        width = images[0].shape[1]
        for i in range(1, len(images)):
            if images[i].shape[1] != width:
                images[i] = cv2.resize(images[i], (width, images[i].shape[0]))

        stitched = images[0]

        for i in range(1, len(images)):
            if not running:
                logger.info("Stitching cancelled")
                return None

            prev = images[i - 1]
            curr = images[i]

            overlap = find_overlap(prev, curr, check_height)

            if 0 < overlap < curr.shape[0]:
                stitched = np.vstack((stitched, curr[overlap:]))
            else:
                stitched = np.vstack((stitched, curr))

        final = Image.fromarray(cv2.cvtColor(stitched, cv2.COLOR_BGR2RGB))
        final.save(FINAL_IMAGE)
        logger.info(f"Stitched image saved to {FINAL_IMAGE}")
        return FINAL_IMAGE
    except Exception as e:
        logger.error(f"Image stitching failed: {e}")
        return None

def split_image(image_path: str, slice_height: int) -> List[str]:
    """Split a large image into pages."""
    try:
        img = Image.open(image_path)
        width, height = img.size

        pages = []
        for i, y in enumerate(range(0, height, slice_height)):
            piece = img.crop((0, y, width, min(y + slice_height, height)))
            filename = os.path.join(os.path.dirname(__file__), f"page_{i}.png")
            piece.save(filename)
            pages.append(filename)

        logger.info(f"Image split into {len(pages)} pages")
        return pages
    except Exception as e:
        logger.error(f"Image splitting failed: {e}")
        return []

def make_pdf(pages: List[str]) -> None:
    """Create a PDF from image pages."""
    try:
        images = [Image.open(p).convert("RGB") for p in pages if os.path.exists(p)]
        if images:
            pdf_path = os.path.join(os.path.dirname(__file__), "comic.pdf")
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
            logger.info(f"PDF created: {pdf_path}")
    except Exception as e:
        logger.error(f"PDF creation failed: {e}")


# ---------- MAIN CAPTURE FUNCTION ----------
def run_capture(scroll_amount: float, delay: float, region: Optional[Tuple]) -> None:
    """Main capture loop with image stitching."""
    global running
    running = True

    try:
        max_shots = int(max_shots_entry.get()) if max_shots_entry.get() else SETTINGS["max_shots"]
        threshold = int(diff_threshold_entry.get()) if diff_threshold_entry.get() else SETTINGS["diff_threshold"]
        same_threshold = int(same_threshold_entry.get()) if same_threshold_entry.get() else SETTINGS["same_image_threshold"]
        check_height = int(check_height_entry.get()) if check_height_entry.get() else SETTINGS["overlap_check_height"]
        slice_height = int(slice_height_entry.get()) if slice_height_entry.get() else SETTINGS["slice_height"]
    except ValueError as e:
        update_status(f"Invalid settings value: {e}")
        logger.error(f"Invalid settings: {e}")
        running = False
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # ---------- START ----------
    update_status("Click browser in 5 seconds...")
    time.sleep(5)

    pyautogui.press('home')
    time.sleep(2)

    files = []

    img = take_screenshot(region)
    if img is None:
        update_status("Failed to take screenshot")
        running = False
        return

    filename = os.path.join(OUTPUT_FOLDER, "shot_0.png")
    img.save(filename)

    files.append(filename)
    prev_img = img

    same_count = 0

    for i in range(1, max_shots):
        if not running:
            update_status("Stopped")
            return

        update_status(f"Capturing {i}/{max_shots}")
        update_progress(i / max_shots)

        pyautogui.scroll(int(scroll_amount))
        time.sleep(delay)

        img = take_screenshot(region)
        if img is None:
            update_status("Screenshot failed, aborting")
            running = False
            return

        filename = os.path.join(OUTPUT_FOLDER, f"shot_{i}.png")
        img.save(filename)

        files.append(filename)

        if images_similar(prev_img, img, threshold):
            same_count += 1
        else:
            same_count = 0

        if same_count >= same_threshold:
            update_status(f"Reached end (same frame {same_count} times)")
            break

        prev_img = img

    update_status("Stitching...")
    final = stitch_images(files, check_height)

    if final:
        update_status("Splitting...")
        pages = split_image(final, slice_height)
        if pages:
            make_pdf(pages)

    update_progress(1)
    update_status("Done")
    running = False



# ---------- CONTROLS ----------
def start():
    global running
    if not running:
        use_region = region_toggle.get()

        if use_region:
            try:
                x = int(x_entry.get())
                y = int(y_entry.get())
                w = int(w_entry.get())
                h = int(h_entry.get())
                if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > screen_width or y + h > screen_height:
                    update_status("Invalid region values")
                    return
                region = (x, y, w, h)
            except ValueError:
                update_status("Region values must be numbers")
                return
        else:
            region = None

        Thread(
            target=run_capture,
            args=(scroll_slider.get(), delay_slider.get(), region)
        ).start()


def stop():
    global running
    running = False


def open_folder():
    os.startfile(os.path.dirname(__file__))

# ---------- UI ----------
app = ctk.CTk()
app.title("Screenshot bot by @spaghettinthefryingpan")
app.iconbitmap(r"C:\Users\anaos\Downloads\folder for app\favicon.ico")
app.geometry("450x850")

# Scrollable frame for all settings
scroll_frame = ctk.CTkScrollableFrame(app)
scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

title = ctk.CTkLabel(scroll_frame, text="Screenshot Bot", font=("Arial", 20))
title.pack(pady=10)

# ===== CAPTURE SETTINGS =====
settings_label = ctk.CTkLabel(scroll_frame, text="Capture Settings", font=("Arial", 14, "bold"))
settings_label.pack(pady=(10, 5))

# Scroll
ctk.CTkLabel(scroll_frame, text="Scroll Amount").pack()
scroll_slider = ctk.CTkSlider(scroll_frame, from_=-1500, to=-200, command=lambda val: scroll_value.configure(text=f"{int(val)}"))
scroll_slider.set(-800)
scroll_slider.pack()
scroll_value = ctk.CTkLabel(scroll_frame, text="-800")
scroll_value.pack(pady=5)

# Delay
ctk.CTkLabel(scroll_frame, text="Delay (seconds)").pack()
delay_slider = ctk.CTkSlider(scroll_frame, from_=0.5, to=4, command=lambda val: delay_value.configure(text=f"{val:.1f}s"))
delay_slider.set(2)
delay_slider.pack()
delay_value = ctk.CTkLabel(scroll_frame, text="2.0s")
delay_value.pack(pady=5)

# ===== ADVANCED SETTINGS =====
advanced_label = ctk.CTkLabel(scroll_frame, text="Advanced Settings", font=("Arial", 14, "bold"))
advanced_label.pack(pady=(15, 5))

# Max shots
ctk.CTkLabel(scroll_frame, text="Max Shots", font=("Arial", 10)).pack()
max_shots_entry = ctk.CTkEntry(scroll_frame)
max_shots_entry.insert(0, str(SETTINGS["max_shots"]))
max_shots_entry.pack(padx=20, pady=2)

# Diff threshold
ctk.CTkLabel(scroll_frame, text="Diff Threshold (0-10)", font=("Arial", 10)).pack()
diff_threshold_entry = ctk.CTkEntry(scroll_frame)
diff_threshold_entry.insert(0, str(SETTINGS["diff_threshold"]))
diff_threshold_entry.pack(padx=20, pady=2)

# Same image threshold
ctk.CTkLabel(scroll_frame, text="Same Frame Count to Stop", font=("Arial", 10)).pack()
same_threshold_entry = ctk.CTkEntry(scroll_frame)
same_threshold_entry.insert(0, str(SETTINGS["same_image_threshold"]))
same_threshold_entry.pack(padx=20, pady=2)

# Overlap check height
ctk.CTkLabel(scroll_frame, text="Overlap Check Height", font=("Arial", 10)).pack()
check_height_entry = ctk.CTkEntry(scroll_frame)
check_height_entry.insert(0, str(SETTINGS["overlap_check_height"]))
check_height_entry.pack(padx=20, pady=2)

# Slice height
ctk.CTkLabel(scroll_frame, text="Slice Height (for PDF pages)", font=("Arial", 10)).pack()
slice_height_entry = ctk.CTkEntry(scroll_frame)
slice_height_entry.insert(0, str(SETTINGS["slice_height"]))
slice_height_entry.pack(padx=20, pady=5)

# ===== REGION SETTINGS =====
region_label = ctk.CTkLabel(scroll_frame, text="Capture Region", font=("Arial", 14, "bold"))
region_label.pack(pady=(15, 5))

region_toggle = ctk.CTkCheckBox(scroll_frame, text="Use Custom Capture Area")
region_toggle.pack(pady=10)

# Region inputs
ctk.CTkLabel(scroll_frame, text="X").pack()
x_entry = ctk.CTkEntry(scroll_frame)
x_entry.insert(0, "0")
x_entry.pack()

ctk.CTkLabel(scroll_frame, text="Y").pack()
y_entry = ctk.CTkEntry(scroll_frame)
y_entry.insert(0, "0")
y_entry.pack()

ctk.CTkLabel(scroll_frame, text="Width").pack()
w_entry = ctk.CTkEntry(scroll_frame)
w_entry.insert(0, "1920")
w_entry.pack()

ctk.CTkLabel(scroll_frame, text="Height").pack()
h_entry = ctk.CTkEntry(scroll_frame)
h_entry.insert(0, "900")
h_entry.pack(pady=(0, 10))

# ===== PREVIEW =====
preview_label = ctk.CTkLabel(scroll_frame, text="Preview will appear here", width=320, height=200)
preview_label.pack(pady=10)

# ===== BUTTONS =====
button_frame = ctk.CTkFrame(app)
button_frame.pack(pady=10, fill="x", padx=10)

start_btn = ctk.CTkButton(button_frame, text="Start", command=start)
start_btn.pack(side="left", padx=5)

stop_btn = ctk.CTkButton(button_frame, text="Stop", command=stop)
stop_btn.pack(side="left", padx=5)

open_btn = ctk.CTkButton(button_frame, text="Open Folder", command=open_folder)
open_btn.pack(side="left", padx=5)

# Progress bar
progress = ctk.CTkProgressBar(app)
progress.set(0)
progress.pack(pady=5, fill="x", padx=20)

status_label = ctk.CTkLabel(app, text="Idle")
status_label.pack(pady=5)

app.mainloop() 