import test from 'node:test';
import assert from 'node:assert/strict';

import {
  oauthCallbackParams,
  googleAuthorizeUrl,
  sendEmailOtp,
  verifyEmailOtp,
  refreshAccessToken,
  supabaseLogout,
} from '../utils/oauth.ts';

test('oauthCallbackParams extracts access_token and refresh_token from hash fragment', () => {
  const hash = '#access_token=jwt_sample_access_token&refresh_token=sample_refresh_token&expires_in=3600&token_type=bearer';
  const search = '';
  const params = oauthCallbackParams(search, hash);

  assert.equal(params.accessToken, 'jwt_sample_access_token');
  assert.equal(params.refreshToken, 'sample_refresh_token');
  assert.equal(params.error, null);
});

test('oauthCallbackParams extracts error description from query search params', () => {
  const search = '?error=access_denied&error_description=User+cancelled+sign+in';
  const hash = '';
  const params = oauthCallbackParams(search, hash);

  assert.equal(params.accessToken, null);
  assert.equal(params.refreshToken, null);
  assert.equal(params.error, 'User cancelled sign in');
});

test('googleAuthorizeUrl constructs proper Supabase authorize endpoint with redirect_to', () => {
  const url = googleAuthorizeUrl('https://xyzcompany.supabase.co', 'https://ap-command.onrender.com');
  assert.equal(
    url,
    'https://xyzcompany.supabase.co/auth/v1/authorize?provider=google&redirect_to=https%3A%2F%2Fap-command.onrender.com%2Fauth%2Fcallback'
  );
});

