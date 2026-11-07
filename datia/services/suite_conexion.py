"""Lee el acceso que Devia guarda para la suite. Datia no lo escribe."""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

CONTROLADOR = "{ODBC Driver 18 for SQL Server}"
_UI_FORBIDDEN = 0x1


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(DATA_BLOB),
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB),
]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL
_kernel32.LocalFree.argtypes = [ctypes.c_void_p]
_kernel32.LocalFree.restype = ctypes.c_void_p


def ruta() -> Path:
    override = os.environ.get("DEVIA_CONEXION_PATH", "").strip()
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "devia" / "conexion.json"


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def desproteger(token: str) -> str:
    crudo = base64.b64decode(token)
    blob, _buffer = _blob(crudo)
    salida = DATA_BLOB()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(blob), None, None, None, None, _UI_FORBIDDEN, ctypes.byref(salida)
    )
    if not ok:
        raise OSError("No se pudo leer el secreto")
    try:
        return ctypes.string_at(salida.pbData, salida.cbData).decode("utf-8")
    finally:
        _kernel32.LocalFree(ctypes.cast(salida.pbData, ctypes.c_void_p))


def _vacio() -> dict:
    return {
        "present": False,
        "usable": False,
        "message": "",
        "host": "",
        "port": 1433,
        "user": "",
        "password": "",
        "driver": CONTROLADOR,
        "trust_server_certificate": True,
        "active_database": "",
    }


def leer() -> dict | None:
    """None si Devia todavía no ha guardado un acceso. Si el fichero existe, manda él."""
    path = ruta()
    if not path.is_file():
        return None
    estado = _vacio()
    estado["present"] = True
    try:
        documento = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        estado["message"] = "El acceso de la suite no se puede leer."
        return estado
    estado["host"] = str(documento.get("host") or "").strip()
    try:
        estado["port"] = int(documento.get("port") or 1433)
    except (TypeError, ValueError):
        estado["port"] = 1433
    estado["user"] = str(documento.get("user") or "").strip()
    estado["driver"] = str(documento.get("driver") or CONTROLADOR).strip() or CONTROLADOR
    estado["trust_server_certificate"] = bool(documento.get("trust_server_certificate", True))
    estado["active_database"] = str(documento.get("active_database") or "").strip()
    token = str(documento.get("password_protected") or "")
    secreto = ""
    if token:
        try:
            secreto = desproteger(token)
        except Exception:
            estado["message"] = "El acceso de la suite no se puede leer en esta sesión de Windows."
            return estado
    if not estado["host"] or not estado["user"] or not secreto:
        estado["message"] = "Falta el servidor, el usuario o el secreto de la suite. Complétalo en Devia."
        return estado
    if documento.get("last_test_ok") is not True:
        estado["message"] = str(documento.get("last_test_message") or "El acceso de la suite no está comprobado.")
        return estado
    actualizado = str(documento.get("updated_at") or "")
    comprobado = str(documento.get("last_test_at") or "")
    if not comprobado or actualizado > comprobado:
        estado["message"] = "El acceso de la suite cambió y todavía no está comprobado."
        return estado
    if not estado["active_database"]:
        estado["message"] = "Falta la base activa de la suite. Elígela en Devia."
        return estado
    estado["usable"] = True
    estado["password"] = secreto
    estado["message"] = str(documento.get("last_test_message") or "")
    return estado
