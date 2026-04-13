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
import tkinter as tk
from tkinter import filedialog
import json

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
PRESETS_FILE = os.path.join(os.path.dirname(__file__), "presets.json")

running = False
auto_scroll_mode = False
detected_shifts = []
ui_large = False


def load_presets_file() -> dict:
    try:
        if not os.path.exists(PRESETS_FILE):
            return {}
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.error(f"Failed to load presets: {e}")
    return {}


def save_presets_file(presets: dict) -> bool:
    try:
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save presets: {e}")
        return False


def get_current_preset_config() -> dict:
    return {
        "output_folder": get_output_folder(),
        "base_filename": base_filename_entry.get().strip(),
        "pdf_filename": pdf_filename_entry.get().strip(),
        "max_shots": int(max_shots_entry.get()) if max_shots_entry.get() else SETTINGS["max_shots"],
        "diff_threshold": int(diff_threshold_entry.get()) if diff_threshold_entry.get() else SETTINGS["diff_threshold"],
        "same_image_threshold": int(same_threshold_entry.get()) if same_threshold_entry.get() else SETTINGS["same_image_threshold"],
        "overlap_check_height": int(check_height_entry.get()) if check_height_entry.get() else SETTINGS["overlap_check_height"],
        "slice_height": int(slice_height_entry.get()) if slice_height_entry.get() else SETTINGS["slice_height"],
        "blur_kernel": int(blur_kernel_entry.get()) if blur_kernel_entry.get() else 5,
        "thresh_block": int(thresh_block_entry.get()) if thresh_block_entry.get() else 11,
        "thresh_c": int(thresh_c_entry.get()) if thresh_c_entry.get() else 2,
        "scroll_amount": int(scroll_slider.get()),
        "delay": float(delay_slider.get()),
        "direction": direction_option.get(),
        "auto_scroll": auto_scroll_mode,
        "use_region": region_toggle.get(),
        "region_x": int(x_entry.get()) if x_entry.get() else 0,
        "region_y": int(y_entry.get()) if y_entry.get() else 0,
        "region_w": int(w_entry.get()) if w_entry.get() else screen_width,
        "region_h": int(h_entry.get()) if h_entry.get() else screen_height,
        "auto_crop": auto_crop_toggle.get(),
    }


def set_auto_scroll(enabled: bool) -> None:
    global auto_scroll_mode
    auto_scroll_mode = enabled
    status_text = "Auto-Scroll: On" if auto_scroll_mode else "Auto-Scroll: Off"
    button_color = "#0078d4" if auto_scroll_mode else "gray"
    auto_scroll_btn.configure(text=status_text, fg_color=button_color)


def apply_preset(config: dict) -> None:
    output_folder_entry.delete(0, tk.END)
    output_folder_entry.insert(0, config.get("output_folder", OUTPUT_FOLDER))

    base_filename_entry.delete(0, tk.END)
    base_filename_entry.insert(0, config.get("base_filename", "comic_clean"))

    pdf_filename_entry.delete(0, tk.END)
    pdf_filename_entry.insert(0, config.get("pdf_filename", "comic"))

    max_shots_entry.delete(0, tk.END)
    max_shots_entry.insert(0, str(config.get("max_shots", SETTINGS["max_shots"])))

    diff_threshold_entry.delete(0, tk.END)
    diff_threshold_entry.insert(0, str(config.get("diff_threshold", SETTINGS["diff_threshold"])))

    same_threshold_entry.delete(0, tk.END)
    same_threshold_entry.insert(0, str(config.get("same_image_threshold", SETTINGS["same_image_threshold"])))

    check_height_entry.delete(0, tk.END)
    check_height_entry.insert(0, str(config.get("overlap_check_height", SETTINGS["overlap_check_height"])))

    slice_height_entry.delete(0, tk.END)
    slice_height_entry.insert(0, str(config.get("slice_height", SETTINGS["slice_height"])))

    blur_kernel_entry.delete(0, tk.END)
    blur_kernel_entry.insert(0, str(config.get("blur_kernel", 5)))

    thresh_block_entry.delete(0, tk.END)
    thresh_block_entry.insert(0, str(config.get("thresh_block", 11)))

    thresh_c_entry.delete(0, tk.END)
    thresh_c_entry.insert(0, str(config.get("thresh_c", 2)))

    scroll_slider.set(config.get("scroll_amount", 800))
    delay_slider.set(config.get("delay", 2))
    direction_option.set(config.get("direction", "Down"))
    set_auto_scroll(config.get("auto_scroll", False))

    if config.get("use_region", False):
        region_toggle.select()
    else:
        region_toggle.deselect()

    x_entry.delete(0, tk.END)
    x_entry.insert(0, str(config.get("region_x", 0)))
    y_entry.delete(0, tk.END)
    y_entry.insert(0, str(config.get("region_y", 0)))
    w_entry.delete(0, tk.END)
    w_entry.insert(0, str(config.get("region_w", 1920)))
    h_entry.delete(0, tk.END)
    h_entry.insert(0, str(config.get("region_h", 900)))

    auto_crop_toggle.select() if config.get("auto_crop", False) else auto_crop_toggle.deselect()


