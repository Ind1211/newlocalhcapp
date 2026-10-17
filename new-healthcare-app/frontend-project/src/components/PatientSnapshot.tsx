import { useEffect, useState } from 'react';
import { SNAPSHOT_FIELD_META } from '../types';
import { useCase, useUpdateCaseContext } from '../hooks/useApi';

const SECTIONS: { key: 'general' | 'kidney' | 'cardiology'; label: string }[] = [
  { key: 'general', label: 'General' },
  { key: 'kidney', label: 'Kidney' },
  { key: 'cardiology', label: 'Cardiology' },
];

export function PatientSnapshot({ caseId }: { caseId: string }) {
  const caseData = useCase(caseId);
  const updateContext = useUpdateCaseContext(caseId);
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (caseData.data?.context) setValues(caseData.data.context);
  }, [caseData.data?.context]);

  const set = (key: string, val: string) => {
    const next = { ...values, [key]: val };
    setValues(next);
    updateContext.mutate(next);
  };

  return (
    <div className="card" style={{ marginBottom: 26 }}>
      <h2 style={{ margin: '0 0 4px', fontSize: 16 }}>Patient snapshot</h2>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13, marginTop: 0, marginBottom: 16 }}>
        Shared across every assessment in this case. Fill it once here — matching fields
        (age, sex, eGFR, ACR, vitals, key labs) pre-fill automatically wherever they're used
        below.
      </p>

      {SECTIONS.map((section) => {
        const fields = SNAPSHOT_FIELD_META.filter((f) => f.program === section.key);
        return (
          <div key={section.key} style={{ marginBottom: 14 }}>
            <div
              style={{
                fontFamily: "'Inter', sans-serif",
                fontSize: 10.5,
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--ink-soft)',
                marginBottom: 8,
              }}
            >
              {section.label}
            </div>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              {fields.map((f) => (
                <div key={f.key}>
                  <div style={{ fontSize: 10.5, color: 'var(--ink-soft)', marginBottom: 4 }}>
                    {f.label.toUpperCase()} {f.unit ? f.unit.toUpperCase() : ''}
                  </div>
                  {f.key === 'sex' ? (
                    <select
                      className="field-input"
                      style={{ width: 90, textAlign: 'left' }}
                      value={values.sex ?? ''}
                      onChange={(e) => set('sex', e.target.value)}
                    >
                      <option value="">—</option>
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                    </select>
                  ) : (
                    <input
                      className="field-input"
                      type="number"
                      style={{ width: 90 }}
                      value={values[f.key] ?? ''}
                      onChange={(e) => set(f.key, e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
