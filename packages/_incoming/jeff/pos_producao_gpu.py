#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pos_producao_gpu.py — Pós-Produção Multiplataforma (Windows NVIDIA CUDA + MacBook Apple Silicon M1/M2/M3/M4)
============================================================================================================
Módulo enxuto e independente com detecção automática de Sistema Operacional e Hardware:
  1. Tesoura Fonética (`Faster-Whisper`):
     - Em Windows/Linux com GPU NVIDIA: usa `device="cuda", compute_type="float16"`.
     - Em MacBook (macOS Apple Silicon M1/M2/M3/M4 ou Intel) ou sem CUDA: usa automaticamente
       `device="cpu", compute_type="int8"` com multithreading nativo (`os.cpu_count()`),
       evitando o erro `Unsupported device cuda` no Mac.
  2. Corte & Concatenação FFmpeg com Aceleração de Hardware Multiplataforma:
     - Windows/Linux NVIDIA: `h264_nvenc -preset p1`
     - MacBook (macOS VideoToolbox M1/M2/M3/M4/Intel): `h264_videotoolbox -b:v 6M -allow_sw 1`
     - Fallback Universal (qualquer máquina): `libx264 -preset ultrafast -crf 20`
"""

import os
import platform
import subprocess
import sys
import threading
from typing import List, Optional, Tuple

_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()
_ENCODER_CACHE: Optional[List[str]] = None


def _configurar_cuda_dlls_windows() -> None:
    """Adiciona torch/lib ao PATH no Windows caso o PyTorch esteja instalado."""
    if sys.platform != "win32":
        return
    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(torch_lib):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(torch_lib)
            if torch_lib not in os.environ.get("PATH", ""):
                os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def obter_whisper_gpu(model_size: str = "small"):
    """
    Inicializa o Faster-Whisper automaticamente:
    - Tenta GPU NVIDIA CUDA (`float16`) se disponível (Windows/Linux).
    - No MacBook (`darwin`) ou sem CUDA, faz fallback imediato para `cpu` (`int8`) usando
      todos os núcleos do Apple Silicon M1/M2/M3/M4.
    """
    global _WHISPER_MODEL
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL

        _configurar_cuda_dlls_windows()
        from faster_whisper import WhisperModel

        n_threads = max(4, min(16, os.cpu_count() or 8))

        # No macOS (darwin), não existe NVIDIA CUDA; vamos direto para CPU/ARM64 int8
        candidatos: List[Tuple[str, str]] = (
            [("cpu", "int8")]
            if sys.platform == "darwin"
            else [("cuda", "float16"), ("cuda", "int8_float16"), ("cpu", "int8")]
        )

        ultimo_erro = None
        for device, compute_type in candidatos:
            try:
                _WHISPER_MODEL = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=n_threads if device == "cpu" else 4,
                    num_workers=4,
                )
                print(f"  [Whisper] Inicializado em device='{device}' ({compute_type})", flush=True)
                return _WHISPER_MODEL
            except Exception as e:
                ultimo_erro = e
                continue

        raise RuntimeError(f"Não foi possível inicializar o faster-whisper: {ultimo_erro}")


def _detectar_melhor_encoder_h264() -> List[str]:
    """
    Detecta e testa o encoder H.264 mais rápido disponível no sistema:
    - macOS (MacBook): `h264_videotoolbox` (chip Apple M1/M2/M3/M4) -> fallback `libx264`
    - Windows/Linux: `h264_nvenc` (GPU NVIDIA) -> fallback `libx264`
    """
    global _ENCODER_CACHE
    if _ENCODER_CACHE is not None:
        return list(_ENCODER_CACHE)

    candidatos: List[Tuple[str, List[str]]] = []
    if sys.platform == "darwin":
        candidatos.append(("h264_videotoolbox", ["-c:v", "h264_videotoolbox", "-b:v", "6M", "-allow_sw", "1"]))
    else:
        candidatos.append(("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p1", "-b:v", "6M"]))

    candidatos.append(("libx264", ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20"]))

    for nome, flags in candidatos:
        try:
            cmd_teste = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                *flags,
                "-f", "null", "-",
            ]
            r = subprocess.run(cmd_teste, capture_output=True, timeout=8)
            if r.returncode == 0:
                _ENCODER_CACHE = flags
                print(f"  [FFmpeg] Encoder de vídeo selecionado ({platform.system()}): {nome}", flush=True)
                return list(_ENCODER_CACHE)
        except Exception:
            continue

    _ENCODER_CACHE = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20"]
    return list(_ENCODER_CACHE)


def detectar_ponto_corte_fonetico(
    caminho_mp4: str,
    margem_pos_fala_s: float = 0.18,
    duracao_minima_s: float = 2.5,
) -> Optional[float]:
    """
    Transcreve os timestamps de palavras do take (`beam_size=1`)
    e retorna o segundo exato onde a última palavra termina (+ margem suave).
    """
    try:
        model = obter_whisper_gpu()
        segments, _ = model.transcribe(
            caminho_mp4,
            beam_size=1,
            word_timestamps=True,
            vad_filter=True,
        )
        ultimo_fim = 0.0
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    if w.end > ultimo_fim:
                        ultimo_fim = w.end
            elif seg.end > ultimo_fim:
                ultimo_fim = seg.end

        if ultimo_fim >= duracao_minima_s:
            return round(ultimo_fim + margem_pos_fala_s, 3)
    except Exception:
        pass
    return None


def cortar_take_preciso(
    entrada_mp4: str,
    saida_mp4: str,
    fim_s: Optional[float] = None,
    inicio_s: float = 0.05,
) -> str:
    """
    Corta o take com recodificação ultrarrápida multiplataforma:
    - NVIDIA (`h264_nvenc`) no Windows/Linux
    - Apple Silicon (`h264_videotoolbox`) no MacBook
    - Fallback automático para `libx264 -preset ultrafast` se necessário.
    """
    if fim_s is None:
        fim_s = detectar_ponto_corte_fonetico(entrada_mp4)

    base_cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{inicio_s:.3f}"]
    if fim_s and fim_s > inicio_s + 1.0:
        base_cmd += ["-to", f"{fim_s:.3f}"]

    encoder_flags = _detectar_melhor_encoder_h264()
    cmd = [
        *base_cmd,
        "-i", entrada_mp4,
        *encoder_flags,
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        saida_mp4,
    ]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        # Fallback garantido em CPU (libx264) caso ocorra qualquer erro de driver/GPU
        cmd_cpu = [
            *base_cmd,
            "-i", entrada_mp4,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            saida_mp4,
        ]
        subprocess.run(cmd_cpu, check=True)
    return saida_mp4


def concatenar_takes_nvenc(lista_takes_mp4: List[str], destino_final_mp4: str) -> str:
    """
    Une os takes já normalizados em ~0.05s via `-c copy`.
    Caso haja diferença de stream, faz fallback automático para o encoder do sistema
    (`h264_videotoolbox` no MacBook / `h264_nvenc` no PC RTX / `libx264` universal).
    """
    os.makedirs(os.path.dirname(os.path.abspath(destino_final_mp4)), exist_ok=True)
    lista_txt = f"{destino_final_mp4}.concat.txt"
    with open(lista_txt, "w", encoding="utf-8") as f:
        for caminho in lista_takes_mp4:
            caminho_limpo = os.path.abspath(caminho).replace("\\", "/")
            f.write(f"file '{caminho_limpo}'\n")

    try:
        cmd_copy = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", lista_txt,
            "-c", "copy",
            "-movflags", "+faststart",
            destino_final_mp4,
        ]
        r = subprocess.run(cmd_copy)
        if r.returncode != 0:
            encoder_flags = _detectar_melhor_encoder_h264()
            cmd_enc = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", lista_txt,
                *encoder_flags,
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                destino_final_mp4,
            ]
            r2 = subprocess.run(cmd_enc)
            if r2.returncode != 0:
                cmd_cpu = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", lista_txt,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    destino_final_mp4,
                ]
                subprocess.run(cmd_cpu, check=True)
    finally:
        if os.path.exists(lista_txt):
            os.remove(lista_txt)

    return destino_final_mp4