def update_preset_menu() -> None:
    presets = load_presets_file()
    if presets:
        preset_selector.configure(values=list(presets.keys()))
        preset_selector.set(list(presets.keys())[0])
    else:
        preset_selector.configure(values=["No presets"])
        preset_selector.set("No presets")


def save_preset() -> None:
    preset_name = preset_name_entry.get().strip()
    if not preset_name:
        update_status("Preset name is required")
        return

    presets = load_presets_file()
    presets[preset_name] = get_current_preset_config()

    if save_presets_file(presets):
        update_preset_menu()
        preset_selector.set(preset_name)
        update_status(f"Preset '{preset_name}' saved")
    else:
        update_status("Failed to save preset")


def load_preset() -> None:
    preset_name = preset_selector.get()
    if not preset_name or preset_name == "No presets":
        update_status("No preset selected")
        return

    presets = load_presets_file()
    preset = presets.get(preset_name)
    if not preset:
        update_status("Preset not found")
        return

    apply_preset(preset)
    preset_name_entry.delete(0, tk.END)
    preset_name_entry.insert(0, preset_name)
    update_status(f"Preset '{preset_name}' loaded")

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

def display_preview(img):
    img = img.resize((320, 200))
    img_tk = ImageTk.PhotoImage(img)
    preview_label.configure(image=img_tk, text="")
    preview_label.image = img_tk  # prevent garbage collection
    app.update()


def update_progress(val):
    progress.set(val)
    app.update()

def hide_app_window():
    try:
        app.withdraw()
        app.update()
        time.sleep(0.2)
    except Exception as e:
        logger.error(f"Failed to hide app window: {e}")

def show_app_window():
    try:
        app.deiconify()
        app.lift()
        app.attributes("-topmost", True)
        app.update()
        app.attributes("-topmost", False)
    except Exception as e:
        logger.error(f"Failed to show app window: {e}")


def toggle_ui_size():
    global ui_large
    ui_large = not ui_large
    if ui_large:
        app.geometry("600x950")
        ui_size_btn.configure(text="Smaller UI")
    else:
        app.geometry("450x850")
        ui_size_btn.configure(text="Larger UI")
    app.update()


def select_output_folder():
    folder = filedialog.askdirectory(initialdir=os.path.dirname(__file__))
    if folder:
        output_folder_entry.delete(0, tk.END)
        output_folder_entry.insert(0, folder)


def get_output_folder() -> str:
    folder = output_folder_entry.get().strip()
    return folder if folder else OUTPUT_FOLDER


def get_output_file_name() -> str:
    raw_name = base_filename_entry.get().strip()
    if not raw_name:
        raw_name = "comic_clean"
    raw_name = os.path.basename(raw_name)
    if raw_name.lower().endswith(".png"):
        raw_name = raw_name[:-4]
    return raw_name


