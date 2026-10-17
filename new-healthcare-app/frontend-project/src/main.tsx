import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Auth0Provider } from '@auth0/auth0-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App';
import { AuthTokenBridge } from './auth/AuthTokenBridge';
import './index.css';

const queryClient = new QueryClient();

const domain = import.meta.env.VITE_AUTH0_DOMAIN;
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID;
const audience = import.meta.env.VITE_AUTH0_AUDIENCE;

if (!domain || !clientId) {
  // eslint-disable-next-line no-console
  console.warn(
    'VITE_AUTH0_DOMAIN / VITE_AUTH0_CLIENT_ID are not set — copy .env.example to .env and fill in your Auth0 application values.'
  );
}
if (!audience) {
  // eslint-disable-next-line no-console
  console.warn(
    'VITE_AUTH0_AUDIENCE is not set — without it, Auth0 issues an opaque token instead of a real JWT, ' +
    'and the API gateway cannot validate requests. Create an API resource in your Auth0 dashboard and set its identifier as VITE_AUTH0_AUDIENCE.'
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Auth0Provider
      domain={domain ?? ''}
      clientId={clientId ?? ''}
      authorizationParams={{
        redirect_uri: window.location.origin,
        ...(audience ? { audience } : {}),
      }}
    >
      <AuthTokenBridge>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </AuthTokenBridge>
    </Auth0Provider>
  </StrictMode>
);
