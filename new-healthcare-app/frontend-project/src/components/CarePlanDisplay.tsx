import type { CarePlan } from '../types';

const URGENCY_SEVERITY: Record<string, string> = { routine: 'good', soon: 'warning', urgent: 'critical' };

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ink-soft)', marginBottom: 6 }}>
        {title}
      </div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>
        {items.map((item, i) => (
          <li key={i} style={{ marginBottom: 4 }}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CarePlanDisplay({ carePlan }: { carePlan: CarePlan }) {
  const referralSeverity = carePlan.referral?.needed
    ? URGENCY_SEVERITY[carePlan.referral.urgency] ?? 'caution'
    : 'good';

  return (
    <div className={`result-card ${referralSeverity}`} style={{ marginTop: 20 }}>
      <div className="result-headline" style={{ marginBottom: 12 }}>
        AI-generated care plan — review before acting on it
      </div>

      <p style={{ fontSize: 14, marginTop: 0, marginBottom: 14 }}>{carePlan.stageSummary}</p>

      <Section title="Red flags" items={carePlan.redFlags} />

      {carePlan.referral && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ink-soft)', marginBottom: 6 }}>
            Referral
          </div>
          <div style={{ fontSize: 13.5 }}>
            {carePlan.referral.needed
              ? `Recommended — ${carePlan.referral.urgency}. ${carePlan.referral.reason}`
              : 'Not indicated based on the information provided.'}
          </div>
        </div>
      )}

      {carePlan.monitoring && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ink-soft)', marginBottom: 6 }}>
            Monitoring
          </div>
          <div style={{ fontSize: 13.5 }}>
            {carePlan.monitoring.frequency}
            {carePlan.monitoring.labsToTrend?.length ? ` — trend: ${carePlan.monitoring.labsToTrend.join(', ')}` : ''}
          </div>
        </div>
      )}

      <Section title="Medications to consider" items={carePlan.medications} />
      <Section title="Lifestyle" items={carePlan.lifestyle} />
      <Section title="Patient education" items={carePlan.patientEducation} />

      {carePlan.suggestedAssessments?.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--ink-soft)', marginBottom: 6 }}>
            Suggested follow-up assessments
          </div>
          <div style={{ fontSize: 13.5 }}>{carePlan.suggestedAssessments.join(', ')}</div>
        </div>
      )}

      {carePlan.caveats && <div className="result-notes">{carePlan.caveats}</div>}
    </div>
  );
}