def get_pdf_file_name() -> str:
    raw_name = pdf_filename_entry.get().strip()
    if not raw_name:
        raw_name = "comic"
    raw_name = os.path.basename(raw_name)
    if raw_name.lower().endswith(".pdf"):
        raw_name = raw_name[:-4]
    return raw_name


def get_final_image_path() -> str:
    return os.path.join(get_output_folder(), f"{get_output_file_name()}.png")


def get_pdf_path() -> str:
    return os.path.join(get_output_folder(), f"{get_pdf_file_name()}.pdf")


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

def detect_vertical_shift(img1, img2) -> int:
    """Detect vertical shift between two consecutive images using phase correlation."""
    try:
        gray1 = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2GRAY)
        
        # Use phase correlation to find shift
        correlation = cv2.phaseCorrelate(gray1, gray2)[0]
        shift_y = int(abs(correlation[1]))
        
        return shift_y
    except Exception as e:
        logger.error(f"Vertical shift detection failed: {e}")
        return 0

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

def stitch_images(files: List[str], check_height: int, output_path: str) -> Optional[str]:
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
        final.save(output_path)
        logger.info(f"Stitched image saved to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Image stitching failed: {e}")
        return None

def split_image(image_path: str, slice_height: int, output_folder: str) -> List[str]:
    """Split a large image into pages."""
    try:
        img = Image.open(image_path)
        width, height = img.size

        pages = []
        for i, y in enumerate(range(0, height, slice_height)):
            piece = img.crop((0, y, width, min(y + slice_height, height)))
            filename = os.path.join(output_folder, f"page_{i}.png")
            piece.save(filename)
            pages.append(filename)

        logger.info(f"Image split into {len(pages)} pages")
        return pages
    except Exception as e:
        logger.error(f"Image splitting failed: {e}")
        return []

def make_pdf(pages: List[str], pdf_path: str) -> None:
    """Create a PDF from image pages."""
    try:
        images = [Image.open(p).convert("RGB") for p in pages if os.path.exists(p)]
        if images:
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
            logger.info(f"PDF created: {pdf_path}")
    except Exception as e:
        logger.error(f"PDF creation failed: {e}")

def auto_crop_image(image_path: str) -> bool:
    """Automatically crop the image to remove borders and non-main content using contour detection."""
    try:
        # Get parameters from UI, with defaults
        try:
            blur_kernel = int(blur_kernel_entry.get()) if blur_kernel_entry.get() else 5
            if blur_kernel % 2 == 0: blur_kernel += 1  # Ensure odd
        except ValueError:
            blur_kernel = 5

        try:
            thresh_block = int(thresh_block_entry.get()) if thresh_block_entry.get() else 11
            if thresh_block % 2 == 0: thresh_block += 1  # Ensure odd
        except ValueError:
            thresh_block = 11

        try:
            thresh_c = int(thresh_c_entry.get()) if thresh_c_entry.get() else 2
        except ValueError:
            thresh_c = 2

        # Read image with OpenCV
        img_cv = cv2.imread(image_path)
        if img_cv is None:
            logger.error("Failed to read image with OpenCV")
            return False

        # Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)

        # Use adaptive threshold to handle varying backgrounds
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, thresh_block, thresh_c)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            logger.warning("No contours found, image not cropped")
            return False

        # Find the largest contour by area
        largest_contour = max(contours, key=cv2.contourArea)

        # Get bounding box
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Crop the image
        cropped = img_cv[y:y+h, x:x+w]

        # Save back to PIL for consistency
        cropped_pil = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        cropped_pil.save(image_path)

        logger.info(f"Image cropped to main content and saved to {image_path}")
        return True
    except Exception as e:
        logger.error(f"Cropping failed: {e}")
        return False


