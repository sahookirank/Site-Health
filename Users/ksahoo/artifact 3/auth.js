// Simple prompt-based authentication
// - Compares entered access key against EXPECTED_SECRET_HASH from auth-config.json (SHA-256)
// - Creates a short-lived session in localStorage on success and redirects to dashboard

(async () => {
  const DEFAULTS = {
    REPO_SECRET_NAME: 'USER',
    EXPECTED_SECRET_HASH: '', // If empty, any non-empty key will work (useful for local testing)
    SESSION_TIMEOUT: 24 * 60 * 60 * 1000, // 24h
    SESSION_STORAGE_KEY: 'auth_session',
    SUCCESS_REDIRECT: 'index.html'
  };

  async function sha256(message) {
    const msgUint8 = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  async function loadConfig() {
    try {
      const res = await fetch('auth-config.json', { cache: 'no-store' });
      if (!res.ok) throw new Error('Failed to load auth-config.json');
      const json = await res.json();
      return { ...DEFAULTS, ...json };
    } catch (e) {
      console.warn('auth-config.json missing or invalid, falling back to defaults:', e.message);
      return { ...DEFAULTS };
    }
  }

  function getSession(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function isSessionValid(session, timeout) {
    if (!session || !session.authenticated || !session.ts) return false;
    return (Date.now() - session.ts) < timeout;
  }

  function createSession(key) {
    const payload = { authenticated: true, ts: Date.now() };
    localStorage.setItem(key, JSON.stringify(payload));
  }

  function clearSession(key) {
    try { localStorage.removeItem(key); } catch {}
  }

  function setupInlineAuth(config) {
    const startBtn = document.getElementById('startAuth');
    if (startBtn) startBtn.style.display = 'none';

    const main = document.querySelector('main') || document.body;

    let form = document.getElementById('authForm');
    let input, msg, submit;

    if (!form) {
      const wrapper = document.createElement('div');
      wrapper.className = 'auth-pane';
      wrapper.innerHTML = `
        <form id="authForm" autocomplete="off" novalidate style="display:flex; flex-direction:column; gap:12px;">
          <label for="accessKey" style="font-weight:600;">Access key (${config.REPO_SECRET_NAME})</label>
          <input id="accessKey" type="password" placeholder="Enter access key" required style="padding:10px; border:1px solid #ddd; border-radius:8px;" />
          <button type="submit" id="submitAccess" style="appearance:none; border:none; background:#2563eb; color:#fff; padding:10px 16px; border-radius:8px; font-weight:600; cursor:pointer;">Continue</button>
          <div id="authMsg" class="msg" aria-live="polite" style="min-height:1em; font-size:13px;"></div>
        </form>
      `;
      main.appendChild(wrapper);
      form = wrapper.querySelector('#authForm');
    }

    input = form.querySelector('#accessKey') || (() => {
      const i = document.createElement('input');
      i.id = 'accessKey';
      i.type = 'password';
      i.required = true;
      form.prepend(i);
      return i;
    })();

    submit = form.querySelector('button[type="submit"]') || form.querySelector('#submitAccess');
    msg = form.querySelector('#authMsg') || (() => {
      const d = document.createElement('div');
      d.id = 'authMsg';
      form.appendChild(d);
      return d;
    })();

    return { form, input, msg, submit };
  }

  async function runInlineAuth(config) {
    const { form, input, msg, submit } = setupInlineAuth(config);

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const value = (input.value || '').trim();

      if (!value) {
        msg.textContent = 'Access key is required.';
        msg.style.color = '#b91c1c';
        input.focus();
        return;
      }

      submit.disabled = true;
      const originalText = submit.textContent;
      submit.textContent = 'Checking...';
      msg.textContent = '';

      try {
        let ok;
        if (config.EXPECTED_SECRET_HASH) {
          const hash = await sha256(value);
          ok = (hash === config.EXPECTED_SECRET_HASH);
        } else {
          ok = true; // dev mode: any non-empty works
        }

        if (ok) {
          createSession(config.SESSION_STORAGE_KEY);
          msg.textContent = 'Authenticated. Redirecting...';
          msg.style.color = '#166534';
          location.href = config.SUCCESS_REDIRECT;
        } else {
          msg.textContent = 'Invalid access key. Please try again.';
          msg.style.color = '#b91c1c';
          input.focus();
          input.select?.();
        }
      } catch (err) {
        console.error('Auth error:', err);
        msg.textContent = 'Unexpected error. Please try again.';
        msg.style.color = '#b91c1c';
      } finally {
        submit.disabled = false;
        submit.textContent = originalText;
      }
    }, { once: true });
  }

  const config = await loadConfig();

  // Sign out flow: if URL requests signout (either ?signout=1) or dedicated page
  try {
    const url = new URL(window.location.href);
    if (url.searchParams.get('signout') === '1' || /\/signout\.html$/.test(url.pathname)) {
      clearSession(config.SESSION_STORAGE_KEY);
      window.location.replace('auth.html');
      return;
    }
  } catch {}

  const session = getSession(config.SESSION_STORAGE_KEY);

  if (isSessionValid(session, config.SESSION_TIMEOUT)) {
    if (!location.pathname.endsWith(`/${config.SUCCESS_REDIRECT}`) && !location.pathname.endsWith(config.SUCCESS_REDIRECT)) {
      location.href = config.SUCCESS_REDIRECT;
    }
    return;
  }

  await runInlineAuth(config);
})();