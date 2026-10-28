# Pacote Core: Flow Turbo Engine (`213–324 vídeos/h` em 1 Aba, `0 Créditos`)

- **Autor**: Jeff (`aifredericai11-lgtm`)
- **Branch**: `incoming/jeff`
- **Escopo deste pacote**: **Apenas o núcleo essencial, 100% agnóstico e plug-and-play**, para os demais DEVs implementarem nos próprios sistemas de geração no Google Labs Flow (`labs.google/fx/pt/tools/flow`).

---

## 1. Resumo Executivo & Benchmark Real

Este pacote entrega a engenharia reversa do protocolo interno **`batchexecute` RPC (Google Wiz / TailwindUi)** do Google Labs Flow combinada com o pipeline de pós-produção em GPU local:

| Métrica | Resultado Auditado (1 Única Aba Chrome `:9225`) |
| :--- | :--- |
| **Modelo de Imagem (`startFrame`)** | `BELUGA` / `NARWHAL` (Imagen 3 — **0 créditos**, proporção `9:16`) |
| **Modelo de Vídeo (`i2v`)** | `veo_3_1_i2v_lite_low_priority` (**0 créditos**, **COM `startFrame`**, 3 takes por vídeo) |
| **Takes Simultâneos na Mesma Aba** | **27 a 28 takes renderizando ao mesmo tempo** na GPU do Google |
| **Teste Curto (12 vídeos = 36 takes)** | **`133.3s a 219.4s`** (**`197 a 324 vídeos prontos/hora`**) |
| **Hard Test (100 vídeos = 100 imagens + 300 takes do zero)** | **`28.14 minutos` (`1688.7s`)** = **`213 vídeos prontos/hora`** |

---

## 2. Arquitetura: Os 5 RPC IDs do `batchexecute` (`flow-core.js`)

O Google Labs Flow não utiliza endpoints REST tradicionais (`/api/generate-video`). Todas as operações trafegam por um único endpoint multiplexado:

```text
POST https://labs.google/fx/_/LabsTailwindUi/data/batchexecute?rpcids=<RPC_ID>
Content-Type: application/x-www-form-urlencoded;charset=UTF-8
```

### Mapa de RPC IDs descobertos no bundle `LabsTailwindUi`:

| RPC ID | Operação Interna | Função em `window.__FLOW` | Descrição |
| :--- | :--- | :--- | :--- |
| **`F611Jc`** | `GenerateImage` | `window.__FLOW.generateImage(prompt, count, model, ratio, refs)` | Gera imagens `BELUGA` (`0 créditos`) em `9:16` (código `2`) e retorna o `mediaId` para usar como `startFrame`. |
| **`Zzl0ze`** | `UploadImage` | `window.__FLOW.uploadImage(base64DataUrl)` | Faz upload de frame/avatar externo e retorna o `mediaId` registrado no projeto. |
| **`eb1hJf`** | `GenerateVideo` | `window.__FLOW.generateVideo(prompt, mediaId, ratio, model, endMediaId)` | Dispara geração de vídeo no Veo 3.1 (`veo_3_1_i2v_lite_low_priority`) ancorado no `startFrame` (`mediaId`). |
| **`jwpduf`** | `ListProjectMedia` | `window.__FLOW.checkStatus(uuidArray)` | Lista em **1 única chamada RPC** o status (`generationCode`) e a URL `.mp4` de **todos os takes do projeto**. |
| **`as29s`** | `GetMedia` | Uso interno sob demanda | Busca metadados individuais de um `mediaId` específico. |

---

## 3. Como funciona o Token reCAPTCHA Enterprise Nativo

Cada chamada de escrita (`F611Jc` ou `eb1hJf`) exige um token `reCAPTCHA Enterprise` recém-emitido no header:
```http
x-browser-validation: <token_recaptcha>
```
Em vez de serviços externos de captcha, o `flow-core.js` roda no `world: "MAIN"` da própria aba autenticada do Chrome e invoca diretamente o SDK oficial já carregado pelo Google:

```javascript
const SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV";
const token = await grecaptcha.enterprise.execute(SITE_KEY, {
  action: "FLOW_GENERATION"
});
```
Como o token é gerado dentro da própria aba legítima do navegador (mesmo TLS fingerprint, mesmos cookies e sessão real), o score é máximo e **não há risco de flag por automação externa**.

---

## 4. O Segredo dos `28 Takes Simultâneos`: Correção do Gargalo `jwpduf` vs `as29s`

### Por que outras automações travavam em ~12 takes com `PUBLIC_ERROR_USER_REQUESTS_THROTTLED`?
1. Quando você dispara `eb1hJf` (`generateVideo`), o Google retorna **2 UUIDs** no payload de resposta:
   - `mediaId` (ID real do clipe de vídeo)
   - `workflowId` (ID do job de orquestração)
