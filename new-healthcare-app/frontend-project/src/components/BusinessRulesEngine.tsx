import { useState } from 'react';
import {
  useBusinessRules, useCreateBusinessRule, useDeleteBusinessRule, useEditBusinessRule, useEnableBusinessRule,
  useDisableBusinessRule, useFireEventManually, usePatients, useTestRuleInIsolation,
} from '../hooks/useApi';

const EXAMPLE_DSL = `RULE "Critical assessment result triggers urgent risk escalation"
WHEN assessment.completed
IF event.severity == "critical"
THEN
  ESCALATE_RISK "critical"
  CREATE_TASK "Urgent review of critical assessment result" ASSIGN "Nurse" DUE "24h"
END`;

function jsonTextarea(value: string, onChange: (v: string) => void, placeholder: string) {
  return (
    <textarea
      className="field-input" style={{ width: '100%', maxWidth: 'none', minHeight: 70, fontSize: 12 }}
      value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} spellCheck={false}
    />
  );
}

// =============================================================================
// Form builder — an alternative to writing DSL by hand, ported from the
// reference's own syncFormToDsl. Deliberately AND-only (no OR/NOT/parentheses)
// — the same simplification the reference makes; anything more complex still
// needs the DSL editor directly.
// =============================================================================
interface FormCondition { left: string; op: string; right: string }
interface FormAction { type: string; [key: string]: string }

const ACTION_FIELD_DEFS: Record<string, { key: string; ph: string }[]> = {
  CREATE_TASK: [{ key: 'label', ph: 'Task label' }, { key: 'assignee', ph: 'Assignee' }, { key: 'due', ph: 'Due (e.g. 24h)' }],
  UPDATE_STATUS: [{ key: 'value', ph: 'New status value' }],
  ADD_GOAL: [{ key: 'goal', ph: 'Goal title' }],
  SEND_NOTIFICATION: [{ key: 'template', ph: 'Notification template' }, { key: 'to', ph: 'Recipient' }],
  TRANSITION: [{ key: 'workflow', ph: 'Workflow key (e.g. care_plan)' }, { key: 'target', ph: 'Target state' }],
  ESCALATE_RISK: [{ key: 'level', ph: 'Risk level' }],
};
const ACTION_DEFAULTS: Record<string, FormAction> = {
  CREATE_TASK: { type: 'CREATE_TASK', label: '', assignee: '', due: '' },
  UPDATE_STATUS: { type: 'UPDATE_STATUS', value: '' },
  ADD_GOAL: { type: 'ADD_GOAL', goal: '' },
  SEND_NOTIFICATION: { type: 'SEND_NOTIFICATION', template: '', to: '' },
  TRANSITION: { type: 'TRANSITION', workflow: '', target: '' },
  ESCALATE_RISK: { type: 'ESCALATE_RISK', level: '' },
};

function quoteForDsl(v: string): string {
  v = (v || '').trim();
  if (v === 'true' || v === 'false') return v;
  if (v !== '' && !isNaN(Number(v))) return v;
  return `"${v.replace(/"/g, '')}"`;
}

