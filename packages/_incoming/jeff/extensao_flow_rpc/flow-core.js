// flow-core.js — MAIN world da aba comum do Flow. Fala com o Flow pelo protocolo dele (batchexecute),
// com token reCAPTCHA cunhado pelo execute ORIGINAL (guardado pela armadilha trap-main.js).
// Candidate-only core. Never reuse Zerum2's __zr2 or its token traps.
(function () {
  const protocol = 'zerum-candidate-core-v1';
  if (window.__zerumCandidateCoreV1) {
    if (window.__zerumCandidateCoreV1.protocol !== protocol) throw new Error('CORE_CANDIDATA_INCOMPATIVEL');
    return;
  }
  const U = () => crypto.randomUUID().toUpperCase();
  const SEED = () => Math.floor(Math.random() * 2147483647);
  const RID = () => Math.floor(1000000 + Math.random() * 8000000);
  const W = () => window.WIZ_global_data || {};
  const CONTA = () => (location.pathname.match(/^\/u\/\d+/) || [''])[0];
  const PROJ_URL = () => (location.href.match(/project\/([0-9a-fA-F\-]{36})/) || [])[1] || '';
  const clean = (t) => (t || '').replace(/\\+u([0-9a-fA-F]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16))).replace(/\\+\//g, '/');
  const uuids = (t) => Array.from(new Set(clean(t).match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g) || []));
  const erro = (t) => {
    if (t.indexOf('UNUSUAL_ACTIVITY') !== -1 || /recaptcha evaluation failed/i.test(t)) return 'INCOMUM';
    const m = t.match(/PUBLIC_ERROR_[A-Z_]+/); if (m) return m[0];
    if (/PER_MODEL_DAILY_QUOTA|QUOTA/i.test(t)) return 'COTA';
    if (/TOO_MUCH_TRAFFIC|RESOURCE_EXHAUSTED/.test(t)) return 'TRAFEGO';
    return '';
  };
  function uploadId(t) { try { const line = t.split('\n').find(x => x.startsWith('[[\"wrb.fr\"')); const rows = JSON.parse(line); const row = rows.find(x => x[1] === 'maseQ'); const payload = JSON.parse(row[2]); const id = payload[0]?.[0]; return /^[0-9a-f-]{36}$/i.test(id) ? id : ''; } catch { return ''; } }
  // Same batchexecute envelope parser as Hercules account-pool.payloadDoBatchexecute.
  function rpcPayload(text, rpc) {
    for (const line of text.split('\n')) {
      if (!line.trim().startsWith('[')) continue;
      try { for (const row of JSON.parse(line)) if (row[0] === 'wrb.fr' && row[1] === rpc && typeof row[2] === 'string') return JSON.parse(row[2]); } catch {}
    }
    return null;
  }
  function siteKey() {
    for (const s of document.querySelectorAll('script[src*="recaptcha"]')) { const m = s.src.match(/[?&]render=([^&]+)/); if (m && m[1] !== 'explicit') return m[1]; }
    try { const c = window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients; for (const k in c) { const st = JSON.stringify(c[k], (kk, v) => (typeof v === 'object' && v && v.window ? undefined : v)); const m = st && st.match(/"sitekey":"([^"]+)"/); if (m) return m[1]; } } catch (e) {}
    return '';
  }
  // 0.4.17 (16/10 FRENTE 1H): desde ~19h o Google CONGELA window.grecaptcha / enterprise / execute (configurable:false,
  // writable:false) e troca o execute pelo embrulho "extension_hijack_detected". A armadilha registra
  // RECAPTCHA_ACESSOR_NAO_CONFIGURAVEL nesse caminho e NUNCA observa o embrulho (compose não notifica quando não é
  // configurável), logo trap.exec continua sendo o execute ORIGINAL capturado antes do congelamento. Esse erro,
  // sozinho, não invalida o exec: aceitar. Qualquer outro erro (captura tardia, observação falhou) segue recusado.
  const ERRO_TOLERADO = 'RECAPTCHA_ACESSOR_NAO_CONFIGURAVEL';
  function execOriginal() {
    const trap = window.__zerumCandidateTrapV1;
    if (trap?.protocol === 'zerum-candidate-trap-v1' && (!trap.error || trap.error === ERRO_TOLERADO) && typeof trap.exec === 'function') return trap.exec;
    return null;
  }
  async function token(action) {
    const ex = execOriginal(); if (!ex) throw new Error('SEM_ARMADILHA');
    const g = window.grecaptcha && window.grecaptcha.enterprise; if (!g) throw new Error('SEM_RECAPTCHA');
    await Promise.race([new Promise((r) => g.ready(r)), new Promise((_, j) => setTimeout(() => j(new Error('RECAPTCHA_TIMEOUT')), 12000))]);
    const t = await Promise.race([ex(siteKey(), { action }), new Promise((_, reject) => setTimeout(() => reject(new Error('RECAPTCHA_EXEC_TIMEOUT')), 12000))]);
    if (!t || t.length < 100) throw new Error('TOKEN_VAZIO');
    return t;
  }
  let bound = null;
  function bind(c) { bound = c; }
  async function batch(rpc, inner, proj) {
    if (bound) { const i = info(); if (i.email.toLowerCase() !== bound.accountId.toLowerCase() || i.projeto !== bound.projectId || i.conta !== bound.accountPath || (proj && proj !== bound.projectId)) throw new Error('CONTA_OU_PROJETO_MUDOU'); }
    const w = W(); const P = proj; if (!P || P !== PROJ_URL()) throw new Error('PROJETO_DIVERGENTE'); const C = CONTA();
    const url = C + '/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=' + rpc + '&source-path=' + encodeURIComponent(C + (P ? '/project/' + P : '/'))
      + '&bl=' + encodeURIComponent(w.cfb2h) + '&f.sid=' + encodeURIComponent(w.FdrFJe) + '&hl=en&_reqid=' + RID() + '&rt=c';
    const body = 'f.req=' + encodeURIComponent(JSON.stringify([[[rpc, JSON.stringify(inner), null, 'generic']]])) + '&at=' + encodeURIComponent(w.SNlM0e) + '&';
    return await new Promise((res) => {
      const x = new XMLHttpRequest(); x.open('POST', url, true);
      x.setRequestHeader('X-Same-Domain', '1'); x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded;charset=utf-8');
      x.timeout = rpc === 'agJzFb' ? 120000 : rpc === 'as29s' ? 20000 : rpc === 'ogiZ0b' ? 120000 : 25000; x.ontimeout = () => res({ s: 0, t: 'TIMEOUT_AMBIGUO' }); x.onabort = () => res({ s: 0, t: 'ABORT_AMBIGUO' }); x.withCredentials = true; x.onload = () => res({ s: x.status, t: x.responseText || '' }); x.onerror = () => res({ s: 0, t: 'onerror' }); x.send(body);
    });
  }
  const CTX = (proj, tk) => [null, 22, null, null, null, proj, null, null, null, null, [tk, 1]];
  function info() {
    const el = [...document.querySelectorAll('[aria-label]')].find((x) => /@/.test(x.getAttribute('aria-label') || '') && /Google/.test(x.getAttribute('aria-label') || ''));
    const email = el ? ((el.getAttribute('aria-label').match(/[\w.+-]+@[\w.-]+/) || [])[0] || '') : '';
    const projects = [...document.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>{try{const u=new URL(h);return u.origin===location.origin && /^\/(?:u\/\d+\/)?project\/[a-f0-9-]{36}\/?$/i.test(u.pathname);}catch{return false;}});
    return { email, projects:[...new Set(projects)], projeto: PROJ_URL(), conta: CONTA(), armadilha: !!execOriginal(), armadilhaErro: window.__zerumCandidateTrapV1?.error || '', recaptcha: !!(window.grecaptcha && window.grecaptcha.enterprise), wiz: !!W().SNlM0e };
  }
  async function credito(proj) {
    const r = await batch('nzlxg', [], proj); const m = r.t.match(/"nzlxg","\[(\d+)/);
    return { s: r.s, creditos: m ? parseInt(m[1]) : null };
  }
  // Read-only HTrJv. It describes tier costs, NOT the logged-in account's tier.
  // Preserve unknown requirement enums and unavailable/malformed costs; never assume zero.
  async function catalogo(proj) {
    const r = await batch('HTrJv', [], proj), payload = rpcPayload(r.t, 'HTrJv');
    const root = Array.isArray(payload?.[0]) ? payload[0] : payload;
    const families = Array.isArray(root?.[4]) ? root[4] : null;
    if (r.s !== 200 || erro(r.t) || !families) return { ok: false, s: r.s, erro: erro(r.t) || 'CATALOGO_ATUAL_ILEGIVEL' };
    const models = [];
    for (const family of families) for (const u of Array.isArray(family?.[1]) ? family[1] : []) {
      if (!Array.isArray(u) || typeof u[0] !== 'string') continue;
      const costs = {};
      for (const pair of Array.isArray(u[4]) ? u[4] : []) {
        const cost = pair?.[1]?.[0]?.[1];
        if ([1, 2, 3].includes(pair?.[0])) costs[pair[0]] = typeof cost === 'number' && Number.isFinite(cost) && cost >= 0 ? cost : null;
      }
      models.push({ key: u[0], family: family[3], displayName: family[0], costs,
        requirements: (Array.isArray(u[7]?.[0]) ? u[7][0] : []).map(g => Array.isArray(g?.[0]) ? g[0] : []),
        outputsAudio: u[10] === true, duration: u[16],
        aspects: Array.isArray(u[12]?.[0]) ? u[12][0] : [], resolutions: Array.isArray(u[23]?.[0]) ? u[23][0] : [] });
    }
    return { ok: true, s: r.s, models, accountTier: null };
  }
  // 851g (14/10): image families of the same read-only HTrJv (root[5]; video is root[4]). Read live 14/10 on Refúgio /u/0:
  // '🍌 Nano Banana Pro'→GEM_PIX_2 · '🍌 Nano Banana 2 Lite'→HARBOR_SEAL · '🍌 Nano Banana 2.1'→BELUGA (short label 'Nano Banana 2').
  async function catalogoImagem(proj) {
    const r = await batch('HTrJv', [], proj), payload = rpcPayload(r.t, 'HTrJv');
    const root = Array.isArray(payload?.[0]) ? payload[0] : payload;
    const families = Array.isArray(root?.[5]) ? root[5] : null;
    if (r.s !== 200 || erro(r.t) || !families) return { ok: false, s: r.s, erro: erro(r.t) || 'CATALOGO_IMAGEM_ILEGIVEL' };
    const models = [];
    for (const f of families) {
      if (!Array.isArray(f) || typeof f[0] !== 'string') continue;
      const aliases = (Array.isArray(f[4]) ? f[4] : []).map(a => Array.isArray(a) ? a[0] : a).filter(a => typeof a === 'string');
      for (const u of Array.isArray(f[1]) ? f[1] : []) if (Array.isArray(u) && typeof u[0] === 'string') models.push({ key: u[0], displayName: f[0], aliases, slug: typeof f[3] === 'string' ? f[3] : '' });
    }
    return { ok: true, s: r.s, models };
  }
  function contextoUpload(proj) {
    const i = info();
    if (!proj || proj !== i.projeto) throw new Error('PROJETO_DIVERGENTE');
    if (bound && (i.email.toLowerCase() !== bound.accountId.toLowerCase() || i.projeto !== bound.projectId || i.conta !== bound.accountPath)) throw new Error('CONTA_OU_PROJETO_MUDOU');
  }
  // Host wO1vlb (09/10): i9b -> t5a -> n5a/VR/NR, NOT maseQ/UploadImage.
  // Source/field evidence and the required real test are documented in save-video-end-frame.test.mjs.
  // No retry: loss of a start/finalize response leaves the existing operation uncertain.
  async function subirVideo(b64, mime, nome, proj) {
    contextoUpload(proj);
    if (mime !== 'video/mp4') throw new Error('UPLOAD_MIME_NAO_SUPORTADO');
    if (typeof b64 !== 'string' || !b64.length || b64.length % 4 || !/^[A-Za-z0-9+/]+={0,2}$/.test(b64)) throw new Error('UPLOAD_BASE64_INVALIDO');
    const chunks = [];
    for (let offset = 0; offset < b64.length; offset += 4 * 16384) {
      const text = atob(b64.slice(offset, offset + 4 * 16384));
      const bytes = new Uint8Array(text.length);
      for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
      chunks.push(bytes);
    }
    const blob = new Blob(chunks, { type: mime });
    const xsrf = W().SNlM0e;
    if (!xsrf) throw new Error('UPLOAD_SEM_XSRF');
    const headers = { 'X-Framework-Xsrf-Token': xsrf, Slug: encodeURIComponent(nome || 'video.mp4') };
    // 786 12/10: the root-relative Scotty endpoint carries no /u/N, so on a /u/N (N>0) tab the cookie jar
    // defaults to session 0 and the start fails fast (journal: Liberty /u/1 save = failed in 5 s, Refúgio /u/0 = ok).
    // Select the tab's own session explicitly (query + header, like the host); /u/0 and root tabs send exactly what they sent before.
    const authUser = (CONTA().match(/^\/u\/(\d+)$/) || [])[1];
    if (authUser && authUser !== '0') headers['X-Goog-AuthUser'] = authUser;
    const send = (url, body, extra) => {
      contextoUpload(proj);
      return new Promise(resolve => {
        const x = new XMLHttpRequest(); x.open('POST', url, true); x.withCredentials = true; x.timeout = 20000;
        for (const [k, v] of Object.entries({ ...headers, ...extra })) x.setRequestHeader(k, v);
        const uncertain = () => resolve({ s: 0, t: '', status: '', url: '' });
        x.onerror = uncertain; x.ontimeout = uncertain; x.onabort = uncertain;
        x.onload = () => resolve({ s: x.status, t: x.responseText || '', status: x.getResponseHeader('X-Goog-Upload-Status') || '', url: x.getResponseHeader('X-Goog-Upload-URL') || '' });
        try { x.send(body); } catch { uncertain(); }
      });
    };
    const fail = (r, fallback) => ({ ok: false, s: r.s, erro: erro(r.t) || (r.s === 429 ? 'COTA_HTTP_429' : fallback), state: r.s === 0 || r.s === 408 || r.s >= 500 || (r.s >= 200 && r.s < 300) ? 'unknown' : 'failed' });
    // n5a uses this root-relative endpoint (no /u/N prefix); XSRF + project bind the request.
    // 786 v2 (medido na aba /u/1, 12/10 11:12): sem nada = 403 'User does not have access to project'; só X-Goog-AuthUser = 403;
    // ?authuser=1 = 200 active (a URL de sessão devolvida já traz authuser). É o que a camada de upload do host faz.
    const start = await send('/upload/v1/flow/upload/video/' + proj + (authUser && authUser !== '0' ? '?authuser=' + authUser : ''), '', {
      'X-Goog-Upload-Protocol': 'resumable', 'X-Goog-Upload-Command': 'start',
      'X-Goog-Upload-Header-Content-Length': String(blob.size),
    });
    if (start.s !== 200 || start.status !== 'active' || !start.url) return fail(start, 'UPLOAD_INICIO_INCERTO');
    let url;
    try { url = new URL(start.url, location.href); } catch { return fail(start, 'UPLOAD_URL_INVALIDA'); }
    // The captured host gives no evidence for forwarding session headers to another origin.
    if (url.protocol !== 'https:' || url.origin !== new URL(location.href).origin) return fail(start, 'UPLOAD_ORIGEM_NAO_VALIDADA');
    let result;
    try { result = await send(url.href, blob, { 'Content-Type': mime, 'X-Goog-Upload-Command': 'upload, finalize', 'X-Goog-Upload-Offset': '0' }); }
    catch { return fail({ s: 0, t: '' }, 'UPLOAD_CONTEXTO_MUDOU_APOS_INICIO'); }
    if (result.s < 200 || result.s >= 300 || result.status !== 'final') return fail(result, 'UPLOAD_FINAL_INCERTO');
    // t5a reads mediaId or media.name; workflow identifiers are NEVER media identifiers.
    let data; try { data = JSON.parse(result.t); } catch { return fail(result, 'UPLOAD_RESPOSTA_INVALIDA'); }
    const basename = v => typeof v === 'string' ? v.split('/').pop() : '';
    const media = basename(data?.media?.name);
    const id = data?.mediaId != null ? basename(data.mediaId) : media;
    if (typeof id !== 'string' || !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id) || (media && media.toLowerCase() !== id.toLowerCase())) return fail(result, 'UPLOAD_SEM_ID_EXATO');
    if (erro(result.t)) return fail(result, 'UPLOAD_RECUSADO');
    return { ok: true, mediaId: id, s: result.s };
  }
  async function subir(b64, mime, nome, proj) {
    if (mime === 'video/mp4') return subirVideo(b64, mime, nome, proj);
    const P = proj; if (!P || P !== PROJ_URL()) throw new Error('PROJETO_DIVERGENTE'); const tk = await token('UPLOAD_IMAGE');
    const r = await batch('maseQ', [CTX(P, tk), b64, mime || 'image/jpeg', 1, null, null, null, null, nome || 'foto.jpg', null, U(), U()], P);
    const e = erro(r.t); const ids = uuids(r.t);
    return { ok: r.s === 200 && !e && !!uploadId(r.t), mediaId: uploadId(r.t), erro: e, s: r.s, raw: r.t.slice(0, 300) };
  }
  // imagem: refs = [mediaId,...] (i2i) ou []; aspecto 2=9:16 3=16:9
  async function imagem({ prompt, refs, aspecto, modelo, proj }) {
    const P = proj; if (!P || P !== PROJ_URL()) throw new Error('PROJETO_DIVERGENTE'); const tk = await token('IMAGE_GENERATION');
    const rs = refs && refs.length ? refs.map((x) => [x, null, null, null, 1]) : null;
    const F = [null, null, rs, SEED(), aspecto || 2, modelo || 'GEM_PIX_2', null, CTX(P, tk), [[[prompt]]], null, null, null, U(), U()];
    const r = await batch('ogiZ0b', [null, [F], 1, CTX(P, tk), [U()]], P);
    const e = erro(r.t); const c = clean(r.t);
    const url = (c.match(/https?:\/\/flow-content\.google\/image\/[^"\s\\]+/) || [])[0] || '';
    const ids = uuids(r.t); const mid = (url.match(/image\/([0-9a-f-]{36})/) || [])[1] || ids[0] || '';
    return { ok: r.s === 200 && !e && !!mid, cands: ids.filter(x => ![P, ...(refs || [])].map(x => String(x).toLowerCase()).includes(x)), mediaId: url ? mid : '', url, erro: e, s: r.s, raw: e ? r.t.slice(0, 400) : '' };
  }
  // vídeo: r2v (refs), i2v (img), interpolation (img + imgFim), t2v; aspecto 1=9:16 2=16:9
  async function video({ tipo, prompt, refs, img, imgFim, modelo, aspecto, proj, liteAutorizado }) {
    const P = proj; if (!P || P !== PROJ_URL()) throw new Error('PROJETO_DIVERGENTE'); if (!['r2v', 'i2v', 't2v', 'interpolation'].includes(tipo)) throw new Error('TIPO_VIDEO_INVALIDO');
    // 0.4.10: o core continua bloqueando modelo pago SOZINHO; a única exceção é o Lite da mesma família com autorização explícita do executor
    // (escolherModeloVideo → liteAutorizado:{teto≤5, custo≤teto}). Qualquer outra chave, ou Lite sem autorização, cai no mesmo erro de sempre.
    // 863 (15/10, Ramsés): sem trava de Lower Priority — o executor já resolveu o modelo pedido contra o catálogo DESTA conta
    // (escolherModeloLivre). Aqui só confere que veio uma chave de modelo de verdade.
    if (typeof modelo !== 'string' || !/^[a-z0-9_]{3,80}$/.test(modelo)) throw new Error('MODELO_VIDEO_INVALIDO');
    const validId = x => typeof x === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(x);
    if (tipo === 'interpolation' ? (!validId(img) || !validId(imgFim) || refs?.length) : imgFim != null) throw new Error('QUADRO_FINAL_REQUER_INTERPOLATION');
    const tk = await token('VIDEO_GENERATION'); const A = aspecto || 1; let rpc, inner;
    if (tipo === 'r2v') {
      rpc = 'MZZa6b'; const M = modelo;
      inner = [[[[null, null, [[[prompt]]]], (refs || []).map((x) => [null, x]), M, A, null, [null, null, null, null, U(), U()]]], CTX(P, tk), [U(), 1]];
    } else if (tipo === 'interpolation') {
      // Host o5a START_END_FRAMES -> nprQif/T2a: P2a fields 5=start, 6=end, 7=metadata.
      // mP field 2=mediaId; absent crop means the WHOLE original image (LM(undefined)).
      rpc = 'nprQif';
      inner = [[[[null, null, [[[prompt]]]], modelo, A, null, [null, img], [null, imgFim], [null, null, null, null, U(), U()]]], CTX(P, tk), [U(), 2]];
    } else if (tipo === 'i2v') {
      rpc = 'eb1hJf'; const M = modelo;
      inner = [[[[null, null, [[[prompt]]]], M, A, null, [null, img, null, null, null, [0, null, 1, 1]], [null, null, null, null, U(), U()]]], CTX(P, tk), [U(), 2]];
    } else {
      rpc = 'YhhmEf'; const M = modelo;
      inner = [[[[null, null, [[[prompt]]]], M, A, null, [null, null, null, null, U(), U()]]], CTX(P, tk), [U(), 2]];
    }
    const r = await batch(rpc, inner, P); const e = erro(r.t); const ids = uuids(r.t);
    // a resposta traz vários UUIDs (fluxo, mídia, projeto, refs) e a ordem varia: devolve todos os candidatos e o status acha o que vira /video/<id>
    const fora = new Set([P, img, imgFim, ...(refs || [])].filter(Boolean).map((x) => String(x).toLowerCase()));
    const cands = ids.filter((x) => !fora.has(x));
    return { ok: r.s === 200 && !e && cands.length >= 1, videoId: '', cands, fluxoId: ids[0] || '', erro: e, s: r.s, rpc, raw: e ? r.t.slice(0, 400) : '' };
  }
  // texto (Gemini do Flow, o mesmo do kit da ferramenta): RPC agJzFb, token TEXT_GENERATION. partes = [{mime, b64}] (imagem/vídeo pequeno)
  async function texto({ prompt, sistema, partes, modelo, proj }) {
    const tk = await token('TEXT_GENERATION');
    const conteudo = [[String(prompt || '')]].concat((partes || []).map((x) => [null, [x.mime, x.b64]]));
    const req = [modelo || 'gemini-3-flash-preview', null, null, null, null, null, null, null, null, [[conteudo, 'user']], null, sistema ? [[[String(sistema)]]] : null, null, null, null, [tk, 1]];
    const r = await batch('agJzFb', req, proj); let e = erro(r.t);
    let txt = '';
    try { const l = r.t.split('\n').find((x) => x.startsWith('[["wrb.fr"')); const inn = JSON.parse(JSON.parse(l)[0][2]); for (const p of inn[3][0][1][0]) if (p && typeof p[0] === 'string' && !p[4]) txt += p[0]; } catch (er) {}
    // Preserve the explicit RPC rejection separately from empty or malformed responses.
    if (!txt && !e && r.s === 200) {
      for (const line of r.t.split('\n')) {
        try { for (const row of JSON.parse(line)) {
          if (row?.[0] !== 'wrb.fr' || row?.[1] !== 'agJzFb') continue;
          const payload = typeof row[2] === 'string' ? JSON.parse(row[2]) : null;
          if (Array.isArray(row[5]) && row[5].length === 1 && row[5][0] === 3 || Array.isArray(payload) && payload.length === 1 && payload[0] === 3) e = 'FLOW_TEXT_CODE_3';
        } } catch {}
      }
    }
    return { ok: r.s === 200 && !e && !!txt, texto: txt, erro: e || (txt ? '' : 'SEM_TEXTO'), s: r.s, raw: txt ? '' : r.t.slice(0, 300) };
  }
  // status de vários de uma vez: [{id, tipo:'video'|'image'}] → {id: {pronto, url, falhou}}
  async function status(itens, proj) {
    const out = {};
    // STATUS_GERACAO_878V: GetMedia omits failed asynchronous generations. The Flow
    // host polls BatchCheckAsyncVideoGenerationStatus (jwpduf), response field3.
    // Proven 15/10 on Refugio: GetMedia=[5], generation=4/UNSAFE, same media+project.
    // No generation, retry or new quality gate here; only read the existing job.
    const videos = itens.filter(it => it.tipo === 'video');
    const videosProntosSemUrl = new Set();
    let jwpdufOk = false;
    if (videos.length) {
      try {
        const r = await batch('jwpduf', [null, null, videos.map(it => [it.id])], proj);
        const rows = rpcPayload(r.t, 'jwpduf')?.[2];
        if (r.s === 200 && Array.isArray(rows)) {
          jwpdufOk = true;
          for (const media of rows) {
            const it = videos.find(it => media?.[0] === it.id);
            if (!it || media?.[1] !== proj) continue;
            const generation = media?.[5]?.[8], generationCode = generation?.[0];
            const encoded = clean(JSON.stringify(media));
            const urls = encoded.match(/https?:[^"\s]+/g) || [];
            const url = urls.find(value => { try { const u = new URL(value); return u.protocol === 'https:' && u.hostname === 'flow-content.google' && u.pathname === '/video/' + it.id; } catch { return false; } }) || '';
            const falhou = [4, 5, 7].includes(generationCode);
            // Completed generation status has no signed CDN URL: GetMedia (as29s) supplies it ONLY for this confirmed mediaId!
            if (!falhou && !url && ![1, 2, 6].includes(generationCode)) {
              videosProntosSemUrl.add(it.id);
              continue;
            }
            const codigo = String(generationCode ?? '');
            const erro = falhou ? (String(generation?.[1]?.[1] || '').match(/PUBLIC_ERROR_[A-Z_]+/) || [])[0] || (generationCode === 5 ? 'MEDIA_GENERATION_CANCELED' : 'MEDIA_GENERATION_STATUS_FAILED') : '';
            const estado = falhou ? 'falhou' : url ? 'pronto' : generationCode === 6 ? 'fila_google' : 'gerando';
            out[it.id] = { verified: true, pronto: !!url && !falhou, url: falhou ? '' : url, mediaType: 'video', falhou, sumiu: false, estado, codigo, erro, s: r.s, fonte: 'generation-status' };
          }
          // Mark non-matching video candidate UUIDs (workflowIds/sceneIds) so we NEVER spam as29s on them!
          for (const vIt of videos) {
            if (!out[vIt.id] && !videosProntosSemUrl.has(vIt.id)) {
              out[vIt.id] = { verified: false, pronto: false, url: '', mediaType: 'video', falhou: false, sumiu: true, estado: 'workflow_id_ignorado', codigo: '5', erro: '', s: 200 };
            }
          }
        }
      } catch { /* Older host / temporary read failure: keep the established read. */ }
    }
    await Promise.all(itens.filter(it => !out[it.id] && (it.tipo !== 'video' || !jwpdufOk || videosProntosSemUrl.has(it.id))).map(async (it) => {
      const r = await batch('as29s', [it.id], proj); const c = clean(r.t);
      const media = rpcPayload(r.t, 'as29s');
      // Observed 09/10 on the same account: as29s root field7=image, field8=video.
      // Shared field6 includes the JPEG thumbnail for BOTH. Its URL is not a type.
      const exact = media?.[0] === it.id && media?.[1] === proj;
      const isImage = exact && Array.isArray(media[6]), isVideo = exact && Array.isArray(media[7]);
      const mediaType = isImage !== isVideo ? (isVideo ? 'video' : 'image') : '';
      const url = (c.match(new RegExp('https?://flow-content\\.google/' + (it.tipo || 'video') + '/' + it.id + '[^"\\s\\\\]*')) || [])[0] || '';
      // 10/10 (MIDIA_FALHOU precoce): "não encontrado" NÃO é veredito. Logo após o envio o as29s responde
      // [5]/"Media not found" tanto pro sceneId (nunca vira mídia) quanto pro mediaId ainda não indexado;
      // o Flow só DECLARA falha com MEDIA_GENERATION_STATUS_FAILED / PUBLIC_ERROR_*. O resto é pendente.
      const codigo = (c.match(/"as29s",null,null,null,\[(\d+)\]/) || [])[1] || '';
      const naoEncontrado = (codigo === '5' || /Media not found/.test(c)) && !url;
      const falhou = /MEDIA_GENERATION_STATUS_FAILED|PUBLIC_ERROR/.test(c) && !url;
      const estado = url ? 'pronto' : falhou ? 'falhou' : naoEncontrado ? 'nao_encontrado' : exact ? 'gerando' : 'desconhecido';
      const raw = c.replace(/^\)\]\}'[\s\S]*?\n(?=\[)/, '').replace(/\s+/g, ' ').slice(0, 200);
      out[it.id] = { verified: exact, pronto: !!url, url, mediaType, falhou, sumiu: naoEncontrado, estado, codigo, raw, erro: falhou ? ((c.match(/PUBLIC_ERROR_[A-Z_]+/) || [''])[0] || 'MEDIA_GENERATION_STATUS_FAILED') : '', s: r.s };
    }));
    return out;
  }
  window.__zerumCandidateCoreV1 = { protocol, v: '0.4', bind, info, credito, catalogo, catalogoImagem, token, batch, subir, imagem, video, status, texto };
})();
