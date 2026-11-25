# -*- coding: utf-8 -*-
"""用独立 Chromium 验证切片音频可被浏览器解码（检查 duration/readyState）。"""
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8891/%E9%9F%B3%E9%A2%91/%E5%8D%95%E8%AF%8D/Unit4/01_goal.mp3"
URL2 = "http://127.0.0.1:8891/%E9%9F%B3%E9%A2%91/019-Unit%204_1%20Start%20up_1%20Read%20and%20answer.mp3"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    for u in [URL, URL2]:
        result = page.evaluate("""async (u) => {
            const a = new Audio(u);
            return await new Promise(res => {
                let done = false;
                a.onloadedmetadata = () => { if(!done){done=true; res({ok:true, duration:a.duration, readyState:a.readyState});} };
                a.onerror = (e) => { if(!done){done=true; res({ok:false, err:String(a.error && a.error.code)});} };
                setTimeout(()=>{ if(!done){done=true; res({ok:false, err:'timeout', readyState:a.readyState});} }, 8000);
            });
        }""", u)
        print(u.split('/')[-1][:40], result)
    b.close()