function actionRowToDslLine(a: FormAction): string {
  const esc = (s: string) => (s || '').replace(/"/g, '');
  switch (a.type) {
    case 'CREATE_TASK': return `CREATE_TASK "${esc(a.label)}" ASSIGN "${esc(a.assignee)}" DUE "${esc(a.due)}"`;
    case 'UPDATE_STATUS': return `UPDATE_STATUS "${esc(a.value)}"`;
    case 'ADD_GOAL': return `ADD_GOAL "${esc(a.goal)}"`;
    case 'SEND_NOTIFICATION': return `SEND_NOTIFICATION "${esc(a.template)}" TO "${esc(a.to)}"`;
    case 'TRANSITION': return `TRANSITION ${(a.workflow || 'workflow').trim()} TO "${esc(a.target)}"`;
    case 'ESCALATE_RISK': return `ESCALATE_RISK "${esc(a.level)}"`;
    default: return '';
  }
}

function generateDslFromForm(name: string, trigger: string, conditions: FormCondition[], actions: FormAction[]): string {
  const finalName = name.trim() || 'Untitled rule';
  const finalTrigger = trigger.trim() || 'trigger.event';
  const condLines = conditions.filter((c) => c.left.trim()).map((c) => `${c.left.trim()} ${c.op} ${quoteForDsl(c.right)}`);
  const condStr = condLines.length ? condLines.join('\n  AND ') : '1 == 1';
  const actionLines = actions.map(actionRowToDslLine).filter(Boolean);
  return `RULE "${finalName}"\nWHEN ${finalTrigger}\nIF ${condStr}\nTHEN\n${actionLines.map((l) => '  ' + l).join('\n')}\nEND`;
}

export function BusinessRulesEngine({ onBack, onViewVisualizer }: { onBack: () => void; onViewVisualizer: () => void }) {
  const rules = useBusinessRules();
  const createRule = useCreateBusinessRule();
  const editRule = useEditBusinessRule();
  const enableRule = useEnableBusinessRule();
  const disableRule = useDisableBusinessRule();
  const deleteRule = useDeleteBusinessRule();
  const testRule = useTestRuleInIsolation();
  const fireEvent = useFireEventManually();
  const patients = usePatients('', 1, false, 'name', 'asc');

  const [dslText, setDslText] = useState(EXAMPLE_DSL);
  const [governance, setGovernance] = useState('operational');
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [expandedRuleId, setExpandedRuleId] = useState<string | null>(null);
  const [tenantJson, setTenantJson] = useState('{}');
  const [eventJson, setEventJson] = useState('{ "severity": "critical" }');
  const [stateJson, setStateJson] = useState('{}');
  const [testPatientId, setTestPatientId] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);

  const [authorMode, setAuthorMode] = useState<'dsl' | 'form'>('dsl');
  const [formName, setFormName] = useState('');
  const [formTrigger, setFormTrigger] = useState('');
  const [formConditions, setFormConditions] = useState<FormCondition[]>([{ left: '', op: '==', right: '' }]);
  const [formActions, setFormActions] = useState<FormAction[]>([{ ...ACTION_DEFAULTS.CREATE_TASK }]);

  // The single DSL string actually submitted to test/save, regardless of
  // which mode authored it — form mode never edits dslText directly, it
  // generates this on the fly, matching the reference's "test and save work
  // identically regardless of authoring mode" behavior.
  const effectiveDslText = authorMode === 'form'
    ? generateDslFromForm(formName, formTrigger, formConditions, formActions)
    : dslText;

  const updateFormCondition = (i: number, key: keyof FormCondition, value: string) => {
    setFormConditions((prev) => prev.map((c, idx) => (idx === i ? { ...c, [key]: value } : c)));
  };
  const addFormCondition = () => setFormConditions((prev) => [...prev, { left: '', op: '==', right: '' }]);
  const removeFormCondition = (i: number) => setFormConditions((prev) => {
    const next = prev.filter((_, idx) => idx !== i);
    return next.length ? next : [{ left: '', op: '==', right: '' }];
  });

  const updateFormActionType = (i: number, type: string) => {
    setFormActions((prev) => prev.map((a, idx) => (idx === i ? { ...ACTION_DEFAULTS[type] } : a)));
  };
  const updateFormAction = (i: number, key: string, value: string) => {
    setFormActions((prev) => prev.map((a, idx) => (idx === i ? { ...a, [key]: value } : a)));
  };
  const addFormAction = () => setFormActions((prev) => [...prev, { ...ACTION_DEFAULTS.CREATE_TASK }]);
  const removeFormAction = (i: number) => setFormActions((prev) => {
    const next = prev.filter((_, idx) => idx !== i);
    return next.length ? next : [{ ...ACTION_DEFAULTS.CREATE_TASK }];
  });

  const [fireTrigger, setFireTrigger] = useState('assessment.completed');
  const [fireEventJson, setFireEventJson] = useState('{ "severity": "critical" }');
  const [firePatientId, setFirePatientId] = useState('');
  const [fireDryRun, setFireDryRun] = useState(true);

  const parseOrEmpty = (text: string): object => {
    try { return JSON.parse(text || '{}'); } catch { return {}; }
  };

  const handleTest = () => {
    testRule.mutate({
      dsl_text: effectiveDslText,
      tenant: parseOrEmpty(tenantJson),
      event: parseOrEmpty(eventJson),
      state: parseOrEmpty(stateJson),
      patient_id: testPatientId || undefined,
    });
  };

  const handleSave = () => {
    setSaveError(null);
    if (editingRuleId) {
      editRule.mutate({ ruleId: editingRuleId, dsl_text: effectiveDslText, governance }, {
        onSuccess: () => setEditingRuleId(null),
        onError: (err) => setSaveError((err as Error).message),
      });
    } else {
      createRule.mutate({ dsl_text: effectiveDslText, governance }, {
        onError: (err) => setSaveError((err as Error).message),
      });
    }
  };

  const handleEditClick = (rule: { id: string; dsl_text: string; governance: string }) => {
    setAuthorMode('dsl'); // always edit via raw DSL — round-tripping through the AND-only form builder could silently lose OR/NOT/parentheses logic
    setDslText(rule.dsl_text);
    setGovernance(rule.governance);
    setEditingRuleId(rule.id);
    setSaveError(null);
  };

  const handleCancelEdit = () => {
    setEditingRuleId(null);
    setDslText(EXAMPLE_DSL);
    setGovernance('operational');
    setSaveError(null);
  };

  const handleEnable = (ruleId: string, isClinical: boolean) => {
    if (isClinical) {
      const confirmed = window.confirm(
        'This is a clinical-tier rule — it affects thresholds, risk scoring, or care plan stage transitions.\n\nConfirm clinical governance sign-off to activate it?'
      );
      if (!confirmed) return;
      enableRule.mutate({ ruleId, confirmed: true });
    } else {
      enableRule.mutate({ ruleId, confirmed: false });
    }
  };

  const handleFireEvent = () => {
    if (!firePatientId) return;
    fireEvent.mutate({
      trigger: fireTrigger,
      event: parseOrEmpty(fireEventJson),
      patient_id: firePatientId,
      dry_run: fireDryRun,
    });
  };

  return (
    <div>
      <a className="back-link" onClick={onBack}>← Back to My Patients</a>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        <h1 style={{ marginTop: 16 }}>Business Rules Engine</h1>
        <button className="btn" style={{ marginTop: 16 }} onClick={onViewVisualizer}>View all workflows →</button>
      </div>
      <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginBottom: 24 }}>
        Author automation rules that react to real events in this app — a patient being imported, an
        assessment completing, a care plan review coming due. Saving a rule stores it as a draft; it
        only ever runs once you explicitly enable it, and clinical-tier rules need a sign-off first.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'start' }}>
        {/* LEFT: authoring */}
        <div>
          <div className="field-group">
            <div className="section-label">Author &amp; test in isolation</div>

            <div style={{ display: 'flex', gap: 6, background: 'var(--canvas)', borderRadius: 8, padding: 4, marginBottom: 14 }}>
              <button
                style={{
                  flex: 1, textAlign: 'center', padding: '8px 0', borderRadius: 6, border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--font-display)', fontSize: 12.5, fontWeight: 600,
                  background: authorMode === 'dsl' ? 'var(--surface)' : 'none',
                  color: authorMode === 'dsl' ? 'var(--ink)' : 'var(--ink-soft)',
                  boxShadow: authorMode === 'dsl' ? 'var(--shadow-sm)' : 'none',
                }}
                onClick={() => setAuthorMode('dsl')}
              >
                DSL editor
              </button>
              <button
                style={{
                  flex: 1, textAlign: 'center', padding: '8px 0', borderRadius: 6, border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--font-display)', fontSize: 12.5, fontWeight: 600,
                  background: authorMode === 'form' ? 'var(--surface)' : 'none',
                  color: authorMode === 'form' ? 'var(--ink)' : 'var(--ink-soft)',
                  boxShadow: authorMode === 'form' ? 'var(--shadow-sm)' : 'none',
                }}
                onClick={() => setAuthorMode('form')}
              >
                Form builder
              </button>
            </div>

            {authorMode === 'form' ? (
              <>
                <div className="field-row">
                  <div className="field-label">Rule name</div>
                  <input className="field-input" style={{ maxWidth: 'none' }} placeholder="e.g. Escalate high BP readings" value={formName} onChange={(e) => setFormName(e.target.value)} />
                </div>
                <div className="field-row">
                  <div className="field-label">Trigger event</div>
                  <input className="field-input" style={{ maxWidth: 'none' }} placeholder="e.g. lab.result.received" value={formTrigger} onChange={(e) => setFormTrigger(e.target.value)} />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 14 }}>
                  <div className="section-label" style={{ marginBottom: 6 }}>Conditions</div>
                  <span style={{ fontSize: 11, color: 'var(--ink-soft)' }}>— all must be true (AND)</span>
                </div>
                {formConditions.map((c, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                    <input
                      className="field-input" style={{ flex: 1, maxWidth: 'none', fontSize: 12.5 }}
                      placeholder="event.field or state.workflow.current" value={c.left}
                      onChange={(e) => updateFormCondition(i, 'left', e.target.value)}
                    />
                    <select className="field-input" style={{ maxWidth: 80, flexShrink: 0 }} value={c.op} onChange={(e) => updateFormCondition(i, 'op', e.target.value)}>
                      {['==', '!=', '<', '>', '<=', '>='].map((op) => <option key={op} value={op}>{op}</option>)}
                    </select>
                    <input
                      className="field-input" style={{ flex: 1, maxWidth: 'none', fontSize: 12.5 }}
                      placeholder="value" value={c.right} onChange={(e) => updateFormCondition(i, 'right', e.target.value)}
                    />
                    {formConditions.length > 1 && (
                      <button className="btn" style={{ flexShrink: 0, padding: '0 10px' }} onClick={() => removeFormCondition(i)} aria-label="Remove condition">✕</button>
                    )}
                  </div>
                ))}
                <button className="btn" style={{ fontSize: 12 }} onClick={addFormCondition}>+ Add condition</button>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 16 }}>
                  <div className="section-label" style={{ marginBottom: 6 }}>Actions</div>
                  <span style={{ fontSize: 11, color: 'var(--ink-soft)' }}>— run in order</span>
                </div>
                {formActions.map((a, i) => (
                  <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                    <select className="field-input" style={{ maxWidth: 150, flexShrink: 0 }} value={a.type} onChange={(e) => updateFormActionType(i, e.target.value)}>
                      {Object.keys(ACTION_FIELD_DEFS).map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    {ACTION_FIELD_DEFS[a.type].map((f) => (
                      <input
                        key={f.key} className="field-input" style={{ flex: 1, minWidth: 100, maxWidth: 'none', fontSize: 12.5 }}
                        placeholder={f.ph} value={a[f.key] || ''} onChange={(e) => updateFormAction(i, f.key, e.target.value)}
                      />
                    ))}
                    {formActions.length > 1 && (
                      <button className="btn" style={{ flexShrink: 0, padding: '0 10px' }} onClick={() => removeFormAction(i)} aria-label="Remove action">✕</button>
                    )}
                  </div>
                ))}
                <button className="btn" style={{ fontSize: 12 }} onClick={addFormAction}>+ Add action</button>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 16 }}>
                  <div className="section-label" style={{ marginBottom: 6 }}>Generated DSL</div>
                  <span style={{ fontSize: 11, color: 'var(--ink-soft)' }}>— auto-updates from the form, read-only here</span>
                </div>
                <textarea
                  className="field-input" readOnly style={{ width: '100%', maxWidth: 'none', minHeight: 160, fontSize: 13, lineHeight: 1.6, fontFamily: "'Inter', sans-serif", color: 'var(--ink-soft)' }}
                  value={effectiveDslText}
                />
              </>
            ) : (
              <textarea
                className="field-input" style={{ width: '100%', maxWidth: 'none', minHeight: 200, fontSize: 13, lineHeight: 1.6 }}
                value={dslText} onChange={(e) => setDslText(e.target.value)} spellCheck={false}
              />
            )}

            <div className="field-row" style={{ marginTop: 14 }}>
              <div className="field-label">Tenant config (JSON)</div>
              {jsonTextarea(tenantJson, setTenantJson, '{ "egfr_threshold": 30 }')}
            </div>
            <div className="field-row">
              <div className="field-label">Event payload (JSON)</div>
              {jsonTextarea(eventJson, setEventJson, '{ "severity": "critical" }')}
            </div>
            <div className="field-row">
              <div className="field-label">Workflow state (JSON)</div>
              {jsonTextarea(stateJson, setStateJson, '{ "escalation": { "current": "Normal" } }')}
            </div>
            <div className="field-row">
              <div className="field-label">Test against patient</div>
              <select className="field-input" style={{ maxWidth: 'none' }} value={testPatientId} onChange={(e) => setTestPatientId(e.target.value)}>
                <option value="">(describe actions only — no real patient)</option>
                {patients.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>

            <button className="btn btn-primary" style={{ width: '100%', marginTop: 14 }} disabled={testRule.isPending} onClick={handleTest}>
              {testRule.isPending ? 'Testing…' : 'Test this rule in isolation'}
            </button>

            {testRule.data && (
              <div className={`result-card ${testRule.data.condition_result ? 'good' : 'warning'}`} style={{ marginTop: 12 }}>
                <div className="result-headline" style={{ fontSize: 13 }}>
                  Condition evaluated to <b>{String(testRule.data.condition_result)}</b>
                </div>
                {testRule.data.actions.length > 0 && (
                  <ul style={{ fontSize: 12.5, margin: '8px 0 0', paddingLeft: 18 }}>
                    {testRule.data.actions.map((a, i) => <li key={i}>{a.summary}</li>)}
                  </ul>
                )}
              </div>
            )}
            {testRule.isError && (
              <div className="result-card critical" style={{ marginTop: 12 }}>
                <div className="result-headline" style={{ fontSize: 12.5 }}>{(testRule.error as Error).message}</div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginTop: 14 }}>
              <div style={{ flex: 1 }}>
                <div className="field-label" style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--ink-soft)', textTransform: 'uppercase', letterSpacing: '.03em', marginBottom: 6 }}>
                  Governance tier
                </div>
                <select className="field-input" style={{ width: '100%', maxWidth: 'none' }} value={governance} onChange={(e) => setGovernance(e.target.value)}>
                  <option value="operational">Operational (routing, notifications)</option>
                  <option value="clinical">Clinical (thresholds, scoring)</option>
                </select>
              </div>
              <button className="btn btn-primary" style={{ flex: 1 }} disabled={createRule.isPending || editRule.isPending} onClick={handleSave}>
                {editingRuleId
                  ? (editRule.isPending ? 'Saving changes…' : 'Save changes')
                  : (createRule.isPending ? 'Saving…' : 'Save to rule library')}
              </button>
              {editingRuleId && (
                <button className="btn" style={{ flex: 1 }} onClick={handleCancelEdit}>Cancel edit</button>
              )}
            </div>
            {editingRuleId && (
              <div className="tag tag-accent" style={{ marginTop: 10, display: 'inline-block' }}>
                Editing an existing rule — saving will update it in place
              </div>
            )}
            {saveError && (
              <div className="result-card critical" style={{ marginTop: 12 }}>
                <div className="result-headline" style={{ fontSize: 12.5 }}>{saveError}</div>
              </div>
            )}
          </div>

          <div className="field-group">
            <div className="section-label">Fire an event</div>
            <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 12 }}>
              Evaluates every enabled saved rule listening for this trigger against a real patient —
              the manual equivalent of what a real event in the app does automatically.
            </p>
            <div className="field-row">
              <div className="field-label">Trigger</div>
              <input className="field-input" style={{ maxWidth: 'none' }} value={fireTrigger} onChange={(e) => setFireTrigger(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">Event payload</div>
              {jsonTextarea(fireEventJson, setFireEventJson, '{ "severity": "critical" }')}
            </div>
            <div className="field-row">
              <div className="field-label">Patient</div>
              <select className="field-input" style={{ maxWidth: 'none' }} value={firePatientId} onChange={(e) => setFirePatientId(e.target.value)}>
                <option value="">Select a patient…</option>
                {patients.data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, marginTop: 8, cursor: 'pointer' }}>
              <input type="checkbox" checked={fireDryRun} onChange={(e) => setFireDryRun(e.target.checked)} />
              Dry run (describe what would happen, don't actually change this patient's record)
            </label>
            <button className="btn btn-primary" style={{ width: '100%', marginTop: 12 }} disabled={!firePatientId || fireEvent.isPending} onClick={handleFireEvent}>
              {fireEvent.isPending ? 'Firing…' : 'Fire event against saved rules'}
            </button>
            {fireEvent.data && (
              <div className={`result-card ${fireEvent.data.rules_matched > 0 ? 'good' : 'warning'}`} style={{ marginTop: 12 }}>
                <div className="result-headline" style={{ fontSize: 13 }}>
                  {fireEvent.data.rules_checked} enabled rule(s) checked, {fireEvent.data.rules_matched} matched
                </div>
                {fireEvent.data.fired.map((f) => (
                  <div key={f.rule_id} style={{ marginTop: 8 }}>
                    <b style={{ fontSize: 12.5 }}>{f.rule_name}</b>
                    <ul style={{ fontSize: 12, margin: '4px 0 0', paddingLeft: 18 }}>
                      {f.actions.map((a, i) => <li key={i}>{a.summary}</li>)}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: library */}
        <div>
          <div className="field-group">
            <div className="section-label">
              Rule library
              <span className="tag" style={{ marginLeft: 8, fontWeight: 600 }}>
                {rules.data?.length ?? 0} rule{rules.data?.length === 1 ? '' : 's'}, {rules.data?.filter((r) => r.enabled).length ?? 0} enabled
              </span>
            </div>
            {rules.isLoading && <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</span>}
            {rules.data?.length === 0 && (
              <p style={{ fontSize: 13, color: 'var(--ink-soft)' }}>No rules saved yet — author one on the left and save it.</p>
            )}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {rules.data?.map((rule) => (
                <div key={rule.id} style={{ padding: '12px 0', borderTop: '1px solid var(--line)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 600 }}>{rule.name}</div>
                      <div style={{ display: 'flex', gap: 6, marginTop: 5, flexWrap: 'wrap' }}>
                        <span className="tag" style={{ fontSize: 10.5 }}>{rule.trigger}</span>
                        <span className={`tag ${rule.governance === 'clinical' ? 'tag-critical' : 'tag-accent'}`} style={{ fontSize: 10.5 }}>{rule.governance}</span>
                        <span className={`tag ${rule.enabled ? 'tag-good' : ''}`} style={{ fontSize: 10.5 }}>{rule.enabled ? 'enabled' : 'draft'}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                      <button className="btn" style={{ fontSize: 11.5 }} onClick={() => setExpandedRuleId(expandedRuleId === rule.id ? null : rule.id)}>
                        {expandedRuleId === rule.id ? 'Hide DSL' : 'View DSL'}
                      </button>
                      <button
                        className="btn" style={{ fontSize: 11.5 }}
                        disabled={rule.enabled}
                        title={rule.enabled ? 'Disable this rule first to edit it' : undefined}
                        onClick={() => handleEditClick(rule)}
                      >
                        Edit
                      </button>
                      {rule.enabled ? (
                        <button className="btn" style={{ fontSize: 11.5 }} onClick={() => disableRule.mutate(rule.id)}>Disable</button>
                      ) : (
                        <button className="btn btn-primary" style={{ fontSize: 11.5 }} onClick={() => handleEnable(rule.id, rule.governance === 'clinical')}>Enable</button>
                      )}
                      <button
                        className="btn" style={{ fontSize: 11.5, color: 'var(--critical)' }}
                        onClick={() => { if (window.confirm(`Delete "${rule.name}" from the rule library?`)) deleteRule.mutate(rule.id); }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {expandedRuleId === rule.id && (
                    <pre style={{ fontSize: 11.5, background: 'var(--canvas)', padding: 10, borderRadius: 6, marginTop: 8, marginBottom: 0, overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                      {rule.dsl_text}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
