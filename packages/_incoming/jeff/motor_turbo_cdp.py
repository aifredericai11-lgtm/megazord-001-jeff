#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motor_turbo_cdp.py — SDK Essencial de Alta Concorrência para Google Labs Flow via CDP (Mac & Windows)
=====================================================================================================
Conecta a uma aba autenticada do Google Labs Flow (com `extensao_flow_rpc` ativa ou auto-injetada)
via Chrome DevTools Protocol (WebSocket) e executa:
  1. Geração em lote de `startFrame`s (modelo `BELUGA` — 0 créditos, 9:16).
  2. Disparo em rajada de takes de vídeo (`veo_3_1_i2v_lite_low_priority` — 0 créditos)
     ancorados em `startFrame` (i2v), mantendo até 28 takes simultâneos na mesma aba
     através de 4 workers JS + micro-retry de 2.4s.
  3. Polling cirúrgico de 1 único RPC (`jwpduf`) a cada 4 segundos.
  4. Download HTTP multithread dos arquivos `.mp4` assim que `code == 3` (com suporte SSL macOS).
"""

import json
import os
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import websocket as _ws_sync
except ImportError:
    _ws_sync = None

EXT_DIR = Path(__file__).resolve().parent / "extensao_flow_rpc"
_SSL_CTX_UNVERIFIED = ssl._create_unverified_context()


def _cdp_ws_batch(ws_url: str, commands: List[tuple], timeout: float = 180.0, sleep_after_idx: Optional[Dict[int, float]] = None) -> List[Dict[str, Any]]:
    """Executa comandos CDP via `websocket-client` ou `websockets` (fallback automático sem erro de módulo)."""
    if _ws_sync is not None:
        ws = _ws_sync.create_connection(ws_url, timeout=timeout, suppress_origin=True)
        try:
            respostas = []
            for idx, (method, params) in enumerate(commands):
                rid = idx + 1 + int((time.time() * 1000) % 1000000)
                ws.send(json.dumps({"id": rid, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == rid:
                        respostas.append(msg)
                        break
                if sleep_after_idx and idx in sleep_after_idx:
                    time.sleep(sleep_after_idx[idx])
            return respostas
        finally:
            ws.close()
    else:
        import asyncio
        import websockets

        async def _run_async():
            async with websockets.connect(
                ws_url,
                max_size=64 * 1024 * 1024,
                open_timeout=20,
                close_timeout=5,
                ping_interval=None,
            ) as ws:
                respostas = []
                for idx, (method, params) in enumerate(commands):
                    rid = idx + 1 + int((time.time() * 1000) % 1000000)
                    await ws.send(json.dumps({"id": rid, "method": method, "params": params or {}}))
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        msg = json.loads(raw)
                        if msg.get("id") == rid:
                            respostas.append(msg)
                            break
                    if sleep_after_idx and idx in sleep_after_idx:
                        await asyncio.sleep(sleep_after_idx[idx])
                return respostas

        return asyncio.run(_run_async())


def _urlopen_resiliente(req_or_url, timeout: float = 60.0):
    """Faz urlopen com fallback automático para contexto SSL sem verificação (evita erro SSL no MacBook)."""
    try:
        return urllib.request.urlopen(req_or_url, timeout=timeout)
    except Exception as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e) or "SSL" in str(e):
            return urllib.request.urlopen(req_or_url, timeout=timeout, context=_SSL_CTX_UNVERIFIED)
        raise


class FlowTurboCDP:
    def __init__(self, cdp_port: int = 9225):
        self.cdp_port = cdp_port
        self._msg_id = 0
        self.ws_url = self._descobrir_aba_flow()
        self._garantir_core_injetado()

    def _descobrir_aba_flow(self) -> str:
        url = f"http://127.0.0.1:{self.cdp_port}/json/list"
        try:
            with _urlopen_resiliente(url, timeout=5) as req:
                abas = json.loads(req.read().decode("utf-8"))
        except Exception:
            # Tenta abrir o Chrome automaticamente no Mac/Windows caso a porta 9225 esteja fechada
            try:
                from abrir_chrome_flow import garantir_chrome_flow_aberto
                garantir_chrome_flow_aberto(self.cdp_port)
                time.sleep(2.0)
                with _urlopen_resiliente(url, timeout=5) as req:
                    abas = json.loads(req.read().decode("utf-8"))
            except Exception as e:
                raise RuntimeError(
                    f"Não foi possível conectar ao Chrome na porta {self.cdp_port} ({e}).\n"
                    f"Rode primeiro: python abrir_chrome_flow.py"
                )

        # Prioridade 1: Aba com /project/ aberto (flow.google.com ou labs.google)
        for aba in abas:
            u = str(aba.get("url", ""))
            if aba.get("type") == "page" and ("flow.google.com/project/" in u or ("labs.google" in u and "/project/" in u)):
                if aba.get("webSocketDebuggerUrl"):
                    return aba["webSocketDebuggerUrl"]

        # Prioridade 2: Qualquer aba do Flow/Labs
        for aba in abas:
            u = str(aba.get("url", ""))
            if aba.get("type") == "page" and ("flow.google.com" in u or "labs.google/fx" in u):
                if aba.get("webSocketDebuggerUrl"):
                    return aba["webSocketDebuggerUrl"]

        raise RuntimeError(
            f"Nenhuma aba do Google Flow encontrada em 127.0.0.1:{self.cdp_port}.\n"
            "Abra um projeto em https://flow.google.com/project/<ID> na janela do Chrome aberta pelo script."
        )

    def _garantir_core_injetado(self) -> None:
        """
        Verifica se `window.__FLOW` e `window.__zerumCandidateCoreV1` estão ativos na aba.
        Se o usuário no MacBook/Windows não tiver carregado a extensão, injeta `trap-main.js` + `flow-core.js`
        via CDP (`Page.addScriptToEvaluateOnNewDocument`) e recarrega a aba automaticamente!
        """
        try:
            ok = self.eval_js("Boolean(window.__FLOW && window.__zerumCandidateCoreV1 && window.__zerumCandidateCoreV1.info().armadilha)", timeout=10)
            if ok:
                return
        except Exception:
            pass

        trap_js = EXT_DIR / "trap-main.js"
        core_js = EXT_DIR / "flow-core.js"
        if not trap_js.exists() or not core_js.exists():
            return

        codigo = trap_js.read_text(encoding="utf-8") + "\n;\n" + core_js.read_text(encoding="utf-8")
        _cdp_ws_batch(
            self.ws_url,
            [
                ("Page.enable", {}),
                ("Page.addScriptToEvaluateOnNewDocument", {"source": codigo}),
                (
                    "Runtime.evaluate",
                    {
                        "expression": """(() => {
                            const m = location.href.match(/project\\/([0-9a-fA-F-]{36})/);
                            if (location.hostname === 'labs.google' && m) {
                                location.href = 'https://flow.google.com/project/' + m[1];
                                return true;
                            }
                            return false;
                        })()""",
                        "returnByValue": True,
                    },
                ),
                ("Page.reload", {"ignoreCache": False}),
            ],
            timeout=30.0,
            sleep_after_idx={3: 5.5},
        )

    def eval_js(self, expression: str, timeout: int = 180):
        """Executa uma Promise/expressão JS no contexto MAIN da aba do Flow."""
        resp = _cdp_ws_batch(
            self.ws_url,
            [
                (
                    "Runtime.evaluate",
                    {
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True,
                    },
                )
            ],
            timeout=float(timeout),
        )[0]
        res = resp.get("result", {}).get("result", {})
        if "value" in res:
            return res["value"]
        raise RuntimeError(f"Erro JS CDP: {resp}")

    def _eval_js(self, expression: str, timeout: int = 180):
        return self.eval_js(expression, timeout=timeout)

    def gerar_start_frame(
        self,
        prompt: str,
        destino_jpg: Optional[str] = None,
        modelo_img: str = "BELUGA",
        proporcao: str = "9:16",
        refs: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Gera 1 startFrame (BELUGA, 0 créditos) e baixa o .jpg opcionalmente, retornando o mediaId."""
        res = self.eval_js(
            f"window.__FLOW.generateImage({json.dumps(prompt)}, 1, {json.dumps(modelo_img)}, {json.dumps(proporcao)}, {json.dumps(refs or [])})",
            timeout=180,
        )
        if isinstance(res, dict) and res.get("ok") and res.get("images"):
            img0 = res["images"][0]
            mid = img0.get("mediaId")
            url = img0.get("url")
            if destino_jpg and url:
                os.makedirs(os.path.dirname(os.path.abspath(destino_jpg)), exist_ok=True)
                self._baixar_mp4(url, destino_jpg)
            return mid
        return None

    def disparar_video_veo31(
        self,
        prompt: str,
        start_frame_id: Optional[str] = None,
        modelo_video: str = "veo_3_1_i2v_lite_low_priority",
        proporcao: str = "9:16",
        end_frame_id: Optional[str] = None,
    ) -> List[str]:
        """Dispara 1 take de vídeo no Veo 3.1 e retorna a lista de UUIDs candidatos."""
        res = self.eval_js(
            f"window.__FLOW.generateVideo({json.dumps(prompt)}, {json.dumps(start_frame_id)}, {json.dumps(proporcao)}, {json.dumps(modelo_video)}, {json.dumps(end_frame_id)})",
            timeout=120,
        )
        if isinstance(res, dict) and res.get("ok"):
            return list(res.get("uuids") or [])
        return []

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
        """
        os.makedirs(pasta_saida, exist_ok=True)
        takes_json = json.dumps(takes, ensure_ascii=False)

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

    def _baixar_mp4(self, url: str, destino: str) -> Optional[str]:
        # 1ª tentativa: download direto autenticado dentro da própria aba do Chrome (com cookies da conta Google)
        try:
            res_b64 = self.eval_js(
                f"window.__zerumCandidateCoreV1.baixarBase64({json.dumps(url)})",
                timeout=90,
            )
            if isinstance(res_b64, dict) and res_b64.get("ok") and res_b64.get("base64"):
                import base64
                with open(destino, "wb") as f:
                    f.write(base64.b64decode(res_b64["base64"]))
                if os.path.exists(destino) and os.path.getsize(destino) > 10_000:
                    return destino
        except Exception:
            pass

        # 2ª tentativa: download HTTP direto via Python
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _urlopen_resiliente(req, timeout=60) as r, open(destino, "wb") as f:
            f.write(r.read())
        return destino if os.path.exists(destino) and os.path.getsize(destino) > 10_000 else None
