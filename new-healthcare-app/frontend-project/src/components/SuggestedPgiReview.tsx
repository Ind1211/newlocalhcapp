import { useState } from 'react';
import { api } from '../api/client';
import type { SuggestedPgi } from '../types';

interface SelectionState {
  [problemIndex: number]: {
    checked: boolean;
    goals: {
      [goalIndex: number]: {
        checked: boolean;
        interventions: { [interventionIndex: number]: boolean };
      };
    };
  };
}

function buildDefaultSelection(suggested: SuggestedPgi): SelectionState {
  const state: SelectionState = {};
  suggested.problems.forEach((problem, pIdx) => {
    state[pIdx] = { checked: true, goals: {} };
    problem.goals.forEach((goal, gIdx) => {
      state[pIdx].goals[gIdx] = { checked: true, interventions: {} };
      goal.interventions.forEach((_, iIdx) => {
        state[pIdx].goals[gIdx].interventions[iIdx] = true;
      });
    });
  });
  return state;
}

export function SuggestedPgiReview({
  suggested,
  patientId,
  onApplied,
  onDismiss,
}: {
  suggested: SuggestedPgi;
  patientId: string;
  onApplied: () => void;
  onDismiss: () => void;
}) {
  const [selection, setSelection] = useState<SelectionState>(() => buildDefaultSelection(suggested));
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleProblem = (pIdx: number) =>
    setSelection((s) => ({ ...s, [pIdx]: { ...s[pIdx], checked: !s[pIdx].checked } }));
  const toggleGoal = (pIdx: number, gIdx: number) =>
    setSelection((s) => ({
      ...s,
      [pIdx]: { ...s[pIdx], goals: { ...s[pIdx].goals, [gIdx]: { ...s[pIdx].goals[gIdx], checked: !s[pIdx].goals[gIdx].checked } } },
    }));
  const toggleIntervention = (pIdx: number, gIdx: number, iIdx: number) =>
    setSelection((s) => ({
      ...s,
      [pIdx]: {
        ...s[pIdx],
        goals: {
          ...s[pIdx].goals,
          [gIdx]: {
            ...s[pIdx].goals[gIdx],
            interventions: { ...s[pIdx].goals[gIdx].interventions, [iIdx]: !s[pIdx].goals[gIdx].interventions[iIdx] },
          },
        },
      },
    }));

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      // Sequential, not parallel — each goal needs its parent problem's real
      // database id, and each intervention needs its parent goal's, so these
      // genuinely have to happen in dependency order, one create awaited before
      // the next can even be attempted.
      for (let pIdx = 0; pIdx < suggested.problems.length; pIdx++) {
        if (!selection[pIdx]?.checked) continue;
        const problem = suggested.problems[pIdx];
        const createdProblem = await api.post<{ id: string }>(`/api/patients/${patientId}/pgi`, {
          description: problem.description,
        });

        for (let gIdx = 0; gIdx < problem.goals.length; gIdx++) {
          if (!selection[pIdx].goals[gIdx]?.checked) continue;
          const goal = problem.goals[gIdx];
          const createdGoal = await api.post<{ id: string }>(`/api/pgi/problems/${createdProblem.id}/goals`, {
            description: goal.description,
          });

          for (let iIdx = 0; iIdx < goal.interventions.length; iIdx++) {
            if (!selection[pIdx].goals[gIdx].interventions[iIdx]) continue;
            await api.post(`/api/pgi/goals/${createdGoal.id}/interventions`, {
              description: goal.interventions[iIdx],
            });
          }
        }
      }
      onApplied();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApplying(false);
    }
  };

  const anyChecked = Object.values(selection).some((p) => p.checked);

  return (
    <div className="field-group" style={{ marginTop: 16 }}>
      <div className="section-label">Suggested Problems, Goals &amp; Interventions</div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 14 }}>
        Structured from the care plan above — review before adding anything to this patient's PGI tab.
        Nothing is saved until you click Apply.
      </p>

      {suggested.problems.length === 0 ? (
        <p style={{ fontSize: 13.5, color: 'var(--ink-soft)' }}>No PGI structure could be suggested from this plan.</p>
      ) : (
        suggested.problems.map((problem, pIdx) => (
          <div key={pIdx} style={{ padding: '10px 0', borderTop: pIdx > 0 ? '1px solid var(--line)' : 'none' }}>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer' }}>
              <input type="checkbox" checked={selection[pIdx]?.checked ?? false} onChange={() => toggleProblem(pIdx)} style={{ marginTop: 3 }} />
              <span style={{ fontWeight: 700, fontSize: 14 }}>{problem.description}</span>
            </label>
            {problem.goals.map((goal, gIdx) => (
              <div key={gIdx} style={{ marginLeft: 26, marginTop: 6, paddingLeft: 12, borderLeft: '2px solid var(--accent-tint)' }}>
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={selection[pIdx]?.goals[gIdx]?.checked ?? false}
                    onChange={() => toggleGoal(pIdx, gIdx)}
                    style={{ marginTop: 3 }}
                    disabled={!selection[pIdx]?.checked}
                  />
                  <span style={{ fontWeight: 600, fontSize: 13 }}>→ {goal.description}</span>
                </label>
                {goal.interventions.map((intervention, iIdx) => (
                  <label key={iIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginLeft: 24, marginTop: 4, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selection[pIdx]?.goals[gIdx]?.interventions[iIdx] ?? false}
                      onChange={() => toggleIntervention(pIdx, gIdx, iIdx)}
                      disabled={!selection[pIdx]?.checked || !selection[pIdx]?.goals[gIdx]?.checked}
                    />
                    <span style={{ fontSize: 12.5 }}>↳ {intervention}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
        ))
      )}

      {error && (
        <div className="result-card critical" style={{ marginTop: 12 }}>
          <div className="result-headline">{error}</div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button className="btn" onClick={onDismiss} disabled={applying}>Dismiss</button>
        <button className="btn btn-primary" disabled={!anyChecked || applying} onClick={handleApply}>
          {applying && <span className="spinner" />}
          {applying ? 'Applying…' : 'Apply to PGI'}
        </button>
      </div>
    </div>
  );
}
