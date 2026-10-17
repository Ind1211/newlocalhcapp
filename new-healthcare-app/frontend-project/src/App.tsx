import { useEffect, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import tallyLogo from './assets/tally_logo.svg';
import { CkdStagingWizard } from './components/CkdStagingWizard';
import { NotificationBell } from './components/NotificationBell';
import { UserProfileMenu } from './components/UserProfileMenu';
import { api } from './api/client';
import { useCheckDueNotifications } from './hooks/useApi';
import { CustomAssessmentBuilder } from './components/CustomAssessmentBuilder';
import { CustomAssessmentHistory } from './components/CustomAssessmentHistory';
import { DynamicForm } from './components/DynamicForm';
import { ManageCustomAssessments } from './components/ManageCustomAssessments';
import { BusinessRulesEngine } from './components/BusinessRulesEngine';
import { WorkflowVisualizer } from './components/WorkflowVisualizer';
import { PatientDetail } from './components/PatientDetail';
import { BulkImportPatients } from './components/BulkImportPatients';
import { StaffManagement } from './components/StaffManagement';
import { PatientsList } from './components/PatientsList';
import { SuggestedPathwayReview } from './components/SuggestedPathwayReview';
import { useAssessmentDetail, useLatestResult, usePatientCase } from './hooks/useApi';
import type { AssessmentDefinition, Patient, PatientAssessmentSummary } from './types';

function LoginGate() {
  const { loginWithRedirect } = useAuth0();
  return (
    <div className="empty-state">
      <p>Sign in to access patient assessments.</p>
      <button className="btn btn-primary" onClick={() => loginWithRedirect()}>
        Log in
      </button>
    </div>
  );
}

// Resolves the patient's primary case (auto-created server-side) plus the specific
// assessment's full field detail before handing off to whichever filling-in
// component applies. Passes through the assigned-assessment id and any existing
// draft so Save Progress and resuming an In Progress assessment both work.
function FillAssessment({
  patient,
  summary,
  onBack,
}: {
  patient: Patient;
  summary: PatientAssessmentSummary;
  onBack: () => void;
}) {
  const patientCase = usePatientCase(patient.id);
  const detail = useAssessmentDetail(summary.assessment_definition_key, patient.id);
  const caseId = patientCase.data?.id ?? null;
  const latestResult = useLatestResult(caseId, summary.assessment_definition_key);
  const hasDraft = !!summary.draft_answers && Object.keys(summary.draft_answers).length > 0;
  // 'pending' only matters when there's a real prior result to offer and no
  // existing draft already in progress — an in-progress draft always takes
  // priority over "start from last time", since it's the person's own more
  // recent, unfinished work.
  const [prefillChoice, setPrefillChoice] = useState<'pending' | 'use-prior' | 'fresh'>(
    hasDraft ? 'fresh' : 'pending'
  );

  if (patientCase.isLoading || detail.isLoading || (prefillChoice === 'pending' && latestResult.isLoading)) {
    return <div className="empty-state">Loading assessment…</div>;
  }
  if (patientCase.isError || detail.isError || !detail.data) {
    return (
      <div className="empty-state">
        <a className="back-link" onClick={onBack}>
          ← Back to {patient.name}
        </a>
        <p>Could not load this assessment.</p>
      </div>
    );
  }

  if (prefillChoice === 'pending' && latestResult.data) {
    const completedDate = new Date(latestResult.data.completed_at).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
    return (
      <div className="field-group" style={{ maxWidth: 480 }}>
        <a className="back-link" onClick={onBack}>
          ← Back to {patient.name}
        </a>
        <h3 style={{ marginTop: 16 }}>Start from last time?</h3>
        <p style={{ fontSize: 13.5, color: 'var(--ink-soft)' }}>
          {patient.name} completed this same assessment on {completedDate}. You can start
          from those answers and just update what's changed, or start with a blank form.
        </p>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button className="btn" onClick={() => setPrefillChoice('fresh')}>
            Start fresh
          </button>
          <button className="btn btn-primary" onClick={() => setPrefillChoice('use-prior')}>
            Start from {completedDate} →
          </button>
        </div>
      </div>
    );
  }

  const initialAnswers =
    prefillChoice === 'use-prior' ? (latestResult.data?.answers ?? summary.draft_answers) : summary.draft_answers;

  // ckd_staging is deliberately special-cased here — the same architectural
  // decision the original JS app made, since its step branching depends on
  // client-side CKD-EPI 2021 computation as the user progresses, not just static
  // field metadata the generic DynamicForm reads.
  if (summary.assessment_definition_key === 'ckd_staging') {
    return (
      <CkdStagingWizard
        caseId={caseId!}
        onBack={onBack}
        patientId={patient.id}
        assignedAssessmentId={summary.assigned_assessment_id}
        initialAnswers={initialAnswers}
      />
    );
  }
  return (
    <DynamicForm
      assessment={detail.data}
      caseId={caseId!}
      onBack={onBack}
      patientId={patient.id}
      assignedAssessmentId={summary.assigned_assessment_id}
      initialAnswers={initialAnswers}
      renderResult={
        summary.assessment_definition_key === 'basic_intake'
          ? (result) => <SuggestedPathwayReview result={result} patientId={patient.id} onDone={onBack} />
          : undefined
      }
    />
  );
}

function EditCustomAssessmentLoader({
  assessmentKey,
  onBack,
  onSaved,
}: {
  assessmentKey: string;
  onBack: () => void;
  onSaved: (key: string) => void;
}) {
  const detail = useAssessmentDetail(assessmentKey);

  if (detail.isLoading) return <div className="empty-state">Loading assessment…</div>;
  if (detail.isError || !detail.data) {
    return (
      <div className="empty-state">
        <a className="back-link" onClick={onBack}>
          ← Back
        </a>
        <p>Could not load this assessment for editing.</p>
      </div>
    );
  }
  return <CustomAssessmentBuilder onBack={onBack} onSaved={onSaved} editingAssessment={detail.data} />;
}

type View =
  | { screen: 'patients' }
  | { screen: 'patient-detail'; patient: Patient }
  | { screen: 'fill-assessment'; patient: Patient; summary: PatientAssessmentSummary }
  | { screen: 'manage-custom' }
  | { screen: 'workflows' }
  | { screen: 'workflow-visualizer' }
  | { screen: 'bulk-import' }
  | { screen: 'staff-management' }
  | { screen: 'edit-custom'; assessmentKey: string; returnTo: View }
  | { screen: 'custom-history'; assessmentKey: string; returnTo: View };

function MainApp() {
  const { user, logout } = useAuth0();
  const [view, setView] = useState<View>({ screen: 'patients' });
  const checkDue = useCheckDueNotifications();

  const backToPatientDetail = (patient: Patient) => setView({ screen: 'patient-detail', patient });

  // The real, working substitute for a background scheduler — no job runner
  // exists anywhere in this app, so this is what actually makes "task due
  // soon" / "assessment overdue" notifications get created at all, for a
  // prototype/demo deployment. A genuine production deployment would want a
  // real cron hitting this same endpoint on a fixed schedule instead of
  // depending on someone having the app open at all.
  useEffect(() => {
    checkDue.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Notifications only carry a patient ID, not the full Patient object the
  // rest of this app's navigation state requires — this fetches it on demand,
  // right when someone actually clicks through, rather than needing every
  // notification to already know the full object up front.
  const openPatientFromNotification = async (patientId: string) => {
    try {
      const patient = await api.get<Patient>(`/api/patients/${patientId}`);
      setView({ screen: 'patient-detail', patient });
    } catch {
      // If the patient can't be found (e.g. deactivated and filtered out
      // somewhere, or a genuinely stale notification), fail quietly rather
      // than crash the whole app over a single notification click.
    }
  };

  return (
    <>
      <div className="masthead">
        <div>
          <img src={tallyLogo} alt="Tally" style={{ height: 28, display: 'block' }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <NotificationBell onOpenPatient={openPatientFromNotification} />
          <UserProfileMenu
            email={user?.email ?? null}
            onLogout={() => logout({ logoutParams: { returnTo: window.location.origin } })}
            onManageStaff={() => setView({ screen: 'staff-management' })}
            onManageAssessments={() => setView({ screen: 'manage-custom' })}
            onManageWorkflows={() => setView({ screen: 'workflows' })}
          />
        </div>
      </div>

      {view.screen === 'patients' && (
        <PatientsList
          onSelectPatient={(patient) => setView({ screen: 'patient-detail', patient })}
          onBulkImport={() => setView({ screen: 'bulk-import' })}
        />
      )}

      {view.screen === 'bulk-import' && (
        <BulkImportPatients onBack={() => setView({ screen: 'patients' })} />
      )}

      {view.screen === 'staff-management' && (
        <StaffManagement onBack={() => setView({ screen: 'patients' })} />
      )}

      {view.screen === 'patient-detail' && (
        <PatientDetail
          patient={view.patient}
          onBack={() => setView({ screen: 'patients' })}
          onOpenAssessment={(summary) => setView({ screen: 'fill-assessment', patient: view.patient, summary })}
          onPatientUpdated={backToPatientDetail}
        />
      )}

      {view.screen === 'fill-assessment' && (
        <FillAssessment
          patient={view.patient}
          summary={view.summary}
          onBack={() => backToPatientDetail(view.patient)}
        />
      )}

      {view.screen === 'manage-custom' && (
        <ManageCustomAssessments
          onBack={() => setView({ screen: 'patients' })}
          onEdit={(a: AssessmentDefinition) => setView({ screen: 'edit-custom', assessmentKey: a.key, returnTo: view })}
          onViewHistory={(a: AssessmentDefinition) => setView({ screen: 'custom-history', assessmentKey: a.key, returnTo: view })}
        />
      )}

      {view.screen === 'workflows' && (
        <BusinessRulesEngine onBack={() => setView({ screen: 'patients' })} onViewVisualizer={() => setView({ screen: 'workflow-visualizer' })} />
      )}

      {view.screen === 'workflow-visualizer' && (
        <WorkflowVisualizer onBack={() => setView({ screen: 'workflows' })} />
      )}

      {view.screen === 'edit-custom' && (
        <EditCustomAssessmentLoader
          assessmentKey={view.assessmentKey}
          onBack={() => setView(view.returnTo)}
          onSaved={() => setView(view.returnTo)}
        />
      )}

      {view.screen === 'custom-history' && (
        <CustomAssessmentHistory
          assessmentKey={view.assessmentKey}
          onBack={() => setView(view.returnTo)}
        />
      )}
    </>
  );
}

export function App() {
  const { isLoading, isAuthenticated, error } = useAuth0();

  if (isLoading) return <div className="app-shell empty-state">Loading…</div>;
  if (error) return <div className="app-shell empty-state">Authentication error: {error.message}</div>;

  return <div className="app-shell">{isAuthenticated ? <MainApp /> : <LoginGate />}</div>;
}
