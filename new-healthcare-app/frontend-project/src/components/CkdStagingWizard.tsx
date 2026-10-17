import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { FieldRenderer } from './FieldRenderer';
import { ResultCard } from './ResultCard';
import { CarePlanDisplay } from './CarePlanDisplay';
import { useCase, useGenerateCarePlan, useSaveDraft, useSubmitResult } from '../hooks/useApi';
import { prefillFromSnapshot } from '../types';
import type { FieldDef } from '../types';

type Answers = Record<string, string | string[]>;

// Mirrors calcEgfrCkdEpi2021 in the original JS app exactly — duplicated here (not
// called over the network) so step visibility can be computed live as the user
// progresses, the same way the original wizard computes its flags() locally.
function calcEgfrCkdEpi2021(scr: number, age: number, sex: string): number {
  const kappa = sex === 'female' ? 0.7 : 0.9;
  const alpha = sex === 'female' ? -0.241 : -0.302;
  const ratio = scr / kappa;
  const minR = Math.min(ratio, 1);
  const maxR = Math.max(ratio, 1);
  let egfr = 142 * Math.pow(minR, alpha) * Math.pow(maxR, -1.2) * Math.pow(0.9938, age);
  if (sex === 'female') egfr *= 1.012;
  return Math.round(egfr * 10) / 10;
}

function getEgfrEstimate(a: Answers): number | null {
  if (a.knownEgfr === 'yes' && a.egfrValue) return parseFloat(a.egfrValue as string);
  if (a.knownEgfr === 'no' && a.scrValue && a.age && a.sex) {
    return calcEgfrCkdEpi2021(parseFloat(a.scrValue as string), parseFloat(a.age as string), a.sex as string);
  }
  return null;
}

function getACategory(a: Answers): string | null {
  if (a.knownAcr === 'yes' && a.acrValue) {
    const acr = parseFloat(a.acrValue as string);
    if (acr < 30) return 'A1';
    if (acr <= 300) return 'A2';
    return 'A3';
  }
  if (a.knownAcr === 'no' && a.dipstickProtein) {
    const map: Record<string, string> = { negative: 'A1', trace: 'A1', '1+': 'A2', '2+': 'A3', '3+': 'A3' };
    return map[a.dipstickProtein as string] ?? 'A2';
  }
  return null;
}

function computeFlags(a: Answers) {
  const rf = Array.isArray(a.riskFactors) ? a.riskFactors : [];
  const egfr = getEgfrEstimate(a);
  const aCat = getACategory(a);
  return {
    isDiabetic: rf.includes('diabetes'),
    isCvd: rf.includes('cvd'),
    isOlderHtn: rf.includes('hypertension') && !!a.age && parseFloat(a.age as string) >= 60,
    ckdSuspected: (egfr !== null && egfr < 60) || (aCat !== null && aCat !== 'A1'),
    g3bOrWorse: egfr !== null && egfr < 45,
    g4g5: egfr !== null && egfr < 30,
    egfr,
    aCat,
  };
}

interface StepDef {
  id: string;
  title: string;
  fields: FieldDef[];
}

