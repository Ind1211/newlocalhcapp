import { useState } from 'react';
import { useGenerateIntegratedCarePlan, useLogContact, usePatient, usePatientAssessments } from '../hooks/useApi';
import { IntegratedCarePlanDisplay } from './IntegratedCarePlanDisplay';
import { EditPatientModal } from './EditPatientModal';
import { SuggestedPgiReview } from './SuggestedPgiReview';
import { NewAssessmentModal } from './NewAssessmentModal';
import { OnboardingProgressStepper } from './OnboardingProgressStepper';
import { PatientAuditLog } from './PatientAuditLog';
import { PatientHealthDetails } from './PatientHealthDetails';
import { PatientVoiceNotes } from './PatientVoiceNotes';
import { PatientCareNotes } from './PatientCareNotes';
import { PatientCareTeam } from './PatientCareTeam';
import { PatientDocuments } from './PatientDocuments';
import { PatientPgi } from './PatientPgi';
import { PatientTasks } from './PatientTasks';
import { RecentAutomation } from './RecentAutomation';
import { PrintableAssessments } from './PrintableAssessments';
import { PrintableFullRecord } from './PrintableFullRecord';
import type { Patient, PatientAssessmentSummary } from '../types';

function initials(name: string | null): string {
  if (!name) return '?';
  return name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();
}

