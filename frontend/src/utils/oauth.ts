export function googleAuthorizeUrl(supabaseUrl: string, origin: string): string {
  const url = new URL(`${supabaseUrl.replace(/\/+$/, '')}/auth/v1/authorize`);
  url.searchParams.set('provider', 'google');
  url.searchParams.set('redirect_to', `${origin}/auth/callback`);
  return url.toString();
}

export function oauthCallbackParams(search: string, hash: string): { accessToken: string | null; error: string | null } {
  const query = new URLSearchParams(search);
  const fragment = new URLSearchParams(hash.replace(/^#/, ''));
  return {
    accessToken: fragment.get('access_token'),
    error: query.get('error_description') || query.get('error') || fragment.get('error_description') || fragment.get('error'),
  };
}

export interface OtpResult {
  success: boolean;
  message?: string;
  error?: string;
}

export interface VerifyOtpResult {
  success: boolean;
  accessToken?: string;
  refreshToken?: string;
  user?: any;
  error?: string;
}

/**
 * Requests a 6-digit OTP code to be sent to the user's email via Supabase Auth REST API.
 */
export async function sendEmailOtp(
  supabaseUrl: string,
  anonKey: string,
  email: string
): Promise<OtpResult> {
  if (!supabaseUrl || !anonKey) {
    return {
      success: false,
      error: 'Supabase authentication service is not configured (missing URL or anon key).',
    };
  }

  const cleanEmail = email.trim().toLowerCase();
  if (!cleanEmail || !cleanEmail.includes('@')) {
    return {
      success: false,
      error: 'Please enter a valid email address.',
    };
  }

  try {
    const endpoint = `${supabaseUrl.replace(/\/+$/, '')}/auth/v1/otp`;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: anonKey,
      },
      body: JSON.stringify({
        email: cleanEmail,
        create_user: true,
      }),
    });

    if (!res.ok) {
      let errMsg = `Request failed (HTTP ${res.status})`;
      try {
        const data = await res.json();
        errMsg = data.msg || data.message || data.error_description || errMsg;
      } catch {
        // default fallback
      }
      return { success: false, error: errMsg };
    }

    return {
      success: true,
      message: `A verification code was sent to ${cleanEmail}. Please check your inbox.`,
    };
  } catch (err: any) {
    return {
      success: false,
      error: err.message || 'Network error reaching authentication service.',
    };
  }
}

/**
 * Verifies a 6-digit OTP code against Supabase Auth REST API and retrieves an authentic session access_token.
 */
export async function verifyEmailOtp(
  supabaseUrl: string,
  anonKey: string,
  email: string,
  token: string
): Promise<VerifyOtpResult> {
  if (!supabaseUrl || !anonKey) {
    return {
      success: false,
      error: 'Supabase authentication service is not configured (missing URL or anon key).',
    };
  }

  const cleanEmail = email.trim().toLowerCase();
  const cleanToken = token.trim();

  if (!cleanEmail || !cleanToken) {
    return {
      success: false,
      error: 'Please enter both your email address and the 6-digit verification code.',
    };
  }

  try {
    const endpoint = `${supabaseUrl.replace(/\/+$/, '')}/auth/v1/verify`;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: anonKey,
      },
      body: JSON.stringify({
        type: 'email',
        email: cleanEmail,
        token: cleanToken,
      }),
    });

    if (!res.ok) {
      let errMsg = `Verification failed (HTTP ${res.status})`;
      try {
        const data = await res.json();
        errMsg = data.msg || data.message || data.error_description || errMsg;
      } catch {
        // default fallback
      }
      return { success: false, error: errMsg };
    }

    const data = await res.json();
    if (!data.access_token) {
      return {
        success: false,
        error: 'Authentication provider returned an invalid session response.',
      };
    }

    return {
      success: true,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      user: data.user,
    };
  } catch (err: any) {
    return {
      success: false,
      error: err.message || 'Network error verifying authentication code.',
    };
  }
}
