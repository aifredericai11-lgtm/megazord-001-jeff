#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pos_producao_gpu.py — Pós-Produção Acelerada por GPU (Faster-Whisper CUDA + NVENC)
==================================================================================
Módulo enxuto e independente para:
  1. Tesoura Fonética em GPU (`Faster-Whisper` float16, `beam_size=1`, `num_workers=4`):
     Remove alucinações ou respiração extra no final de cada take gerado pelo Veo 3.1
     cortando exatamente após a última palavra válida do roteiro.
  2. Concatenação instantânea (`-c copy` em ~0.05s) + Renderização final via hardware
     NVIDIA (`h264_nvenc -preset p1` em ~0.8s por vídeo).
"""

import os
import subprocess
from typing import List, Optional

_WHISPER_MODEL = None


def obter_whisper_gpu(model_size: str = "small"):
    """Inicializa o Faster-Whisper em GPU CUDA (float16) com 4 workers concorrentes."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        _WHISPER_MODEL = WhisperModel(
            model_size,
            device="cuda",
            compute_type="float16",
            num_workers=4,
        )
    return _WHISPER_MODEL


def detectar_ponto_corte_fonetico(
    caminho_mp4: str,
    margem_pos_fala_s: float = 0.18,
    duracao_minima_s: float = 2.5,
) -> Optional[float]:
    """
    Transcreve os timestamps de palavras do take em GPU (`beam_size=1`)
    e retorna o segundo exato onde a última palavra termina (+ margem suave).
    """
    try:
        model = obter_whisper_gpu()
        segments, _ = model.transcribe(
            caminho_mp4,
            language="pt",
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
    """Corta o take com recodificação ultrarrápida em GPU (`h264_nvenc -preset p1`)."""
    if fim_s is None:
        fim_s = detectar_ponto_corte_fonetico(entrada_mp4)

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{inicio_s:.3f}"]
    if fim_s and fim_s > inicio_s + 1.0:
        cmd += ["-to", f"{fim_s:.3f}"]

    cmd += [
        "-i", entrada_mp4,
        "-c:v", "h264_nvenc",
        "-preset", "p1",
        "-b:v", "6M",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        saida_mp4,
    ]
    subprocess.run(cmd, check=True)
    return saida_mp4


def concatenar_takes_nvenc(lista_takes_mp4: List[str], destino_final_mp4: str) -> str:
    """
    Une os takes já normalizados (mesmo codec/resolução/sample rate) em ~0.05s via `-c copy`.
    Caso haja diferença de stream, faz fallback automático para `h264_nvenc -preset p1`.
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
            cmd_nvenc = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0",
                "-i", lista_txt,
                "-c:v", "h264_nvenc", "-preset", "p1", "-b:v", "6M",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                destino_final_mp4,
            ]
            subprocess.run(cmd_nvenc, check=True)
    finally:
        if os.path.exists(lista_txt):
            os.remove(lista_txt)

    return destino_final_mp4
