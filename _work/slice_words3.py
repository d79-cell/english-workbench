# -*- coding: utf-8 -*-
"""精确切片 v3：用"静音间隔"定位每个词，不用均匀切、不用中点猜。
原理：n 个词之间有 n-1 个长静音；词 k = [静音(k-1)终点, 静音(k)起点]。
音表音频朗读模式：英文词 + 中文义，两者间是短停顿(<0.9s)，词与词之间是长停顿(>=0.9s)。
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
    if m: dur = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    sils, ss = [], None
    for line in txt.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m: ss = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and ss is not None:
            sils.append((ss, float(m.group(1)))); ss = None
    return dur, sils

def make_segments(dur, sils, n):
    """用词间静音切出 n 段。返回 [(start,end)] 或 None 表示无法可靠对齐。"""
    # 过滤掉开头/结尾的静音（真正的词间静音前后都有语音）
    # 保留所有静音，用词数决定取舍
    if len(sils) == n - 1:
        # 完美：n-1 个词间静音
        segs = []
        prev_end = 0.0
        for s, e in sils:
            segs.append((prev_end, s))
            prev_end = e
        segs.append((prev_end, dur))
        return segs
    if len(sils) == n:
        # 多一个静音：可能开头或结尾有静音，去掉最短的靠边那个
        if sils[0][0] < 0.6:
            sils = sils[1:]
        elif dur - sils[-1][1] < 0.6:
            sils = sils[:-1]
        if len(sils) == n-1:
            segs, prev = [], 0.0
            for s,e in sils: segs.append((prev,s)); prev=e
            segs.append((prev,dur)); return segs
    return None  # 无法可靠对齐，调用方需换阈值重试

result = {}
report = []
for unit, words in wordlist.items():
    src = os.path.join(AUDIO, AUDIO_MAP[unit])
    n = len(words)
    segs = None
    used = None
    # 尝试多组阈值，直到静音数恰好 n-1
    for noise, md in [("-32dB","0.9"),("-34dB","0.8"),("-30dB","0.7"),("-36dB","1.0"),("-28dB","0.9"),("-32dB","0.7")]:
        dur, sils = detect(src, noise, md)
        if not dur: continue
        segs = make_segments(dur, sils, n)
        if segs:
            used = (noise, md, len(sils))
            break
    udir = os.path.join(OUT, unit.replace(" ", ""))
    os.makedirs(udir, exist_ok=True)
    for f in os.listdir(udir): os.remove(os.path.join(udir, f))
    if not segs:
        report.append((unit, n, "ALIGN_FAIL", ""))
        print(f"[{unit}] 对齐失败 词{n}", flush=True)
        continue
    entries = []
    for i, (w, (st, en)) in enumerate(zip(words, segs), 1):
        word = w[0]
        safe = re.sub(r'[\\/:*?"<>| ]', '_', word)
        fname = f"{i:02d}_{safe}.mp3"
        dst = os.path.join(udir, fname)
        a, b = max(0, st), min(dur, en)
        subprocess.run([FF, "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{b-a:.3f}",
                        "-vn", "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", dst],
                       capture_output=True)
        entries.append({"word": word, "cn": w[1], "file": f"音频/单词/{unit.replace(' ','')}/{fname}",
                        "start": round(a, 3), "end": round(b, 3), "dur": round(b-a, 3)})
    result[unit] = entries
    report.append((unit, n, f"OK {used[2]}静音", f"{used[0]}/{used[1]}"))
    print(f"[{unit}] 词{n} 静音{used[2]} 阈值{used[0]}/{used[1]} 首段{entries[0]['dur']}s", flush=True)

json.dump(result, open(os.path.join(BASE, "data", "wordaudio.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[完成] 对齐报告:", report, flush=True)
