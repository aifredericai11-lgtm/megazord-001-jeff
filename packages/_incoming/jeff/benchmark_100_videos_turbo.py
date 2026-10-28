#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_100_videos_turbo.py — Exemplo Completo do Pipeline de 3 Estágios (213–324 vídeos/h)
=============================================================================================
Demonstra como orquestrar a geração de lotes massivos do zero (100 vídeos = 100 startFrames
BELUGA + 300 takes Veo 3.1 Lite Low Priority com startFrame + Corte Whisper CUDA + NVENC)
em uma única aba do navegador.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from motor_turbo_cdp import FlowTurboCDP
from pos_producao_gpu import cortar_take_preciso, concatenar_takes_nvenc


def executar_lote_turbo(
    roteiros: List[Dict],
    pasta_trabalho: str = "./output_turbo",
    cdp_port: int = 9225,
    tamanho_onda_videos: int = 9,
):
    """
    Executa um lote de vídeos de 3 takes em ondas de 9 vídeos (= 27 takes simultâneos por onda).

    Formato esperado de `roteiros`:
    [
        {
            "id": "video_001",
            "prompt_frame": "Vertical 9:16 portrait of a presenter in a studio, realistic lighting",
            "takes": [
                "Prompt do take 1 com a fala...",
                "Prompt do take 2 com a fala...",
                "Prompt do take 3 com a fala..."
            ]
        },
        ...
    ]
    """
    t0 = time.time()
    os.makedirs(pasta_trabalho, exist_ok=True)
    pasta_takes_brutos = os.path.join(pasta_trabalho, "takes_brutos")
    pasta_takes_cortados = os.path.join(pasta_trabalho, "takes_cortados")
    pasta_prontos = os.path.join(pasta_trabalho, "prontos")
    for p in (pasta_takes_brutos, pasta_takes_cortados, pasta_prontos):
        os.makedirs(p, exist_ok=True)

    flow = FlowTurboCDP(cdp_port=cdp_port)

    # Estágio 1: Gerar todos os startFrames em paralelo (BELUGA = 0 créditos)
    print(f"[1/3] Gerando {len(roteiros)} startFrames (BELUGA 9:16 - 0 créditos)...")
    pedidos_frames = [{"id": r["id"], "prompt": r["prompt_frame"]} for r in roteiros]
    mapa_frames = flow.gerar_startframes_em_lote(pedidos_frames)
    print(f"      -> {len(mapa_frames)}/{len(roteiros)} startFrames prontos em {time.time() - t0:.1f}s")

    # Estágio 2 e 3 sobrepostos: Disparar ondas de 9 vídeos (27 takes) enquanto a GPU local edita a onda anterior
    pool_edicao_gpu = ThreadPoolExecutor(max_workers=8)
    futures_videos_prontos = []

    def _editar_video_completo(vid_id: str, caminhos_brutos: List[str]) -> str:
        cortados = []
        for idx, bruto in enumerate(caminhos_brutos, start=1):
            out_corte = os.path.join(pasta_takes_cortados, f"{vid_id}_t{idx}_cut.mp4")
            cortar_take_preciso(bruto, out_corte)
            cortados.append(out_corte)
        destino_final = os.path.join(pasta_prontos, f"{vid_id}_FINAL.mp4")
        return concatenar_takes_nvenc(cortados, destino_final)

    for i in range(0, len(roteiros), tamanho_onda_videos):
        onda = roteiros[i : i + tamanho_onda_videos]
        takes_onda = []
        for r in onda:
            vid_id = r["id"]
            frame_id = mapa_frames.get(vid_id)
            if not frame_id:
                continue
            for idx_t, prompt_take in enumerate(r["takes"], start=1):
                takes_onda.append({
                    "key": f"{vid_id}_t{idx_t}",
                    "prompt": prompt_take,
                    "start_frame_id": frame_id,
                })

        print(f"[2/3] Disparando onda ({len(takes_onda)} takes simultâneos no Veo 3.1 LP i2v)...")
        baixados = flow.disparar_e_coletar_takes_video(takes_onda, pasta_takes_brutos)

        for r in onda:
            vid_id = r["id"]
            brutos_vid = [
                baixados.get(f"{vid_id}_t{idx_t}")
                for idx_t in range(1, len(r["takes"]) + 1)
            ]
            if all(brutos_vid):
                futures_videos_prontos.append(
                    pool_edicao_gpu.submit(_editar_video_completo, vid_id, brutos_vid)
                )

    prontos = [f.result() for f in futures_videos_prontos]
    pool_edicao_gpu.shutdown(wait=True)

    dt = time.time() - t0
    taxa_hora = (len(prontos) / dt) * 3600 if dt > 0 else 0
    print(f"[3/3] Concluído! {len(prontos)} vídeos prontos em {dt:.1f}s ({taxa_hora:.1f} vídeos/hora).")
    return prontos


if __name__ == "__main__":
    # Exemplo rápido com 3 vídeos (9 takes simultâneos)
    exemplo_roteiros = [
        {
            "id": f"demo_video_{n:02d}",
            "prompt_frame": "Vertical 9:16 medium shot of a charismatic tech creator in a modern studio, natural lighting",
            "takes": [
                "The creator looks at the camera and says in Portuguese: Muita gente achava que o limite por aba era doze takes.",
                "The creator gestures with one hand and says in Portuguese: Mas quando você limpa o polling RPC, a mesma aba roda vinte e oito takes juntos.",
                "The creator smiles and concludes in Portuguese: Resultado: mais de duzentos vídeos prontos por hora com zero créditos.",
            ],
        }
        for n in range(1, 4)
    ]
    executar_lote_turbo(exemplo_roteiros)
