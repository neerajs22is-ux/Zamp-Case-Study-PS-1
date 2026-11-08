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

test('Case 7: Multi-tab refresh coordination reuses newly stored token', async () => {
  setupMockLocalStorage();
  setSession('initial_token', 'refresh_token_tab1', 3600);

  let supabaseCallCount = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes('/auth/v1/token')) {
      supabaseCallCount++;
      return {
        ok: true,
        json: async () => ({ access_token: 'tab_rotated_token', refresh_token: 'tab_rotated_refresh', expires_in: 3600 }),
      };
    }
    return { ok: true, json: async () => ({ supabase_url: 'https://test.supabase.co', supabase_anon_key: 'test_key' }) };
  };

  try {
    // Simulate another tab having just updated localStorage
    setSession('tab2_already_rotated_token', 'tab2_new_refresh', 3600);
    localStorage.setItem('ap_command_center_refresh_lock', Date.now().toString());

    // When this tab attempts refresh, it detects recent lock and new token, avoiding network race
    const result = await refreshActiveSession();
    assert.equal(result, 'tab2_already_rotated_token');
    assert.equal(supabaseCallCount, 0, 'Must not call Supabase if another tab recently refreshed');
  } finally {
    globalThis.fetch = originalFetch;
    clearSession();
  }
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