# ---------- MAIN CAPTURE FUNCTION ----------
def get_adaptive_scroll_amount() -> int:
    """Calculate adaptive scroll amount based on detected shifts."""
    if len(detected_shifts) < 1:
        return int(scroll_slider.get())
    
    # Average last 3 detected shifts
    recent_shifts = detected_shifts[-3:]
    avg_shift = int(np.mean(recent_shifts))
    
    # Clamp to reasonable bounds
    adaptive_amount = max(50, min(avg_shift, 2000))
    return adaptive_amount

def perform_scroll(amount: int, direction: str) -> None:
    """Scroll in the selected direction."""
    try:
        if direction == "Up":
            pyautogui.scroll(amount)
        elif direction == "Down":
            pyautogui.scroll(-amount)
        elif direction == "Right":
            pyautogui.press("right")
        elif direction == "Left":
            pyautogui.press("left")
    except Exception as e:
        logger.error(f"Scroll failed: {e}")
        update_status(f"Scroll failed: {e}")


def reverse_direction(direction: str) -> str:
    return {
        "Up": "Down",
        "Down": "Up",
        "Left": "Right",
        "Right": "Left"
    }.get(direction, direction)


def test_scroll() -> None:
    if running:
        update_status("Cannot test while capture is running")
        return

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

    current_scroll = int(scroll_slider.get())
    scroll_direction = direction_option.get()
    delay = delay_slider.get()

    update_status("Testing scroll once...")
    hide_app_window()
    perform_scroll(current_scroll, scroll_direction)
    time.sleep(delay)

    img = take_screenshot(region)
    if img is None:
        show_app_window()
        update_status("Test scroll failed")
        return

    perform_scroll(current_scroll, reverse_direction(scroll_direction))
    show_app_window()

    display_preview(img)
    update_status("Test scroll complete. Preview shown. Confirm settings before full capture.")


def run_capture(scroll_amount: float, delay: float, region: Optional[Tuple], scroll_direction: str, use_auto_scroll: bool = False) -> None:
    """Main capture loop with image stitching."""
    global running, detected_shifts
    running = True
    detected_shifts = []  # Reset shifts for new capture

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

    output_folder = get_output_folder()
    final_image_path = get_final_image_path()
    pdf_path = get_pdf_path()
    os.makedirs(output_folder, exist_ok=True)

    # ---------- START ----------
    update_status("Click browser in 5 seconds...")
    time.sleep(5)

    pyautogui.press('home')
    time.sleep(2)

    files = []

    hide_app_window()
    img = take_screenshot(region)
    show_app_window()

    if img is None:
        update_status("Failed to take screenshot")
        running = False
        return

    filename = os.path.join(output_folder, "shot_0.png")
    img.save(filename)

    files.append(filename)
    prev_img = img

    same_count = 0
    start_time = time.time()

    for i in range(1, max_shots):
        if not running:
            update_status("Stopped")
            return

        # Determine scroll amount
        if use_auto_scroll:
            current_scroll = get_adaptive_scroll_amount()
            status_suffix = " [AUTO]"
        else:
            current_scroll = int(scroll_amount)
            status_suffix = ""

        # Calculate progress metrics
        elapsed = time.time() - start_time
        fps = i / elapsed if elapsed > 0 else 0
        time_per_capture = elapsed / i if i > 0 else 0
        remaining_captures = max_shots - i
        estimated_remaining_seconds = time_per_capture * remaining_captures
        
        # Format estimated time
        minutes = int(estimated_remaining_seconds) // 60
        seconds = int(estimated_remaining_seconds) % 60
        time_str = f"{minutes}m {seconds}s"

        update_status(f"Capturing {i}/{max_shots} ({fps:.1f} fps) - ETA: {time_str} (Scroll: {current_scroll}){status_suffix}")
        update_progress(i / max_shots)

        perform_scroll(current_scroll, scroll_direction)
        time.sleep(delay)

        hide_app_window()
        img = take_screenshot(region)
        show_app_window()

        if img is None:
            update_status("Screenshot failed, aborting")
            running = False
            return

        # Detect vertical shift if auto-scroll enabled
        if use_auto_scroll:
            shift = detect_vertical_shift(prev_img, img)
            detected_shifts.append(shift)
            logger.info(f"Detected vertical shift: {shift}px")

        filename = os.path.join(output_folder, f"shot_{i}.png")
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
    final = stitch_images(files, check_height, final_image_path)

    if final:
        if auto_crop_toggle.get():
            update_status("Auto-cropping...")
            auto_crop_image(final)
        update_status("Splitting...")
        pages = split_image(final, slice_height, output_folder)
        if pages:
            make_pdf(pages, pdf_path)

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
            args=(scroll_slider.get(), delay_slider.get(), region, direction_option.get(), auto_scroll_mode)
        ).start()


