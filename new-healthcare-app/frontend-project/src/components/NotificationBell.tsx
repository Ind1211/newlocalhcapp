import { useEffect, useRef, useState } from 'react';
import { useMarkAllRead, useMarkNotificationRead, useNotifications, useUnreadCount } from '../hooks/useApi';
import type { Notification } from '../types';

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const TYPE_ICONS: Record<string, string> = {
  task_assigned: '📋',
  task_due_soon: '⏰',
  assessment_overdue: '⚠️',
  business_rule: '⚙️',
};

export function NotificationBell({ onOpenPatient }: { onOpenPatient: (patientId: string) => void }) {
  const [open, setOpen] = useState(false);
  const unreadCount = useUnreadCount();
  const notifications = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllRead();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleClick = (n: Notification) => {
    if (!n.is_read) markRead.mutate(n.id);
    if (n.related_patient_id) {
      onOpenPatient(n.related_patient_id);
      setOpen(false);
    }
  };

  const count = unreadCount.data?.count ?? 0;

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <button
        className="btn"
        onClick={() => setOpen((o) => !o)}
        style={{ position: 'relative', width: 38, height: 38, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%' }}
        aria-label="Notifications"
      >
        🔔
        {count > 0 && (
          <span
            style={{
              position: 'absolute', top: -4, right: -4, background: 'var(--critical)', color: '#fff',
              borderRadius: '50%', fontSize: 10.5, fontWeight: 700, minWidth: 17, height: 17,
              display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px',
            }}
          >
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute', top: '100%', right: 0, marginTop: 8, width: 360, maxHeight: 440,
            background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12,
            boxShadow: 'var(--shadow-md)', zIndex: 60, display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: '1px solid var(--line)' }}>
            <span style={{ fontWeight: 700, fontSize: 13.5 }}>Notifications</span>
            {count > 0 && (
              <button className="btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={() => markAllRead.mutate()}>
                Mark all read
              </button>
            )}
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {notifications.isLoading && <div style={{ padding: 16, fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}
            {notifications.data && notifications.data.length === 0 && (
              <div style={{ padding: 20, fontSize: 13, color: 'var(--ink-soft)', textAlign: 'center' }}>Nothing yet.</div>
            )}
            {notifications.data?.map((n) => (
              <div
                key={n.id}
                onClick={() => handleClick(n)}
                style={{
                  padding: '10px 16px', borderBottom: '1px solid var(--line)', cursor: 'pointer',
                  background: n.is_read ? 'transparent' : 'var(--accent-tint)',
                  display: 'flex', gap: 10,
                }}
              >
                <span style={{ fontSize: 15 }}>{TYPE_ICONS[n.type] ?? '🔔'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: n.is_read ? 500 : 700 }}>{n.title}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 2 }}>{n.body}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--ink-soft)', marginTop: 3 }}>{formatRelativeTime(n.created_at)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
