# -*- coding: utf-8 -*-
"""改进版切片：用"长静音(>=0.9s)"作为词条边界，每个词条=英文读音+中文释义。
若静音段数不足词数，则按比例在长语音段内再切。"""
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

def get_info(src, thresh="-32dB", dur="0.9"):
    r = subprocess.run([FF, "-i", src, "-af", f"silencedetect=noise={thresh}:d={dur}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    txt = r.stderr
    dur_s = None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m: dur_s = int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3))
    long_sil = []
    ss = None
    for line in txt.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m: ss = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and ss is not None:
            long_sil.append((ss, float(m.group(1))))
            ss = None
    return dur_s, long_sil

def build_entries(dur, sil, n):
    """n=词条数，返回 n 个 (start,end)。边界取静音中点。"""
    bounds = [0.0]
    for s, e in sil:
        if s > 0.3:
            bounds.append((s+e)/2)
    bounds.append(dur)
    # 若边界数 = n+1，完美
    if len(bounds) == n+1:
        return [(bounds[i], bounds[i+1]) for i in range(n)]
    # 若边界过多（短语被切碎），合并相邻直到 n+1
    if len(bounds) > n+1:
        # 保留间隔最大的 n-1 个内部边界
        inner = bounds[1:-1]
        gaps = []
        for i in range(len(inner)-1):
            gaps.append((inner[i+1]-inner[i], i))
        # 选择分布最均匀的：按目标间隔取最近的点
        target = dur/n
        chosen = []
        for k in range(1, n):
            want = target*k
            chosen.append(min(inner, key=lambda x: abs(x-want)))
        chosen = sorted(set(chosen))
        bounds = [0.0]+chosen+[dur]
        if len(bounds) != n+1:
            # 兜底：均匀切
            return [(dur*i/n, dur*(i+1)/n) for i in range(n)]
        return [(bounds[i], bounds[i+1]) for i in range(n)]
    # 边界不足：均匀切
    return [(dur*i/n, dur*(i+1)/n) for i in range(n)]

result = {}
for unit, words in wordlist.items():
    src = os.path.join(AUDIO, AUDIO_MAP[unit])
    dur, sil = get_info(src)
    n = len(words)
    segs = build_entries(dur, sil, n)
    udir = os.path.join(OUT, unit.replace(" ", ""))
    os.makedirs(udir, exist_ok=True)
    # 清空旧切片
    for f in os.listdir(udir):
        os.remove(os.path.join(udir, f))
    entries = []
    for i, (w, (st, en)) in enumerate(zip(words, segs), 1):
        word = w[0]
        safe = re.sub(r'[\\/:*?"<>| ]', '_', word)
        fname = f"{i:02d}_{safe}.mp3"
        dst = os.path.join(udir, fname)
        a = max(0, st+0.05); b = min(dur, en-0.05)
        subprocess.run([FF, "-y", "-i", src, "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                        "-c", "copy", "-avoid_negative_ts", "make_zero", dst],
                       capture_output=True)
        entries.append({"word": word, "cn": w[1], "file": f"单词/{unit.replace(' ','')}/{fname}",
                        "start": round(a, 3), "end": round(b, 3)})
    result[unit] = entries
    print(f"[{unit}] 词 {n} 音频 {dur:.1f}s 静音边界 {len(sil)} 切片 {len(segs)}", flush=True)

json.dump(result, open(os.path.join(BASE, "data", "wordaudio.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("[完成]", flush=True)
