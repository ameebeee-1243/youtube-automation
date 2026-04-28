"""
YouTube Shorts Meme Pipeline v5
- gTTS voiceover narrating each slide
- FFmpeg-generated lo-fi background beat
- Impact sound effect between slides
- Better meme image prompts
- Guaranteed audio track
"""

import os
import json
import random
import requests
import subprocess
import time
import math
from pathlib import Path
from gtts import gTTS

GROQ_API_KEY          = os.environ["GROQ_API_KEY"]
PEXELS_API_KEY        = os.environ["PEXELS_API_KEY"]
YOUTUBE_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

WORK_DIR = Path("output").resolve()
WORK_DIR.mkdir(exist_ok=True)

SLIDES_COUNT       = 7
DURATION_PER_SLIDE = 3.5   # seconds — enough to read + hear narration


# ── Step 1: Generate meme scenarios ─────────────────────────────────────────
def generate_meme_scenarios() -> dict:
    print("🧠 Generating meme scenarios...")

    themes = [
        "school and studying struggles",
        "being broke and adulting fails",
        "sleep deprivation and 3am thoughts",
        "phone addiction and brain rot",
        "gym motivation vs reality",
        "procrastination and deadlines",
        "overthinking everything",
        "food cravings at midnight",
        "social anxiety moments",
        "gaming rage and fails",
        "chaotic friend group moments",
        "that one friend who does everything wrong",
        "monday morning suffering",
        "when you accidentally open front camera",
    ]
    theme = random.choice(themes)

    prompt = f"""Create a viral YouTube Shorts meme compilation about: "{theme}"

Make exactly {SLIDES_COUNT} slides. Each needs:
- CAPTION: ALL CAPS, punchy, max 7 words, gen-z humor, very relatable. Like real meme text.
- NARRATION: 1 short funny sentence (10-15 words) that a narrator would say about this. Conversational, funny, like a commentary channel.
- IMAGE_PROMPT: Very specific funny scene. Describe exact characters, expressions, setting, colors. Must be clearly funny and relatable to the caption.

Good caption examples: "POV: IT'S 3AM AND YOU'RE COOKED", "ME AFTER ONE SIP OF COFFEE", "BRAIN.EXE HAS STOPPED WORKING"
Good narration examples: "Bro really thought he could pull an all nighter.", "The audacity. The disrespect. The accuracy.", "We have all been this person and you know it."

Respond ONLY in valid JSON:
{{
  "theme": "{theme}",
  "title": "funny viral title with emoji, max 55 chars",
  "description": "2 funny relatable sentences. #memes #relatable #funny #shorts #viral #comedy",
  "tags": ["memes", "relatable", "funny", "shorts", "viral", "humor", "comedy", "trending"],
  "slides": [
    {{
      "caption": "CAPTION IN ALL CAPS",
      "narration": "Short funny narrator line here.",
      "image_prompt": "Very specific funny scene description"
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
    while len(data["slides"]) < SLIDES_COUNT:
        data["slides"].append({
            "caption": "WHEN YOU RELATE TO THIS",
            "narration": "You know exactly what this feels like.",
            "image_prompt": "funny cartoon person pointing at screen looking shocked, bright colors"
        })
    data["slides"] = data["slides"][:SLIDES_COUNT]

    print(f"✅ Theme: {data['theme']}")
    print(f"📝 Title: {data['title']}")
    return data


# ── Step 2: Generate voiceover for each slide ────────────────────────────────
def generate_narrations(slides: list) -> list:
    print("🎙️ Generating voiceovers...")
    audio_paths = []
    for i, slide in enumerate(slides):
        path = WORK_DIR / f"narration_{i:02d}.mp3"
        try:
            tts = gTTS(text=slide["narration"], lang="en", slow=False)
            tts.save(str(path))
            print(f"  ✅ Narration {i+1}: {slide['narration'][:40]}...")
        except Exception as e:
            print(f"  ⚠️ Narration {i+1} failed: {e}, using silence")
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo",
                "-t", "2", str(path)
            ], capture_output=True)
        audio_paths.append(path)
    return audio_paths


# ── Step 3: Generate lo-fi background music with FFmpeg ──────────────────────
def generate_lofi_music(duration: float) -> Path:
    print("🎵 Generating lo-fi background music...")
    music_path = WORK_DIR / "music.mp3"

    # Layer multiple sine waves for a lo-fi chord feel
    # Notes: C(261Hz) + E(329Hz) + G(392Hz) = C major chord, nice and chill
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", (
            f"sine=frequency=261:duration={duration},"
            f"volume=0.15"
        ),
        "-f", "lavfi",
        "-i", (
            f"sine=frequency=329:duration={duration},"
            f"volume=0.1"
        ),
        "-f", "lavfi",
        "-i", (
            f"sine=frequency=392:duration={duration},"
            f"volume=0.08"
        ),
        "-filter_complex",
        "[0][1][2]amix=inputs=3:duration=longest,lowpass=f=800,aecho=0.8:0.9:40:0.4",
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(music_path)
    ], capture_output=True)

    print(f"✅ Music generated ({music_path.stat().st_size//1024}KB)")
    return music_path


# ── Step 4: Generate impact sound effect ─────────────────────────────────────
def generate_impact_sound() -> Path:
    print("💥 Generating impact sound...")
    sfx_path = WORK_DIR / "impact.mp3"

    # Quick descending tone = "womp womp" / impact effect
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=200:duration=0.4",
        "-af", "afade=t=out:st=0.1:d=0.3,volume=0.6",
        "-c:a", "libmp3lame",
        str(sfx_path)
    ], capture_output=True)

    return sfx_path


# ── Step 5: Generate meme images ─────────────────────────────────────────────
def generate_image(prompt: str, index: int) -> Path:
    image_path = WORK_DIR / f"meme_{index:02d}.jpg"

    full_prompt = (
        f"{prompt}, "
        f"funny meme illustration, cartoon style, vibrant saturated colors, "
        f"exaggerated facial expression, clean digital art, "
        f"vertical 9:16 portrait format, detailed background"
    )
    encoded = requests.utils.quote(full_prompt)
    seed = random.randint(1, 99999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&seed={seed}&model=flux"

    print(f"  🎨 Image {index+1}/{SLIDES_COUNT}: {prompt[:50]}...")

    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=90)
            if resp.status_code == 200 and len(resp.content) > 5000:
                image_path.write_bytes(resp.content)
                print(f"     ✅ {len(resp.content)//1024}KB")
                return image_path
            print(f"     ⚠️ Attempt {attempt+1}: {resp.status_code}")
            time.sleep(5)
        except Exception as e:
            print(f"     ⚠️ Attempt {attempt+1}: {e}")
            time.sleep(5)

    # Colorful fallback
    colors = ["1a1a2e", "16213e", "533483", "2b2d42", "3d405b", "81b29a", "f2cc8f", "e07a5f"]
    color = colors[index % len(colors)]
    print(f"     🔄 Color fallback")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c={color}:size=1080x1920:rate=1",
        "-vf", "format=yuv420p",
        "-frames:v", "1", str(image_path)
    ], capture_output=True)
    return image_path


# ── Step 6: Render each slide with caption + narration + sfx ─────────────────
def make_slide(img_path: Path, caption: str, narration_path: Path, sfx_path: Path, index: int) -> Path:
    slide_path = WORK_DIR / f"slide_{index:02d}.mp4"

    # Word wrap caption
    words = caption.split()
    lines, current = [], []
    for word in words:
        current.append(word)
        if len(' '.join(current)) >= 16:
            lines.append(' '.join(current))
            current = []
    if current:
        lines.append(' '.join(current))

    line_height = 95
    start_y = 1920 - 160 - (len(lines) - 1) * line_height

    vf_parts = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "setsar=1",
        f"drawbox=x=0:y={start_y-80}:w=1080:h={80+len(lines)*line_height+60}:color=black@0.72:t=fill",
    ]
    for i, line in enumerate(lines):
        safe = line.replace("'","").replace(":","").replace("\\","").replace(",","").replace(";","").replace("!","").replace("?","")
        y = start_y + i * line_height
        vf_parts.append(
            f"drawtext=text='{safe}':"
            f"fontsize=88:fontcolor=white:"
            f"x=(w-text_w)/2:y={y}:"
            f"shadowcolor=black@0.95:shadowx=5:shadowy=5:"
            f"borderw=5:bordercolor=black"
        )

    vf = ",".join(vf_parts)

    # Mix narration + sfx at start
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-i", str(narration_path),
        "-i", str(sfx_path),
        "-filter_complex",
        f"[0:v]{vf}[v];"
        f"[1:a]volume=1.8,apad=pad_dur={DURATION_PER_SLIDE}[nar];"
        f"[2:a]volume=0.5,adelay=0|0[sfx];"
        f"[nar][sfx]amix=inputs=2:duration=longest[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-t", str(DURATION_PER_SLIDE),
        "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        str(slide_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ Slide {index} error: {result.stderr[-400:]}")
        # Fallback: no audio mix
        cmd2 = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-i", str(narration_path),
            "-filter_complex", f"[0:v]{vf}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", str(DURATION_PER_SLIDE),
            "-r", "30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            str(slide_path)
        ]
        subprocess.run(cmd2, capture_output=True)
    else:
        print(f"  ✅ Slide {index+1} done")
    return slide_path


# ── Step 7: Concat slides + add background music ─────────────────────────────
def assemble_video(slide_paths: list, music_path: Path) -> Path:
    print("🎬 Assembling final video...")
    output_path = WORK_DIR / "final_short.mp4"
    concat_path = WORK_DIR / "concat.mp4"
    list_file   = WORK_DIR / "slides.txt"

    valid = [sp for sp in slide_paths if sp.exists() and sp.stat().st_size > 1000]
    print(f"  📊 Valid slides: {len(valid)}/{len(slide_paths)}")
    if not valid:
        raise RuntimeError("No valid slides!")

    with open(list_file, "w") as f:
        for sp in valid:
            f.write(f"file '{sp}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(concat_path)
    ], capture_output=True, check=True)

    total = len(valid) * DURATION_PER_SLIDE

    # Mix background music quietly under narration
    r = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(concat_path),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex",
        "[0:a]volume=1.0[speech];"
        "[1:a]volume=0.15,atrim=duration=" + str(total) + "[music];"
        "[speech][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-t", str(total),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ], capture_output=True, text=True)

    if r.returncode != 0 or not output_path.exists():
        print("Audio mix fallback...")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(concat_path),
            "-c", "copy", "-movflags", "+faststart", str(output_path)
        ], capture_output=True)

    size = output_path.stat().st_size // (1024*1024)
    print(f"✅ Final: {total:.1f}s, {size}MB")
    return output_path


# ── Step 8: Upload to YouTube ────────────────────────────────────────────────
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
    print(f"\n🚀 Meme Pipeline v5 — {SLIDES_COUNT} slides × {DURATION_PER_SLIDE}s\n")

    data   = generate_meme_scenarios()
    slides = data["slides"]

    narration_paths = generate_narrations(slides)

    sfx_path = generate_impact_sound()

    total_duration = SLIDES_COUNT * DURATION_PER_SLIDE
    music_path = generate_lofi_music(total_duration + 5)

    print(f"\n🎨 Generating {SLIDES_COUNT} meme images (~4 min)...")
    image_paths = []
    for i, slide in enumerate(slides):
        img = generate_image(slide["image_prompt"], i)
        image_paths.append(img)
        time.sleep(2)

    print(f"\n🖼️  Rendering slides with captions + audio...")
    slide_videos = []
    for i, (img, slide, nar) in enumerate(zip(image_paths, slides, narration_paths)):
        sv = make_slide(img, slide["caption"], nar, sfx_path, i)
        slide_videos.append(sv)

    video  = assemble_video(slide_videos, music_path)
    vid_id = upload_to_youtube(video, data)

    print(f"\n🎉 Done! https://youtube.com/shorts/{vid_id}\n")


if __name__ == "__main__":
    main()
