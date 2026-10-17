import { useState } from 'react';
import { usePatientCase, useUpdateCaseContext } from '../hooks/useApi';

// Both auto-extracted keys (already sent as friendly labels by the backend —
// "eGFR", "Systolic BP", "HbA1c") and manually-typed keys (whatever someone
// actually typed into "+ Add Field") are already in their intended display
// form by the time they reach here. The previous version re-split every
// key on each uppercase letter individually, which mangled real acronyms —
// "eGFR" became "E G F R" — since it couldn't tell a genuine camelCase
// boundary from a deliberate run of capitals. Simplest correct fix: display
// exactly what's stored, no transformation.
function formatLabel(key: string): string {
  return key;
}

export function PatientHealthDetails({ patientId }: { patientId: string }) {
  const patientCase = usePatientCase(patientId);
  const updateContext = useUpdateCaseContext(patientCase.data?.id ?? null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [showAddField, setShowAddField] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  const context = patientCase.data?.context ?? {};
  const entries = Object.entries(context);

  // The backend REPLACES the whole context object rather than merging — so
  // every save here has to send the complete, current-plus-changed dict, or it
  // would silently erase every other field already stored (vitals, labs, etc.
  // from completed assessments) that this screen isn't even touching right now.
  const saveContext = (updated: Record<string, string>) => {
    updateContext.mutate(updated, { onSuccess: () => patientCase.refetch() });
  };

  const startEdit = (key: string, value: string) => {
    setEditingKey(key);
    setEditValue(value);
  };

  const commitEdit = () => {
    if (!editingKey) return;
    saveContext({ ...context, [editingKey]: editValue });
    setEditingKey(null);
  };

  const removeField = (key: string) => {
    const updated = { ...context };
    delete updated[key];
    saveContext(updated);
  };

  const addField = () => {
    if (!newKey.trim()) return;
    saveContext({ ...context, [newKey.trim()]: newValue });
    setNewKey('');
    setNewValue('');
    setShowAddField(false);
  };

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Patient Health Details</div>
        {!showAddField && (
          <button className="btn" style={{ fontSize: 12 }} onClick={() => setShowAddField(true)}>+ Add Field</button>
        )}
      </div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 14 }}>
        Vitals, labs, and conditions recorded from completed assessments — the same values
        used to pre-fill matching fields on any future assessment for this patient.
      </p>

      {showAddField && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          <input className="field-input" style={{ maxWidth: 200 }} placeholder="Field name (e.g. weight)" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
          <input className="field-input" style={{ maxWidth: 200 }} placeholder="Value" value={newValue} onChange={(e) => setNewValue(e.target.value)} />
          <button className="btn btn-primary" style={{ fontSize: 12.5 }} disabled={!newKey.trim() || updateContext.isPending} onClick={addField}>Add</button>
          <button className="btn" style={{ fontSize: 12.5 }} onClick={() => { setShowAddField(false); setNewKey(''); setNewValue(''); }}>Cancel</button>
        </div>
      )}

      {patientCase.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}
      {entries.length === 0 && !patientCase.isLoading && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>
          Nothing recorded yet — this fills in automatically as assessments are completed.
        </p>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
        {entries.map(([key, value]) => (
          <div key={key} style={{ padding: '14px 16px', background: 'var(--canvas)', borderRadius: 10, border: '1px solid var(--line)' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.03em' }}>{formatLabel(key)}</div>
            {editingKey === key ? (
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  className="field-input" style={{ fontSize: 13, padding: '4px 8px' }}
                  value={editValue} onChange={(e) => setEditValue(e.target.value)} autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && commitEdit()}
                />
                <button className="btn" style={{ fontSize: 11, padding: '4px 8px' }} onClick={commitEdit}>Save</button>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <span
                  style={{ fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
                  onClick={() => startEdit(key, String(value))}
                  title="Click to edit"
                >
                  {String(value)}
                </span>
                <button
                  className="btn" style={{ fontSize: 10, padding: '2px 6px' }}
                  onClick={() => removeField(key)}
                  aria-label={`Remove ${formatLabel(key)}`}
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {updateContext.isError && (
        <div className="result-card critical" style={{ marginTop: 12 }}>
          <div className="result-headline">{(updateContext.error as Error).message}</div>
        </div>
      )}
    </div>
  );
}
