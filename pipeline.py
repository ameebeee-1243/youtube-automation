"""
YouTube Shorts Meme Pipeline v3
- More reliable image generation with longer timeouts
- Better caption styling
- Guaranteed minimum video length
- Faster Pollinations requests with better error handling
"""

import os
import json
import random
import requests
import subprocess
import time
from pathlib import Path

GROQ_API_KEY          = os.environ["GROQ_API_KEY"]
PEXELS_API_KEY        = os.environ["PEXELS_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

WORK_DIR = Path("output")
WORK_DIR.mkdir(exist_ok=True)

SLIDES_COUNT = 8          # number of meme slides
DURATION_PER_SLIDE = 2.8  # seconds per slide → ~22 seconds total


# ── Step 1: Generate meme scenarios ─────────────────────────────────────────
def generate_meme_scenarios() -> dict:
    print("🧠 Generating meme scenarios...")

    themes = [
        "school and studying struggles",
        "being broke and adulting fails",
        "sleep deprivation and 3am thoughts",
        "phone addiction and internet brain rot",
        "gym motivation vs reality",
        "Monday morning pain",
        "procrastination and deadlines",
        "overthinking everything",
        "food cravings at midnight",
        "social anxiety moments",
        "gaming rage and fails",
        "chaotic friend group situations",
    ]
    theme = random.choice(themes)

    prompt = f"""Create a viral YouTube Shorts meme compilation about: "{theme}"

Make exactly {SLIDES_COUNT} meme slides. Each needs:
- CAPTION: Short, punchy, ALL CAPS, max 6 words, extremely relatable and funny
- IMAGE_PROMPT: Describe a funny illustrated scene (cartoon style, expressive characters, bright colors)

Rules for captions: think dank memes, Twitter humor, gen-z jokes. Examples:
"MY BRAIN AT 3AM THO", "POV: YOU'RE COOKED", "NOT ME DOING THIS AGAIN", "BRO REALLY SAID THAT"

Respond ONLY with valid JSON, no extra text:
{{
  "theme": "{theme}",
  "title": "funny relatable title with emoji max 55 chars",
  "description": "2 funny sentences about the video. #relatable #memes #funny #shorts #viral",
  "tags": ["memes", "relatable", "funny", "shorts", "viral", "humor", "comedy"],
  "slides": [
    {{"caption": "CAPTION HERE", "image_prompt": "detailed image description here"}}
  ]
}}"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.95,
            "max_tokens": 2000
        }
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    data = json.loads(raw)
    # Ensure we have exactly SLIDES_COUNT slides
    while len(data["slides"]) < SLIDES_COUNT:
        data["slides"].append({
            "caption": "WHEN YOU RELATE TO THIS",
            "image_prompt": "funny cartoon person looking shocked and pointing at screen, bright colors, meme style"
        })
    data["slides"] = data["slides"][:SLIDES_COUNT]

    print(f"✅ Theme: {data['theme']}")
    print(f"📝 Title: {data['title']}")
    return data


# ── Step 2: Generate images via Pollinations.ai ──────────────────────────────
def generate_image(prompt: str, index: int) -> Path:
    image_path = WORK_DIR / f"meme_{index:02d}.png"

    # Style modifiers for meme aesthetic
    styles = [
        "cartoon illustration, vibrant colors, funny expressive face, clean lines, meme style",
        "digital art, bright bold colors, exaggerated expression, comic style, funny",
        "flat design illustration, colorful, humorous scene, bold outlines, clean art style",
    ]
    style = styles[index % len(styles)]
    full_prompt = f"{prompt}, {style}, vertical 9:16 composition, high quality"
    encoded = requests.utils.quote(full_prompt)
    
    seed = random.randint(1, 99999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={seed}&model=flux"

    print(f"  🎨 Image {index+1}/{SLIDES_COUNT}: {prompt[:45]}...")

    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 5000:
                image_path.write_bytes(resp.content)
                print(f"     ✅ Got it! ({len(resp.content)//1024}KB)")
                return image_path
            else:
                print(f"     ⚠️ Attempt {attempt+1}: status {resp.status_code}, size {len(resp.content)}")
                time.sleep(5)
        except Exception as e:
            print(f"     ⚠️ Attempt {attempt+1} failed: {e}")
            time.sleep(5)

    # Fallback: colored gradient background
    print(f"     🔄 Using colored fallback for image {index+1}")
    bg_colors = ["#2b2d42", "#8338ec", "#3a86ff", "#ff006e", "#fb5607", "#06d6a0"]
    color = bg_colors[index % len(bg_colors)]
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={color.replace('#','')}:size=1080x1920:rate=1",
        "-vf", "format=yuv420p",
        "-frames:v", "1", str(image_path)
    ], capture_output=True)
    return image_path


# ── Step 3: Build slide video with caption ───────────────────────────────────
def make_slide(img_path: Path, caption: str, index: int) -> Path:
    slide_path = WORK_DIR / f"slide_{index:02d}.mp4"

    # Word-wrap caption: max 14 chars per line
    words = caption.split()
    lines = []
    current = []
    for word in words:
        current.append(word)
        if len(' '.join(current)) >= 14:
            lines.append(' '.join(current))
            current = []
    if current:
        lines.append(' '.join(current))
    
    # Build drawtext filters — one per line, stacked
    line_height = 95
    start_y = 1920 - 120 - (len(lines) - 1) * line_height
    
    # Build the filter chain
    vf_parts = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "setsar=1",
        # Dark gradient at bottom for caption readability
        f"drawbox=x=0:y={start_y - 80}:w=1080:h={80 + len(lines)*line_height + 40}:color=black@0.65:t=fill",
    ]

    for i, line in enumerate(lines):
        safe = line.replace("'", "").replace(":", " ").replace("\\", "")
        y = start_y + i * line_height
        vf_parts.append(
            f"drawtext=text='{safe}':"
            f"fontsize=88:fontcolor=white:font=Arial:fontstyle=Bold:"
            f"x=(w-text_w)/2:y={y}:"
            f"shadowcolor=black@0.9:shadowx=5:shadowy=5:"
            f"borderw=4:bordercolor=black@0.8"
        )

    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-vf", vf,
        "-t", str(DURATION_PER_SLIDE),
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(slide_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ Slide {index} render error: {result.stderr[-300:]}")
    return slide_path


# ── Step 4: Get background music ────────────────────────────────────────────
def get_background_music(duration: float) -> Path:
    print("🎵 Getting background music...")
    music_path = WORK_DIR / "music.mp3"

    tracks = [
        "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/WFMU/Broke_For_Free/Directionless_EP/Broke_For_Free_-_01_-_Night_Owl.mp3",
        "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/ccCommunity/Kai_Engel/Irsens_Tales/Kai_Engel_-_04_-_Interlude.mp3",
    ]

    for url in tracks:
        try:
            r = requests.get(url, timeout=20, stream=True)
            if r.status_code == 200:
                with open(music_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                if music_path.stat().st_size > 50000:
                    print(f"✅ Music ready ({music_path.stat().st_size//1024}KB)")
                    return music_path
        except:
            continue

    # Fallback: silent audio
    print("  🎵 Generating silent fallback audio...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo:duration={duration}",
        str(music_path)
    ], capture_output=True)
    return music_path


# ── Step 5: Concatenate slides + add music ───────────────────────────────────
def assemble_video(slide_paths: list, music_path: Path) -> Path:
    print("🎬 Assembling final video...")
    output_path = WORK_DIR / "final_short.mp4"
    concat_path = WORK_DIR / "concat.mp4"
    list_file   = WORK_DIR / "slides.txt"

    with open(list_file, "w") as f:
        for sp in slide_paths:
            f.write(f"file '{sp.resolve()}'\n")

    # Concatenate
    r = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(concat_path)
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print("Concat error:", r.stderr[-500:])

    total = SLIDES_COUNT * DURATION_PER_SLIDE

    # Add music at low volume
    r2 = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(concat_path),
        "-stream_loop", "-1", "-i", str(music_path),
        "-map", "0:v",
        "-map", "1:a",
        "-af", "volume=0.2",
        "-t", str(total),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ], capture_output=True, text=True)

    if r2.returncode != 0 or not output_path.exists():
        # Fallback: no music
        subprocess.run([
            "ffmpeg", "-y", "-i", str(concat_path),
            "-c", "copy", "-movflags", "+faststart",
            str(output_path)
        ], capture_output=True)

    size = output_path.stat().st_size // (1024*1024)
    print(f"✅ Final video: {total:.1f}s, {size}MB")
    return output_path


# ── Step 6: Upload to YouTube ────────────────────────────────────────────────
def get_access_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    })
    r.raise_for_status()
    return r.json()["access_token"]


def upload_to_youtube(video_path: Path, meta: dict) -> str:
    print("📤 Uploading to YouTube...")
    token = get_access_token()

    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size)
        },
        json={
            "snippet": {
                "title": meta["title"],
                "description": meta["description"],
                "tags": meta["tags"],
                "categoryId": "23"
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
    )
    init.raise_for_status()
    upload_url = init.headers["Location"]

    data = video_path.read_bytes()
    up = requests.put(upload_url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "video/mp4",
        "Content-Length": str(len(data))
    }, data=data)
    up.raise_for_status()

    vid_id = up.json()["id"]
    print(f"✅ Live: https://youtube.com/shorts/{vid_id}")
    return vid_id


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\n🚀 Meme Pipeline v3 — {SLIDES_COUNT} slides × {DURATION_PER_SLIDE}s = {SLIDES_COUNT*DURATION_PER_SLIDE:.0f}s video\n")

    data   = generate_meme_scenarios()
    slides = data["slides"]

    print(f"\n🎨 Generating {SLIDES_COUNT} images (this takes ~4 min)...")
    image_paths = []
    for i, slide in enumerate(slides):
        img = generate_image(slide["image_prompt"], i)
        image_paths.append(img)
        time.sleep(3)

    print(f"\n🖼️  Rendering {SLIDES_COUNT} slide videos...")
    slide_videos = []
    for i, (img, slide) in enumerate(zip(image_paths, slides)):
        sv = make_slide(img, slide["caption"], i)
        slide_videos.append(sv)

    music = get_background_music(SLIDES_COUNT * DURATION_PER_SLIDE)
    video = assemble_video(slide_videos, music)
    vid_id = upload_to_youtube(video, data)

    print(f"\n🎉 Done! https://youtube.com/shorts/{vid_id}\n")


if __name__ == "__main__":
    main()