const BASE_STEPS: StepDef[] = [
  { id: 'demographics', title: 'Patient demographics', fields: [
    { name: 'age', label: 'Patient age', type: 'number', unit: 'years', placeholder: 'e.g. 64' },
    { name: 'sex', label: 'Sex', type: 'pill', options: [{ value: 'female', label: 'Female' }, { value: 'male', label: 'Male' }] },
    { name: 'reason', label: 'Reason for assessment', type: 'select', options: [
      { value: 'screening', label: 'Routine risk-based screening' }, { value: 'incidental', label: 'Incidental abnormal labs' },
      { value: 'aki_ckd', label: 'Suspected AKI-on-CKD' }, { value: 'referral', label: 'Referral for CKD management' }, { value: 'followup', label: 'Follow-up of known CKD' },
    ] },
  ] },
  { id: 'risk_factors', title: 'Risk factors', fields: [
    { name: 'riskFactors', label: 'Select all known risk factors', type: 'checkboxgroup', options: [
      { value: 'diabetes', label: 'Diabetes' }, { value: 'hypertension', label: 'Hypertension' }, { value: 'cvd', label: 'Cardiovascular disease' },
      { value: 'familyHistory', label: 'Family history of kidney failure' }, { value: 'akiHistory', label: 'Prior episode of AKI' },
      { value: 'stonesRecurrentUTI', label: 'Recurrent UTI / kidney stones' }, { value: 'autoimmune', label: 'Autoimmune disease (e.g. lupus)' },
      { value: 'nephrotoxicMeds', label: 'Chronic nephrotoxic medication use' }, { value: 'obesity', label: 'Obesity' }, { value: 'smoking', label: 'Current smoker' },
      { value: 'none', label: 'No known risk factors' },
    ] },
  ] },
  { id: 'labs_egfr', title: 'Kidney function — eGFR', fields: [
    { name: 'knownEgfr', label: 'Do you have a recent eGFR result?', type: 'pill', options: [{ value: 'yes', label: 'Yes, I have a value' }, { value: 'no', label: 'No, calculate from creatinine' }] },
    { name: 'egfrValue', label: 'Reported eGFR', type: 'number', unit: 'mL/min/1.73m²', placeholder: 'e.g. 52' },
    { name: 'scrValue', label: 'Serum creatinine', type: 'number', unit: 'mg/dL', placeholder: 'e.g. 1.4' },
  ] },
  { id: 'labs_acr', title: 'Albuminuria — urine ACR', fields: [
    { name: 'knownAcr', label: 'Recent urine ACR available?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No, use dipstick instead' }] },
    { name: 'acrValue', label: 'Urine ACR', type: 'number', unit: 'mg/g', placeholder: 'e.g. 45' },
    { name: 'dipstickProtein', label: 'Urine dipstick protein (surrogate)', type: 'select', options: [
      { value: 'negative', label: 'Negative' }, { value: 'trace', label: 'Trace' }, { value: '1+', label: '1+' }, { value: '2+', label: '2+' }, { value: '3+', label: '3+' },
    ] },
  ] },
  { id: 'vitals', title: 'Vitals & blood pressure', fields: [
    { name: 'sbp', label: 'Systolic BP', type: 'number', unit: 'mmHg' },
    { name: 'dbp', label: 'Diastolic BP', type: 'number', unit: 'mmHg' },
    { name: 'antihtnCount', label: 'Antihypertensive medication classes used', type: 'number', placeholder: '0–6' },
  ] },
];

