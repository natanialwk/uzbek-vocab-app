import asyncio
import json
import os
import re

BASE_DIR = os.path.dirname(__file__)
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
VOCAB_FILE = os.path.join(BASE_DIR, "vocab.html")
STORIES_FILE = os.path.join(BASE_DIR, "stories.html")
VOICE_UZ = "uz-UZ-MadinaNeural"
VOICE_CN = "zh-CN-XiaoxiaoNeural"

os.makedirs(AUDIO_DIR, exist_ok=True)

def clean_cn(t):
    if not t:
        return "好"
    t = re.sub(r'\(.*?\)|（.*?）', '', t).strip()
    if '/' in t:
        t = t.split('/')[0].strip()
    return t or "好"

async def main():
    import edge_tts

    with open(VOCAB_FILE, "r", encoding="utf-8") as f:
        vocab_html = f.read()

    with open(STORIES_FILE, "r", encoding="utf-8") as f:
        stories_html = f.read()

    m = re.search(r'const DEFAULT_VOCAB\s*=\s*(\[.*?\]);', vocab_html, re.DOTALL)
    if not m:
        print("Error: Could not find DEFAULT_VOCAB in vocab file")
        return

    vocab = json.loads(m.group(1))
    print(f"Total vocabulary items: {len(vocab)} (Uzbek + Chinese)")

    semaphore = asyncio.Semaphore(10)
    success_uz = 0
    skip_uz = 0
    success_cn = 0
    skip_cn = 0

    async def generate_single(text, voice, out_file):
        for attempt in range(4):
            try:
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(out_file)
                return True
            except Exception as e:
                await asyncio.sleep(0.4 * (attempt + 1))
        return False

    async def worker(item):
        nonlocal success_uz, skip_uz, success_cn, skip_cn
        no = item.get("no")
        word_uz = item.get("uzbek")
        raw_cn = item.get("chinese", "")
        word_cn = clean_cn(raw_cn)
        if not no:
            return

        out_uz = os.path.join(AUDIO_DIR, f"{no}.mp3")
        if os.path.exists(out_uz) and os.path.getsize(out_uz) > 500:
            skip_uz += 1
        elif word_uz:
            async with semaphore:
                ok = await generate_single(word_uz, VOICE_UZ, out_uz)
                if ok:
                    success_uz += 1

        out_cn = os.path.join(AUDIO_DIR, f"{no}_cn.mp3")
        if os.path.exists(out_cn) and os.path.getsize(out_cn) > 500:
            skip_cn += 1
        elif word_cn:
            async with semaphore:
                ok = await generate_single(word_cn, VOICE_CN, out_cn)
                if ok:
                    success_cn += 1

    tasks = [worker(item) for item in vocab]
    await asyncio.gather(*tasks)

    print(f"Finished vocab! Uzbek: (New: {success_uz}, Existing: {skip_uz}) | Chinese: (New: {success_cn}, Existing: {skip_cn})")

    # 3. Dialogues Audio
    d_dir = os.path.join(AUDIO_DIR, "dialogues")
    os.makedirs(d_dir, exist_ok=True)
    m_dialogues = re.search(r'const DIALOGUES_DATA\s*=\s*(\[.*?\]);', stories_html, re.DOTALL)
    if m_dialogues:
        dialogues = json.loads(m_dialogues.group(1))
        d_tasks = []
        for d in dialogues:
            for sent in d.get("sentences", []):
                rel_path = sent.get("audio")
                if not rel_path: continue
                out_d = os.path.join(BASE_DIR, rel_path)
                if os.path.exists(out_d) and os.path.getsize(out_d) > 400:
                    continue
                text = sent.get("uzbek")
                if text:
                    async def d_worker(t, p):
                        async with semaphore:
                            await generate_single(t, VOICE_UZ, p)
                    d_tasks.append(d_worker(text, out_d))
        if d_tasks:
            await asyncio.gather(*d_tasks)
            print(f"Generated {len(d_tasks)} new dialogue sentence audio files.")
        else:
            print("All dialogue sentence audio files already up-to-date.")

    # 4. Words Audio
    words_dir = os.path.join(AUDIO_DIR, "words")
    os.makedirs(words_dir, exist_ok=True)
    m_lemmas = re.search(r'const LEMMA_MAP\s*=\s*(\{.*?\});', stories_html, re.DOTALL)
    if m_lemmas:
        lemmas = json.loads(m_lemmas.group(1))
        word_tasks = []
        for k, v in lemmas.items():
            lemma = v.get("lemma")
            clean_key = re.sub(r"[^a-zA-Z0-9_\x27]", "", k.lower()).replace("\x27", "_")
            out_word = os.path.join(words_dir, f"{clean_key}.mp3")
            if os.path.exists(out_word) and os.path.getsize(out_word) > 400:
                continue
            if lemma:
                async def w_worker(t, p):
                    async with semaphore:
                        await generate_single(t, VOICE_UZ, p)
                word_tasks.append(w_worker(lemma, out_word))
        if word_tasks:
            await asyncio.gather(*word_tasks)
            print(f"Generated {len(word_tasks)} new dialogue word audio files.")
        else:
            print("All dialogue word audio files already up-to-date.")

if __name__ == "__main__":
    asyncio.run(main())
