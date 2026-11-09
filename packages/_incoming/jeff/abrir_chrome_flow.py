#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
abrir_chrome_flow.py — Inicializador Multiplataforma (MacBook macOS / Windows / Linux)
======================================================================================
Abre o Google Chrome com:
  1. `--remote-debugging-port=9225`
  2. `--user-data-dir` dedicado (`~/.chrome-flow-profile` no Mac/Linux ou `%LOCALAPPDATA%\\Google\\Chrome\\FlowProfile` no Windows)
     * IMPORTANTE NO MACBOOK: O Chrome 136+ no macOS IGNORA `--remote-debugging-port` se não houver `--user-data-dir` exclusivo
       ou se o Chrome padrão já estiver aberto no Dock! Este script resolve isso automaticamente.
  3. Carregamento automático da extensão `extensao_flow_rpc` (`trap-main.js` + `flow-core.js`).
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CDP_PORT = int(os.environ.get("FLOW_CDP_PORT", "9225"))
EXT_DIR = Path(__file__).resolve().parent / "extensao_flow_rpc"
FLOW_HOME_URL = "https://flow.google.com/"


def _cdp_ja_ativo(port: int = CDP_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def _encontrar_chrome_executavel() -> str:
    if sys.platform == "darwin":
        candidatos_mac = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        for c in candidatos_mac:
            if os.path.isfile(c):
                return c
    elif sys.platform == "win32":
        candidatos_win = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for c in candidatos_win:
            if os.path.isfile(c):
                return c
    else:
        for b in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            p = shutil.which(b)
            if p:
                return p
    raise FileNotFoundError("Executável do Google Chrome não encontrado no sistema.")


def _obter_pasta_perfil() -> str:
    if sys.platform == "win32":
        base = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\FlowProfile")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Google/Chrome/FlowProfile")
    else:
        base = os.path.expanduser("~/.config/google-chrome-flow-profile")
    os.makedirs(base, exist_ok=True)
    return base


def garantir_chrome_flow_aberto(port: int = CDP_PORT, url_inicial: str = FLOW_HOME_URL) -> bool:
    """Garante que o Chrome com CDP na porta `port` está aberto no Mac, Windows ou Linux."""
    if _cdp_ja_ativo(port):
        return True

    exe = _encontrar_chrome_executavel()
    perfil = _obter_pasta_perfil()
    ext_str = str(EXT_DIR.resolve())

    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={perfil}",
        f"--disable-extensions-except={ext_str}",
        f"--load-extension={ext_str}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--window-size=1440,900",
        url_inicial,
    ]

    print(f"🚀 Abrindo Chrome Flow ({sys.platform}) na porta CDP {port}...")
    print(f"   Perfil dedicado: {perfil}")
    print(f"   Extensão RPC:    {ext_str}")

    if sys.platform == "win32":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200
        )
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    for _ in range(20):
        time.sleep(0.5)
        if _cdp_ja_ativo(port):
            print(f"✅ Chrome CDP ativo em http://127.0.0.1:{port}!")
            print("👉 Faça login no Google Flow e abra um projeto (https://flow.google.com/project/<ID>).")
            return True

    print(f"⚠️ Chrome iniciado, mas a porta {port} ainda não respondeu. Verifique se abriu na tela.")
    return False


if __name__ == "__main__":
    garantir_chrome_flow_aberto()