const DIABETES_STEP: StepDef = { id: 'diabetes_detail', title: 'Diabetes detail', fields: [
  { name: 'hba1c', label: 'Most recent HbA1c', type: 'number', unit: '%', placeholder: 'e.g. 7.8' },
  { name: 'sglt2i', label: 'Currently on an SGLT2 inhibitor?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
] };
const CV_STEP: StepDef = { id: 'cv_detail', title: 'Cardiovascular detail', fields: [
  { name: 'statin', label: 'Currently on a statin?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
  { name: 'priorMiStroke', label: 'Prior MI or stroke?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
] };
const SYMPTOMS_STEP: StepDef = { id: 'symptoms', title: 'Symptoms', fields: [
  { name: 'symptoms', label: 'Select any reported symptoms', type: 'checkboxgroup', options: [
    { value: 'fatigue', label: 'Fatigue' }, { value: 'pruritus', label: 'Itching (pruritus)' }, { value: 'nauseaAppetite', label: 'Nausea / poor appetite' },
    { value: 'nocturia', label: 'Nocturia' }, { value: 'foamyUrine', label: 'Foamy urine' }, { value: 'none', label: 'No symptoms reported' },
  ] },
] };
const MED_SAFETY_STEP: StepDef = { id: 'medication_safety', title: 'Medication safety', fields: [
  { name: 'nsaidUse', label: 'Regular NSAID use?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
  { name: 'recentContrast', label: 'Recent IV contrast exposure?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
  { name: 'metforminUse', label: 'On metformin?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
] };
const COMPLICATIONS_STEP: StepDef = { id: 'labs_complications', title: 'Complication labs', fields: [
  { name: 'hemoglobin', label: 'Hemoglobin', type: 'number', unit: 'g/dL', placeholder: 'e.g. 11.2' },
  { name: 'potassium', label: 'Potassium', type: 'number', unit: 'mmol/L', placeholder: 'e.g. 4.8' },
  { name: 'bicarbonate', label: 'Bicarbonate', type: 'number', unit: 'mmol/L', placeholder: 'e.g. 22' },
] };
const ADVANCED_CARE_STEP: StepDef = { id: 'advanced_care', title: 'Advanced CKD planning', fields: [
  { name: 'activeReferral', label: 'Nephrology referral currently active?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
  { name: 'transplantDiscussed', label: 'Transplant candidacy discussed?', type: 'pill', options: [{ value: 'yes', label: 'Yes' }, { value: 'no', label: 'No' }] },
] };

function buildVisibleSteps(answers: Answers): StepDef[] {
  const f = computeFlags(answers);
  const steps = [...BASE_STEPS];
  if (f.isDiabetic) steps.push(DIABETES_STEP);
  if (f.isCvd || f.isOlderHtn) steps.push(CV_STEP);
  if (f.ckdSuspected) steps.push(SYMPTOMS_STEP);
  steps.push(MED_SAFETY_STEP);
  if (f.g3bOrWorse) steps.push(COMPLICATIONS_STEP);
  if (f.g4g5) steps.push(ADVANCED_CARE_STEP);
  return steps;
}

function fieldsComplete(fields: FieldDef[], answers: Answers): boolean {
  return fields.every((f) => {
    if (['egfrValue', 'scrValue', 'acrValue', 'dipstickProtein'].includes(f.name)) return true;
    const v = answers[f.name];
    return v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0);
  });
}

// Extracted from the render filter so auto-advance below checks the exact same
// visibility rules as what's actually on screen — this wizard's field visibility
// is hand-coded per step id, not a reusable show_only_if, so keeping both in sync
// by construction (one function, two call sites) matters here specifically.
function visibleFieldsForStep(step: StepDef, answers: Answers): FieldDef[] {
  return step.fields.filter((field) => {
    if (step.id === 'labs_egfr' && field.name === 'egfrValue') return answers.knownEgfr === 'yes';
    if (step.id === 'labs_egfr' && field.name === 'scrValue') return answers.knownEgfr === 'no';
    if (step.id === 'labs_acr' && field.name === 'acrValue') return answers.knownAcr === 'yes';
    if (step.id === 'labs_acr' && field.name === 'dipstickProtein') return answers.knownAcr === 'no';
    return true;
  });
}

// Extracted so auto-advance and the rendered Next-step button check identical
// completion rules — this step-completion logic has hand-coded special cases
// (labs_egfr / labs_acr use a different rule than "all visible fields answered"),
// so duplicating it inline in two places would be a real place for the two to
// silently drift apart.
function isStepComplete(step: StepDef, answers: Answers): boolean {
  if (step.id === 'labs_egfr') {
    return !!answers.knownEgfr && (
      (answers.knownEgfr === 'yes' && !!answers.egfrValue) ||
      (answers.knownEgfr === 'no' && !!answers.scrValue && !!answers.age && !!answers.sex)
    );
  }
  if (step.id === 'labs_acr') {
    return !!answers.knownAcr && (
      (answers.knownAcr === 'yes' && !!answers.acrValue) ||
      (answers.knownAcr === 'no' && !!answers.dipstickProtein)
    );
  }
  return fieldsComplete(step.fields, answers);
}

const AUTO_ADVANCE_TYPES = new Set(['pill', 'select', 'dropdown']);

// Same rule as DynamicForm's version: only an unambiguous two-option yes/no field
// qualifies — never guesses at a scale, multi-select, or a dropdown with more than
// two choices.
function findNegativeOption(field: FieldDef): string | null {
  if (!['pill', 'select', 'dropdown'].includes(field.type)) return null;
  const options = field.options;
  if (!options || options.length !== 2) return null;
  const normalized = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  const match = normalized.find((o) => o.value.toLowerCase() === 'no' || o.label.toLowerCase() === 'no');
  return match ? match.value : null;
}

export function CkdStagingWizard({
  caseId,
  onBack,
  patientId,
  assignedAssessmentId,
  initialAnswers,
}: {
  caseId: string;
  onBack: () => void;
  patientId?: string;
  assignedAssessmentId?: string;
  initialAnswers?: Record<string, unknown> | null;
}) {
  const [answers, setAnswers] = useState<Answers>((initialAnswers as Answers) ?? {});
  const [stepIndex, setStepIndex] = useState(0);
  const [prefilled, setPrefilled] = useState(false);
  const submit = useSubmitResult(caseId, patientId ?? null);
  const saveDraft = useSaveDraft(patientId ?? null, assignedAssessmentId ?? null);
  const carePlan = useGenerateCarePlan(caseId);
  const caseData = useCase(caseId);
  const fieldGroupRef = useRef<HTMLDivElement>(null);

  // Mirrors prefillCkdFromSnapshot() exactly: the general fields (age, sex, etc.)
  // prefill directly, but eGFR/creatinine/ACR need the CKD wizard's own field names
  // (egfrValue/scrValue/knownEgfr/acrValue/knownAcr), not the plain snapshot keys —
  // this is the same field-naming translation the original app had to do too.
  useEffect(() => {
    const context = caseData.data?.context;
    if (context && !prefilled) {
      setAnswers((prev) => {
        let next = prefillFromSnapshot(context, prev) as Answers;
        if (context.egfr && !next.egfrValue) {
          next = { ...next, knownEgfr: 'yes', egfrValue: context.egfr };
        } else if (context.creatinine && !next.scrValue) {
          next = { ...next, knownEgfr: 'no', scrValue: context.creatinine };
        }
        if (context.acr && !next.acrValue) {
          next = { ...next, knownAcr: 'yes', acrValue: context.acr };
        }
        return next;
      });
      setPrefilled(true);
    }
  }, [caseData.data?.context, prefilled]);

  // Autofocus the first focusable field whenever the step changes.
  useEffect(() => {
    fieldGroupRef.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus();
  }, [stepIndex]);

  const steps = buildVisibleSteps(answers);
  const clampedIndex = Math.min(stepIndex, steps.length - 1);
  const currentStep = steps[clampedIndex];
  const onLastStep = clampedIndex === steps.length - 1;
  const stepComplete = isStepComplete(currentStep, answers);

  const remainingNegatable = visibleFieldsForStep(currentStep, answers).filter(
    (f) => (answers[f.name] === undefined || answers[f.name] === '') && findNegativeOption(f) !== null
  );

  const handleFillRemainingNo = () => {
    const updates: Answers = { ...answers };
    for (const f of remainingNegatable) {
      const negativeValue = findNegativeOption(f);
      if (negativeValue) updates[f.name] = negativeValue;
    }
    setAnswers(updates);
  };

  // Same rule as DynamicForm's auto-advance: only fires when this step has
  // exactly one visible, auto-advance-eligible field, that field is the one that
  // just changed, and the step's own (possibly special-cased) completion rule is
  // now satisfied. Never fires on the last step — Mark Complete / Calculate always
  // stays an explicit click.
  const set = (name: string, value: string | string[] | undefined) => {
    const nextAnswers = { ...answers, [name]: value ?? '' };
    setAnswers(nextAnswers);

    if (onLastStep) return;
    const visible = visibleFieldsForStep(currentStep, nextAnswers);
    const changedField = visible.find((f) => f.name === name);
    const isSoleAutoAdvanceField = visible.length === 1 && changedField && AUTO_ADVANCE_TYPES.has(changedField.type);
    if (isSoleAutoAdvanceField && isStepComplete(currentStep, nextAnswers)) {
      setTimeout(() => setStepIndex((i) => i + 1), 220);
    }
  };

  const f = computeFlags(answers);

  // Shared by the Next/Mark Complete buttons and Enter-key handling below.
  const handleAdvance = () => {
    if (!stepComplete) return;
    if (!onLastStep) {
      setStepIndex(clampedIndex + 1);
    } else if (!submit.isPending) {
      submit.mutate({ assessment_definition_key: 'ckd_staging', answers });
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (e.key === 'Enter' && target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      handleAdvance();
    }
  };

  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back to assessments
      </a>
      <h2 style={{ margin: '16px 0 4px' }}>CKD Staging (KDIGO)</h2>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0 }}>
        Adaptive intake — steps branch based on your answers, computing CKD-EPI 2021 staging.
      </p>

      <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 11.5, color: 'var(--ink-soft)', marginBottom: 8 }}>
        STEP {clampedIndex + 1} OF {steps.length} — {currentStep.title.toUpperCase()}
      </div>

      {remainingNegatable.length > 1 && (
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <button className="btn" style={{ fontSize: 12.5 }} onClick={handleFillRemainingNo}>
            Mark remaining {remainingNegatable.length} as No
          </button>
        </div>
      )}

      <div className="field-group wizard-step-enter" key={clampedIndex} ref={fieldGroupRef} onKeyDown={handleKeyDown}>
        {visibleFieldsForStep(currentStep, answers)
          .map((field) => (
            <div className="field-row" key={field.name}>
              <div className="field-label">
                {field.label}
                {field.unit ? <span style={{ color: 'var(--ink-soft)' }}> ({field.unit})</span> : null}
              </div>
              <FieldRenderer field={field} value={answers[field.name]} onChange={(v) => set(field.name, v)} />
            </div>
          ))}
      </div>

      {f.egfr !== null && (
        <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginBottom: 12 }}>
          Live estimate: eGFR {f.egfr} mL/min/1.73m² {f.aCat ? `· ACR category ${f.aCat}` : ''}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        {clampedIndex > 0 && (
          <button className="btn" onClick={() => setStepIndex(clampedIndex - 1)}>
            ← Previous step
          </button>
        )}
        {!onLastStep && (
          <button className="btn btn-primary" disabled={!stepComplete} onClick={handleAdvance}>
            Next step →
          </button>
        )}
        {assignedAssessmentId && (
          <button
            className="btn"
            disabled={saveDraft.isPending}
            onClick={() => saveDraft.mutate(answers, { onSuccess: onBack })}
          >
            {saveDraft.isPending ? 'Saving…' : 'Save Progress'}
          </button>
        )}
        {onLastStep && (
          <button
            className="btn btn-primary"
            disabled={!stepComplete || submit.isPending}
            onClick={handleAdvance}
          >
            {submit.isPending ? 'Calculating…' : 'Mark Complete'}
          </button>
        )}
      </div>

      {saveDraft.isError && (
        <div className="result-card critical" style={{ marginTop: 16 }}>
          <div className="result-headline">Could not save progress: {(saveDraft.error as Error).message}</div>
        </div>
      )}

      {submit.isError && (
        <div className="result-card critical" style={{ marginTop: 16 }}>
          <div className="result-headline">{(submit.error as Error).message}</div>
        </div>
      )}

      {submit.isSuccess && (
        <>
          <ResultCard result={submit.data.result} />

          <div style={{ marginTop: 16 }}>
            <button
              className="btn btn-primary"
              disabled={carePlan.isPending}
              onClick={() => carePlan.mutate(answers)}
            >
              {carePlan.isPending ? 'Generating care plan…' : '✨ Generate AI care plan'}
            </button>
            <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 6 }}>
              Sends the structured answers above (no name or identifiers) to Claude for a
              narrative summary and recommendations. Review everything before acting on it.
            </p>
          </div>

          {carePlan.isError && (
            <div className="result-card critical" style={{ marginTop: 12 }}>
              <div className="result-headline">{(carePlan.error as Error).message}</div>
            </div>
          )}

          {carePlan.isSuccess && <CarePlanDisplay carePlan={carePlan.data.carePlan} />}
        </>
      )}
    </div>
  );
}
