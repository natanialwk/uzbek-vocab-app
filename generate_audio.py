import asyncio
import json
import os
import re

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")
INDEX_FILE = os.path.join(os.path.dirname(__file__), "index.html")
VOICE = "uz-UZ-MadinaNeural"

os.makedirs(AUDIO_DIR, exist_ok=True)

async def main():
    import edge_tts

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    m = re.search(r'const DEFAULT_VOCAB\s*=\s*(\[.*?\]);', html, re.DOTALL)
    if not m:
        print("Error: Could not find DEFAULT_VOCAB in index.html")
        return

    vocab = json.loads(m.group(1))
    print(f"Total vocabulary to process: {len(vocab)}")

    semaphore = asyncio.Semaphore(8)
    success_count = 0
    skip_count = 0
    failed_items = []

    async def worker(item):
        nonlocal success_count, skip_count
        no = item.get("no")
        word = item.get("uzbek")
        if not no or not word:
            return

        out_file = os.path.join(AUDIO_DIR, f"{no}.mp3")
        if os.path.exists(out_file) and os.path.getsize(out_file) > 500:
            skip_count += 1
            return

        async with semaphore:
            for attempt in range(4):
                try:
                    communicate = edge_tts.Communicate(word, VOICE)
                    await communicate.save(out_file)
                    success_count += 1
                    total_done = success_count + skip_count
                    if total_done % 50 == 0 or total_done == len(vocab):
                        print(f"Progress: {total_done}/{len(vocab)} audio files ready...")
                    return
                except Exception as e:
                    if attempt == 3:
                        print(f"Failed for [{no}] {word}: {e}")
                        failed_items.append((no, word, str(e)))
                    await asyncio.sleep(0.5 * (attempt + 1))

    tasks = [worker(item) for item in vocab]
    await asyncio.gather(*tasks)

    print(f"\nFinished! Newly generated: {success_count}, Existing: {skip_count}, Failed: {len(failed_items)}")

if __name__ == "__main__":
    asyncio.run(main())