test('sendEmailOtp passes create_user: false and rejects unknown evaluator email cleanly', async () => {
  // Mock fetch to simulate Supabase rejecting an unauthorized email when create_user is false
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    const body = JSON.parse(options.body);
    assert.equal(body.create_user, false, 'create_user must be false for pre-provisioned evaluation accounts');
    assert.equal(body.email, 'unknown_evaluator@company.com');
    return {
      ok: false,
      status: 400,
      json: async () => ({ msg: 'Signups not allowed for otp', error_code: 'signup_disabled' }),
    };
  };

  try {
    const res = await sendEmailOtp(
      'https://xyzcompany.supabase.co',
      'sb_anon_test_key',
      'unknown_evaluator@company.com',
      false
    );
    assert.equal(res.success, false);
    assert.match(res.error, /not an authorized evaluation account/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('verifyEmailOtp surfaces friendly expired code error message', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: false,
    status: 400,
    json: async () => ({ msg: 'Token has expired or is invalid' }),
  });

  try {
    const res = await verifyEmailOtp(
      'https://xyzcompany.supabase.co',
      'sb_anon_test_key',
      'hr_evaluator@company.com',
      '123456'
    );
    assert.equal(res.success, false);
    assert.match(res.error, /has expired or is invalid/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('refreshAccessToken cleanly returns rotated tokens on success', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    const body = JSON.parse(options.body);
    assert.equal(body.refresh_token, 'active_refresh_token_abc');
    return {
      ok: true,
      status: 200,
      json: async () => ({
        access_token: 'new_rotated_jwt_token',
        refresh_token: 'new_rotated_refresh_token',
        expires_in: 3600,
        user: { id: 'usr_eval_01', email: 'hr_evaluator@company.com' },
      }),
    };
  };

  try {
    const res = await refreshAccessToken(
      'https://xyzcompany.supabase.co',
      'sb_anon_test_key',
      'active_refresh_token_abc'
    );
    assert.equal(res.success, true);
    assert.equal(res.accessToken, 'new_rotated_jwt_token');
    assert.equal(res.refreshToken, 'new_rotated_refresh_token');
    assert.equal(res.expiresIn, 3600);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('refreshAccessToken cleanly reports invalid_grant error when refresh token is rejected', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: false,
    status: 400,
    json: async () => ({
      error: 'invalid_grant',
      error_description: 'Invalid Refresh Token: Already Used',
    }),
  });

  try {
    const res = await refreshAccessToken(
      'https://xyzcompany.supabase.co',
      'sb_anon_test_key',
      'stale_already_used_refresh_token'
    );
    assert.equal(res.success, false);
    assert.match(res.error, /Invalid Refresh Token/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

import {
  getAuthToken,
  getRefreshToken,
  setSession,
  clearSession,
  refreshActiveSession,
  api,
} from '../api/client.ts';

// Setup Mock LocalStorage for Node.js
function setupMockLocalStorage() {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, val) => store.set(key, String(val)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
  };
  return store;
}

test('Case 9: Invalid or malformed session data in local storage is sanitized', () => {
  setupMockLocalStorage();
  localStorage.setItem('ap_command_center_auth_token', 'undefined');
  localStorage.setItem('ap_command_center_refresh_token', '   ');
  assert.equal(getAuthToken(), null, 'undefined string must evaluate to null');
  assert.equal(getRefreshToken(), null, 'whitespace string must evaluate to null');

  localStorage.setItem('ap_command_center_auth_token', 'null');
  assert.equal(getAuthToken(), null, 'null string must evaluate to null');

  setSession('  valid_access_token  ', '  valid_refresh_token  ', 3600);
  assert.equal(getAuthToken(), 'valid_access_token');
  assert.equal(getRefreshToken(), 'valid_refresh_token');
  clearSession();
  assert.equal(getAuthToken(), null);
  assert.equal(getRefreshToken(), null);
});

test('Case 3: Backend-revoked access token rejects refresh, clears session, and throws', async () => {
  setupMockLocalStorage();
  setSession('revoked_access_token', 'still_valid_refresh_token', 3600);

  let refreshCalled = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes('/api/v1/auth/status')) {
      refreshCalled = true;
      return { ok: true, json: async () => ({ supabase_url: 'https://test.supabase.co', supabase_anon_key: 'test_key' }) };
    }
    // Return explicit 401 Session token has been revoked
    return {
      status: 401,
      ok: false,
      clone: () => ({
        json: async () => ({ detail: 'Session token has been revoked.' }),
      }),
      json: async () => ({ detail: 'Session token has been revoked.' }),
    };
  };

  try {
    await assert.rejects(
      async () => {
        await api.getCurrentUser();
      },
      (err) => {
        assert.equal(err.status, 401);
        assert.equal(err.isRevoked, true, 'isRevoked flag must be set');
        assert.match(err.message, /Session token has been revoked/);
        return true;
      }
    );
    assert.equal(refreshCalled, false, 'Refresh must NOT be attempted when token is revoked');
    assert.equal(getAuthToken(), null, 'Session must be immediately cleared from storage');
    assert.equal(getRefreshToken(), null, 'Refresh token must be wiped from storage');
  } finally {
    globalThis.fetch = originalFetch;
    clearSession();
  }
});

test('Case 1 & 6: Expired access token initiates deduplicated refresh', async () => {
  setupMockLocalStorage();
  setSession('expired_token', 'valid_refresh_token', 3600);

  let refreshEndpointCallCount = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    const authHeader = options?.headers instanceof Headers ? options.headers.get('Authorization') : (options?.headers?.['Authorization'] || (options?.headers?.get && options.headers.get('Authorization')));
    if (url.includes('/api/v1/auth/status')) {
      return { ok: true, json: async () => ({ supabase_url: 'https://test.supabase.co', supabase_anon_key: 'test_key' }) };
    }
    if (url.includes('/auth/v1/token')) {
      refreshEndpointCallCount++;
      return {
        ok: true,
        json: async () => ({
          access_token: 'new_rotated_access_token',
          refresh_token: 'new_rotated_refresh_token',
          expires_in: 3600,
        }),
      };
    }
    if (authHeader === 'Bearer expired_token') {
      return {
        status: 401,
        ok: false,
        clone: () => ({ json: async () => ({ detail: 'Token has expired. Please re-authenticate.' }) }),
        json: async () => ({ detail: 'Token has expired. Please re-authenticate.' }),
      };
    }
    return {
      status: 200,
      ok: true,
      json: async () => ({ id: 'usr_01', email: 'evaluator@zamp.com' }),
    };
  };

  try {
    // Fire two simultaneous requests
    const [res1, res2] = await Promise.all([
      api.getCurrentUser(),
      api.getCurrentUser(),
    ]);

    assert.equal(res1.email, 'evaluator@zamp.com');
    assert.equal(res2.email, 'evaluator@zamp.com');
    assert.equal(refreshEndpointCallCount, 1, 'Simultaneous requests must deduplicate into exactly 1 refresh call');
    assert.equal(getAuthToken(), 'new_rotated_access_token');
    assert.equal(getRefreshToken(), 'new_rotated_refresh_token');
  } finally {
    globalThis.fetch = originalFetch;
    clearSession();
  }
});

test('Case 7A: Realistic interleaving - Tab 2 awaits Tab 1 in-flight refresh and receives the new token', async () => {
  setupMockLocalStorage();
  setSession('expired_token_shared', 'shared_refresh_token', 3600);

  let tab1RefreshCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes('/api/v1/auth/status')) {
      return { ok: true, json: async () => ({ supabase_url: 'https://test.supabase.co', supabase_anon_key: 'test_key' }) };
    }
    if (url.includes('/auth/v1/token')) {
      tab1RefreshCalls++;
      // Simulate network latency for Tab 1
      await new Promise(r => setTimeout(r, 120));
      return {
        ok: true,
        json: async () => ({
          access_token: 'tab1_rotated_access_token',
          refresh_token: 'tab1_rotated_refresh_token',
          expires_in: 3600,
        }),
      };
    }
    return { ok: true, json: async () => ({}) };
  };

  try {
    // Tab 1 initiates refresh
    const tab1Promise = refreshActiveSession();

    // Tab 2 enters refresh 30ms later while Tab 1's lock is held
    await new Promise(r => setTimeout(r, 30));
    // Verify lock is set and token in storage is STILL the expired token
    assert.ok(localStorage.getItem('ap_command_center_refresh_lock'));
    assert.equal(getAuthToken(), 'expired_token_shared');

    // In Tab 2 context (simulating separate tab waiting on storage):
    // Tab 2 awaits Tab 1's completion instead of reusing expired_token_shared
    const [res1, res2] = await Promise.all([
      tab1Promise,
      refreshActiveSession(),
    ]);

    assert.equal(res1, 'tab1_rotated_access_token');
    assert.equal(res2, 'tab1_rotated_access_token');
    assert.notEqual(res2, 'expired_token_shared', 'Tab 2 must NEVER reuse expired initial token');
    assert.equal(tab1RefreshCalls, 1, 'Exactly one network refresh call should occur');
  } finally {
    globalThis.fetch = originalFetch;
    clearSession();
  }
});

