/**
 * Hook-level tests — verifying each hook calls the backend with the parameters
 * you'd actually expect, not that the hook merely exists or renders.
 *
 * This suite exists specifically because of a real incident: usePatients() was
 * built, and the BACKEND for sorting/filtering was built and thoroughly
 * tested — but the hook itself never actually sent sort_by, sort_order, or any
 * filter to the API at all. Every backend test passed the whole time, because
 * the backend was genuinely correct; nothing would have caught this except a
 * test that checks what the hook actually sends. That's what these do.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';

vi.mock('../../api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25, total_pages: 1 }),
    post: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}));

import { api } from '../../api/client';
import { useCreateTask, useDeactivatePatient, usePatients, useUpdateCaseContext, useUpdatePatient } from '../useApi';

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe('usePatients', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends sort_by and sort_order when provided — the exact parameters that were silently missing during the real incident', async () => {
    renderHook(() => usePatients('', 1, false, 'name', 'asc'), { wrapper });
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    const calledUrl = (api.get as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('sort_by=name');
    expect(calledUrl).toContain('sort_order=asc');
  });

  it('sends every filter parameter when provided', async () => {
    renderHook(
      () => usePatients('', 1, false, 'created_at', 'desc', 'active', 'completed', 'staff-id-123'),
      { wrapper },
    );
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    const calledUrl = (api.get as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('eligibility_status=active');
    expect(calledUrl).toContain('program_status=completed');
    expect(calledUrl).toContain('care_team_staff_id=staff-id-123');
  });

  it('omits optional filters entirely when not provided, rather than sending empty values', async () => {
    renderHook(() => usePatients('', 1, false), { wrapper });
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    const calledUrl = (api.get as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('eligibility_status');
    expect(calledUrl).not.toContain('program_status');
    expect(calledUrl).not.toContain('care_team_staff_id');
  });

  it('includes search and include_inactive when set', async () => {
    renderHook(() => usePatients('walter', 1, true), { wrapper });
    await waitFor(() => expect(api.get).toHaveBeenCalled());

    const calledUrl = (api.get as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('search=walter');
    expect(calledUrl).toContain('include_inactive=true');
  });
});

describe('useCreateTask', () => {
  beforeEach(() => vi.clearAllMocks());

  it('posts to the correct patient-scoped endpoint with the given payload', async () => {
    const { result } = renderHook(() => useCreateTask('patient-123'), { wrapper });
    result.current.mutate({ title: 'Call patient', due_date: '2026-01-01' });

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, body] = (api.post as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/patients/patient-123/tasks');
    expect(body).toEqual({ title: 'Call patient', due_date: '2026-01-01' });
  });
});

describe('useUpdatePatient', () => {
  beforeEach(() => vi.clearAllMocks());

  it('patches the correct patient endpoint with the given payload', async () => {
    const { result } = renderHook(() => useUpdatePatient('patient-456'), { wrapper });
    result.current.mutate({ payor_name: 'Aetna' });

    await waitFor(() => expect(api.patch).toHaveBeenCalled());
    const [url, body] = (api.patch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/patients/patient-456');
    expect(body).toEqual({ payor_name: 'Aetna' });
  });
});

describe('useDeactivatePatient', () => {
  beforeEach(() => vi.clearAllMocks());

  it('posts to the correct deactivate endpoint with the reason', async () => {
    const { result } = renderHook(() => useDeactivatePatient(), { wrapper });
    result.current.mutate({ patientId: 'patient-789', reason: 'Discharged' });

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    const [url, body] = (api.post as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/patients/patient-789/deactivate');
    expect(body).toEqual({ reason: 'Discharged' });
  });
});

describe('useUpdateCaseContext', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends exactly the context object passed in, without silently adding or transforming fields', async () => {
    /**
     * This matters specifically because the backend REPLACES the whole
     * context object rather than merging it (verified in the backend suite's
     * test_context_update_replaces_rather_than_merges) — so this hook must
     * never construct a partial payload on its own. Any caller is responsible
     * for sending the full, merged dict; this test only confirms the hook
     * itself doesn't mangle whatever it's given.
     */
    const { result } = renderHook(() => useUpdateCaseContext('case-111'), { wrapper });
    const fullContext = { weight: '78kg', bloodType: 'O+', height: '180cm' };
    result.current.mutate(fullContext);

    await waitFor(() => expect(api.patch).toHaveBeenCalled());
    const [url, body] = (api.patch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe('/api/cases/case-111/context');
    expect(body).toEqual({ context: fullContext });
  });
});
