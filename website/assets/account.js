(() => {
  const stateNode = document.querySelector('[data-account-status]');
  const profile = document.querySelector('[data-account-profile]');
  const guest = document.querySelector('[data-account-guest]');
  const startLinks = [...document.querySelectorAll('[data-auth-start]')];
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
    document.querySelectorAll('[data-account-signup]').forEach(link => {
      link.hidden = Boolean(data.authenticated);
    });
    if (profile) profile.hidden = !data.authenticated;
    if (guest) guest.hidden = Boolean(data.authenticated);
    csrf = data.csrfToken || '';
    if (data.authenticated) {
      document.querySelectorAll('[data-account-email]').forEach(n => { n.textContent = data.user.email; });
      document.querySelectorAll('[data-account-name]').forEach(n => {
        n.textContent = [data.user.firstName, data.user.lastName].filter(Boolean).join(' ') || 'Nektron member';
      });
      status('You are signed in to Nektron.');
    } else if (profile) {
      status('Sign in to view your account.');
    }
  }
  const errors = {
    expired: 'Your sign-in session expired. Please try again.',
    verify_email: 'Please verify your email using the Auth0 email, then log in again.',
    signin_failed: 'We could not complete sign-in. Please try again or contact info@nektron.ai.',
  };
  const error = new URLSearchParams(location.search).get('error');
  if (error && errors[error]) status(errors[error], true);

  async function load() {
    try {
      const response = await fetch('/api/account/session', {
        credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error('unavailable');
      const data = await response.json();
      if (typeof data.authenticated !== 'boolean') throw new Error('invalid response');
      showSession(data);
      if (error && errors[error] && !data.authenticated) status(errors[error], true);
    } catch {
      if (profile) profile.hidden = true;
      if (guest) guest.hidden = false;
      status('Account access is temporarily unavailable. Please try again shortly.', true);
    }
  }

  startLinks.forEach(link => link.addEventListener('click', () => {
    if (busy) return;
    busy = true;
    status('Opening secure sign-in...');
  }));
  document.querySelector('[data-account-logout]')?.addEventListener('click', async event => {
    if (busy) return;
    busy = true;
    event.currentTarget.disabled = true;
    try {
      const response = await fetch('/api/account/logout', {
        method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrf },
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error('logout failed');
      showSession({ authenticated: false });
      status('You have been signed out of this website.');
    } catch {
      status('Sign-out did not complete. Please try again.', true);
    } finally {
      busy = false;
      event.target.disabled = false;
    }
  });
  // Refresh on back/forward restores, including a page restored after logout.
  window.addEventListener('pageshow', () => { busy = false; load(); });
})();
