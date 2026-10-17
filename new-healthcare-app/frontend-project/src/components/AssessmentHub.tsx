import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { usePrograms, useAssessments } from '../hooks/useApi';
import type { AssessmentDefinition } from '../types';

// Extracted directly from the original checkpoint's CATEGORY_ORDER constant. 'Basic
// Intake' and 'Custom' are included for fidelity even though this app doesn't have
// those features yet — they're harmless no-ops until it does, and keeping the full
// list means nothing needs to change here when it does.
const CATEGORY_ORDER = [
  'Basic Intake', 'Screening & staging', 'Acute kidney injury', 'Dialysis', 'Procedures & Access',
  'Medication Safety', 'Transplant', 'Complications', 'Disease-specific', 'Pregnancy',
  'Nutrition & frailty', 'Patient-reported', 'Palliative & Conservative Care', 'Pediatric',
  'Arrhythmia & anticoagulation', 'Electrophysiology', 'Heart failure', 'Acute coronary syndrome',
  'Valvular heart disease', 'Cardiomyopathy', 'Congenital heart disease', 'Cardio-obstetrics',
  'Syncope', 'Pericardial disease', 'Infective endocarditis', 'Aortic disease', 'Pulmonary embolism',
  'Primary prevention', 'Vascular & preoperative risk', 'Cardiac rehabilitation',
  'Cardiology measurements', 'Palliative & Advanced Heart Failure', 'Custom',
];

function groupByCategory(assessments: AssessmentDefinition[]): [string, AssessmentDefinition[]][] {
  const groups = new Map<string, AssessmentDefinition[]>();
  for (const a of assessments) {
    if (!groups.has(a.category)) groups.set(a.category, []);
    groups.get(a.category)!.push(a);
  }
  return [...groups.entries()].sort((a, b) => {
    const ia = CATEGORY_ORDER.indexOf(a[0]);
    const ib = CATEGORY_ORDER.indexOf(b[0]);
    // Anything not in the known list sorts after everything that is, rather than
    // silently disappearing or breaking the sort if a new category shows up later.
    if (ia === -1 && ib === -1) return a[0].localeCompare(b[0]);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
}

// Mirrors matchesSearch() exactly: substring match against title, category, or
// blurb — this is why "potassium" finds Hyperkalemia even though the word never
// appears in the title, it's in the blurb.
function matchesSearch(item: AssessmentDefinition, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    item.title.toLowerCase().includes(q) ||
    item.category.toLowerCase().includes(q) ||
    (item.blurb ?? '').toLowerCase().includes(q)
  );
}

export function AssessmentHub({
  onSelect,
  onBuildCustom,
  onEditCustom,
  onViewHistory,
}: {
  onSelect: (a: AssessmentDefinition) => void;
  onBuildCustom: () => void;
  onEditCustom: (a: AssessmentDefinition) => void;
  onViewHistory: (a: AssessmentDefinition) => void;
}) {
  const [programFilter, setProgramFilter] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const programs = usePrograms();
  const assessments = useAssessments(programFilter);
  const queryClient = useQueryClient();
  const deleteMutation = useMutation({
    mutationFn: (key: string) => api.delete(`/api/assessments/custom/${key}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assessments'] });
      setConfirmingDelete(null);
    },
  });

  const filtered = assessments.data?.filter((a) => matchesSearch(a, search)) ?? [];
  const grouped = groupByCategory(filtered);
  // "Custom" always shows (with at least the build card) unless actively searching
  // and nothing matches — matching the original's exact behavior.
  const hasCustomGroup = grouped.some(([cat]) => cat === 'Custom');
  if (!hasCustomGroup && !search) {
    grouped.push(['Custom', []]);
    grouped.sort((a, b) => CATEGORY_ORDER.indexOf(a[0]) - CATEGORY_ORDER.indexOf(b[0]));
  }

  return (
    <div>
      <div className="filter-row">
        <button
          className={`filter-pill ${programFilter === null ? 'active' : ''}`}
          onClick={() => setProgramFilter(null)}
        >
          All programs
        </button>
        {programs.data?.map((p) => (
          <button
            key={p.key}
            className={`filter-pill ${programFilter === p.key ? 'active' : ''}`}
            onClick={() => setProgramFilter(p.key)}
          >
            {p.icon} {p.label}
          </button>
        ))}
      </div>

      <div className="field" style={{ marginBottom: 20 }}>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder='Search assessments (e.g. "potassium", "transplant", "AKI")'
          style={{
            maxWidth: 420,
            padding: '10px 14px',
            border: '1px solid var(--line)',
            borderRadius: 20,
            fontSize: 13.5,
            width: '100%',
          }}
        />
      </div>

      {assessments.isLoading && <div className="empty-state">Loading assessments…</div>}

      {assessments.isError && (
        <div className="result-card critical">
          <div className="result-headline">
            Could not load assessments: {(assessments.error as Error).message}
          </div>
          <div className="result-notes">
            Check that the backend is running and reachable at the API URL in your .env.
          </div>
        </div>
      )}

      {assessments.data && filtered.length === 0 && (
        <div className="empty-state">
          {search ? `No assessments match "${search}".` : 'No assessments match this filter yet.'}
        </div>
      )}

      {grouped.map(([category, items]) => (
        <div key={category} style={{ marginBottom: 28 }}>
          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 11.5,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--ink-soft)',
              marginBottom: 10,
              paddingBottom: 6,
              borderBottom: '1px solid var(--line)',
            }}
          >
            {category}
          </div>
          <div className="assessment-grid">
            {category === 'Custom' && (
              <div
                className="assessment-card"
                style={{ textAlign: 'left', borderStyle: 'dashed' }}
                onClick={onBuildCustom}
              >
                <div className="title">+ Build a custom assessment</div>
                <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 6 }}>
                  Create your own — by form or by uploading a JSON template. Available in
                  every case once saved.
                </div>
              </div>
            )}
            {items.map((a) =>
              category === 'Custom' ? (
                <div className="assessment-card" key={a.key} style={{ cursor: 'default' }}>
                  <div onClick={() => onSelect(a)} style={{ cursor: 'pointer' }}>
                    <div className="title">{a.title}</div>
                    {a.blurb && (
                      <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 4 }}>{a.blurb}</div>
                    )}
                  </div>
                  {confirmingDelete === a.key ? (
                    <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
                      <span style={{ fontSize: 12.5, color: 'var(--critical)', flex: 1 }}>Delete this?</span>
                      <button className="btn" onClick={() => setConfirmingDelete(null)}>
                        Cancel
                      </button>
                      <button
                        className="btn"
                        style={{ background: 'var(--critical)', color: '#fff', borderColor: 'var(--critical)' }}
                        disabled={deleteMutation.isPending}
                        onClick={() => deleteMutation.mutate(a.key)}
                      >
                        {deleteMutation.isPending ? 'Deleting…' : 'Confirm delete'}
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
                      <button className="btn" onClick={() => onEditCustom(a)}>
                        Edit
                      </button>
                      <button className="btn" onClick={() => onViewHistory(a)}>
                        History
                      </button>
                      <button className="btn" onClick={() => setConfirmingDelete(a.key)}>
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="assessment-card" key={a.key} onClick={() => onSelect(a)}>
                  <div className="title">{a.title}</div>
                </div>
              )
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