def stop():
    global running
    running = False


def open_folder():
    folder = get_output_folder()
    if not os.path.exists(folder):
        folder = os.path.dirname(__file__)
    os.startfile(folder)

def crop_final_image():
    final_image = get_final_image_path()
    if os.path.exists(final_image):
        if auto_crop_image(final_image):
            update_status("Image cropped successfully")
        else:
            update_status("Cropping failed")
    else:
        update_status("No final image to crop")

def toggle_auto_scroll():
    """Toggle auto-scroll mode on/off."""
    global auto_scroll_mode
    auto_scroll_mode = not auto_scroll_mode
    status_text = "Auto-Scroll: On" if auto_scroll_mode else "Auto-Scroll: Off"
    button_color = "#0078d4" if auto_scroll_mode else "gray"
    auto_scroll_btn.configure(text=status_text, fg_color=button_color)
    update_status(status_text)

def select_region():
    """Open an overlay to select a region on the screen."""
    overlay = tk.Tk()
    overlay.attributes('-transparent', 'color')
    overlay.attributes('-topmost', True)
    overlay.geometry(f"{screen_width}x{screen_height}+0+0")
    overlay.configure(bg='color')
    
    canvas = tk.Canvas(overlay, bg='color', highlightthickness=0, cursor="crosshair")
    canvas.pack(fill=tk.BOTH, expand=True)
    
    state = {"start_x": 0, "start_y": 0, "rect": None}
    
    def on_mouse_down(event):
        state["start_x"] = event.x
        state["start_y"] = event.y
        canvas.delete("rect")
    
    def on_mouse_motion(event):
        if state["rect"]:
            canvas.delete(state["rect"])
        
        x1, y1 = state["start_x"], state["start_y"]
        x2, y2 = event.x, event.y
        
        # Normalize coordinates
        x_min = min(x1, x2)
        y_min = min(y1, y2)
        x_max = max(x1, x2)
        y_max = max(y1, y2)
        
        # Draw rectangle with blue outline
        state["rect"] = canvas.create_rectangle(
            x_min, y_min, x_max, y_max,
            outline="#0078d4", width=2, tags="rect"
        )
        
        # Draw dimensions text
        width = x_max - x_min
        height = y_max - y_min
        canvas.delete("text")
        canvas.create_text(
            x_min + 10, y_min + 10,
            text=f"W: {width} H: {height}",
            fill="white", anchor="nw", tags="text",
            font=("Arial", 12, "bold")
        )
    
    def on_mouse_up(event):
        x1, y1 = state["start_x"], state["start_y"]
        x2, y2 = event.x, event.y
        
        # Normalize coordinates
        x_min = min(x1, x2)
        y_min = min(y1, y2)
        x_max = max(x1, x2)
        y_max = max(y1, y2)
        
        width = x_max - x_min
        height = y_max - y_min
        
        if width > 10 and height > 10:  # Minimum region size
            x_entry.delete(0, tk.END)
            x_entry.insert(0, str(x_min))
            y_entry.delete(0, tk.END)
            y_entry.insert(0, str(y_min))
            w_entry.delete(0, tk.END)
            w_entry.insert(0, str(width))
            h_entry.delete(0, tk.END)
            h_entry.insert(0, str(height))
            
            update_status(f"Region selected: X={x_min}, Y={y_min}, W={width}, H={height}")
            region_toggle.select()
        
        overlay.destroy()
    
    def on_escape(event):
        overlay.destroy()
    
    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_motion)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    canvas.bind("<Escape>", on_escape)
    
    update_status("Click and drag to select region. Press ESC to cancel.")
    overlay.mainloop()

