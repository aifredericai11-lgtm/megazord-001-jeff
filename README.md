# FICHA — `flow-turbo-rpc` (Motor Flow RPC 213–324 vídeos/h em 1 Aba, 0 Créditos)

**Dono:** Jeff (`aifredericai11-lgtm`)
**Pasta:** `packages/_incoming/jeff/`

## 1. Qual estação?

- [ ] **Infra de contas** — perfil, proxy, fanpage, aquecimento, multilogin
- [x] **Produção** — criar criativo (imagem, vídeo, copy, montagem)
- [ ] **Produção retroativa** — recuperar/refazer o que já funcionou
- [ ] **Postagem** — publicar na página, agendar, conferir
- [ ] **Análise** — métrica, venda, o que pegou, que página está queimando
- [ ] **Banco / dados** — onde a operação guarda o estado
- [ ] Outra:

## 2. O que faz, em 3 linhas

Recebe lista de roteiros (prompt de `startFrame` + 3 prompts de takes com fala) → gera as imagens em `BELUGA` (`0 créditos`, `9:16`) e dispara até **28 takes simultâneos na mesma aba** no `veo_3_1_i2v_lite_low_priority` (`0 créditos`, **com `startFrame`**) via RPC interno `batchexecute` → corta alucinações finais com Faster-Whisper CUDA (`float16`) e concatena via `h264_nvenc` entregando **213 a 324 vídeos completos por hora** em 1 única aba.

## 3. Roda em produção?

- Roda de verdade hoje? **Sim.**
- Desde quando? **Outubro/2026.**
- Quanto? **Testado e auditado em lote contínuo de 100 vídeos do zero (100 imagens + 300 takes Veo 3.1 LP com `startFrame` + edição GPU) concluídos em `28.14 minutos` (`213 vídeos/hora`) e lotes curtos de 12 vídeos em `133s–219s` (`197–324 vídeos/hora`) em uma única aba.**
- Quanto tempo de atenção sua por dia ele exige? **~5 min para disparar a leva.**
- Quanto custa por mês para rodar? **Assinatura Google Labs Flow (consome `0 créditos` de geração usando `BELUGA` + `veo_3_1_i2v_lite_low_priority`).**
- Deu resultado? **Mais de 280 vídeos completos gerados e entregues no mesmo dia em 1 única conta sem bloqueio.**
- Como você sabe hoje qual página gerou uma venda? **Fora do escopo deste pacote (este pacote entrega apenas o motor de geração/edição limpa).**

## 4. Linguagem, dependências e onde roda

- Linguagem/versão: **JavaScript (Extensão Chrome Manifest V3 `world: MAIN`) + Python 3.11+**
- Principais libs/ferramentas: **`websocket-client` (CDP), `faster-whisper` (CUDA `float16`), `FFmpeg` (`h264_nvenc`), Chrome com `--remote-debugging-port=9225`**
- Precisa de algum serviço pago para rodar? **Apenas uma conta logada no Google Labs Flow.**
- Como se instala e roda (o comando):
  ```bash
  pip install -r packages/_incoming/jeff/requirements.txt
  python packages/_incoming/jeff/benchmark_100_videos_turbo.py
  ```
- Onde roda: **Windows/Linux, máquina local com GPU NVIDIA (RTX), disparado sob demanda ou em fila contínua.**

## 5. Onde guarda os dados hoje

- Guarda os takes brutos, takes cortados e vídeos finais em disco local (`./output_turbo/takes_brutos`, `./output_turbo/takes_cortados`, `./output_turbo/prontos`).
- Não depende de banco de dados externo — o estado de geração em andamento vive em memória no dicionário `mapa_uuids` retornado pelo RPC `eb1hJf` e consultado em lote via `jwpduf`.

## 5b. No que ele está amarrado

- Multilogin: **Qualquer navegador Chromium com porta CDP aberta (Chrome puro, AdsPower, GoLogin, etc.).** Como fala com ele: **Conecta por WebSocket CDP (`Runtime.evaluate`) na aba aberta do Flow.** Se trocar o multilogin, quanto quebra? **Nada (basta apontar `FLOW_CDP_PORT` para a porta CDP do navegador).**
- O que da SUA operação está chumbado no código: **Absolutamente nada. O pacote foi 100% higienizado e desacoplado de nicho, prompts privados ou caminhos locais para que qualquer DEV do grupo possa plugar direto na própria esteira.**

## 6. O que ele NÃO faz / onde quebra

- Exige que a extensão `extensao_flow_rpc/` esteja carregada na aba do Flow e que o usuário já esteja logado em um projeto válido (`https://labs.google/fx/pt/tools/flow/project/<ID>`).
- Se disparar mais de ~21 takes no exato mesmo milissegundo sem micro-retry, o `batchexecute` retorna `PUBLIC_ERROR_USER_REQUESTS_THROTTLED` para o excedente — por isso o `motor_turbo_cdp.py` usa 4 workers JS com micro-retry de `2.4s`, que absorve o throttle e preenche **27 a 28 takes simultâneos** na GPU do Google.
- **Zero contas derrubadas**: como tanto o `reCAPTCHA Enterprise` quanto o `batchexecute` rodam dentro da própria aba real do Chrome (`world: MAIN`), o TLS fingerprint, cookies e sessão são 100% nativos.

