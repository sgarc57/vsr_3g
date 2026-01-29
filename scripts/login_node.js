const fs = require('fs');
const path = require('path');
const vm = require('vm');
const http = require('http');
const https = require('https');
const { URL } = require('url');

const ROUTER_BASE = process.env.ROUTER_BASE || 'http://192.168.7.1/';
const ROUTER_ACTUAL = process.env.ROUTER_ACTUAL || 'http://192.168.7.1/';
const USERNAME = process.env.ROUTER_USER || 'admin';
const PASSWORD = process.env.ROUTER_PASS || 'admin';

function httpRequest(method, urlStr, { headers = {}, body = null, cookieJar } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const lib = url.protocol === 'https:' ? https : http;

    const finalHeaders = { ...headers };
    if (cookieJar && cookieJar.cookieHeader()) {
      finalHeaders['Cookie'] = cookieJar.cookieHeader();
    }

    const req = lib.request(
      {
        method,
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: url.pathname + url.search,
        headers: finalHeaders,
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const buf = Buffer.concat(chunks);
          const text = buf.toString('utf8');
          const setCookie = res.headers['set-cookie'];
          if (cookieJar && setCookie) cookieJar.addSetCookie(setCookie);
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            text,
          });
        });
      }
    );
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

class CookieJar {
  constructor() {
    this.cookies = new Map();
  }

  addSetCookie(setCookieHeader) {
    const arr = Array.isArray(setCookieHeader) ? setCookieHeader : [setCookieHeader];
    for (const sc of arr) {
      const first = sc.split(';')[0];
      const idx = first.indexOf('=');
      if (idx === -1) continue;
      const name = first.slice(0, idx).trim();
      const value = first.slice(idx + 1).trim();
      // ignore "deleted" cookies (they intentionally clear)
      if (value.toLowerCase() === 'deleted') {
        this.cookies.delete(name);
        continue;
      }
      this.cookies.set(name, value);
    }
  }

  set(name, value) {
    this.cookies.set(name, value);
  }

  get(name) {
    return this.cookies.get(name);
  }

  cookieHeader() {
    if (this.cookies.size === 0) return '';
    return Array.from(this.cookies.entries())
      .map(([k, v]) => `${k}=${v}`)
      .join('; ');
  }
}

function loadFile(rel) {
  return fs.readFileSync(path.resolve(__dirname, '..', rel), 'utf8');
}

function makeSandbox() {
  // Minimal jQuery stub + globals expected by tpEncrypt.js
  const sandbox = {
    window: {},
    navigator: { userAgent: 'node' },
    document: {},
    localStorage: {
      _m: new Map(),
      setItem(k, v) { this._m.set(String(k), String(v)); },
      getItem(k) { return this._m.has(String(k)) ? this._m.get(String(k)) : null; },
      removeItem(k) { this._m.delete(String(k)); },
    },
    console,
    atob: (s) => Buffer.from(s, 'base64').toString('binary'),
    btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
  };

  // jQuery-ish object used by tpEncrypt.js/encrypt.js
  sandbox.$ = sandbox.jQuery = function () {};
  sandbox.$.extend = function (target, ...srcs) {
    target = target || {};
    for (const s of srcs) {
      if (!s) continue;
      for (const k of Object.keys(s)) target[k] = s[k];
    }
    return target;
  };
  sandbox.$.encrypt = {};

  sandbox.window = sandbox;
  return sandbox;
}

function evalInSandbox(code, sandbox, filename) {
  const script = new vm.Script(code, { filename });
  const ctx = vm.createContext(sandbox);
  script.runInContext(ctx);
  return sandbox;
}

function parseGetParm(text) {
  const nn = /var\s+nn="([0-9A-Fa-f]+)"/.exec(text)?.[1];
  const ee = /var\s+ee="([0-9A-Fa-f]+)"/.exec(text)?.[1];
  const seq = /var\s+seq="?(\d+)"?/.exec(text)?.[1];
  if (!nn || !ee || !seq) throw new Error('Failed to parse nn/ee/seq from getParm');
  return { nn, ee, seq };
}

