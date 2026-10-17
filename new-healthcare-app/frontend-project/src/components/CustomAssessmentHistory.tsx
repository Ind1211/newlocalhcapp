import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

interface VersionEntry {
  version_number: number;
  title: string;
  blurb: string | null;
  created_by: string;
  created_at: string;
}

export function CustomAssessmentHistory({ assessmentKey, onBack }: { assessmentKey: string; onBack: () => void }) {
  const versions = useQuery({
    queryKey: ['custom-versions', assessmentKey],
    queryFn: () => api.get<VersionEntry[]>(`/api/assessments/custom/${assessmentKey}/versions`),
  });

  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back
      </a>
      <h1 style={{ margin: '16px 0 4px' }}>Version history</h1>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0, marginBottom: 20 }}>
        Every saved version is kept — a case that already used an earlier version keeps its
        original answers and result even after this assessment is edited again.
      </p>

      {versions.isLoading && <div className="empty-state">Loading history…</div>}

      {versions.data?.map((v, i) => (
        <div
          className="field-group"
          key={v.version_number}
          style={{ marginBottom: 12, position: 'relative' }}
        >
          {i === 0 && (
            <span className="pathway-tag mandatory" style={{ position: 'absolute', top: 16, right: 16 }}>
              Current
            </span>
          )}
          <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, color: 'var(--ink-soft)', marginBottom: 4 }}>
            VERSION {v.version_number}
          </div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{v.title}</div>
          {v.blurb && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>{v.blurb}</div>}
          <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 8 }}>
            Saved by {v.created_by} on {new Date(v.created_at).toLocaleDateString()}
          </div>
        </div>
      ))}
    </div>
  );
}
