import { useEffect } from 'react';
import {
  useResult, usePatientCareNotes, usePatientDocuments, usePatientPgi, usePatientTasks,
} from '../hooks/useApi';
import type { Patient, PatientAssessmentSummary } from '../types';

function PrintableResultBlock({ summary }: { summary: PatientAssessmentSummary }) {
  const result = useResult(summary.result_id);
  return (
    <div style={{ marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #ddd' }}>
      <div style={{ fontSize: 14, fontWeight: 700 }}>{summary.title}</div>
      <div style={{ fontSize: 11, color: '#666', marginBottom: 6 }}>
        {summary.source === 'custom' ? 'Custom' : 'Template'} · Completed {summary.scheduled_date}
      </div>
      {result.isLoading && <div style={{ fontSize: 12, color: '#666' }}>Loading…</div>}
      {result.data && (
        <>
          <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 4 }}>{result.data.result.headline}</div>
          {result.data.result.flags?.length > 0 && (
            <ul style={{ fontSize: 11.5, margin: '0 0 4px', paddingLeft: 16 }}>
              {result.data.result.flags.map((f, i) => <li key={i}>{f.text}</li>)}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function PrintableFullRecord({
  patient,
  completed,
  onDone,
}: {
  patient: Patient;
  completed: PatientAssessmentSummary[];
  onDone: () => void;
}) {
  const documents = usePatientDocuments(patient.id);
  const careNotes = usePatientCareNotes(patient.id);
  const tasks = usePatientTasks(patient.id);
  const pgi = usePatientPgi(patient.id);

  const allLoaded = !documents.isLoading && !careNotes.isLoading && !tasks.isLoading && !pgi.isLoading;

  // Waits for every section's own data before printing — this covers a lot more
  // ground than the assessments-only export it's modeled on, so the same fixed
  // short delay that worked there isn't a safe bet here; printing before PGI or
  // care notes have actually loaded would silently produce an incomplete document.
  useEffect(() => {
    if (!allLoaded) return;
    const timer = setTimeout(() => window.print(), 400);
    return () => clearTimeout(timer);
  }, [allLoaded]);

  return (
    <div>
      <div className="no-print" style={{ marginBottom: 16 }}>
        <a className="back-link" onClick={onDone}>← Back to {patient.name}</a>
        <button className="btn btn-primary" style={{ marginLeft: 12 }} disabled={!allLoaded} onClick={() => window.print()}>
          🖨 Print
        </button>
        {!allLoaded && <span style={{ marginLeft: 10, fontSize: 12.5, color: 'var(--ink-soft)' }}><span className="spinner" />Preparing record…</span>}
      </div>

      <div style={{ fontFamily: 'Georgia, serif', color: '#111' }}>
        <h1 style={{ fontSize: 20, marginBottom: 2 }}>{patient.name}</h1>
        <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
          MRN {patient.mrn} · DOB {formatDate(patient.dob)}
        </div>
        <div style={{ fontSize: 12, color: '#666', marginBottom: 24 }}>
          {patient.clinical_programs.length > 0
            ? patient.clinical_programs.map((p) => p.label).join(', ')
            : patient.care_pathway || 'No program on file'}
          {patient.payor_name && ` · ${patient.payor_name}`}
        </div>

        <h2 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '2px solid #111', paddingBottom: 6 }}>
          Completed Assessments
        </h2>
        {completed.map((s) => <PrintableResultBlock key={s.assigned_assessment_id} summary={s} />)}
        {completed.length === 0 && <p style={{ fontSize: 12.5, color: '#666' }}>No completed assessments yet.</p>}

        <h2 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '2px solid #111', paddingBottom: 6, marginTop: 24 }}>
          Documents
        </h2>
        {documents.data && documents.data.length > 0 ? (
          <table style={{ fontSize: 12, width: '100%' }}>
            <tbody>
              {documents.data.map((d) => (
                <tr key={d.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '4px 0' }}>{d.filename}</td>
                  <td style={{ padding: '4px 0', color: '#666' }}>{formatDate(d.uploaded_at)}</td>
                  <td style={{ padding: '4px 0', color: '#666' }}>{d.extraction_status === 'ok' ? 'Text extracted' : d.extraction_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ fontSize: 12.5, color: '#666' }}>No documents uploaded.</p>
        )}

        <h2 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '2px solid #111', paddingBottom: 6, marginTop: 24 }}>
          Care Notes
        </h2>
        {careNotes.data && careNotes.data.length > 0 ? (
          careNotes.data.map((n) => (
            <div key={n.id} style={{ marginBottom: 10, fontSize: 12.5 }}>
              <div>{n.content}</div>
              <div style={{ fontSize: 11, color: '#666' }}>{n.author?.name ?? 'Unknown'} · {formatDate(n.created_at)}</div>
            </div>
          ))
        ) : (
          <p style={{ fontSize: 12.5, color: '#666' }}>No care notes.</p>
        )}

        <h2 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '2px solid #111', paddingBottom: 6, marginTop: 24 }}>
          Tasks
        </h2>
        {tasks.data && tasks.data.length > 0 ? (
          <table style={{ fontSize: 12, width: '100%' }}>
            <tbody>
              {tasks.data.map((t) => (
                <tr key={t.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '4px 0' }}>{t.title}</td>
                  <td style={{ padding: '4px 0', color: '#666' }}>{t.assigned_to?.name ?? 'Unassigned'}</td>
                  <td style={{ padding: '4px 0', color: '#666' }}>{t.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ fontSize: 12.5, color: '#666' }}>No tasks.</p>
        )}

        <h2 style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '2px solid #111', paddingBottom: 6, marginTop: 24 }}>
          Problems, Goals &amp; Interventions
        </h2>
        {pgi.data && pgi.data.length > 0 ? (
          pgi.data.map((p) => (
            <div key={p.id} style={{ marginBottom: 12, fontSize: 12.5 }}>
              <div style={{ fontWeight: 700 }}>{p.description} ({p.status})</div>
              {p.goals.map((g) => (
                <div key={g.id} style={{ marginLeft: 14, marginTop: 4 }}>
                  <div style={{ fontWeight: 600 }}>→ {g.description} ({g.status})</div>
                  {g.interventions.map((iv) => (
                    <div key={iv.id} style={{ marginLeft: 14, fontSize: 11.5, color: '#444' }}>↳ {iv.description} ({iv.status})</div>
                  ))}
                </div>
              ))}
            </div>
          ))
        ) : (
          <p style={{ fontSize: 12.5, color: '#666' }}>No PGI items tracked.</p>
        )}
      </div>
    </div>
  );
}
