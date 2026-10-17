import { useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { setTokenGetter } from './tokenProvider';

// Mounted once, inside Auth0Provider but above everything else — its only job is
// keeping tokenProvider's module-level reference in sync with the real,
// hook-provided getAccessTokenSilently, so plain (non-component) code can use it.
export function AuthTokenBridge({ children }: { children: React.ReactNode }) {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  useEffect(() => {
    setTokenGetter(isAuthenticated ? getAccessTokenSilently : null);
    return () => setTokenGetter(null);
  }, [getAccessTokenSilently, isAuthenticated]);

  return children as React.ReactElement;
}
