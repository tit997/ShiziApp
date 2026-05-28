"""
Generate MP3 for all characters + words using edge-tts (Microsoft Xiaoxiao)
Output: app/src/main/assets/audio/{char_codepoint}.mp3 + index.json
"""
import asyncio
import json
import re
from pathlib import Path

import edge_tts

ASSETS_DIR = Path(__file__).parent / "app" / "src" / "main" / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"
CHARS_FILE = ASSETS_DIR / "chars.js"
VOICE = "zh-CN-XiaoxiaoNeural"
MAX_CONCURRENT = 5


async def gen_one(sem, text, filename, audio_dir, index):
    """Generate MP3 for text and add to index. Skip if file exists."""
    filepath = audio_dir / filename
    if filepath.exists():
        index[text] = filename
        return None
    if not text.strip():
        return None

    async with sem:
        try:
            communicate = edge_tts.Communicate(text, voice=VOICE)
            await communicate.save(str(filepath))
            index[text] = filename
            return text
        except Exception as e:
            return f"ERROR:{text}:{e}"


async def main():
    content = CHARS_FILE.read_text(encoding="utf-8")

    # Extract chars and words
    char_matches = re.findall(r"char:\s*'([^']+)'", content)
    seen_chars = set()
    chars = []
    for c in char_matches:
        if c not in seen_chars:
            seen_chars.add(c)
            chars.append(c)

    word_lists = re.findall(r"words:\s*\[([^\]]*)\]", content)
    seen_words = set()
    words = []
    for wl in word_lists:
        for w in re.findall(r"'([^']+)'", wl):
            if w not in seen_words:
                seen_words.add(w)
                words.append(w)

    print(f"Chars: {len(chars)}, Words: {len(words)}, Total: {len(chars)+len(words)}")

    AUDIO_DIR.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    index = {}

    # Generate chars (filename = codepoint.mp3)
    BATCH = 20
    char_results = []
    for i in range(0, len(chars), BATCH):
        batch = chars[i:i + BATCH]
        tasks = [gen_one(sem, c, f"{ord(c)}.mp3", AUDIO_DIR, index) for c in batch]
        char_results.extend(await asyncio.gather(*tasks))
        print(f"  chars [{min(i+BATCH, len(chars))}/{len(chars)}]")

    # Generate words (filename = w_NNN.mp3)
    word_results = []
    for i in range(0, len(words), BATCH):
        batch = words[i:i + BATCH]
        tasks = [gen_one(sem, w, f"w_{i+j}.mp3", AUDIO_DIR, index) for j, w in enumerate(batch)]
        word_results.extend(await asyncio.gather(*tasks))
        print(f"  words [{min(i+BATCH, len(words))}/{len(words)}]")

    # Save index
    (AUDIO_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    errors = [r for r in char_results + word_results if r and str(r).startswith("ERROR:")]
    print(f"\nDone. Errors: {len(errors)}")
    for e in errors[:10]:
        print(f"  {e}")

    total_bytes = sum(f.stat().st_size for f in AUDIO_DIR.glob("*.mp3"))
    print(f"Total audio: {total_bytes / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
