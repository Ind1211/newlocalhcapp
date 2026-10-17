import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import type { AssessmentDefinition, ComputedResult, FieldDef } from '../types';
import { prefillFromSnapshot } from '../types';
import { FieldRenderer } from './FieldRenderer';
import { ResultCard } from './ResultCard';
import { DocumentAutoFillReview } from './DocumentAutoFillReview';
import { useAutoFillFromDocuments, useCase, usePatientDocuments, useSaveDraft, useSubmitResult } from '../hooks/useApi';

type Answers = Record<string, string | string[]>;

function isVisible(field: FieldDef, answers: Answers): boolean {
  if (!field.show_only_if) return true;
  const parentVal = answers[field.show_only_if.field];
  // Not yet answered — show it rather than hide prematurely, matching the
  // original's compileShowIf() exactly. Hiding by default (what this used to do)
  // means a question silently never appears until its parent happens to get
  // answered, which reads as broken, not conditional.
  if (parentVal === undefined) return true;
  if (field.show_only_if.equals !== undefined) return parentVal === field.show_only_if.equals;
  if (field.show_only_if.includes !== undefined) return Array.isArray(parentVal) && parentVal.includes(field.show_only_if.includes);
  return true;
}

function fieldsAreComplete(fields: FieldDef[], answers: Answers): boolean {
  return fields
    .filter((f) => isVisible(f, answers) && f.required !== false)
    .every((f) => {
      const v = answers[f.name];
      return v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0);
    });
}

function getMissingRequiredFieldNames(fields: FieldDef[], answers: Answers): Set<string> {
  const missing = new Set<string>();
  for (const f of fields) {
    if (!isVisible(f, answers) || f.required === false) continue;
    const v = answers[f.name];
    const answered = v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0);
    if (!answered) missing.add(f.name);
  }
  return missing;
}

// A choice answer (pill/select/dropdown) has a natural "I'm done" signal the
// moment it's picked — unlike text/number/textarea, where the person may still be
// mid-typing, or checkboxgroup, where they may want to pick more than one option.
// Auto-advance only makes sense for this specific class of field.
const AUTO_ADVANCE_TYPES = new Set(['pill', 'select', 'dropdown']);

// Only ever matches a genuinely unambiguous yes/no field — exactly two options,
// one of which is unmistakably "no" by value or label. A scale, a checkboxgroup,
// or a dropdown with three or more options never has an obvious negative default,
// so this deliberately returns null rather than guess at one.
function findNegativeOption(field: FieldDef): string | null {
  if (!['pill', 'select', 'dropdown'].includes(field.type)) return null;
  const options = field.options;
  if (!options || options.length !== 2) return null;
  const normalized = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  const match = normalized.find((o) => o.value.toLowerCase() === 'no' || o.label.toLowerCase() === 'no');
  return match ? match.value : null;
}

