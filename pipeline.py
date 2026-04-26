"""
YouTube Shorts Automation Pipeline
Niche: AI-generated popular/trending content
Frequency: Daily
Length: 1-2 min (Shorts)

Flow:
1. Groq API → generate trending topic + script
2. ElevenLabs API → convert script to voiceover MP3
3. Pexels API → download relevant stock video clips
4. FFmpeg → assemble video (clips + audio + subtitles + Shorts format)
5. YouTube Data API → upload as a Short
"""

import os
import sys
import json
import random
import requests
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

# ── Config (set via environment variables / GitHub Secrets) ──────────────────
GROQ_API_KEY        = os.environ["GROQ_API_KEY"]
ELEVENLABS_API_KEY  = os.environ["ELEVENLABS_API_KEY"]
PEXELS_API_KEY      = os.environ["PEXELS_API_KEY"]
YOUTUBE_CLIENT_ID   = os.environ["YOUTUBE_CLIENT_ID"]
YOUTUBE_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]
YOUTUBE_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]

ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")  # default: Bella

WORK_DIR = Path("output")
WORK_DIR.mkdir(exist_ok=True)

# ── Step 1: Generate trending topic + script via Groq ────────────────────────
def generate_script() -> dict:
    print("🧠 Generating script with Groq...")

    today = datetime.now().strftime("%B %d, %Y")

    prompt = f"""Today is {today}. You create viral YouTube Shorts scripts about popular, trending, or fascinating topics.

Generate a YouTube Short script (60-90 seconds when read aloud, ~150-200 words).
Topics can include: wild facts, AI news, psychology tricks, life hacks, surprising history, viral internet moments, science breakthroughs, or anything trending.

Respond ONLY with valid JSON in this exact format:
{{
  "title": "Catchy YouTube title under 60 chars with emoji",
  "description": "2-3 sentence video description with relevant hashtags at the end",
  "search_keyword": "2-3 word keyword for stock footage search (e.g. 'artificial intelligence', 'human brain', 'space galaxy')",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "script": "Full word-for-word narration script here. Write it naturally for text-to-speech. No stage directions. Just the words to be spoken."
}}"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 1000
        }
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"]

    # Strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    data = json.loads(raw)
    print(f"✅ Topic: {data['title']}")
    print(f"📝 Script ({len(data['script'].split())} words): {data['script'][:80]}...")
    return data


# ── Step 2: Text-to-Speech via ElevenLabs ───────────────────────────────────
def generate_voiceover(script_text: str) -> Path:
    print("🎙️  Generating voiceover with ElevenLabs...")

    audio_path = WORK_DIR / "voiceover.mp3"

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={
            "Authorization": f"Bearer {ELEVENLABS_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "text": script_text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.85,
                "style": 0.3,
                "use_speaker_boost": True
            }
        }
    )
    response.raise_for_status()

    audio_path.write_bytes(response.content)
    print(f"✅ Voiceover saved ({audio_path.stat().st_size // 1024}KB)")
    return audio_path


# ── Step 3: Download stock footage from Pexels ──────────────────────────────
def get_stock_video(keyword: str) -> Path:
    print(f"🎬 Fetching stock video for '{keyword}'...")

    video_path = WORK_DIR / "stock.mp4"

    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": keyword, "per_page": 10, "orientation": "portrait", "size": "medium"}
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])

    if not videos:
        # Fallback keyword
        print(f"⚠️  No results for '{keyword}', trying 'technology'...")
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": "technology future", "per_page": 10, "orientation": "portrait"}
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

    # Pick a random video from results and get HD portrait file
    video = random.choice(videos[:5])
    video_files = video["video_files"]

    # Prefer portrait (height > width), fallback to any
    portrait_files = [f for f in video_files if f.get("height", 0) > f.get("width", 0)]
    chosen = portrait_files[0] if portrait_files else video_files[0]

    dl = requests.get(chosen["link"], stream=True)
    dl.raise_for_status()
    with open(video_path, "wb") as f:
        for chunk in dl.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"✅ Stock video downloaded ({video_path.stat().st_size // 1024}KB)")
    return video_path


# ── Step 4: Get audio duration ───────────────────────────────────────────────
def get_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


# ── Step 5: Assemble video with FFmpeg ──────────────────────────────────────
def assemble_video(stock_path: Path, audio_path: Path, script_text: str, title: str) -> Path:
    print("🎞️  Assembling video with FFmpeg...")

    output_path = WORK_DIR / "final_short.mp4"
    audio_duration = get_duration(audio_path)

    # Build subtitle lines (word-wrap at ~35 chars, show 3 lines at a time)
    words = script_text.split()
    chunks = []
    chunk_size = 8  # words per subtitle chunk
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))

    # Write SRT subtitle file
    srt_path = WORK_DIR / "subtitles.srt"
    time_per_chunk = audio_duration / max(len(chunks), 1)
    with open(srt_path, "w") as f:
        for idx, chunk in enumerate(chunks):
            start = idx * time_per_chunk
            end = start + time_per_chunk
            f.write(f"{idx+1}\n")
            f.write(f"{_fmt_time(start)} --> {_fmt_time(end)}\n")
            f.write(f"{chunk}\n\n")

    # FFmpeg command:
    # - Loop stock video to match audio length
    # - Scale to 1080x1920 (Shorts format)
    # - Add slight darkening overlay for text readability
    # - Burn in subtitles
    # - Mix in audio
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(stock_path),   # loop video
        "-i", str(audio_path),                          # voiceover
        "-filter_complex",
        (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "setsar=1,"
            f"subtitles={srt_path}:force_style="
            "'FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&HFFFFFF,"
            "OutlineColour=&H000000,Outline=3,Shadow=1,Alignment=2,MarginV=80'[v]"
        ),
        "-map", "[v]",
        "-map", "1:a",
        "-t", str(audio_duration + 0.5),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFmpeg stderr:", result.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    print(f"✅ Video assembled: {output_path} ({output_path.stat().st_size // (1024*1024)}MB)")
    return output_path


def _fmt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# ── Step 6: Upload to YouTube ────────────────────────────────────────────────
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

    # Step A: Initialize resumable upload
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
                "tags": metadata["tags"] + ["Shorts", "viral", "trending", "AI"],
                "categoryId": "28"  # Science & Technology
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]

    # Step B: Upload video bytes
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
    print("\n🚀 YouTube Shorts Automation Pipeline Starting...\n")

    # 1. Generate script
    metadata = generate_script()

    # 2. Voiceover
    audio_path = generate_voiceover(metadata["script"])

    # 3. Stock footage
    stock_path = get_stock_video(metadata["search_keyword"])

    # 4. Assemble
    video_path = assemble_video(stock_path, audio_path, metadata["script"], metadata["title"])

    # 5. Upload
    video_id = upload_to_youtube(video_path, metadata)

    print(f"\n🎉 Done! Your Short is live: https://youtube.com/shorts/{video_id}\n")


if __name__ == "__main__":
    main()