## 7. Gotchas que você descobriu na marra (O Segredo dos 28 Takes Simultâneos)

1. **Por que todo mundo travava em ~12 takes com `PUBLIC_ERROR_USER_REQUESTS_THROTTLED`?**
   - Quando você chama o RPC `eb1hJf` (`GenerateVideo`), o Google devolve **2 UUIDs** no array da resposta: o `mediaId` (ID real do vídeo) e o `workflowId` (ID do job).
   - O método `checkStatus` antigo chamava `jwpduf` (`ListProjectMedia`, que só retorna `mediaId`s) e, para todos os `workflowId`s que não apareciam na lista ou takes ainda gerando, disparava **dezenas de chamadas XHR individuais para o RPC `as29s` (`GetMedia`) a cada ciclo de polling** (+600 RPCs/minuto).
   - Esse flood de `as29s` estourava o rate-limit do endpoint `batchexecute` e bloqueava novos disparos de vídeo!
   - **A Correção Cirúrgica (`extensao_flow_rpc/flow-core.js`)**: Removemos completamente as chamadas `as29s` durante o polling de takes em andamento (`generationCode` em `[1, 2, 6]`) e para `workflowId`s. Agora o polling faz **1 única chamada RPC `jwpduf` a cada 4s** para ler o projeto inteiro. Isso reduziu o tráfego de RPC em **96%** e liberou **27 a 28 takes `veo_3_1_i2v_lite_low_priority` com `startFrame` rodando ao mesmo tempo na mesma aba**!
2. **Assinatura Nativa do `reCAPTCHA Enterprise`**:
   - O Flow exige o header `x-browser-validation` com token recém-emitido da sitekey `6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV` e action `FLOW_GENERATION`. Rodando no `world: "MAIN"` da aba, basta chamar `await grecaptcha.enterprise.execute('6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV', {action: 'FLOW_GENERATION'})`.
3. **Lock Global no Faster-Whisper matava o paralelismo local**:
   - Configurar `WhisperModel("small", device="cuda", compute_type="float16", num_workers=4)` com `beam_size=1` sem lock global permite cortar múltiplos takes simultaneamente em `~0.15s` por take.

## 8. O que você jogaria fora se fosse refazer

- **Jogaria fora**: Qualquer automação baseada em clique de DOM/Playwright nos botões da UI do React do Flow (lenta, quebra quando o layout muda e trava quando a lista de vídeos cresce) e qualquer polling individual com `as29s`.
- **Manteria a qualquer custo**: O disparo direto via `window.__FLOW` (`batchexecute` RPC `F611Jc` + `eb1hJf`) com polling cirúrgico de 1 único RPC (`jwpduf`) + corte fonético em GPU (`Faster-Whisper` + `h264_nvenc -preset p1`).

## 9. Arquivos pesados (se tiver)

- Nenhum arquivo pesado incluído no Git. Todos os `.mp4` e `.jpg` são gerados localmente em tempo de execução.

---

## 10. Guia Técnico Rápido para os DEVs Implementarem

### Mapa dos 5 RPC IDs do `batchexecute` (`https://labs.google/fx/_/LabsTailwindUi/data/batchexecute`)

| RPC ID | Operação Interna | Função em `window.__FLOW` | Descrição |
| :--- | :--- | :--- | :--- |
| **`F611Jc`** | `GenerateImage` | `window.__FLOW.generateImage(prompt, count, model, ratio, refs)` | Gera imagens `BELUGA` (`0 créditos`) em `9:16` (código `2`) e retorna o `mediaId` para usar como `startFrame`. |
| **`Zzl0ze`** | `UploadImage` | `window.__FLOW.uploadImage(base64DataUrl)` | Faz upload de frame/avatar externo e retorna o `mediaId` registrado no projeto. |
| **`eb1hJf`** | `GenerateVideo` | `window.__FLOW.generateVideo(prompt, mediaId, ratio, model, endMediaId)` | Dispara geração de vídeo no Veo 3.1 (`veo_3_1_i2v_lite_low_priority`) ancorado no `startFrame` (`mediaId`). |
| **`jwpduf`** | `ListProjectMedia` | `window.__FLOW.checkStatus(uuidArray)` | Lista em **1 única chamada RPC** o status (`generationCode`) e a URL `.mp4` de **todos os takes do projeto**. |
| **`as29s`** | `GetMedia` | Uso interno sob demanda | Busca metadados individuais de um `mediaId` específico. |

### Exemplo de Uso Direto no JS (Console / Puppeteer / Playwright / CDP)

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