export function DynamicForm({
  assessment,
  caseId,
  onBack,
  patientId,
  assignedAssessmentId,
  initialAnswers,
  renderResult,
}: {
  assessment: AssessmentDefinition;
  caseId: string;
  onBack: () => void;
  // Only present when opened from the patient-centric flow — the old flat hub had
  // no notion of an assigned assessment to save progress against, so Save Progress
  // only appears when these are provided.
  patientId?: string;
  assignedAssessmentId?: string;
  initialAnswers?: Record<string, unknown> | null;
  // Lets a caller show something other than the plain result card after a
  // successful submission — used for basic_intake, which needs a review/confirm
  // step for its suggested pathway rather than just displaying the result.
  renderResult?: (result: ComputedResult) => ReactNode;
}) {
  const [answers, setAnswers] = useState<Answers>((initialAnswers as Answers) ?? {});
  const [stepIndex, setStepIndex] = useState(0);
  const [showValidationErrors, setShowValidationErrors] = useState(false);
  const [prefilled, setPrefilled] = useState(false);
  const [showAutoFillReview, setShowAutoFillReview] = useState(false);
  const submit = useSubmitResult(caseId, patientId ?? null);
  const saveDraft = useSaveDraft(patientId ?? null, assignedAssessmentId ?? null);
  const caseData = useCase(caseId);
  const fieldGroupRef = useRef<HTMLDivElement>(null);
  const documents = usePatientDocuments(patientId ?? null);
  const autoFill = useAutoFillFromDocuments(patientId ?? null);
  const hasExtractedDocuments = (documents.data ?? []).some((d) => d.extraction_status === 'ok');

  // Fills matching fields from the case's shared snapshot exactly once, as soon as
  // it's available — never overwrites something the user's already typed, and
  // never re-runs on every render (which would fight the user's own edits).
  useEffect(() => {
    if (caseData.data?.context && !prefilled) {
      setAnswers((prev) => prefillFromSnapshot(caseData.data!.context, prev) as Answers);
      setPrefilled(true);
    }
  }, [caseData.data?.context, prefilled]);

  // Autofocus the first focusable field whenever the step changes — a container
  // ref + querySelector, rather than threading autoFocus through every individual
  // field type in FieldRenderer, since this works identically regardless of
  // whether the first field is a text input, a pill button, or anything else.
  useEffect(() => {
    fieldGroupRef.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus();
  }, [stepIndex]);

  const steps = assessment.fields?.steps;
  const flatFields = assessment.fields?.fields;
  const isWizard = assessment.interaction === 'wizard' && steps && steps.length > 0;

  const currentFields: FieldDef[] = isWizard ? steps![stepIndex].fields : flatFields ?? [];
  const onLastStep = !isWizard || stepIndex === steps!.length - 1;
  const currentStepComplete = fieldsAreComplete(currentFields, answers);
  const missingRequiredFieldNames = getMissingRequiredFieldNames(currentFields, answers);

  // Auto-advances only when: this step has exactly one required, visible field;
  // that field is a choice type with a natural "done" signal; the step is now
  // complete after this update; and it isn't the last step — Mark Complete always
  // stays an explicit, deliberate click, even when every step before it auto-advanced.
  const set = (name: string, value: string | string[] | undefined) => {
    const nextAnswers = { ...answers, [name]: value ?? '' };
    setAnswers(nextAnswers);

    if (!isWizard || onLastStep) return;
    const visibleRequired = currentFields.filter((f) => isVisible(f, nextAnswers) && f.required !== false);
    const changedField = currentFields.find((f) => f.name === name);
    const isSoleAutoAdvanceField =
      visibleRequired.length === 1 && visibleRequired[0].name === name && changedField && AUTO_ADVANCE_TYPES.has(changedField.type);
    if (isSoleAutoAdvanceField && fieldsAreComplete(currentFields, nextAnswers)) {
      // A short delay gives a visible moment to see the selection register before
      // the screen changes — an instant jump reads as the click didn't land.
      setTimeout(() => setStepIndex((i) => i + 1), 220);
    }
  };

  const renderFieldRow = (field: FieldDef) => {
    const isMissing = showValidationErrors && missingRequiredFieldNames.has(field.name);
    return (
      <div
        className={field.show_only_if ? 'field-row field-row-reveal' : 'field-row'}
        key={field.name}
        data-field-name={field.name}
        style={isMissing ? { background: 'var(--critical-tint)', borderRadius: 8, margin: '0 -10px', padding: '10px' } : undefined}
      >
        <div className="field-label">
          {field.label}
          {field.required !== false && <span style={{ color: 'var(--critical)' }} title="Required"> *</span>}
          {field.unit ? <span style={{ color: 'var(--ink-soft)' }}> ({field.unit})</span> : null}
          {isMissing && (
            <div style={{ fontSize: 11, fontWeight: 400, color: 'var(--critical)', marginTop: 2 }}>This question is required</div>
          )}
        </div>
        <FieldRenderer field={field} value={answers[field.name]} onChange={(v) => set(field.name, v)} />
      </div>
    );
  };

  // Only counts fields that are currently visible, currently unanswered, and have
  // an unambiguous negative option — a long checklist that's already mostly
  // answered, or made of fields with no clear "no", correctly shows no button
  // rather than one that would do nothing or guess wrong.
  const remainingNegatable = currentFields.filter(
    (f) => isVisible(f, answers) && (answers[f.name] === undefined || answers[f.name] === '') && findNegativeOption(f) !== null
  );

  const handleFillRemainingNo = () => {
    const updates: Answers = { ...answers };
    for (const f of remainingNegatable) {
      const negativeValue = findNegativeOption(f);
      if (negativeValue) updates[f.name] = negativeValue;
    }
    setAnswers(updates);
  };

  // Flattened across every step (not just the current one) — a document might
  // give a confident answer for a field on a step the person hasn't reached yet,
  // and the review screen needs every field's real label regardless of which
  // step it lives on.
  const allFieldsAcrossSteps: FieldDef[] = isWizard ? steps!.flatMap((s) => s.fields) : flatFields ?? [];

  // Matches the same "answered" definition already used by remainingNegatable
  // above — a value that's neither undefined nor an empty string counts as
  // answered, regardless of which step it lives on.
  const totalQuestionCount = allFieldsAcrossSteps.length;
  const answeredQuestionCount = allFieldsAcrossSteps.filter(
    (f) => answers[f.name] !== undefined && answers[f.name] !== ''
  ).length;

  const applyAutoFillSuggestions = (accepted: Record<string, string>) => {
    setAnswers((a) => ({ ...a, ...accepted }));
    setShowAutoFillReview(false);
  };

  // Shared by both the Next/Mark Complete buttons and Enter-key handling below —
  // one function, so keyboard and mouse can never trigger subtly different logic.
  const handleAdvance = () => {
    if (!currentStepComplete) {
      setShowValidationErrors(true);
      const firstMissingName = currentFields.find((f) => missingRequiredFieldNames.has(f.name))?.name;
      if (firstMissingName) {
        const el = fieldGroupRef.current?.querySelector<HTMLElement>(`[data-field-name="${firstMissingName}"]`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }
    setShowValidationErrors(false);
    if (isWizard && !onLastStep) {
      setStepIndex((i) => i + 1);
    } else if (!submit.isPending) {
      submit.mutate({ assessment_definition_key: assessment.key, answers });
    }
  };

  // Enter advances/submits from a text or number field, matching what the visible
  // button would do — but not from a textarea, where Enter has to stay a newline,
  // and not from anything already handled by the browser's own key handling
  // (a select's own dropdown, for instance).
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (e.key === 'Enter' && target.tagName !== 'TEXTAREA') {
      e.preventDefault();
      handleAdvance();
    }
  };

  return (
    <div className="assessment-form-step" style={{ maxWidth: 820, margin: '0 auto' }}>
      <a className="back-link" onClick={onBack}>
        ← Back to assessments
      </a>
      <h2 style={{ margin: '16px 0 4px' }}>{assessment.title}</h2>
      {assessment.blurb && (
        <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0 }}>{assessment.blurb}</p>
      )}

      {hasExtractedDocuments && (
        <div style={{ marginBottom: 14 }}>
          <button
            className="btn"
            style={{ fontSize: 12.5 }}
            disabled={autoFill.isPending}
            onClick={() => autoFill.mutate(assessment.key, { onSuccess: () => setShowAutoFillReview(true) })}
          >
            {autoFill.isPending && <span className="spinner" />}
            {autoFill.isPending ? 'Reading documents…' : '✨ Suggest from documents'}
          </button>
          {autoFill.isError && (
            <div style={{ fontSize: 12, color: 'var(--critical)', marginTop: 6 }}>
              {(autoFill.error as Error).message}
            </div>
          )}
        </div>
      )}

      {isWizard && (
        <div style={{ marginBottom: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontFamily: "'Inter', sans-serif", fontSize: 12, color: 'var(--ink-soft)' }}>
            <span>Step <b style={{ color: 'var(--ink)' }}>{stepIndex + 1}</b> of {steps!.length}</span>
            <span><b style={{ color: 'var(--ink)' }}>{answeredQuestionCount}</b> of {totalQuestionCount} questions answered</span>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {steps!.map((_, i) => (
              <div
                key={i}
                style={{
                  flex: 1, height: 6, borderRadius: 3,
                  background: i <= stepIndex ? 'var(--accent)' : 'var(--line)',
                  transition: 'background-color 0.2s ease',
                }}
              />
            ))}
          </div>
          <div style={{ fontFamily: "'Inter', sans-serif", fontSize: 16, fontWeight: 700, color: 'var(--ink)', marginTop: 14 }}>
            {steps![stepIndex].title}
          </div>
        </div>
      )}

      {remainingNegatable.length > 1 && (
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <button className="btn" style={{ fontSize: 12.5 }} onClick={handleFillRemainingNo}>
            Mark remaining {remainingNegatable.length} as No
          </button>
        </div>
      )}

      <div className="field-group wizard-step-enter" key={stepIndex} ref={fieldGroupRef} onKeyDown={handleKeyDown}>{currentFields.filter((f) => isVisible(f, answers)).map(renderFieldRow)}</div>

      <div style={{ display: 'flex', gap: 8 }}>
        {isWizard && stepIndex > 0 && (
          <button className="btn" onClick={() => { setShowValidationErrors(false); setStepIndex((i) => i - 1); }}>
            ← Previous step
          </button>
        )}
        {isWizard && !onLastStep && (
          <button className="btn btn-primary" onClick={handleAdvance}>
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
            disabled={submit.isPending}
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
          <div className="result-notes">
            If this assessment doesn't have calculator logic wired up yet on the backend, this
            is the expected response — not every assessment has been ported yet.
          </div>
        </div>
      )}

      {submit.isSuccess && (renderResult ? renderResult(submit.data.result) : <ResultCard result={submit.data.result} />)}

      {showAutoFillReview && autoFill.data && (
        <DocumentAutoFillReview
          suggestions={autoFill.data.suggestions}
          allFields={allFieldsAcrossSteps}
          onApply={applyAutoFillSuggestions}
          onClose={() => setShowAutoFillReview(false)}
        />
      )}
    </div>
  );
}
