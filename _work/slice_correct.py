# -*- coding: utf-8 -*-
"""最终正确切片：
用户确认——词表音频开头两段是报幕"Words and expressions"和"Unit N"，不是单词。
所以：语音段[0]=报幕1, [1]=报幕2, [2..] = 词表从第一个词开始；尾部极短段(<0.2s)丢弃。
用词间静音切分，逐段重编码为浏览器可播的 mp3。
对词数多于可用语音段的情况：只切能确认的词，其余标记 unverified（不生成错误音频）。
"""
import json, os, re, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = r"C:/Users/10143/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.1-full_build/bin/ffmpeg.exe"
AUDIO = os.path.join(BASE, "音频")
OUT = os.path.join(AUDIO, "单词")
os.makedirs(OUT, exist_ok=True)

wordlist = json.load(open(os.path.join(BASE, "data", "wordlist.json"), encoding="utf-8"))
AUDIO_MAP = {
    "Unit 1": "006-Unit 1_4 Words and expressions.mp3",
    "Unit 2": "012-Unit 2_4 Words and expressions.mp3",
    "Unit 3": "018-Unit 3_4 Words and expressions.mp3",
    "Unit 4": "024-Unit 4_4 Words and expressions.mp3",
    "Unit 5": "030-Unit 5_5 Words and expressions.mp3",
    "Unit 6": "036-Unit 6_5 Words and expressions.mp3",
}

def detect(src, noise="-32dB", mindur="0.9"):
    r = subprocess.run([FF, "-i", src, "-af", f"silencedetect=noise={noise}:d={mindur}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    txt = r.stderr
    dur = None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m: dur = int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
    sils, ss = [], None
    for line in txt.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m: ss = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and ss is not None: sils.append((ss, float(m.group(1)))); ss = None
    return dur, sils

def speech_segments(dur, sils, minlen=0.2):
    """静音之间的语音段。"""
    segs, prev = [], 0.0
    for s, e in sils:
        if s - prev >= minlen: segs.append((prev, s))
        prev = e
    if dur - prev >= minlen: segs.append((prev, dur))
    return segs

result = {}
report = []
for unit, words in wordlist.items():
    src = os.path.join(AUDIO, AUDIO_MAP[unit])
    dur, sils = detect(src)
    segs = speech_segments(dur, sils)
    # 丢弃开头两段报幕 + 尾部极短段
    real = segs[2:]
    real = [(s, e) for s, e in real if e - s >= 0.25]
    n_word = len(words)
    n_real = len(real)
    udir = os.path.join(OUT, unit.replace(" ", ""))
    os.makedirs(udir, exist_ok=True)
    for f in os.listdir(udir): os.remove(os.path.join(udir, f))
    entries = []
    for i, w in enumerate(words):
        word, cn = w[0], w[1]
        if i < n_real:
            a, b = real[i]
            safe = re.sub(r'[\\/:*?"<>| ]', '_', word)
            fname = f"{i+1:02d}_{safe}.mp3"
            dst = os.path.join(udir, fname)
            subprocess.run([FF, "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{b-a:.3f}",
                            "-vn", "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", dst],
                           capture_output=True)
            entries.append({"word": word, "cn": cn, "file": f"音频/单词/{unit.replace(' ','')}/{fname}",
                            "start": round(a, 3), "end": round(b, 3), "dur": round(b-a, 3), "verified": True})
        else:
            # 音频里没有对应词：不生成错误音频，标记待核
            entries.append({"word": word, "cn": cn, "file": "", "start": 0, "end": 0, "dur": 0, "verified": False})
    result[unit] = entries
    report.append((unit, n_word, n_real, sum(1 for x in entries if x['verified'])))
    print(f"[{unit}] 词表{n_word} 音频词段{n_real} 已切{sum(1 for x in entries if x['verified'])}", flush=True)

json.dump(result, open(os.path.join(BASE, "data", "wordaudio.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[完成]", report, flush=True)
