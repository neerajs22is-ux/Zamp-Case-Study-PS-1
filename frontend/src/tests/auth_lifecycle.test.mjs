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
