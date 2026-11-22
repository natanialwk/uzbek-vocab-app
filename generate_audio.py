import asyncio
import json
import os
import re

BASE_DIR = os.path.dirname(__file__)
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
VOCAB_FILE = os.path.join(BASE_DIR, "vocab.html")
STORIES_FILE = os.path.join(BASE_DIR, "stories.html")
DIALOGUES_FILE = os.path.join(BASE_DIR, "dialogues.html")

VOICE_UZ = "uz-UZ-MadinaNeural"
VOICE_CN = "zh-CN-XiaoxiaoNeural"

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(os.path.join(AUDIO_DIR, "dialogues"), exist_ok=True)
os.makedirs(os.path.join(AUDIO_DIR, "stories"), exist_ok=True)
os.makedirs(os.path.join(AUDIO_DIR, "words"), exist_ok=True)

def clean_cn(t):
    if not t:
        return "好"
    t = re.sub(r'\(.*?\)|（.*?）', '', t).strip()
    if '/' in t:
        t = t.split('/')[0].strip()
    return t or "好"

async def main():
    import edge_tts
    semaphore = asyncio.Semaphore(10)

    # 1. Vocab Audio
    with open(VOCAB_FILE, "r", encoding="utf-8") as f:
        vocab_html = f.read()

    m = re.search(r'const DEFAULT_VOCAB\s*=\s*(\[.*?\]);', vocab_html, re.DOTALL)
    if not m:
        print("Error: Could not find DEFAULT_VOCAB in vocab file")
        return

    vocab = json.loads(m.group(1))
    print(f"Total vocabulary items: {len(vocab)} (Uzbek + Chinese)")

    async def generate_single(text, voice, out_file):
        if os.path.exists(out_file) and os.path.getsize(out_file) > 400:
            return True
        for attempt in range(4):
            try:
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(out_file)
                return True
            except Exception:
                await asyncio.sleep(0.4 * (attempt + 1))
        return False

    async def v_worker(item):
        no = item.get("no")
        word_uz = item.get("uzbek")
        raw_cn = item.get("chinese", "")
        word_cn = clean_cn(raw_cn)
        if not no:
            return

        out_uz = os.path.join(AUDIO_DIR, f"{no}.mp3")
        if word_uz:
            async with semaphore:
                await generate_single(word_uz, VOICE_UZ, out_uz)

        out_cn = os.path.join(AUDIO_DIR, f"{no}_cn.mp3")
        if word_cn:
            async with semaphore:
                await generate_single(word_cn, VOICE_CN, out_cn)

    await asyncio.gather(*[v_worker(item) for item in vocab])
    print("Vocab audio check completed.")

    # 2. Dialogues Audio
    with open(DIALOGUES_FILE, "r", encoding="utf-8") as f:
        dialogues_html = f.read()

    m_dialogues = re.search(r'const DIALOGUES_DATA\s*=\s*(\[.*?\]);', dialogues_html, re.DOTALL)
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
                    async def d_worker(t=text, p=out_d):
                        async with semaphore:
                            await generate_single(t, VOICE_UZ, p)
                    d_tasks.append(d_worker())
        if d_tasks:
            await asyncio.gather(*d_tasks)
            print(f"Generated {len(d_tasks)} new dialogue sentence audio files.")
        else:
            print("All dialogue sentence audio files up-to-date.")

    # 3. Stories Audio
    with open(STORIES_FILE, "r", encoding="utf-8") as f:
        stories_html = f.read()

    m_stories = re.search(r'const STORIES_DATA\s*=\s*(\[.*?\]);', stories_html, re.DOTALL)
    if m_stories:
        stories = json.loads(m_stories.group(1))
        s_tasks = []
        for s in stories:
            for sent in s.get("sentences", []):
                rel_path = sent.get("audio")
                if not rel_path: continue
                out_s = os.path.join(BASE_DIR, rel_path)
                if os.path.exists(out_s) and os.path.getsize(out_s) > 400:
                    continue
                text = sent.get("uzbek")
                if text:
                    async def s_worker(t=text, p=out_s):
                        async with semaphore:
                            await generate_single(t, VOICE_UZ, p)
                    s_tasks.append(s_worker())
        if s_tasks:
            await asyncio.gather(*s_tasks)
            print(f"Generated {len(s_tasks)} new story sentence audio files.")
        else:
            print("All story sentence audio files up-to-date.")

    # 4. Words Audio
    m_lemmas = re.search(r'const LEMMA_MAP\s*=\s*(\{.*?\});', dialogues_html, re.DOTALL)
    if m_lemmas:
        lemmas = json.loads(m_lemmas.group(1))
        words_dir = os.path.join(AUDIO_DIR, "words")
        w_tasks = []
        for k, v in lemmas.items():
            lemma = v.get("lemma")
            clean_key = re.sub(r"[^a-zA-Z0-9_\x27]", "", k.lower()).replace("\x27", "_")
            out_word = os.path.join(words_dir, f"{clean_key}.mp3")
            if os.path.exists(out_word) and os.path.getsize(out_word) > 400:
                continue
            if lemma:
                async def w_worker(t=lemma, p=out_word):
                    async with semaphore:
                        await generate_single(t, VOICE_UZ, p)
                w_tasks.append(w_worker())
        if w_tasks:
            await asyncio.gather(*w_tasks)
            print(f"Generated {len(w_tasks)} new dialogue word audio files.")
        else:
            print("All dialogue word audio files up-to-date.")

if __name__ == "__main__":
    asyncio.run(main())
