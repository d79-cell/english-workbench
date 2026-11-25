# -*- coding: utf-8 -*-
"""用词表音频的静音检测，把每个单词切成独立 mp3。
输出：音频/单词/<Unit>/<idx>_<word>.mp3  +  data/wordaudio.json
"""
import json, os, re, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = r"C:/Users/10143/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.1-full_build/bin/ffmpeg.exe"
AUDIO = os.path.join(BASE, "音频")
OUT = os.path.join(AUDIO, "单词")
os.makedirs(OUT, exist_ok=True)

wordlist = json.load(open(os.path.join(BASE, "data", "wordlist.json"), encoding="utf-8"))

# 词表音频文件映射
AUDIO_MAP = {
    "Unit 1": "006-Unit 1_4 Words and expressions.mp3",
    "Unit 2": "012-Unit 2_4 Words and expressions.mp3",
    "Unit 3": "018-Unit 3_4 Words and expressions.mp3",
    "Unit 4": "024-Unit 4_4 Words and expressions.mp3",
    "Unit 5": "030-Unit 5_5 Words and expressions.mp3",
    "Unit 6": "036-Unit 6_5 Words and expressions.mp3",
}

def detect_speech(src):
    """返回语音段 [(start,end)]，用静音检测。"""
    r = subprocess.run(
        [FF, "-i", src, "-af", "silencedetect=noise=-34dB:d=0.28", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="ignore")
    txt = r.stderr
    silences = []
    cur_start = None
    for line in txt.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            cur_start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and cur_start is not None:
            silences.append((cur_start, float(m.group(1))))
            cur_start = None
    # 语音段 = 静音之间
    segs = []
    prev = 0.0
    for s, e in silences:
        if s - prev > 0.30:
            segs.append((prev, s))
        prev = e
    # 末尾
    # 从文件时长估算
    dur = None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m:
        dur = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    if dur and dur - prev > 0.30:
        segs.append((prev, dur))
    return segs

result = {}
for unit, words in wordlist.items():
    src = os.path.join(AUDIO, AUDIO_MAP[unit])
    segs = detect_speech(src)
    n = len(words)
    udir = os.path.join(OUT, unit.replace(" ", ""))
    os.makedirs(udir, exist_ok=True)
    print(f"[{unit}] 词数 {n} 语音段 {len(segs)}", flush=True)

    # 对齐：语音段数与词数不同时，用比例映射（通常音频读单词+中文，段数≈词数×1或×2）
    entries = []
    if len(segs) == n:
        pairs = list(zip(words, segs))
    elif len(segs) > n:
        # 多出的段：取每个词一段，跳过极短段
        segs2 = [s for s in segs if s[1]-s[0] > 0.35]
        if len(segs2) >= n:
            pairs = list(zip(words, segs2[:n]))
        else:
            ratio = len(segs)/n
            pairs = [(words[i], segs[int(i*ratio)]) for i in range(n)]
    else:
        # 段少于词：一段可能含多个词，按顺序均分不足部分
        pairs = []
        for i, w in enumerate(words):
            if i < len(segs):
                pairs.append((w, segs[i]))
            else:
                # 复用最后一段（避免漏）
                pairs.append((w, segs[-1]))
    for i, (w, (st, en)) in enumerate(pairs):
        word = w[0]
        safe = re.sub(r'[\\/:*?"<>| ]', '_', word)
        fname = f"{i+1:02d}_{safe}.mp3"
        dst = os.path.join(udir, fname)
        # 切片：前后各留 0.08 秒余量
        a = max(0, st - 0.08); b = en + 0.12
        subprocess.run([FF, "-y", "-i", src, "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                        "-c", "copy", "-avoid_negative_ts", "make_zero", dst],
                       capture_output=True)
        entries.append({"word": word, "cn": w[1], "file": f"单词/{unit.replace(' ','')}/{fname}",
                        "start": round(a, 3), "end": round(b, 3)})
    result[unit] = entries

json.dump(result, open(os.path.join(BASE, "data", "wordaudio.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[完成] 切片结果写入 data/wordaudio.json", flush=True)
