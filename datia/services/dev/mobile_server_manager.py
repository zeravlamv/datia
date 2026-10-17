import os
import sys
import time
import socket
import subprocess
from urllib.request import urlopen
from urllib.error import URLError
from django.conf import settings

PORT = 8001
BASE_URL = "http://127.0.0.1:8001/"
HEALTH_URL = BASE_URL + "health/"
PID_DIR = os.path.join(settings.BASE_DIR, "datia", "runtime")
PID_FILE = os.path.join(PID_DIR, "mobile_server.pid")

def _ensure_dir():
    os.makedirs(PID_DIR, exist_ok=True)

def _read_pid():
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except:
        return None

def _write_pid(pid):
    _ensure_dir()
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(pid))

def _clear_pid():
    try:
        os.remove(PID_FILE)
    except:
        pass

def is_port_open(host="127.0.0.1", port=PORT):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

def health_check(timeout=2.0):
    try:
        with urlopen(HEALTH_URL, timeout=timeout) as r:
            return r.status == 200
    except:
        return False

def start():
    if health_check() or is_port_open():
        return {"status": "running", "pid": _read_pid(), "url": BASE_URL}
    cmd = [
        sys.executable,
        os.path.join(settings.BASE_DIR, "manage.py"),
        "runserver",
        "0.0.0.0:8001",
        "--settings=config.settings_mobile",
    ]
    p = subprocess.Popen(cmd, cwd=settings.BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _write_pid(p.pid)
    for _ in range(20):
        time.sleep(0.2)
        if health_check():
            return {"status": "started", "pid": p.pid, "url": BASE_URL}
    return {"status": "starting", "pid": p.pid, "url": BASE_URL}

def stop():
    pid = _read_pid()
    if pid:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass
        _clear_pid()
    time.sleep(0.5)
    return {"status": "stopped"}

def status():
    return {"running": health_check(), "pid": _read_pid(), "url": BASE_URL}

