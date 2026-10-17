import type { IntegratedCarePlan } from '../types';

const PRIORITY_COLOR: Record<string, string> = {
  high: 'var(--critical)',
  medium: 'var(--caution)',
  low: 'var(--ink-soft)',
};

export function IntegratedCarePlanDisplay({ carePlan }: { carePlan: IntegratedCarePlan }) {
  return (
    <div className="field-group" style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--ink-soft)', marginBottom: 10 }}>
        Integrated Care Plan — review before acting on it
      </div>

      <p style={{ fontSize: 14, marginTop: 0, marginBottom: 16 }}>{carePlan.summary}</p>

      {carePlan.keyFindings.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--ink-soft)', marginBottom: 6 }}>
            Key Findings
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>
            {carePlan.keyFindings.map((f, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {carePlan.actionItems.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--ink-soft)', marginBottom: 6 }}>
            Action List
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {carePlan.actionItems.map((item, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13.5 }}>
                <span
                  style={{
                    fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: PRIORITY_COLOR[item.priority] ?? 'var(--ink-soft)',
                    border: `1px solid ${PRIORITY_COLOR[item.priority] ?? 'var(--line)'}`, borderRadius: 4, padding: '1px 6px', marginTop: 2, flexShrink: 0,
                  }}
                >
                  {item.priority}
                </span>
                <span>{item.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {carePlan.caveats && (
        <div style={{ fontSize: 12, color: 'var(--ink-soft)', fontStyle: 'italic', marginTop: 8 }}>{carePlan.caveats}</div>
      )}
    </div>
  );
}
