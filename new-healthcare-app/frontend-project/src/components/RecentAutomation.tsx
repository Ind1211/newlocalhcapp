import { useRuleExecutionLog } from '../hooks/useApi';

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMins = Math.round(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.round(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Shows this specific patient's recent rule activity — reuses the same
 * execution-log endpoint the standalone Workflows screen already has,
 * filtered to this patient and to rules that actually matched (a checked-
 * but-not-matched rule isn't "automation that happened," it's noise here).
 * Renders nothing at all if there's no automation to show, rather than an
 * empty-state box cluttering the patient page for the common case of a
 * patient with no rule activity yet. */
export function RecentAutomation({ patientId }: { patientId: string }) {
  const log = useRuleExecutionLog(patientId);
  const matched = (log.data ?? []).filter((entry) => entry.matched).slice(0, 5);

  if (log.isLoading || matched.length === 0) return null;

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div className="section-label" style={{ marginBottom: 10 }}>Recent Automation</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {matched.map((entry) => (
          <div key={entry.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <span style={{ fontSize: 15, flexShrink: 0, lineHeight: '18px' }}>⚡</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>{entry.rule_name ?? 'Unnamed rule'}</div>
              {(entry.actions_executed ?? []).map((summary, i) => (
                <div key={i} style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 2 }}>{summary}</div>
              ))}
            </div>
            <div style={{ fontSize: 11, color: 'var(--ink-soft)', flexShrink: 0, whiteSpace: 'nowrap' }}>
              {formatRelativeTime(entry.performed_at)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
