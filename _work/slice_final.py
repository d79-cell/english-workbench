# -*- coding: utf-8 -*-
"""最终切片：合并相邻静音，用真实词间停顿切分，每个词=英文读音+中文释义整段。"""
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

def detect(src, noise, mindur):
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
        if m and ss is not None: sils.append([ss, float(m.group(1))]); ss = None
    return dur, sils

def merge_adjacent(sils, gap=0.25):
    """合并间隔小于 gap 的相邻静音（同一个词中间的停顿）。"""
    if not sils: return []
    out = [list(sils[0])]
    for s, e in sils[1:]:
        if s - out[-1][1] < gap:
            out[-1][1] = e
        else:
            out.append([s, e])
    return out

def segments(dur, sils, n):
    """用词间静音切 n 段。sils 已合并、已去掉首尾。"""
    if len(sils) != n - 1:
        return None
    segs, prev = [], 0.0
    for s, e in sils:
        segs.append((prev, s)); prev = e
    segs.append((prev, dur))
    return segs

result = {}
for unit, words in wordlist.items():
    src = os.path.join(AUDIO, AUDIO_MAP[unit])
    n = len(words)
    segs, used = None, None
    for noise, md, gap in [("-34dB","0.25",0.25),("-32dB","0.3",0.3),("-34dB","0.3",0.25),
                            ("-30dB","0.3",0.3),("-36dB","0.25",0.25),("-32dB","0.25",0.25)]:
        dur, sils = detect(src, noise, md)
        if not dur: continue
        merged = merge_adjacent(sils, gap)
        # 去掉开头静音(从0开始)和结尾静音(接近dur)
        if merged and merged[0][0] < 0.3: merged = merged[1:]
        if merged and dur - merged[-1][1] < 0.3: merged = merged[:-1]
        segs = segments(dur, merged, n)
        if segs:
            used = (noise, md, gap, len(sils), len(merged)); break
    udir = os.path.join(OUT, unit.replace(" ", ""))
    os.makedirs(udir, exist_ok=True)
    for f in os.listdir(udir): os.remove(os.path.join(udir, f))
    if not segs:
        print(f"[{unit}] FAIL 词{n}", flush=True)
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
    durs = [x['dur'] for x in entries]
    print(f"[{unit}] 词{n} 原始静音{used[3]} 合并后{used[4]} 阈值{used[0]}/{used[1]} 时长范围{min(durs):.2f}-{max(durs):.2f}s", flush=True)

json.dump(result, open(os.path.join(BASE, "data", "wordaudio.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[完成]", flush=True)
