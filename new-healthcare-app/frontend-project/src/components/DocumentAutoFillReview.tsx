import { useState } from 'react';
import type { AutoFillSuggestion } from '../hooks/useApi';
import type { FieldDef } from '../types';

export function DocumentAutoFillReview({
  suggestions,
  allFields,
  onApply,
  onClose,
}: {
  suggestions: Record<string, AutoFillSuggestion>;
  allFields: FieldDef[];
  onApply: (accepted: Record<string, string>) => void;
  onClose: () => void;
}) {
  const suggestionEntries = Object.entries(suggestions);
  const [checked, setChecked] = useState<Record<string, boolean>>(
    Object.fromEntries(suggestionEntries.map(([name]) => [name, true]))
  );

  const labelFor = (name: string) => allFields.find((f) => f.name === name)?.label ?? name;
  const optionLabelFor = (name: string, value: string) => {
    const field = allFields.find((f) => f.name === name);
    const options = field?.options;
    if (!options) return value;
    const match = options.find((o) => (typeof o === 'string' ? o === value : o.value === value));
    if (!match) return value;
    return typeof match === 'string' ? match : match.label;
  };

  const handleApply = () => {
    const accepted: Record<string, string> = {};
    for (const [name, s] of suggestionEntries) {
      if (checked[name]) accepted[name] = s.value;
    }
    onApply(accepted);
  };

  const checkedCount = Object.values(checked).filter(Boolean).length;

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 60,
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto',
      }}
      onClick={onClose}
    >
      <div
        style={{ background: 'var(--surface)', borderRadius: 14, width: '100%', maxWidth: 560, border: '1px solid var(--line)', boxShadow: 'var(--shadow-md)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0 }}>Suggested from documents</h3>
          <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', margin: '6px 0 0' }}>
            Review each suggestion against its source before applying — nothing is filled in until you click Apply.
          </p>
        </div>

        <div style={{ padding: '10px 22px', maxHeight: '55vh', overflowY: 'auto' }}>
          {suggestionEntries.length === 0 ? (
            <p style={{ fontSize: 13.5, color: 'var(--ink-soft)' }}>
              No confident suggestions found in this patient's documents for this assessment.
            </p>
          ) : (
            suggestionEntries.map(([name, s]) => (
              <div key={name} style={{ padding: '12px 0', borderBottom: '1px solid var(--line-soft)', display: 'flex', gap: 12 }}>
                <input
                  type="checkbox"
                  checked={!!checked[name]}
                  onChange={(e) => setChecked((c) => ({ ...c, [name]: e.target.checked }))}
                  style={{ marginTop: 3 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{labelFor(name)}</div>
                  <div style={{ fontSize: 14, marginTop: 2 }}>{optionLabelFor(name, s.value)}</div>
                  <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 4, fontStyle: 'italic' }}>
                    "{s.source}"
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div style={{ padding: '16px 22px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={checkedCount === 0} onClick={handleApply}>
            Apply {checkedCount > 0 ? checkedCount : ''} suggestion{checkedCount === 1 ? '' : 's'}
          </button>
        </div>
      </div>
    </div>
  );
}
