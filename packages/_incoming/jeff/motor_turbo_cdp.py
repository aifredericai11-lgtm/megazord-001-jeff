#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motor_turbo_cdp.py — SDK Essencial de Alta Concorrência para Google Labs Flow via CDP
=====================================================================================
Conecta a uma aba autenticada do Google Labs Flow (com `extensao_flow_rpc` ativa)
via Chrome DevTools Protocol (WebSocket) e executa:
  1. Geração em lote de `startFrame`s (modelo `BELUGA` — 0 créditos, 9:16).
  2. Disparo em rajada de takes de vídeo (`veo_3_1_i2v_lite_low_priority` — 0 créditos)
     ancorados em `startFrame` (i2v), mantendo até 28 takes simultâneos na mesma aba
     através de 4 workers JS + micro-retry de 2.4s.
  3. Polling cirúrgico de 1 único RPC (`jwpduf`) a cada 4 segundos.
  4. Download HTTP multithread dos arquivos `.mp4` assim que `code == 3`.
"""

import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
import websocket


class FlowTurboCDP:
    def __init__(self, cdp_port: int = 9225):
        self.cdp_port = cdp_port
        self.ws_url = self._descobrir_aba_flow()
        self._msg_id = 0

    def _descobrir_aba_flow(self) -> str:
        url = f"http://127.0.0.1:{self.cdp_port}/json"
        req = urllib.request.urlopen(url, timeout=5)
        abas = json.loads(req.read().decode("utf-8"))
        for aba in abas:
            if "labs.google/fx" in aba.get("url", "") and aba.get("type") == "page":
                return aba["webSocketDebuggerUrl"]
        raise RuntimeError(
            f"Nenhuma aba do Google Labs Flow encontrada em 127.0.0.1:{self.cdp_port}. "
            "Abra https://labs.google/fx/pt/tools/flow/project/<ID> no Chrome."
        )

    def eval_js(self, expression: str, timeout: int = 180):
        """Executa uma Promise/expressão JS no contexto MAIN da aba do Flow."""
        self._msg_id += 1
        ws = websocket.create_connection(self.ws_url, timeout=timeout)
        try:
            payload = {
                "id": self._msg_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expression,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            }
            ws.send(json.dumps(payload))
            while True:
                raw = ws.recv()
                resp = json.loads(raw)
                if resp.get("id") == self._msg_id:
                    res = resp.get("result", {}).get("result", {})
                    if "value" in res:
                        return res["value"]
                    raise RuntimeError(f"Erro JS CDP: {resp}")
        finally:
            ws.close()

    def gerar_startframes_em_lote(
        self,
        itens: List[Dict[str, str]],
        modelo_img: str = "BELUGA",
        proporcao: str = "9:16",
        concorrencia_js: int = 5,
    ) -> Dict[str, str]:
        """
        Gera múltiplos startFrames em paralelo (0 créditos com BELUGA).
        `itens`: lista de dicts `[{"id": "vid_01", "prompt": "..."}]`
        Retorna: `{"vid_01": "<mediaId>", ...}`
        """
        itens_json = json.dumps(itens, ensure_ascii=False)
        js = f"""
        (async () => {{
            const itens = {itens_json};
            const resultados = {{}};
            let idx = 0;
            async function worker() {{
                while (idx < itens.length) {{
                    const atual = itens[idx++];
                    for (let tent = 1; tent <= 6; tent++) {{
                        try {{
                            const r = await window.__FLOW.generateImage(
                                atual.prompt, 1, "{modelo_img}", "{proporcao}", atual.refs || []
                            );
                            if (r && r.ok && r.images && r.images.length > 0) {{
                                resultados[atual.id] = r.images[0].mediaId;
                                break;
                            }}
                        }} catch (e) {{}}
                        await new Promise(res => setTimeout(res, 2200));
                    }}
                }}
            }}
            await Promise.all(Array.from({{length: {concorrencia_js}}}, () => worker()));
            return resultados;
        }})()
        """
        return self.eval_js(js, timeout=300)

    def disparar_e_coletar_takes_video(
        self,
        takes: List[Dict[str, str]],
        pasta_saida: str,
        modelo_video: str = "veo_3_1_i2v_lite_low_priority",
        proporcao: str = "9:16",
        workers_disparo_js: int = 4,
        intervalo_polling_s: float = 4.0,
        timeout_total_s: int = 600,
    ) -> Dict[str, str]:
        """
        Dispara uma lista de takes no Veo 3.1 (com startFrame) usando 4 workers JS + micro-retry 2.4s
        e faz polling cirúrgico via `jwpduf` (1 único RPC por ciclo) até todos ficarem prontos.

        `takes`: lista de dicts:
            `[{"key": "v01_t1", "prompt": "...", "start_frame_id": "<mediaId>"}]`
        Retorna:
            `{"v01_t1": "/caminho/para/v01_t1.mp4", ...}`
        """
        os.makedirs(pasta_saida, exist_ok=True)
        takes_json = json.dumps(takes, ensure_ascii=False)

        # 1. Disparo concorrente na aba com micro-retry de 2.4s contra THROTTLED
        js_disparo = f"""
        (async () => {{
            const fila = {takes_json};
            const mapaUuids = {{}};
            let cursor = 0;

            async function worker() {{
                while (cursor < fila.length) {{
                    const item = fila[cursor++];
                    for (let t = 1; t <= 12; t++) {{
                        try {{
                            const r = await window.__FLOW.generateVideo(
                                item.prompt,
                                item.start_frame_id,
                                "{proporcao}",
                                "{modelo_video}",
                                null
                            );
                            if (r && r.ok && r.uuids && r.uuids.length > 0) {{
                                mapaUuids[item.key] = r.uuids;
                                break;
                            }}
                        }} catch (err) {{}}
                        await new Promise(res => setTimeout(res, 2400));
                    }}
                }}
            }}

            await Promise.all(Array.from({{length: {workers_disparo_js}}}, () => worker()));
            return mapaUuids;
        }})()
        """
        mapa_uuids: Dict[str, List[str]] = self.eval_js(js_disparo, timeout=600)

        # 2. Polling cirúrgico de 1 único RPC (jwpduf) + Download HTTP paralelo
        pendentes = dict(mapa_uuids)
        arquivos_baixados: Dict[str, str] = {}
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=16) as pool_dl:
            futures_dl = {}
            while pendentes and (time.time() - t0) < timeout_total_s:
                todos_uuids = [u for uuids in pendentes.values() for u in uuids]
                js_poll = f"window.__FLOW.checkStatus({json.dumps(todos_uuids)})"
                status_res = self.eval_js(js_poll, timeout=45)

                itens_status = (status_res or {}).get("items", [])
                por_uuid = {it["uuid"]: it for it in itens_status if "uuid" in it}

                chaves_concluidas = []
                for key, uuids in pendentes.items():
                    for u in uuids:
                        st = por_uuid.get(u)
                        if st and st.get("code") == 3 and st.get("url"):
                            destino = os.path.join(pasta_saida, f"{key}.mp4")
                            futures_dl[key] = pool_dl.submit(
                                self._baixar_mp4, st["url"], destino
                            )
                            chaves_concluidas.append(key)
                            break
                        elif st and st.get("code") in (4, 5):
                            chaves_concluidas.append(key)
                            break

                for k in chaves_concluidas:
                    pendentes.pop(k, None)

                if pendentes:
                    time.sleep(intervalo_polling_s)

            for key, fut in futures_dl.items():
                caminho = fut.result()
                if caminho:
                    arquivos_baixados[key] = caminho

        return arquivos_baixados

    @staticmethod
    def _baixar_mp4(url: str, destino: str) -> Optional[str]:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
            f.write(r.read())
        return destino if os.path.exists(destino) and os.path.getsize(destino) > 10_000 else None