# ---------- UI ----------
app = ctk.CTk()
app.title("Screenshot bot by @spaghettinthefryingpan")
app.iconbitmap(r"C:\Users\anaos\Downloads\folder for app\favicon.ico")
app.geometry("450x850")

# Scrollable frame for all settings
scroll_frame = ctk.CTkScrollableFrame(app)
scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

header_frame = ctk.CTkFrame(scroll_frame)
header_frame.pack(fill="x", pady=(0, 10))

title = ctk.CTkLabel(header_frame, text="Screenshot Bot", font=("Arial", 20))
title.pack(side="left", pady=10)

header_test_btn = ctk.CTkButton(header_frame, text="Test", width=90, height=30, font=("Arial", 11), command=test_scroll)
header_test_btn.pack(side="right", pady=10, padx=(0, 6))

ui_size_btn = ctk.CTkButton(header_frame, text="Resize", width=90, height=30, font=("Arial", 11), command=toggle_ui_size)
ui_size_btn.pack(side="right", pady=10, padx=(0, 6))

header_crop_btn = ctk.CTkButton(header_frame, text="Crop", width=90, height=30, font=("Arial", 11), command=crop_final_image)
header_crop_btn.pack(side="right", pady=10, padx=(0, 10))

# ===== OUTPUT SETTINGS =====
output_label = ctk.CTkLabel(scroll_frame, text="Output Settings", font=("Arial", 14, "bold"))
output_label.pack(pady=(10, 5))

ctk.CTkLabel(scroll_frame, text="Output Folder", font=("Arial", 10)).pack()
output_folder_frame = ctk.CTkFrame(scroll_frame)
output_folder_frame.pack(fill="x", padx=20, pady=2)
output_folder_entry = ctk.CTkEntry(output_folder_frame)
output_folder_entry.insert(0, OUTPUT_FOLDER)
output_folder_entry.pack(side="left", fill="x", expand=True)
output_folder_btn = ctk.CTkButton(output_folder_frame, text="Browse", width=80, command=select_output_folder)
output_folder_btn.pack(side="left", padx=(8, 0))

ctk.CTkLabel(scroll_frame, text="Preset Name", font=("Arial", 10)).pack()
preset_name_entry = ctk.CTkEntry(scroll_frame)
preset_name_entry.pack(padx=20, pady=2)

preset_buttons = ctk.CTkFrame(scroll_frame)
preset_buttons.pack(fill="x", padx=20, pady=2)

preset_selector = ctk.CTkOptionMenu(preset_buttons, values=["No presets"])
preset_selector.set("No presets")
preset_selector.pack(side="left", fill="x", expand=True)

save_preset_btn = ctk.CTkButton(preset_buttons, text="Save Preset", command=save_preset)
save_preset_btn.pack(side="left", padx=(8, 0))

load_preset_btn = ctk.CTkButton(preset_buttons, text="Load Preset", command=load_preset)
load_preset_btn.pack(side="left", padx=(8, 0))

ctk.CTkLabel(scroll_frame, text="Output Base Filename", font=("Arial", 10)).pack()
base_filename_entry = ctk.CTkEntry(scroll_frame)
base_filename_entry.insert(0, "comic_clean")
base_filename_entry.pack(padx=20, pady=2)

ctk.CTkLabel(scroll_frame, text="PDF Filename", font=("Arial", 10)).pack()
pdf_filename_entry = ctk.CTkEntry(scroll_frame)
pdf_filename_entry.insert(0, "comic")
pdf_filename_entry.pack(padx=20, pady=5)

