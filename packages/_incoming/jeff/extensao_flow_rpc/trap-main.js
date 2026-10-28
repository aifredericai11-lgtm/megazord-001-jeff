// Candidate MAIN/document_start trap. State is private to this extension's namespace.
// grecaptcha itself belongs to Google and is necessarily shared: preserve existing
// accessors, including those installed later by Zerum2 (see NAMESPACES.md).
(() => {
  const protocol = 'zerum-candidate-trap-v1';
  if (window.__zerumCandidateTrapV1) {
    if (window.__zerumCandidateTrapV1.protocol !== protocol) throw new Error('TRAP_CANDIDATA_INCOMPATIVEL');
    return;
  }
  const define = Object.defineProperty;
  const rc = { protocol, installed: true, exec: null, wrapped: false, reassigned: 0, error: '' };
  define(window, '__zerumCandidateTrapV1', { value: rc, configurable: true, enumerable: false });
  const watched = new WeakMap();
  const firsts = new WeakMap();
  let activeEnterprise;
  const HIJACK = 'extension_hijack_detected';
  const notify = (observe, value) => { try { observe(value); } catch { rc.error = 'RECAPTCHA_OBSERVACAO_FALHOU'; } };
  function compose(target, key, descriptor, observe) {
    // Never make Google's or the other extension's property less configurable,
    // bypass its setter, or manufacture a setter for a read-only property.
    if (!descriptor.configurable) {
      rc.error = 'RECAPTCHA_ACESSOR_NAO_CONFIGURAVEL';
      return define(target, key, descriptor);
    }
    let value = descriptor.value;
    const accessor = 'get' in descriptor || 'set' in descriptor;
    const read = accessor ? function () { return descriptor.get?.call(this); } : function () { return value; };
    const write = accessor ? descriptor.set : descriptor.writable ? function (v) { value = v; } : undefined;
    const result = define(target, key, {
      configurable: descriptor.configurable, enumerable: descriptor.enumerable,
      get: read,
      ...(write ? { set(v) { write.call(this, v); notify(observe, read.call(this)); } } : {}),
    });
    notify(observe, read.call(target));
    return result;
  }
  function watch(target, key, observe) {
    let keys = watched.get(target);
    if (!keys) { keys = new Map(); watched.set(target, keys); }
    if (keys.has(key)) { notify(observe, target[key]); return; }
    keys.set(key, observe);
    const descriptor = Object.getOwnPropertyDescriptor(target, key) || { value: target[key], configurable: true, enumerable: true, writable: true };
    compose(target, key, descriptor, observe);
  }
  // Zerum2 replaces these descriptors instead of chaining them. Intercept ONLY
  // the three watched slots; every other Object.defineProperty call goes through
  // unchanged. This also preserves Zerum2 when its trap runs after ours.
  define(Object, 'defineProperty', { value: function defineProperty(target, key, descriptor) {
    const observe = watched.get(target)?.get(key);
    return observe ? compose(target, key, descriptor, observe) : define(target, key, descriptor);
  } });
  function trapExec(ent) {
    activeEnterprise = ent;
    rc.exec = null;
    if (!ent || typeof ent !== 'object') return;
    watch(ent, 'execute', value => {
      if (typeof value !== 'function') return;
      let first = firsts.get(ent);
      if (!first) {
        // A late install must not adopt the known wrapper or steal a legacy trap.
        if (Function.prototype.toString.call(value).includes(HIJACK)) { rc.error = 'RECAPTCHA_CAPTURA_TARDIA'; return; }
        first = value; firsts.set(ent, first);
      } else if (value !== first) {
        rc.reassigned++;
        if (Function.prototype.toString.call(value).includes(HIJACK)) rc.wrapped = true;
      }
      if (ent === activeEnterprise) rc.exec = first.bind(ent);
    });
  }
  function trapG(g) {
    if (!g || typeof g !== 'object') { activeEnterprise = null; rc.exec = null; return; }
    watch(g, 'enterprise', trapExec);
  }
  watch(window, 'grecaptcha', trapG);
})();