2. Na implementação antiga de `checkStatus`, o código chamava `jwpduf` (`ListProjectMedia`, que retorna apenas os `mediaId`s) e, para qualquer UUID que não estivesse pronto ou fosse um `workflowId`, disparava **dezenas de chamadas XHR individuais para `as29s` (`GetMedia`) a cada ciclo de polling**.
3. Com 20 takes em andamento (40 UUIDs), cada ciclo de polling gerava **+30 chamadas RPC extras no `batchexecute`**, estourando o bucket de rate-limit HTTP do usuário e causando `PUBLIC_ERROR_USER_REQUESTS_THROTTLED` nos próximos disparos de vídeo!

### A Correção Cirúrgica implementada em `extensao_flow_rpc/flow-core.js`:
- `checkStatus()` agora faz **exclusivamente 1 única chamada RPC `jwpduf`** para buscar o projeto inteiro de uma só vez.
- **Zero chamadas `as29s`** para `workflowId`s ou vídeos ainda em renderização (`generationCode` em `[1, 2, 6]`).
- Redução de **96% no tráfego de RPC**, liberando o bucket do `batchexecute` para aceitar **27 a 28 takes `veo_3_1_i2v_lite_low_priority` com `startFrame` simultaneamente na mesma aba**!

```javascript
// Status codes retornados por jwpduf:
// 1, 2, 6 = Gerando na GPU do Google
// 3       = Pronto (contém a URL direta do .mp4)
// 4, 5    = Falha / Bloqueio de Safety
```

---

## 5. Estrutura dos Arquivos Essenciais deste Repositório

```text
packages/_incoming/jeff/
├── FICHA.md                         # Documentação técnica e guia de implementação para DEVs
├── .env.example                     # Variáveis de ambiente padrão (porta CDP, concorrência)
├── requirements.txt                 # Dependências Python mínimas
├── extensao_flow_rpc/               # Extensão Chrome (Manifest V3 - MAIN world)
│   ├── manifest.json                # Injeção automática em https://labs.google/fx/*
│   ├── trap-main.js                 # Interceptador de Workspace/Project ID ativo
│   └── flow-core.js                 # Motor RPC batchexecute + Correção cirúrgica jwpduf
├── motor_turbo_cdp.py               # SDK Python assíncrono (CDP WebSocket + Fila 4 Workers + Micro-retry 2.4s)
├── pos_producao_gpu.py              # Corte fonético Faster-Whisper CUDA (float16) + Render FFmpeg h264_nvenc
└── benchmark_100_videos_turbo.py    # Pipeline de 3 estágios sobrepostos (Frame -> 3 Takes -> GPU Render)
```

---

## 6. Guia Rápido de Implementação para os DEVs

### Passo 1: Carregar a Extensão RPC no Chrome com CDP
Inicie o Chrome com `--remote-debugging-port=9225` e carregue a pasta `extensao_flow_rpc/` em `chrome://extensions` (Modo do desenvolvedor -> Carregar sem compactação). Abra um projeto no Flow (`https://labs.google/fx/pt/tools/flow/project/<PROJECT_ID>`).

### Passo 2: Usar direto via JavaScript (Console / Puppeteer / Playwright / CDP)
A extensão expõe `window.__FLOW` na página do Flow:

```javascript
// 1. Gerar startFrame 9:16 grátis (BELUGA = 0 créditos)
const imgRes = await window.__FLOW.generateImage(
  "Portrait of a person in a modern studio, natural lighting, 9:16",
  1,          // quantidade
  "BELUGA",   // modelo 0 créditos
  "9:16",     // proporção
  []          // referências opcionais (mediaIds)
);
const startFrameId = imgRes.images[0].mediaId;

// 2. Disparar take Veo 3.1 Lite Low Priority (0 créditos) com startFrame
const vidRes = await window.__FLOW.generateVideo(
  "The person speaks naturally to the camera with subtle hand gestures",
  startFrameId,                        // startFrame mediaId (i2v)
  "9:16",
  "veo_3_1_i2v_lite_low_priority"      // 0 créditos, sem fila com RPC direto
);

// 3. Consultar status de TODOS os takes ativos em 1 único RPC (jwpduf)
const statusRes = await window.__FLOW.checkStatus(vidRes.uuids);
// Quando statusRes.items[i].code === 3 -> statusRes.items[i].url traz o .mp4 pronto!
```

### Passo 3: Usar o Motor Python de Alta Concorrência (`motor_turbo_cdp.py`)
Para disparar dezenas de takes em paralelo sem perder slots por rate-limit momentâneo, use `FlowTurboCDP` em [`motor_turbo_cdp.py`](packages/_incoming/jeff/motor_turbo_cdp.py):
- **4 Workers JS concorrentes** dentro da aba + **micro-retry automático de `2.4s`** quando o `batchexecute` retorna `THROTTLED`.
- Polling unificado a cada **`4.0s`** via `jwpduf`.
- Download HTTP em paralelo fora da thread do navegador + corte fonético via GPU (`pos_producao_gpu.py`).
