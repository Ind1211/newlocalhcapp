import { useEffect, useRef, useState } from 'react';
import { useMyStaffRecord } from '../hooks/useApi';
import { ROLE_LABELS } from './StaffManagement';

function initials(text: string): string {
  const parts = text.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return text.slice(0, 2).toUpperCase();
}

export function UserProfileMenu({
  email,
  onLogout,
  onManageStaff,
  onManageAssessments,
  onManageWorkflows,
}: {
  email: string | null;
  onLogout: () => void;
  onManageStaff: () => void;
  onManageAssessments: () => void;
  onManageWorkflows: () => void;
}) {
  const [open, setOpen] = useState(false);
  const staff = useMyStaffRecord();
  const isAdmin = staff.data?.role === 'admin';
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // staff.data can be genuinely null — an authenticated Auth0 user with no
  // Staff record yet, a real, expected state — so this falls back to their
  // email for both the avatar initials and the display, rather than showing
  // nothing at all.
  const displayName = staff.data?.name ?? email ?? 'Account';
  const roleLabel = staff.data ? (ROLE_LABELS[staff.data.role] ?? staff.data.role) : null;

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        className="btn"
        onClick={() => setOpen((o) => !o)}
        style={{ width: 38, height: 38, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%' }}
        aria-label="Account menu"
      >
        <div
          style={{
            width: 26, height: 26, borderRadius: '50%', background: 'var(--accent-tint)',
            color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 700, fontSize: 10.5, flexShrink: 0,
          }}
        >
          {initials(displayName)}
        </div>
      </button>

      {open && (
        <div
          style={{
            position: 'absolute', top: '100%', right: 0, marginTop: 8, width: 260,
            background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12,
            boxShadow: 'var(--shadow-md)', zIndex: 60, padding: 16,
          }}
        >
          <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 2 }}>{staff.data?.name ?? 'Account'}</div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', wordBreak: 'break-all', marginBottom: roleLabel ? 8 : 14 }}>
            {email ?? '—'}
          </div>
          {roleLabel && (
            <span className="tag tag-accent" style={{ marginBottom: 14, display: 'inline-block' }}>{roleLabel}</span>
          )}

          {isAdmin && (
            <div style={{ borderTop: '1px solid var(--line)', paddingTop: 8, marginBottom: 8, display: 'flex', flexDirection: 'column' }}>
              <button className="masthead-nav-link" style={{ textAlign: 'left' }} onClick={() => { onManageStaff(); setOpen(false); }}>
                Staff
              </button>
              <button className="masthead-nav-link" style={{ textAlign: 'left' }} onClick={() => { onManageAssessments(); setOpen(false); }}>
                Assessments
              </button>
              <button className="masthead-nav-link" style={{ textAlign: 'left' }} onClick={() => { onManageWorkflows(); setOpen(false); }}>
                Workflows
              </button>
            </div>
          )}

          <button className="btn" style={{ width: '100%' }} onClick={onLogout}>
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