async function main() {
  const jar = new CookieJar();
  jar.set('loginErrorShow', '1');

  const headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Origin': ROUTER_ACTUAL.replace(/\/$/, ''),
    'Referer': ROUTER_ACTUAL,
    'Connection': 'keep-alive',
  };

  // 1) Handshake
  const getParmUrl = new URL('/cgi/getParm', ROUTER_BASE).toString();
  console.log('[*] GET', getParmUrl);
  const gp = await httpRequest('GET', getParmUrl, { headers, cookieJar: jar });
  console.log('[+] getParm status:', gp.statusCode);

  const { nn, ee, seq } = parseGetParm(gp.text);
  console.log('[+] nn bits:', nn.length * 4);
  console.log('[+] seq:', seq);
  console.log('[+] cookies:', jar.cookieHeader());

  // 2) Load router JS crypto into sandbox
  const sandbox = makeSandbox();
  evalInSandbox(loadFile('cryptoJS.min.js'), sandbox, 'cryptoJS.min.js');
  evalInSandbox(loadFile('encrypt.js'), sandbox, 'encrypt.js');
  evalInSandbox(loadFile('tpEncrypt.js'), sandbox, 'tpEncrypt.js');

  // Provide rsa / encryptor manager like UI
  // tpEncrypt.js defines $.encrypt.encryptManager() and $.encrypt.encryptor()
  const rawMgr = sandbox.$?.encrypt?.encryptManager;
  if (!rawMgr) {
    throw new Error('tpEncrypt.js did not define $.encrypt.encryptManager');
  }
  // In lib.js the UI does: $.newencryptorManager=$.encrypt.encryptManager; $.Iencryptor=$.newencryptorManager.getEncryptor()
  sandbox.$.newencryptorManager = typeof rawMgr === 'function' ? rawMgr() : rawMgr;

  const mgr = sandbox.$.newencryptorManager;
  let encryptor = null;
  if (typeof mgr.getEncryptor === 'function') {
    try {
      encryptor = mgr.getEncryptor();
    } catch (e) {
      // getEncryptor() may try to restore an AES key/IV string from localStorage; in our sandbox
      // that value may be null on first run, so fall back to generating a fresh encryptor.
      if (typeof mgr.genEncryptor === 'function') {
        encryptor = mgr.genEncryptor();
      } else {
        throw e;
      }
    }
  } else if (typeof mgr.genEncryptor === 'function') {
    encryptor = mgr.genEncryptor();
  }
  if (!encryptor) {
    const mgrKeys = mgr && typeof mgr === 'object' ? Object.keys(mgr).join(',') : String(typeof mgr);
    throw new Error(`Could not obtain encryptor from encryptManager (keys: ${mgrKeys})`);
  }
  sandbox.$.Iencryptor = encryptor;
  sandbox.$.Iencryptor.setRSAKey(nn, ee);
  sandbox.$.Iencryptor.setSeq(seq);

  // INCLUDE_LOGIN_USERNAME=0 behavior: default username is admin
  const uname = USERNAME || 'admin';

  sandbox.$.Iencryptor.setHash(uname, PASSWORD);
  sandbox.$.Iencryptor.genAESKey();

  // AESEncrypt returns {data, sign}
  const encResult = sandbox.$.Iencryptor.AESEncrypt(`${uname}\n${PASSWORD}`, 1);
  const data = encResult.data;
  const sign = encResult.sign;

  console.log('[+] data:', data, 'len=', data.length);
  console.log('[+] sign:', sign, 'len=', sign.length);

  // 3) Login request (POST, query params, empty body)
  const loginUrl = new URL('/cgi/login', ROUTER_BASE);
  loginUrl.searchParams.set('data', data);
  loginUrl.searchParams.set('sign', sign);
  loginUrl.searchParams.set('Action', '1');
  loginUrl.searchParams.set('LoginStatus', '0');

  console.log('[*] POST', loginUrl.toString());
  const lr = await httpRequest('POST', loginUrl.toString(), { headers, cookieJar: jar });
  console.log('[+] login status:', lr.statusCode);
  console.log('[+] login response:', lr.text.trim());
  console.log('[+] set-cookie:', lr.headers['set-cookie']);
  console.log('[+] cookies:', jar.cookieHeader());

  // 4) Verify
  const busyUrl = new URL('/cgi/getBusy', ROUTER_BASE).toString();
  console.log('[*] GET', busyUrl);
  const br = await httpRequest('GET', busyUrl, { headers, cookieJar: jar });
  console.log('[+] getBusy:', br.text.trim());
}

main().catch((e) => {
  console.error('[!] error:', e);
  process.exitCode = 1;
});
