import { usePatientAuditLog } from '../hooks/useApi';

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

const ACTION_LABELS: Record<string, string> = {
  created: 'Created',
  updated: 'Updated',
  deleted: 'Deleted',
  deactivated: 'Deactivated',
  reactivated: 'Reactivated',
  program_completed: 'Program marked completed',
  program_reopened: 'Program reopened',
  status_changed: 'Status changed',
  resolved: 'Resolved',
  staff_assigned: 'Staff assigned',
  staff_unassigned: 'Staff unassigned',
  uploaded: 'Document uploaded',
  assigned: 'Assigned',
  completed: 'Completed',
  voice_note_created: 'Voice note recorded',
  voice_note_edited: 'Voice note edited',
  extraction_retried: 'Text extraction retried',
};

function describeDetails(action: string, details: Record<string, unknown> | null): string | null {
  if (!details) return null;
  if (action === 'updated' && Array.isArray(details.changed_fields)) {
    return `Changed: ${(details.changed_fields as string[]).join(', ')}`;
  }
  if (action === 'status_changed' && details.from && details.to) {
    return `${details.from} → ${details.to}`;
  }
  if (action === 'deactivated' && details.reason) {
    return `Reason: ${details.reason}`;
  }
  if (typeof details.title === 'string') return details.title;
  if (typeof details.assessment_title === 'string') return details.assessment_title;
  if (typeof details.description === 'string') return details.description;
  if (typeof details.filename === 'string') return details.filename;
  if (typeof details.name === 'string') return details.name;
  return null;
}

const ENTITY_LABELS: Record<string, string> = {
  patient: 'Patient',
  task: 'Task',
  care_note: 'Care Note',
  document: 'Document',
  pgi_problem: 'PGI Problem',
  pgi_goal: 'PGI Goal',
  pgi_intervention: 'PGI Intervention',
  assessment_result: 'Assessment',
  assigned_assessment: 'Assessment',
};

export function PatientAuditLog({ patientId }: { patientId: string }) {
  const auditLog = usePatientAuditLog(patientId);

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div className="section-label">Audit Log</div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 14 }}>
        Every recorded change to this patient's record and everything attached to it — notes, tasks,
        documents, and PGI items — newest first.
      </p>

      {auditLog.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}
      {auditLog.data && auditLog.data.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>No recorded activity yet.</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {auditLog.data?.map((entry) => {
          const detail = describeDetails(entry.action, entry.details);
          return (
            <div key={entry.id} style={{ display: 'flex', gap: 12, padding: '9px 0', borderTop: '1px solid var(--line)', fontSize: 12.5 }}>
              <div style={{ minWidth: 130, color: 'var(--ink-soft)', fontFamily: "'Inter', sans-serif", fontSize: 11.5 }}>
                {formatDateTime(entry.performed_at)}
              </div>
              <div style={{ flex: 1 }}>
                <span className="tag tag-neutral" style={{ marginRight: 6 }}>{ENTITY_LABELS[entry.entity_type] ?? entry.entity_type}</span>
                <span style={{ fontWeight: 600 }}>{ACTION_LABELS[entry.action] ?? entry.action}</span>
                {detail && <span style={{ color: 'var(--ink-soft)' }}> — {detail}</span>}
              </div>
              <div style={{ color: 'var(--ink-soft)' }}>{entry.performed_by ?? 'system'}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
