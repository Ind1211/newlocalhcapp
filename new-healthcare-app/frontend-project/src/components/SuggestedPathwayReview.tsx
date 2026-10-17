import { useState } from 'react';
import { useAssessments, useConfirmPathway } from '../hooks/useApi';
import type { ComputedResult } from '../types';

export function SuggestedPathwayReview({
  result,
  patientId,
  onDone,
}: {
  result: ComputedResult;
  patientId: string;
  onDone: () => void;
}) {
  const pathway = result.suggestedPathway ?? [];
  const allAssessments = useAssessments(null);
  const titleFor = (moduleId: string) => allAssessments.data?.find((a) => a.key === moduleId)?.title ?? moduleId;

  // Everything starts checked — mandatory items included, since they're mandatory
  // for a real clinical reason, but still genuinely removable here. This screen's
  // whole purpose is that nothing gets scheduled without a human looking at it
  // first, mandatory or not.
  const [checked, setChecked] = useState<Record<string, boolean>>(
    Object.fromEntries(pathway.map((p) => [p.moduleId, true]))
  );
  const confirmPathway = useConfirmPathway(patientId);

  const toggle = (moduleId: string) => setChecked((c) => ({ ...c, [moduleId]: !c[moduleId] }));
  const checkedCount = Object.values(checked).filter(Boolean).length;

  const handleConfirm = () => {
    const items = pathway.filter((p) => checked[p.moduleId]).map((p) => ({ module_id: p.moduleId, mandatory: p.mandatory }));
    confirmPathway.mutate(items, { onSuccess: onDone });
  };

  if (pathway.length === 0) {
    return (
      <div className="field-group" style={{ marginTop: 16 }}>
        <div className="result-headline">{result.headline}</div>
        <p style={{ fontSize: 13.5, color: 'var(--ink-soft)' }}>{result.notes}</p>
        <button className="btn btn-primary" onClick={onDone}>
          Continue
        </button>
      </div>
    );
  }

  return (
    <div className="field-group" style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--ink-soft)', marginBottom: 10 }}>
        Review suggested assessments before scheduling
      </div>
      <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 16 }}>
        Based on the intake answers, {pathway.length} assessment{pathway.length === 1 ? '' : 's'} are suggested
        below. Nothing is scheduled yet — uncheck anything that doesn't apply, then confirm.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {pathway.map((item) => (
          <label
            key={item.moduleId}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 0',
              borderTop: '1px solid var(--line)', cursor: 'pointer',
            }}
          >
            <input type="checkbox" checked={!!checked[item.moduleId]} onChange={() => toggle(item.moduleId)} style={{ marginTop: 3 }} />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 13.5 }}>{titleFor(item.moduleId)}</span>
                <span
                  style={{
                    fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.03em',
                    padding: '1px 7px', borderRadius: 4,
                    color: item.mandatory ? 'var(--critical)' : 'var(--ink-soft)',
                    border: `1px solid ${item.mandatory ? 'var(--critical)' : 'var(--line)'}`,
                  }}
                >
                  {item.mandatory ? 'Mandatory' : 'Optional'}
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 2 }}>{item.reasons.join('; ')}</div>
            </div>
          </label>
        ))}
      </div>

      {confirmPathway.isError && (
        <div className="result-card critical" style={{ marginTop: 16 }}>
          <div className="result-headline">{(confirmPathway.error as Error).message}</div>
        </div>
      )}

      <button
        className="btn btn-primary"
        style={{ marginTop: 16 }}
        disabled={confirmPathway.isPending}
        onClick={handleConfirm}
      >
        {confirmPathway.isPending ? 'Scheduling…' : `Confirm & schedule ${checkedCount} assessment${checkedCount === 1 ? '' : 's'} →`}
      </button>
    </div>
  );
}
