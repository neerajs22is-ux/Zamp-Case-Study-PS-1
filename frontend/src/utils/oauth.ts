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
