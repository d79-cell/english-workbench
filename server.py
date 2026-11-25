# -*- coding: utf-8 -*-
"""英语工作台本地服务：静态文件 + 数据接口。零外部依赖。"""
import http.server, socketserver, json, os, urllib.parse, webbrowser, sys

# 本地默认 8891；线上部署时注入 PORT 环境变量并绑定 0.0.0.0
PORT = int(os.environ.get("PORT", "8891"))
BASE = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?")[0])
        if path in ("/api/tasks", "/api/words", "/api/wordaudio", "/api/config"):
            name = {
                "/api/tasks": "tasks.json",
                "/api/words": "wordlist.json",
                "/api/wordaudio": "wordaudio.json",
            }.get(path)
            if name:
                data = open(os.path.join(BASE, "data", name), "rb").read()
            else:
                data = json.dumps({"port": PORT, "base": BASE}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        # 音频支持 Range 请求（浏览器拖动播放需要）
        if path.endswith(".mp3"):
            fp = os.path.join(BASE, path.lstrip("/").replace("/", os.sep))
            if os.path.exists(fp):
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(os.path.getsize(fp)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                with open(fp, "rb") as f:
                    self.wfile.write(f.read())
                return
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass  # 静默，避免黑窗刷屏

class ReuseTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    with ReuseTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        url = f"http://127.0.0.1:{PORT}/index.html"
        print(f"英语工作台已启动：{url}", flush=True)
        if "--no-browser" not in sys.argv:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