test('Case 7B: Tab 1 crash - Tab 2 breaks out after lock timeout and performs the refresh itself', async () => {
  setupMockLocalStorage();
  setSession('expired_token_shared', 'valid_refresh_token', 3600);

  // Simulate Tab 1 acquiring lock 4500ms ago and crashing without updating token or releasing lock
  localStorage.setItem('ap_command_center_refresh_lock', (Date.now() - 4500).toString());

  let tab2Refreshed = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes('/api/v1/auth/status')) {
      return { ok: true, json: async () => ({ supabase_url: 'https://test.supabase.co', supabase_anon_key: 'test_key' }) };
    }
    if (url.includes('/auth/v1/token')) {
      tab2Refreshed = true;
      return {
        ok: true,
        json: async () => ({
          access_token: 'tab2_recovered_token',
          refresh_token: 'tab2_recovered_refresh',
          expires_in: 3600,
        }),
      };
    }
    return { ok: true, json: async () => ({}) };
  };

  try {
    const res = await refreshActiveSession();
    assert.equal(res, 'tab2_recovered_token');
    assert.equal(tab2Refreshed, true, 'Tab 2 must perform the refresh itself after crashed tab timeout');
  } finally {
    globalThis.fetch = originalFetch;
    clearSession();
  }
});

test('Case 7C: Logout or revocation in another tab immediately invalidates waiting tabs', async () => {
  setupMockLocalStorage();
  setSession('token_before_logout', 'refresh_before_logout', 3600);

  // Tab 1 sets lock
  localStorage.setItem('ap_command_center_refresh_lock', Date.now().toString());

  // While Tab 2 starts waiting, user clicks logout in Tab 1
  const waitPromise = refreshActiveSession();
  setTimeout(() => {
    clearSession();
  }, 40);

  const result = await waitPromise;
  assert.equal(result, null, 'Waiting tab must return null when session is cleared by logout');
});

test('Case 4 & 5: Logout handling survives partial provider or server failure', async () => {
  setupMockLocalStorage();
  setSession('token_to_logout', 'refresh_to_logout', 3600);

  // Subcase A: Supabase logout succeeds, backend logout fails
  const supabaseSuccess = await supabaseLogout('https://test.supabase.co', 'anon_key', 'token_to_logout');
  // clearSession still works
  clearSession();
  assert.equal(getAuthToken(), null);
  assert.equal(getRefreshToken(), null);

  // Subcase B: Backend logout succeeds, Supabase logout fails (e.g. network failure)
  setSession('token_to_logout_2', 'refresh_to_logout_2', 3600);
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('Network timeout'); };
  const supabaseFail = await supabaseLogout('https://test.supabase.co', 'anon_key', 'token_to_logout_2');
  assert.equal(supabaseFail, false, 'Should return false without unhandled exception');
  clearSession();
  assert.equal(getAuthToken(), null, 'Client local state must still be wiped cleanly');
  globalThis.fetch = originalFetch;
});
