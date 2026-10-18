"""Arranca ngrok hacia el puerto local y lee la URL pública de su API."""
import json
import os
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

PORT = 8001
LOCAL_API = "http://127.0.0.1:4040/api/tunnels"


def _pick_url(payload):
    tunnels = payload.get("tunnels") or []
    https = []
    for tunnel in tunnels:
        url = str(tunnel.get("public_url") or "")
        if not url.startswith("https://"):
            continue
        addr = str((tunnel.get("config") or {}).get("addr") or "")
        https.append((url, addr))
    for url, addr in https:
        if str(PORT) in addr:
            return url
    if https:
        return https[0][0]
    return None


def current_url():
    try:
        with urlopen(LOCAL_API, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return _pick_url(payload)


def _spawn():
    command = ["ngrok", "http", str(PORT)]
    streams = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            return subprocess.Popen(command, creationflags=flags | 0x01000000, **streams)
        except OSError:
            return subprocess.Popen(command, creationflags=flags, **streams)
    return subprocess.Popen(command, start_new_session=True, **streams)


def open_tunnel():
    existing = current_url()
    if existing:
        return {"status": "ok", "url": existing, "already": True}
    try:
        _spawn()
    except FileNotFoundError:
        return {"status": "error", "message": "ngrok no está instalado en este equipo."}
    except OSError:
        return {"status": "error", "message": "No se pudo arrancar ngrok."}
    for _ in range(30):
        time.sleep(0.4)
        url = current_url()
        if url:
            return {"status": "ok", "url": url, "already": False}
    return {
        "status": "error",
        "message": "ngrok no ha devuelto una dirección. Comprueba que la sesión de ngrok esté iniciada.",
    }
