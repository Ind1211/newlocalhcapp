// api/client.ts is a plain module, not a React component — it can't call useAuth0()
// directly. This module holds a reference to Auth0's token-getter function, set
// once by a small component mounted inside Auth0Provider (see AuthTokenBridge.tsx),
// so the plain client module can still get a current, valid access token.

type TokenGetter = () => Promise<string>;

let tokenGetter: TokenGetter | null = null;

export function setTokenGetter(fn: TokenGetter | null) {
  tokenGetter = fn;
}

export async function getAccessToken(): Promise<string | null> {
  if (!tokenGetter) return null;
  try {
    return await tokenGetter();
  } catch {
    // Not logged in, token expired with no way to refresh silently, etc. — the
    // request proceeds without a token and the gateway/backend rejects it with a
    // real 401, rather than this throwing and masking the actual problem.
    return null;
  }
}
