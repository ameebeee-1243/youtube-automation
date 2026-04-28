"""
YouTube Shorts Automation Pipeline v2
Format: AI Meme Image Compilation with bold captions + music
- Groq → generates 5-8 funny/relatable meme scenarios
- Pollinations.ai → generates meme-style images (free, no API key)
- FFmpeg → assembles fast-cut video with bold captions + music
- Free Music Archive → royalty-free background music
- YouTube API → uploads as a Short
"""

import os
import json
import random
import requests
import subprocess
import time
import urllib.request
from pathlib import Path

GROQ_API_KEY          = os.environ["GROQ_API_KEY"]
PEXELS_API_KEY        = os.environ["PEXELS_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

WORK_DIR = Path("output")
WORK_DIR.mkdir(exist_ok=True)

# ── Step 1: Generate meme scenarios with Groq ────────────────────────────────
def generate_meme_scenarios() -> dict:
    print("🧠 Generating meme scenarios with Groq...")

    themes = [
        "school and studying struggles",
        "social anxiety and awkward situations",
        "being broke and adulting",
        "sleep deprivation and late nights",
        "phone addiction and internet culture",
        "food and hungry brain thoughts",
        "gym and fitness motivation fails",
        "work and Monday morning pain",
        "friendship and chaotic friend groups",
        "gaming and rage moments",
        "procrastination and deadlines",
        "overthinking at 3am",
    ]
    theme = random.choice(themes)

    prompt = f"""You are creating a viral YouTube Shorts meme compilation about: "{theme}"

Generate exactly 6 meme slides. Each slide has:
1. A BOLD CAPTION (funny, relatable, max 8 words, ALL CAPS style, like meme text)
2. An IMAGE PROMPT for AI image generation (describe a funny/expressive scene, cartoon or realistic, that matches the caption)

Respond ONLY with valid JSON:
{{
  "theme": "{theme}",
  "title": "relatable youtube title with emoji, max 60 chars",
  "description": "funny 2-sentence description #memes #relatable #funny #shorts",
  "tags": ["memes", "relatable", "funny", "shorts", "viral"],
  "slides": [
    {{
      "caption": "WHEN YOU STUDY ALL NIGHT BUT FORGET EVERYTHING",
      "image_prompt": "cartoon student sitting at desk, brain completely empty, floating question marks, textbooks everywhere, exhausted face, vibrant colors, meme style illustration"
    }}
  ]
}}"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.95,
            "max_tokens": 1500
        }
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    data = json.loads(raw)
    print(f"✅ Theme: {data['theme']}")
    print(f"📝 Title: {data['title']}")
    print(f"🎭 Generated {len(data['slides'])} meme slides")
    return data


# ── Step 2: Generate meme images via Pollinations.ai ────────────────────────
def generate_meme_image(prompt: str, index: int) -> Path:
    image_path = WORK_DIR / f"meme_{index:02d}.jpg"

    # Enhance prompt for meme style
    enhanced = f"{prompt}, vibrant colors, high contrast, funny expression, meme style, 9:16 vertical format, detailed illustration"
    encoded = requests.utils.quote(enhanced)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={random.randint(1,9999)}"

    print(f"  🎨 Generating image {index+1}: {prompt[:50]}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200 and len(response.content) > 10000:
                image_path.write_bytes(response.content)
                print(f"  ✅ Image {index+1} saved ({image_path.stat().st_size // 1024}KB)")
                return image_path
            else:
                print(f"  ⚠️ Attempt {attempt+1} failed, retrying...")
                time.sleep(3)
        except Exception as e:
            print(f"  ⚠️ Attempt {attempt+1} error: {e}, retrying...")
            time.sleep(3)

    # Fallback: use a colored gradient via FFmpeg
    print(f"  ⚠️ Using fallback for image {index+1}")
    colors = ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#2b2d42", "#8d99ae"]
    color = colors[index % len(colors)]
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={color.replace('#','')}:size=1080x1920:rate=1",
        "-frames:v", "1", str(image_path)
    ], capture_output=True)
    return image_path


# ── Step 3: Get background music ────────────────────────────────────────────
def get_background_music() -> Path:
    print("🎵 Getting background music...")
    music_path = WORK_DIR / "music.mp3"

    # Curated list of free lo-fi/chill tracks from Free Music Archive
    tracks = [
        "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/WFMU/Broke_For_Free/Directionless_EP/Broke_For_Free_-_01_-_Night_Owl.mp3",
        "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/ccCommunity/Kai_Engel/Irsens_Tales/Kai_Engel_-_04_-_Interlude.mp3",
    ]

    for track_url in tracks:
        try:
            response = requests.get(track_url, timeout=30, stream=True)
            if response.status_code == 200:
                with open(music_path, "wb") as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                if music_path.stat().st_size > 50000:
                    print(f"✅ Music downloaded ({music_path.stat().st_size // 1024}KB)")
                    return music_path
        except Exception as e:
            print(f"  ⚠️ Track failed: {e}")
            continue

    # Fallback: generate a simple beat with FFmpeg sine wave
    print("  🎵 Generating fallback music tone...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=60",
        "-af", "volume=0.1",
        str(music_path)
    ], capture_output=True)
    return music_path


# ── Step 4: Assemble video with FFmpeg ──────────────────────────────────────
def assemble_video(image_paths: list, captions: list, music_path: Path, title: str) -> Path:
    print("🎞️  Assembling video with FFmpeg...")

    output_path = WORK_DIR / "final_short.mp4"
    duration_per_slide = 2.5  # seconds per meme slide
    total_duration = len(image_paths) * duration_per_slide

    # Step A: Create individual slide videos with captions burned in
    slide_videos = []
    for i, (img_path, caption) in enumerate(zip(image_paths, captions)):
        slide_path = WORK_DIR / f"slide_{i:02d}.mp4"

        # Wrap caption text
        words = caption.split()
        lines = []
        line = []
        for word in words:
            line.append(word)
            if len(' '.join(line)) > 20:
                lines.append(' '.join(line))
                line = []
        if line:
            lines.append(' '.join(line))
        wrapped = '\\n'.join(lines)

        # Escape special chars for FFmpeg drawtext
        safe_caption = wrapped.replace("'", "\\'").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-vf", (
                f"scale=1080:1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,"
                f"setsar=1,"
                # Dark semi-transparent bar behind text
                f"drawbox=x=0:y=ih-320:w=iw:h=320:color=black@0.6:t=fill,"
                # Main caption text
                f"drawtext=text='{safe_caption}':"
                f"fontsize=72:fontcolor=white:font=Arial:fontstyle=Bold:"
                f"x=(w-text_w)/2:y=h-260:"
                f"shadowcolor=black:shadowx=4:shadowy=4:"
                f"borderw=3:bordercolor=black"
            ),
            "-t", str(duration_per_slide),
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(slide_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠️ Slide {i} error: {result.stderr[-500:]}")
        else:
            slide_videos.append(slide_path)
            print(f"  ✅ Slide {i+1}/{len(image_paths)} rendered")

    # Step B: Concatenate all slides
    concat_path = WORK_DIR / "concat.mp4"
    list_file = WORK_DIR / "slides.txt"
    with open(list_file, "w") as f:
        for sv in slide_videos:
            f.write(f"file '{sv.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy", str(concat_path)
    ], capture_output=True)

    # Step C: Add music
    cmd = [
        "ffmpeg", "-y",
        "-i", str(concat_path),
        "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume=0.25,atrim=duration={total_duration}[music];"
        f"[0:a][music]amix=inputs=2:duration=first[aout]"
        if concat_path.stat().st_size > 0 else
        f"[1:a]volume=0.25,atrim=duration={total_duration}[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ]

    # Simpler audio mix if no audio in concat
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: just add music without mixing
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(concat_path),
            "-i", str(music_path),
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ], capture_output=True)

    size_mb = output_path.stat().st_size // (1024*1024)
    print(f"✅ Video assembled: {output_path} ({size_mb}MB, {total_duration:.1f}s)")
    return output_path


# ── Step 5: Upload to YouTube ────────────────────────────────────────────────
def get_youtube_access_token() -> str:
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "refresh_token": YOUTUBE_REFRESH_TOKEN,
            "grant_type": "refresh_token"
        }
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_to_youtube(video_path: Path, metadata: dict) -> str:
    print("📤 Uploading to YouTube...")
    access_token = get_youtube_access_token()

    init_resp = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size)
        },
        json={
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata["tags"] + ["Shorts", "viral", "memes", "relatable"],
                "categoryId": "23"  # Comedy
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]

    with open(video_path, "rb") as f:
        video_bytes = f.read()

    upload_resp = requests.put(
        upload_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_bytes))
        },
        data=video_bytes
    )
    upload_resp.raise_for_status()

    video_id = upload_resp.json()["id"]
    print(f"✅ Uploaded! https://youtube.com/shorts/{video_id}")
    return video_id


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("\n🚀 YouTube Shorts Meme Pipeline v2 Starting...\n")

    # 1. Generate meme scenarios
    data = generate_meme_scenarios()
    slides = data["slides"]

    # 2. Generate images
    print(f"\n🎨 Generating {len(slides)} meme images...")
    image_paths = []
    for i, slide in enumerate(slides):
        img = generate_meme_image(slide["image_prompt"], i)
        image_paths.append(img)
        time.sleep(2)  # be polite to Pollinations API

    # 3. Get music
    music_path = get_background_music()

    # 4. Assemble
    captions = [s["caption"] for s in slides]
    video_path = assemble_video(image_paths, captions, music_path, data["title"])

    # 5. Upload
    video_id = upload_to_youtube(video_path, data)

    print(f"\n🎉 Done! https://youtube.com/shorts/{video_id}\n")


if __name__ == "__main__":
    main()
