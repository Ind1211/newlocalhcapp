import { useEffect } from 'react';
import { useResult } from '../hooks/useApi';
import type { Patient, PatientAssessmentSummary } from '../types';

function PrintableResultBlock({ summary }: { summary: PatientAssessmentSummary }) {
  const result = useResult(summary.result_id);

  return (
    <div style={{ marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid #ccc' }}>
      <div style={{ fontSize: 15, fontWeight: 700 }}>{summary.title}</div>
      <div style={{ fontSize: 11, color: '#666', marginBottom: 8 }}>
        {summary.source === 'custom' ? 'Custom' : 'Template'} · Completed {summary.scheduled_date}
      </div>
      {result.isLoading && <div style={{ fontSize: 12, color: '#666' }}>Loading…</div>}
      {result.data && (
        <>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{result.data.result.headline}</div>
          {result.data.result.metrics?.length > 0 && (
            <table style={{ fontSize: 12, marginBottom: 8 }}>
              <tbody>
                {result.data.result.metrics.map((m, i) => (
                  <tr key={i}>
                    <td style={{ paddingRight: 12, color: '#666' }}>{m.label}</td>
                    <td style={{ fontWeight: 600 }}>{m.value}{m.unit ? ` ${m.unit}` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.data.result.flags?.length > 0 && (
            <ul style={{ fontSize: 12, margin: '0 0 8px', paddingLeft: 18 }}>
              {result.data.result.flags.map((f, i) => (
                <li key={i}>{f.text}</li>
              ))}
            </ul>
          )}
          {result.data.result.notes && <div style={{ fontSize: 11, color: '#666', fontStyle: 'italic' }}>{result.data.result.notes}</div>}
        </>
      )}
    </div>
  );
}

export function PrintableAssessments({
  patient,
  completed,
  onDone,
}: {
  patient: Patient;
  completed: PatientAssessmentSummary[];
  onDone: () => void;
}) {
  // Triggers the browser's native print dialog once the content (including the
  // individually-fetched full results) has had a moment to render — a real PDF
  // export pipeline is a separate, larger feature; this uses the browser's own
  // print-to-PDF, which every browser already supports for free.
  useEffect(() => {
    const timer = setTimeout(() => window.print(), 600);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div>
      <div className="no-print" style={{ marginBottom: 16 }}>
        <a className="back-link" onClick={onDone}>
          ← Back to {patient.name}
        </a>
        <button className="btn btn-primary" style={{ marginLeft: 12 }} onClick={() => window.print()}>
          🖨 Print
        </button>
      </div>

      <div style={{ fontFamily: 'Georgia, serif', color: '#111' }}>
        <h1 style={{ fontSize: 20, marginBottom: 2 }}>{patient.name}</h1>
        <div style={{ fontSize: 12, color: '#666', marginBottom: 20 }}>
          MRN {patient.mrn} · DOB {patient.dob} · {patient.care_pathway}
        </div>
        <h2 style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '2px solid #111', paddingBottom: 6 }}>
          Completed Assessments
        </h2>
        {completed.map((s) => (
          <PrintableResultBlock key={s.assigned_assessment_id} summary={s} />
        ))}
        {completed.length === 0 && <p style={{ fontSize: 13, color: '#666' }}>No completed assessments yet.</p>}
      </div>
    </div>
  );
}