function formatDate(d: string | null): string {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function StatusPill({ status }: { status: PatientAssessmentSummary['status'] }) {
  const variant = status === 'Completed' ? 'tag-good' : status === 'In Progress' ? 'tag-accent' : 'tag-caution';
  return <span className={`tag ${variant}`}>{status}</span>;
}

function AvatarCircle({ name, size }: { name: string | null; size: number }) {
  return (
    <div
      style={{
        width: size, height: size, borderRadius: '50%', background: 'var(--accent-tint)',
        color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontWeight: 700, fontSize: size * 0.33, flexShrink: 0,
      }}
    >
      {initials(name)}
    </div>
  );
}

export function PatientDetail({
  patient: initialPatient,
  onBack,
  onOpenAssessment,
  onPatientUpdated,
}: {
  patient: Patient;
  onBack: () => void;
  onOpenAssessment: (summary: PatientAssessmentSummary) => void;
  onPatientUpdated: (patient: Patient) => void;
}) {
  // initialPatient is a static snapshot passed down from navigation state —
  // it never updates on its own. A mutation elsewhere (like submitting an
  // assessment result that triggers the rules engine) can change this
  // patient's real data server-side; without this live query, this whole
  // screen would keep showing whatever risk_level, etc. existed at the
  // moment the person first navigated in, no matter how many things
  // change after that. Falls back to the snapshot only until the live
  // fetch resolves, so there's no flash of missing data.
  const livePatient = usePatient(initialPatient.id);
  const patient = livePatient.data ?? initialPatient;

  const [showNewModal, setShowNewModal] = useState(false);
  const [showPrint, setShowPrint] = useState(false);
  const [showFullExport, setShowFullExport] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [pgiSuggestionHandled, setPgiSuggestionHandled] = useState(false);
  const [activeTab, setActiveTab] = useState<'assessments' | 'documents' | 'tasks' | 'care-notes' | 'pgi' | 'care-team' | 'audit-log' | 'health-details' | 'voice-notes'>('assessments');
  const assessments = usePatientAssessments(patient.id);
  const logContact = useLogContact(patient.id);
  const carePlan = useGenerateIntegratedCarePlan(patient.id);
  const completed = assessments.data?.filter((a) => a.status === 'Completed') ?? [];

  if (showPrint) {
    return <PrintableAssessments patient={patient} completed={completed} onDone={() => setShowPrint(false)} />;
  }
  if (showFullExport) {
    return <PrintableFullRecord patient={patient} completed={completed} onDone={() => setShowFullExport(false)} />;
  }

  const TABS: { key: typeof activeTab; label: string }[] = [
    { key: 'assessments', label: 'Assessments' },
    { key: 'documents', label: 'Documents' },
    { key: 'voice-notes', label: 'Voice Notes' },
    { key: 'tasks', label: 'Tasks' },
    { key: 'care-notes', label: 'Care Notes' },
    { key: 'pgi', label: 'PGI' },
    { key: 'care-team', label: 'Care Team' },
    { key: 'health-details', label: 'Patient Health Details' },
    { key: 'audit-log', label: 'Audit Log' },
  ];

  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back to patients
      </a>

      <div className="field-group" style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '10px 20px', marginBottom: 16, marginTop: 12 }}>
        <div style={{ gridRow: 'span 2', display: 'flex', alignItems: 'flex-start', paddingTop: 4 }}>
          <AvatarCircle name={patient.name} size={52} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h2 style={{ margin: 0 }}>{patient.name}</h2>
          {patient.risk_level && (
            <span
              className={`tag ${patient.risk_level === 'critical' || patient.risk_level === 'high' ? 'tag-critical' : patient.risk_level === 'medium' ? 'tag-caution' : 'tag-good'}`}
              style={{ textTransform: 'uppercase', fontSize: 10.5 }}
            >
              {patient.risk_level} risk
            </span>
          )}
          <button className="btn" style={{ fontSize: 11.5, padding: '3px 10px' }} onClick={() => setShowEditModal(true)}>Edit</button>
        </div>

        {/* Every field flows into one responsive grid, filling the full width
            evenly across roughly two rows — rather than three separate flex
            rows that each only used a fraction of the available space,
            leaving the area beside the avatar empty. */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '16px 20px', paddingTop: 4 }}>
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>MRN</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, fontFamily: "'Inter', sans-serif", overflowWrap: 'break-word' }}>{patient.mrn}</div>
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>Date of Birth</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, fontFamily: "'Inter', sans-serif", overflowWrap: 'break-word' }}>{formatDate(patient.dob)}</div>
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>Clinical Programs</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {patient.clinical_programs.length > 0 ? (
                patient.clinical_programs.map((p) => (
                  <span key={p.key} className="tag tag-accent">
                    {p.icon ? `${p.icon} ` : ''}{p.label}
                  </span>
                ))
              ) : (
                <span style={{ fontSize: 13.5, color: 'var(--ink-soft)', fontStyle: 'italic' }}>
                  {patient.care_pathway || 'None yet'}
                </span>
              )}
            </div>
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>Payor</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, overflowWrap: 'break-word' }}>{patient.payor_name || '—'}</div>
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>Member ID</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, fontFamily: "'Inter', sans-serif", overflowWrap: 'break-word' }}>{patient.member_id || '—'}</div>
          </div>
          {patient.group_number && (
            <div style={{ minWidth: 0 }}>
              <div className="section-label" style={{ marginBottom: 2 }}>Group Number</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, fontFamily: "'Inter', sans-serif", overflowWrap: 'break-word' }}>{patient.group_number}</div>
            </div>
          )}
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>Eligibility</div>
            <span
              className={`tag ${patient.eligibility_status === 'active' ? 'tag-good' : patient.eligibility_status === 'inactive' ? 'tag-critical' : 'tag-caution'}`}
              style={{ display: 'inline-block', textTransform: 'capitalize' }}
            >
              {patient.eligibility_status || 'unverified'}
            </span>
          </div>
          {patient.phone_number && (
            <div style={{ minWidth: 0 }}>
              <div className="section-label" style={{ marginBottom: 2 }}>Phone</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, fontFamily: "'Inter', sans-serif", overflowWrap: 'break-word' }}>{patient.phone_number}</div>
            </div>
          )}
          {patient.email && (
            <div style={{ minWidth: 0 }}>
              <div className="section-label" style={{ marginBottom: 2 }}>Email</div>
              <div style={{ fontSize: 13.5, fontWeight: 600, overflowWrap: 'break-word' }}>{patient.email}</div>
            </div>
          )}
          <div style={{ minWidth: 0 }}>
            <div className="section-label" style={{ marginBottom: 2 }}>Last Contact</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13.5, fontWeight: 600 }}>
                {patient.last_contact_date ? formatDate(patient.last_contact_date.slice(0, 10)) : 'Never logged'}
              </span>
              <button
                className="btn" style={{ fontSize: 10.5, padding: '2px 7px' }}
                disabled={logContact.isPending}
                onClick={() => logContact.mutate(undefined, { onSuccess: (updated) => onPatientUpdated(updated) })}
                title="Record that you just reached this patient"
              >
                {logContact.isPending ? '…' : '+ Log now'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <OnboardingProgressStepper patientId={patient.id} />

      <RecentAutomation patientId={patient.id} />

      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'documents' && <PatientDocuments patientId={patient.id} />}
      {activeTab === 'voice-notes' && <PatientVoiceNotes patientId={patient.id} />}
      {activeTab === 'tasks' && <PatientTasks patientId={patient.id} />}
      {activeTab === 'care-notes' && <PatientCareNotes patientId={patient.id} />}
      {activeTab === 'pgi' && <PatientPgi patientId={patient.id} />}
      {activeTab === 'care-team' && <PatientCareTeam patientId={patient.id} />}
      {activeTab === 'health-details' && <PatientHealthDetails patientId={patient.id} />}
      {activeTab === 'audit-log' && <PatientAuditLog patientId={patient.id} />}

      {activeTab === 'assessments' && (
        <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Assessments</h2>
        <button className="btn btn-primary" onClick={() => setShowNewModal(true)}>+ New Assessment</button>
      </div>

      {assessments.isLoading && (
        <div className="empty-state">
          <span className="spinner" /><span style={{ verticalAlign: 1 }}>Loading assessments…</span>
        </div>
      )}

      {assessments.isError && (
        <div className="result-card critical">
          <div className="result-headline">Could not load assessments: {(assessments.error as Error).message}</div>
        </div>
      )}

      {assessments.data && assessments.data.length === 0 && (
        <div className="empty-state">
          <div className="empty-title">No assessments yet</div>
          <div className="empty-detail">Use "+ New Assessment" above to get started.</div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {assessments.data?.map((a) => (
          <button
            key={a.assigned_assessment_id}
            onClick={() => onOpenAssessment(a)}
            className="assessment-card"
            style={{ textAlign: 'left', width: '100%', display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer' }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 14.5 }}>{a.title}</span>
                {a.status !== 'Completed' && (
                  <span className={`tag tag-outline ${a.mandatory ? 'tag-critical' : 'tag-neutral'}`} style={{ background: 'transparent' }}>
                    {a.mandatory ? 'Mandatory' : 'Optional'}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 2 }}>
                {a.source === 'custom' ? 'Custom' : 'Template'}
                {a.scheduled_date ? ` · ${formatDate(a.scheduled_date)}` : ''}
                {a.status === 'Completed' && a.result_headline ? ` · ${a.result_headline}` : ''}
              </div>
            </div>
            <StatusPill status={a.status} />
            <span style={{ color: 'var(--ink-soft)' }}>›</span>
          </button>
        ))}
      </div>

      {showNewModal && (
        <NewAssessmentModal
          patientId={patient.id}
          patientProgramKeys={patient.clinical_programs.map((p) => p.key)}
          onClose={() => setShowNewModal(false)}
          onAssigned={() => setShowNewModal(false)}
        />
      )}
      {completed.length > 0 && (
        <>
          <div className="field-group" style={{ marginTop: 24, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Integrated care plan</div>
              <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 4 }}>
                {completed.length} assessment{completed.length === 1 ? '' : 's'} completed. Generate one
                combined narrative and action list across all of them.
              </div>
            </div>
            <button
              className="btn btn-primary"
              disabled={carePlan.isPending}
              onClick={() => { setPgiSuggestionHandled(false); carePlan.mutate(); }}
            >
              {carePlan.isPending && <span className="spinner" />}
              {carePlan.isPending ? 'Generating…' : 'Generate integrated care plan →'}
            </button>
          </div>

          {carePlan.isError && (
            <div className="result-card critical" style={{ marginTop: 12 }}>
              <div className="result-headline">{(carePlan.error as Error).message}</div>
            </div>
          )}
          {carePlan.isSuccess && <IntegratedCarePlanDisplay carePlan={carePlan.data.carePlan} />}
          {carePlan.isSuccess && !pgiSuggestionHandled && (
            <SuggestedPgiReview
              suggested={carePlan.data.suggestedPgi}
              patientId={patient.id}
              onApplied={() => setPgiSuggestionHandled(true)}
              onDismiss={() => setPgiSuggestionHandled(true)}
            />
          )}

        </>
      )}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 16 }}>
        {completed.length > 0 && (
          <button className="btn" style={{ padding: '9px 12px' }} onClick={() => setShowPrint(true)} title="Print completed assessments" aria-label="Print completed assessments">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M6 9V3h12v6M6 18H4a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-2M6 14h12v7H6v-7z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
        <button className="btn" style={{ padding: '9px 12px' }} onClick={() => setShowFullExport(true)} title="Export full patient record" aria-label="Export full patient record">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8l-5-5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M14 3v5h5" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
        </>
      )}

      {showEditModal && (
        <EditPatientModal
          patient={patient}
          onClose={() => setShowEditModal(false)}
          onUpdated={(updated) => {
            setShowEditModal(false);
            onPatientUpdated(updated);
          }}
        />
      )}
    </div>
  );
}
