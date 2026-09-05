"""
Sayarti - Promotional Video Generator
Creates a professional ad video from website screenshots
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import imageio

# ── Configuration ──────────────────────────────────────────────
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "sayarti_ad.mp4")
FPS = 30
TRANSITION_FRAMES = 15
HOLD_FRAMES = 60
INTRO_FRAMES = 90
OUTRO_FRAMES = 120
VIDEO_W, VIDEO_H = 1080, 1920

# Colors
BG_COLOR = (10, 15, 26)
GOLD = (251, 191, 36)
GOLD_DARK = (245, 158, 11)
WHITE = (241, 245, 249)
SLATE = (148, 163, 184)
BLUE = (96, 165, 250)

# ── Find screenshots ──────────────────────────────────────────
DESKTOP = os.path.expanduser("~\\Desktop")
screenshots = sorted(glob.glob(os.path.join(DESKTOP, "Screenshot_*.jpg")))
print(f"Found {len(screenshots)} screenshots:")
for s in screenshots:
    print(f"  - {os.path.basename(s)}")

# ── Font loading ──────────────────────────────────────────────
def get_font(size):
    font_paths = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()

# ── Helper functions ──────────────────────────────────────────
def resize_fit(img, target_w, target_h):
    """Resize image to fit within target while keeping aspect ratio."""
    ratio = min(target_w / img.width, target_h / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    resized = img.resize(new_size, Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), BG_COLOR)
    x = (target_w - new_size[0]) // 2
    y = (target_h - new_size[1]) // 2
    canvas.paste(resized, (x, y))
    return canvas

def draw_text_centered(draw, text, y, font, color, img_w=VIDEO_W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (img_w - tw) // 2
    # Shadow
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=color)

def blend_images(img1, img2, alpha):
    """Cross-fade between two images."""
    return Image.blend(img1, img2, alpha)

def make_intro_frame(progress):
    """Create animated intro frame."""
    frame = Image.new("RGB", (VIDEO_W, VIDEO_H), BG_COLOR)
    draw = ImageDraw.Draw(frame)

    # Animated circle background
    cx, cy = VIDEO_W // 2, VIDEO_H // 2
    max_r = int(600 * progress)
    for r in range(max_r, 0, -5):
        alpha_factor = 1.0 - (r / max_r) if max_r > 0 else 0
        color_val = int(15 + 20 * alpha_factor)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(color_val, color_val + 5, color_val + 15))

    # Gold line animation
    if progress > 0.3:
        line_progress = min(1.0, (progress - 0.3) / 0.3)
        line_w = int(400 * line_progress)
        y_line = VIDEO_H // 2 - 80
        draw.rectangle([cx - line_w // 2, y_line, cx + line_w // 2, y_line + 4], fill=GOLD)

    # Text animation
    if progress > 0.4:
        text_alpha = min(1.0, (progress - 0.4) / 0.3)
        font_large = get_font(72)
        font_small = get_font(36)

        text = "سيارتي"
        bbox = draw.textbbox((0, 0), text, font=font_large)
        tw = bbox[2] - bbox[0]
        x = (VIDEO_W - tw) // 2
        color = tuple(int(c * text_alpha) for c in GOLD)
        draw.text((x + 2, VIDEO_H // 2 + 10), text, font=font_large, fill=(0, 0, 0))
        draw.text((x, VIDEO_H // 2 + 8), text, font=font_large, fill=color)

        subtitle = "دليل صيانة سياراتك"
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_small)
        tw2 = bbox2[2] - bbox2[0]
        x2 = (VIDEO_W - tw2) // 2
        color2 = tuple(int(c * text_alpha) for c in WHITE)
        draw.text((x2, VIDEO_H // 2 + 100), subtitle, font=font_small, fill=color2)

    # Bottom tagline
    if progress > 0.7:
        tag_alpha = min(1.0, (progress - 0.7) / 0.3)
        font_tag = get_font(28)
        tag = " specifications  |  maintenance  |  oil  |  tires  |  battery"
        bbox3 = draw.textbbox((0, 0), tag, font=font_tag)
        tw3 = bbox3[2] - bbox3[0]
        x3 = (VIDEO_W - tw3) // 2
        color3 = tuple(int(c * tag_alpha) for c in SLATE)
        draw.text((x3, VIDEO_H // 2 + 160), tag, font=font_tag, fill=color3)

    return frame

def make_outro_frame(progress):
    """Create animated outro frame."""
    frame = Image.new("RGB", (VIDEO_W, VIDEO_H), BG_COLOR)
    draw = ImageDraw.Draw(frame)

    # Gradient background
    for y in range(VIDEO_H):
        ratio = y / VIDEO_H
        r = int(10 + 15 * ratio)
        g = int(15 + 10 * ratio)
        b = int(26 + 20 * ratio)
        draw.line([(0, y), (VIDEO_W, y)], fill=(r, g, b))

    font_huge = get_font(90)
    font_large = get_font(48)
    font_med = get_font(32)
    font_small = get_font(24)

    # Main CTA
    if progress > 0.1:
        a = min(1.0, (progress - 0.1) / 0.3)
        text = "sayarti.org"
        bbox = draw.textbbox((0, 0), text, font=font_huge)
        tw = bbox[2] - bbox[0]
        x = (VIDEO_W - tw) // 2
        c = tuple(int(v * a) for v in GOLD)
        draw.text((x, VIDEO_H // 2 - 120), text, font=font_huge, fill=c)

    # Features list
    features = [
        ".penalty specifications for all cars",
        ".oil type and capacity",
        ".spark plugs and tire size",
        ".AI-powered budget finder",
        ".fuel octane calculator",
    ]
    if progress > 0.3:
        for i, feat in enumerate(features):
            feat_progress = min(1.0, (progress - 0.3 - i * 0.05) / 0.2)
            if feat_progress > 0:
                a = feat_progress
                y_pos = VIDEO_H // 2 + 20 + i * 50
                c = tuple(int(v * a) for v in WHITE)
                bbox = draw.textbbox((0, 0), feat, font=font_med)
                tw = bbox[2] - bbox[0]
                x = (VIDEO_W - tw) // 2
                draw.text((x, y_pos), feat, font=font_med, fill=c)

    # Bottom gold bar
    if progress > 0.5:
        bar_w = int(VIDEO_W * min(1.0, (progress - 0.5) / 0.3))
        bar_y = VIDEO_H - 200
        draw.rectangle([0, bar_y, bar_w, bar_y + 4], fill=GOLD)

        if progress > 0.7:
            cta = "Start now - for free!"
            bbox = draw.textbbox((0, 0), cta, font=font_large)
            tw = bbox[2] - bbox[0]
            x = (VIDEO_W - tw) // 2
            draw.text((x, bar_y + 30), cta, font=font_large, fill=GOLD)

    return frame

def make_screenshot_frame(screenshot_img, caption, phone_frame=True):
    """Place screenshot in a phone mockup with caption."""
    frame = Image.new("RGB", (VIDEO_W, VIDEO_H), BG_COLOR)
    draw = ImageDraw.Draw(frame)

    # Subtle gradient bg
    for y in range(VIDEO_H):
        ratio = y / VIDEO_H
        r = int(10 + 8 * ratio)
        g = int(15 + 5 * ratio)
        b = int(26 + 15 * ratio)
        draw.line([(0, y), (VIDEO_W, y)], fill=(r, g, b))

    if phone_frame:
        # Phone frame dimensions
        phone_w, phone_h = 500, 950
        phone_x = (VIDEO_W - phone_w) // 2
        phone_y = (VIDEO_H - phone_h) // 2 - 60

        # Phone outer border
        border = 8
        draw.rounded_rectangle(
            [phone_x - border, phone_y - border,
             phone_x + phone_w + border, phone_y + phone_h + border],
            radius=40, fill=(60, 60, 70)
        )
        # Phone inner
        draw.rounded_rectangle(
            [phone_x, phone_y, phone_x + phone_w, phone_y + phone_h],
            radius=32, fill=(20, 20, 30)
        )

        # Screenshot inside phone
        screenshot_resized = screenshot_img.resize(
            (phone_w - 20, phone_h - 40), Image.LANCZOS
        )
        frame.paste(screenshot_resized, (phone_x + 10, phone_y + 20))

        # Home indicator
        ind_w = 120
        ind_x = (VIDEO_W - ind_w) // 2
        ind_y = phone_y + phone_h - 15
        draw.rounded_rectangle(
            [ind_x, ind_y, ind_x + ind_w, ind_y + 5],
            radius=3, fill=(100, 100, 110)
        )
    else:
        # Full width screenshot
        resized = resize_fit(screenshot_img, VIDEO_W - 80, VIDEO_H - 300)
        frame.paste(resized, (40, 100))

    # Caption at bottom
    font_cap = get_font(32)
    bbox = draw.textbbox((0, 0), caption, font=font_cap)
    tw = bbox[2] - bbox[0]
    x = (VIDEO_W - tw) // 2
    cap_y = VIDEO_H - 180 if phone_frame else VIDEO_H - 120

    # Caption background
    draw.rounded_rectangle(
        [x - 20, cap_y - 10, x + tw + 20, cap_y + 45],
        radius=12, fill=(30, 41, 59)
    )
    draw.text((x, cap_y), caption, font=font_cap, fill=GOLD)

    # Brand watermark top
    font_brand = get_font(24)
    brand = "sayarti.org"
    bbox_b = draw.textbbox((0, 0), brand, font=font_brand)
    tw_b = bbox_b[2] - bbox_b[0]
    draw.text(((VIDEO_W - tw_b) // 2, 40), brand, font=font_brand, fill=SLATE)

    return frame

def apply_ken_burns(img, progress, direction="in"):
    """Apply Ken Burns zoom effect."""
    if direction == "in":
        scale = 1.0 + 0.08 * progress
    else:
        scale = 1.08 - 0.08 * progress

    w, h = img.size
    new_w, new_h = int(w * scale), int(h * scale)
    zoomed = img.resize((new_w, new_h), Image.LANCZOS)

    crop_x = (new_w - w) // 2
    crop_y = (new_h - h) // 2
    return zoomed.crop((crop_x, crop_y, crop_x + w, crop_y + h))

def make_feature_card(title, subtitle, icon_text, progress):
    """Create a feature highlight card."""
    frame = Image.new("RGB", (VIDEO_W, VIDEO_H), BG_COLOR)
    draw = ImageDraw.Draw(frame)

    # Gradient
    for y in range(VIDEO_H):
        ratio = y / VIDEO_H
        draw.line([(0, y), (VIDEO_W, y)],
                  fill=(int(10 + 10 * ratio), int(15 + 8 * ratio), int(26 + 12 * ratio)))

    # Glass card
    card_w, card_h = 900, 400
    card_x = (VIDEO_W - card_w) // 2
    card_y = (VIDEO_H - card_h) // 2

    # Card glow
    if progress > 0.2:
        glow_a = min(0.3, (progress - 0.2) * 0.5)
        for offset in range(20, 0, -1):
            g = int(20 + 40 * glow_a * (offset / 20))
            draw.rounded_rectangle(
                [card_x - offset, card_y - offset,
                 card_x + card_w + offset, card_y + card_h + offset],
                radius=28 + offset, fill=(g, g - 5, g + 10)
            )

    # Card background
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=28, fill=(30, 41, 59, 200)
    )

    # Icon
    if progress > 0.1:
        font_icon = get_font(60)
        draw_text_centered(draw, icon_text, card_y + 40, font_icon, BLUE)

    # Title
    if progress > 0.3:
        a = min(1.0, (progress - 0.3) / 0.3)
        font_title = get_font(44)
        c = tuple(int(v * a) for v in WHITE)
        draw_text_centered(draw, title, card_y + 130, font_title, c)

    # Subtitle
    if progress > 0.5:
        a = min(1.0, (progress - 0.5) / 0.3)
        font_sub = get_font(28)
        c = tuple(int(v * a) for v in SLATE)
        draw_text_centered(draw, subtitle, card_y + 200, font_sub, c)

    # Decorative line
    if progress > 0.4:
        line_w = int(200 * min(1.0, (progress - 0.4) / 0.3))
        line_y = card_y + 260
        draw.rectangle(
            [card_x + (card_w - line_w) // 2, line_y,
             card_x + (card_w + line_w) // 2, line_y + 3],
            fill=GOLD
        )

    # Brand bottom
    font_brand = get_font(22)
    draw_text_centered(draw, "sayarti.org", VIDEO_H - 100, font_brand, SLATE)

    return frame

# ── Main video generation ─────────────────────────────────────
def generate_video():
    frames = []
    total_frames = 0

    # 1. INTRO
    print("Creating intro...")
    for i in range(INTRO_FRAMES):
        progress = i / INTRO_FRAMES
        frame = make_intro_frame(progress)
        frames.append(np.array(frame))
        total_frames += 1

    # Hold intro
    intro_final = make_intro_frame(1.0)
    for _ in range(HOLD_FRAMES):
        frames.append(np.array(intro_final))
        total_frames += 1

    # 2. FEATURE CARDS (between screenshots)
    feature_data = [
        ("Car Specifications", "Search by brand, model, year & engine", "[A]"),
        ("Maintenance Guide", "Oil, spark plugs, tires & more", "[B]"),
        ("Budget Finder", "AI finds cars for your budget", "[C]"),
        ("Fuel Calculator", "Mix fuel grades for optimal octane", "[D]"),
    ]

    # 3. SCREENSHOTS with transitions
    captions = [
        "Smart Car Search",
        "Easy Filtering",
        "Instant Results",
        "Detailed Specifications",
        "Complete Maintenance Guide",
        "All Brands Covered",
    ]

    for idx, shot_path in enumerate(screenshots):
        print(f"Processing screenshot {idx + 1}/{len(screenshots)}...")

        # Load and prepare screenshot
        img = Image.open(shot_path).convert("RGB")

        # Feature card before each screenshot (alternating)
        if idx < len(feature_data):
            fd = feature_data[idx]
            print(f"  Adding feature card: {fd[0]}")
            for i in range(TRANSITION_FRAMES * 2):
                progress = i / (TRANSITION_FRAMES * 2)
                card = make_feature_card(fd[0], fd[1], fd[2], progress)
                frames.append(np.array(card))
                total_frames += 1
            # Hold card
            card_final = make_feature_card(fd[0], fd[1], fd[2], 1.0)
            for _ in range(HOLD_FRAMES // 2):
                frames.append(np.array(card_final))
                total_frames += 1

        # Ken Burns screenshot
        caption = captions[idx] if idx < len(captions) else "Sayarti"
        phone_frame = (idx % 2 == 0)  # Alternate phone/full

        # Transition in
        prev_frame = frames[-1] if frames else np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
        shot_frame = make_screenshot_frame(img, caption, phone_frame)

        for i in range(TRANSITION_FRAMES):
            alpha = i / TRANSITION_FRAMES
            prev_img = Image.fromarray(prev_frame)
            blended = blend_images(prev_img, shot_frame, alpha)
            # Apply subtle Ken Burns
            kb_progress = (i + TRANSITION_FRAMES) / (TRANSITION_FRAMES + HOLD_FRAMES)
            kb_frame = apply_ken_burns(blended, kb_progress, "in" if idx % 2 == 0 else "out")
            frames.append(np.array(kb_frame))
            total_frames += 1

        # Hold on screenshot with Ken Burns
        for i in range(HOLD_FRAMES):
            kb_progress = (TRANSITION_FRAMES + i) / (TRANSITION_FRAMES + HOLD_FRAMES)
            kb_frame = apply_ken_burns(shot_frame, kb_progress, "in" if idx % 2 == 0 else "out")
            frames.append(np.array(kb_frame))
            total_frames += 1

        # Transition out
        if idx < len(screenshots) - 1:
            next_img = Image.open(screenshots[idx + 1]).convert("RGB")
            next_caption = captions[idx + 1] if idx + 1 < len(captions) else "Sayarti"
            next_frame = make_screenshot_frame(next_img, next_caption, not phone_frame)

            for i in range(TRANSITION_FRAMES):
                alpha = i / TRANSITION_FRAMES
                blended = blend_images(shot_frame, next_frame, alpha)
                frames.append(np.array(blended))
                total_frames += 1

    # 4. OUTRO
    print("Creating outro...")
    for i in range(OUTRO_FRAMES):
        progress = i / OUTRO_FRAMES
        frame = make_outro_frame(progress)
        frames.append(np.array(frame))
        total_frames += 1

    # Hold outro
    outro_final = make_outro_frame(1.0)
    for _ in range(HOLD_FRAMES):
        frames.append(np.array(outro_final))
        total_frames += 1

    duration = total_frames / FPS
    print(f"\nTotal frames: {total_frames}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Resolution: {VIDEO_W}x{VIDEO_H}")

    # Write video
    print("\nWriting video...")
    output = os.path.abspath(OUTPUT_PATH)
    writer = imageio.get_writer(output, fps=FPS, codec='libx264', quality=8,
                                 pixelformat='yuv420p', macro_block_size=2)

    for i, frame in enumerate(frames):
        writer.append_data(frame)
        if (i + 1) % 30 == 0:
            pct = (i + 1) / total_frames * 100
            print(f"  Progress: {pct:.0f}% ({i + 1}/{total_frames})")

    writer.close()
    print(f"\nVideo saved: {output}")
    print(f"File size: {os.path.getsize(output) / (1024*1024):.1f} MB")
    return output

if __name__ == "__main__":
    generate_video()