# ===== CAPTURE SETTINGS =====
settings_label = ctk.CTkLabel(scroll_frame, text="Capture Settings", font=("Arial", 14, "bold"))
settings_label.pack(pady=(10, 5))

# Scroll
ctk.CTkLabel(scroll_frame, text="Scroll Amount").pack()
scroll_slider = ctk.CTkSlider(scroll_frame, from_=200, to=1500, command=lambda val: scroll_value.configure(text=f"{int(val)}"))
scroll_slider.set(800)
scroll_slider.pack()
scroll_value = ctk.CTkLabel(scroll_frame, text="800")
scroll_value.pack(pady=5)

ctk.CTkLabel(scroll_frame, text="Scroll Direction").pack()
direction_option = ctk.CTkOptionMenu(
    scroll_frame,
    values=["Down", "Up", "Right", "Left"]
)
direction_option.set("Down")
direction_option.pack(pady=5)

# Delay
ctk.CTkLabel(scroll_frame, text="Delay (seconds)").pack()
delay_slider = ctk.CTkSlider(scroll_frame, from_=0.5, to=4, command=lambda val: delay_value.configure(text=f"{val:.1f}s"))
delay_slider.set(2)
delay_slider.pack()
delay_value = ctk.CTkLabel(scroll_frame, text="2.0s")
delay_value.pack(pady=5)

# Auto-scroll button
auto_scroll_btn = ctk.CTkButton(scroll_frame, text="Auto-Scroll: Off", command=toggle_auto_scroll, fg_color="gray")
auto_scroll_btn.pack(pady=10)

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


# Blur kernel size
ctk.CTkLabel(scroll_frame, text="Crop Blur Kernel Size (odd)", font=("Arial", 10)).pack()
blur_kernel_entry = ctk.CTkEntry(scroll_frame)
blur_kernel_entry.insert(0, "5")
blur_kernel_entry.pack(padx=20, pady=2)

# Adaptive threshold block size
ctk.CTkLabel(scroll_frame, text="Crop Threshold Block Size (odd)", font=("Arial", 10)).pack()
thresh_block_entry = ctk.CTkEntry(scroll_frame)
thresh_block_entry.insert(0, "11")
thresh_block_entry.pack(padx=20, pady=2)

# Adaptive threshold C
ctk.CTkLabel(scroll_frame, text="Crop Threshold C", font=("Arial", 10)).pack()
thresh_c_entry = ctk.CTkEntry(scroll_frame)
thresh_c_entry.insert(0, "2")
thresh_c_entry.pack(padx=20, pady=2)

# Auto crop toggle
auto_crop_toggle = ctk.CTkCheckBox(scroll_frame, text="Auto Crop After Stitching")
auto_crop_toggle.pack(pady=5)

# ===== REGION SETTINGS =====
region_label = ctk.CTkLabel(scroll_frame, text="Capture Region", font=("Arial", 14, "bold"))
region_label.pack(pady=(15, 5))

region_toggle = ctk.CTkCheckBox(scroll_frame, text="Use Custom Capture Area")
region_toggle.pack(pady=10)

# Select region button
select_region_btn = ctk.CTkButton(scroll_frame, text="Select Region On Screen", command=select_region)
select_region_btn.pack(pady=5)

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

test_btn = ctk.CTkButton(button_frame, text="Test Scroll", command=test_scroll)
test_btn.pack(side="left", padx=5)

crop_btn = ctk.CTkButton(button_frame, text="Crop", command=crop_final_image)
crop_btn.pack(side="left", padx=5)

# Progress bar
progress = ctk.CTkProgressBar(app)
progress.set(0)
progress.pack(pady=5, fill="x", padx=20)

status_label = ctk.CTkLabel(app, text="Idle")
status_label.pack(pady=5)

update_preset_menu()
app.mainloop()
# ---------- END OF FILE. FINALLY OMFG I'M SO DONE WITH THIS NOW BRO, I CAN FINALLY GOON TO YURI IN PEACE.---------- 