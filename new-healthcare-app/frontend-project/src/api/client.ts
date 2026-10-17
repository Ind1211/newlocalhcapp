import { getAccessToken } from '../auth/tokenProvider';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

// Used to rewrite /api/... to /api/v1/... for Kong's versioned routing. Kong was
// dropped from the deployment (see claude/azure-container-apps-deployment-plan.md in
// the project notes) — the backend's real routes are just /api/..., so this is now a
// no-op. Kept as a single seam (rather than editing every call site) in case a
// gateway with versioning comes back later.
function versionApiPath(path: string): string {
  return path;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  const res = await fetch(`${API_URL}${versionApiPath(path)}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  // Separate from post() because a file upload needs the browser to set its own
  // Content-Type (with the multipart boundary) — post() always forces
  // application/json, which would corrupt the upload.
  postFile: async <T>(path: string, formData: FormData): Promise<T> => {
    const token = await getAccessToken();
    const res = await fetch(`${API_URL}${versionApiPath(path)}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`);
    }
    return res.json() as Promise<T>;
  },
  // Separate again because this needs the raw response body (a file), not JSON —
  // but still needs the auth token attached, since Kong requires it on every
  // /api/v1/* route. A plain <a href> link to the endpoint URL wouldn't carry
  // that token and would get a 401.
  getBlob: async (path: string): Promise<Blob> => {
    const token = await getAccessToken();
    const res = await fetch(`${API_URL}${versionApiPath(path)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, `Download failed (${res.status})`);
    return res.blob();
  },
};

export { ApiError };
