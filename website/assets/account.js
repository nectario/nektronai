(() => {
  const screen = document.body.dataset.accountScreen;
  if (screen && ['www.nektron.ai', 'nektron.com', 'www.nektron.com'].includes(location.hostname)) {
    location.replace('https://nektron.ai' + location.pathname + location.hash);
    return;
  }
  const stateNode = document.querySelector('[data-account-status]');
  const profile = document.querySelector('[data-account-profile]');
  const guest = document.querySelector('[data-account-guest]');
  const success = document.querySelector('[data-auth-success]');
  const forms = [...document.querySelectorAll('[data-auth-form]')];
  const rawToken = new URLSearchParams(location.hash.slice(1)).get('token') || '';
  const token = /^[A-Za-z0-9_-]{43}$/.test(rawToken) ? rawToken : '';
  if (screen && location.hash) history.replaceState(null, '', location.pathname);
  let csrf = '';
  let busy = false;

  function status(message, error = false) {
    if (!stateNode) return;
    stateNode.textContent = message;
    stateNode.toggleAttribute('data-error', error);
  }
  function showSession(data) {
    document.querySelectorAll('[data-account-login]').forEach(link => {
      link.href = data.authenticated ? 'account.html' : 'login.html';
      link.textContent = data.authenticated ? 'Account' : 'Log in';
    });
    document.querySelectorAll('[data-account-signup]').forEach(link => { link.hidden = Boolean(data.authenticated); });
    if (profile) profile.hidden = !data.authenticated;
    if (guest) guest.hidden = Boolean(data.authenticated);
    csrf = data.csrfToken || '';
    if (data.authenticated) {
      document.querySelectorAll('[data-account-email]').forEach(n => { n.textContent = data.user.email; });
      document.querySelectorAll('[data-account-name]').forEach(n => {
        n.textContent = [data.user.firstName, data.user.middleName, data.user.lastName].filter(Boolean).join(' ') || 'Nektron member';
      });
      document.querySelectorAll('[data-account-country]').forEach(n => { n.textContent = data.user.country || 'Not provided'; });
      document.querySelectorAll('[data-account-phone]').forEach(n => { n.textContent = data.user.phoneNumber || 'Not provided'; });
      if (screen === 'account') status('You are signed in.');
    } else if (screen === 'account') status('Log in to view your account.');
  }
  const messages = {
    INVALID_CREDENTIALS: 'The email or password is incorrect.',
    EMAIL_NOT_VERIFIED: 'Please verify your email before logging in. Use the verification link below if you need a new email.',
    INVALID_EMAIL: 'Enter a valid email address.',
    INVALID_PASSWORD: 'Use a password of 15 to 128 characters.',
    NAME_REQUIRED: 'Please enter your first and last name.',
    INVALID_NAME: 'Enter a valid name of no more than 100 characters.',
    INVALID_COUNTRY: 'Please select your country or region.',
    INVALID_PHONE: 'Enter a phone number using digits, spaces, +, parentheses, or hyphens (up to 30 characters).',
    INVALID_INPUT: 'Please check the form and try again.',
    INVALID_LINK: 'This link has expired or has already been used. Request a new email below.',
    INVALID_CSRF: 'Your form session expired. Please try again.',
    TRY_LATER: 'Too many attempts. Please wait before trying again.',
    ACCOUNT_UNAVAILABLE: 'Account access is temporarily unavailable. Please try again shortly.',
  };

  async function refreshCsrf() {
    const r = await fetch('/api/account/csrf', {credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
    if (!r.ok) throw new Error('ACCOUNT_UNAVAILABLE');
    csrf = (await r.json()).csrfToken;
    if (!csrf) throw new Error('ACCOUNT_UNAVAILABLE');
  }
  async function load() {
    try {
      const r = await fetch('/api/account/session', {credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
      if (!r.ok) throw new Error('ACCOUNT_UNAVAILABLE');
      const data = await r.json();
      if (typeof data.authenticated !== 'boolean') throw new Error('ACCOUNT_UNAVAILABLE');
      showSession(data);
      if (forms.length) {
        await refreshCsrf();
        forms.forEach(f => { f.querySelector('[type="submit"]').disabled = false; });
      }
    } catch {
      if (profile) profile.hidden = true;
      if (guest) guest.hidden = false;
      status('Account access is temporarily unavailable. Please reload this page to try again.', true);
    }
  }
  async function post(action, body) {
    const response = await fetch('/api/account/' + action, {
      method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
      body:JSON.stringify(body),signal:AbortSignal.timeout(20000),
    });
    const data = await response.json();
    if (!response.ok) {
      if (data.error === 'INVALID_CSRF') await refreshCsrf();
      throw new Error(data.error || 'ACCOUNT_UNAVAILABLE');
    }
    return data;
  }

  if (screen === 'verify') {
    document.querySelector('[data-verify-token]').hidden = !token;
    document.querySelector('[data-verify-request]').hidden = Boolean(token);
  }
  if (screen === 'reset' && !token) {
    forms.forEach(f => { f.hidden = true; });
    status(messages.INVALID_LINK, true);
  }
  forms.forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !csrf || !form.reportValidity()) return;
    const data = Object.fromEntries(new FormData(form));
    if (form.dataset.authForm === 'signup') {
      for (const field of ['firstName', 'lastName', 'middleName', 'phoneNumber']) data[field] = (data[field] || '').trim();
      if (!data.firstName || !data.lastName) {
        status(messages.NAME_REQUIRED, true);
        form.elements.namedItem(!data.firstName ? 'firstName' : 'lastName').focus();
        return;
      }
    }
    if ('passwordConfirm' in data && data.passwordConfirm !== data.password) {
      status('The passwords do not match.', true);
      return;
    }
    delete data.passwordConfirm;
    const action = form.dataset.authForm;
    if (action === 'verify-email' || action === 'reset-password') data.token = token;
    busy = true;
    const button = form.querySelector('[type="submit"]');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Please wait...';
    status('');
    try {
      await post(action, data);
      form.reset();
      if (action === 'login') {
        location.assign('account.html');
        return;
      }
      const text = action === 'signup'
        ? 'Check your inbox for the next step. If you already have an account, log in or reset your password.'
        : action === 'request-reset'
        ? 'If this email has an eligible account, a password-reset link is on its way.'
        : action === 'request-verification'
        ? 'If verification is needed, a fresh link is on its way. Please check your inbox.'
        : action === 'verify-email'
        ? 'Your email is verified. You can now log in.'
        : 'Your password is updated. Log in with your new password.';
      form.hidden = true;
      if (success) { success.hidden = false; success.querySelector('p').textContent = text; success.focus(); }
      status(text);
    } catch (error) {
      status(messages[error.message] || 'We could not complete the request. Please try again.', true);
      form.querySelectorAll('input[autocomplete="current-password"], input[autocomplete="new-password"]').forEach(input => { input.value = ''; });
      stateNode?.focus();
    } finally {
      busy = false;
      button.disabled = false;
      button.textContent = original;
    }
  }));
  document.querySelectorAll('[data-show-password]').forEach(button => button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.showPassword);
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    button.textContent = show ? 'Hide' : 'Show';
    button.setAttribute('aria-pressed', String(show));
  }));
  document.querySelector('[data-account-logout]')?.addEventListener('click', async event => {
    if (busy) return;
    busy = true;
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await post('logout', {});
      showSession({authenticated:false});
      status('You have been logged out.');
    } catch { status('Logout did not complete. Please try again.', true); }
    finally { busy = false; button.disabled = false; }
  });
  window.addEventListener('pageshow', () => { busy = false; load(); });
})();
