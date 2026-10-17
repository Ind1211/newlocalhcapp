import { useBusinessRules, useRuleExecutionLog } from '../hooks/useApi';
import type { BusinessRule, ConditionNode, RuleAction } from '../types';

function summarizeCondition(node: ConditionNode): string {
  if (!node) return '—';
  switch (node.type) {
    case 'cmp':
      return `${node.left} ${node.op} ${node.right}`;
    case 'and':
      return `${summarizeCondition(node.left)} AND ${summarizeCondition(node.right)}`;
    case 'or':
      return `${summarizeCondition(node.left)} OR ${summarizeCondition(node.right)}`;
    case 'not':
      return `NOT (${summarizeCondition(node.child)})`;
    default:
      return '—';
  }
}

function actionNodeLabel(a: RuleAction): { label: string; body: string; isTask: boolean } {
  switch (a.type) {
    case 'CREATE_TASK':
      return { label: 'Create task', body: `"${a.label}" → ${a.assignee}, due ${a.due}`, isTask: true };
    case 'UPDATE_STATUS':
      return { label: 'Update status', body: `Set status to "${a.value}"`, isTask: false };
    case 'ADD_GOAL':
      return { label: 'Add goal', body: `"${a.goal}"`, isTask: false };
    case 'SEND_NOTIFICATION':
      return { label: 'Send notification', body: `"${a.template}" → ${a.to}`, isTask: false };
    case 'TRANSITION':
      return { label: 'Transition', body: `${a.workflow} → "${a.target}"`, isTask: false };
    case 'ESCALATE_RISK':
      return { label: 'Escalate risk', body: `Level: "${a.level}"`, isTask: false };
    default:
      return { label: a.type || 'Action', body: '', isTask: false };
  }
}

function RuleBranch({ rule }: { rule: BusinessRule }) {
  return (
    <div className="field-group" style={{ opacity: rule.enabled ? 1 : 0.6, marginBottom: 10, padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13.5, fontWeight: 600 }}>{rule.name}</div>
        <span className={`tag ${rule.governance === 'clinical' ? 'tag-critical' : 'tag-accent'}`} style={{ fontSize: 10 }}>{rule.governance}</span>
        <span className={`tag ${rule.enabled ? 'tag-good' : ''}`} style={{ fontSize: 10 }}>{rule.enabled ? 'enabled' : 'draft'}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, overflowX: 'auto', paddingBottom: 4 }}>
        <div style={{ flexShrink: 0, minWidth: 150, maxWidth: 240, borderRadius: 6, padding: '10px 12px', fontSize: 11.5, lineHeight: 1.4, background: 'var(--caution-tint)', color: 'var(--caution)' }}>
          <span style={{ fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.05em', opacity: 0.8, display: 'block', marginBottom: 4 }}>If</span>
          {summarizeCondition(rule.condition_tree)}
        </div>
        {rule.actions.map((a, i) => {
          const n = actionNodeLabel(a);
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{ padding: '0 6px', color: 'var(--ink-soft)', flexShrink: 0, fontSize: 16 }}>→</div>
              <div
                style={{
                  flexShrink: 0, minWidth: 150, maxWidth: 240, borderRadius: 6, padding: '10px 12px', fontSize: 11.5, lineHeight: 1.4,
                  background: n.isTask ? '#E9F1FF' : 'var(--accent-tint)', color: n.isTask ? '#1B4E8C' : 'var(--accent)',
                }}
              >
                <span style={{ fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.05em', opacity: 0.8, display: 'block', marginBottom: 4 }}>{n.label}</span>
                {n.body}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function WorkflowVisualizer({ onBack }: { onBack: () => void }) {
  const rules = useBusinessRules();
  const executionLog = useRuleExecutionLog();

  const groups: Record<string, BusinessRule[]> = {};
  (rules.data ?? []).forEach((r) => {
    if (!groups[r.trigger]) groups[r.trigger] = [];
    groups[r.trigger].push(r);
  });

  const triggerCount = Object.keys(groups).length;
  const enabledCount = (rules.data ?? []).filter((r) => r.enabled).length;
  const taskNodeCount = (rules.data ?? []).reduce((sum, r) => sum + r.actions.filter((a) => a.type === 'CREATE_TASK').length, 0);

  return (
    <div>
      <a className="back-link" onClick={onBack}>← Back to My Patients</a>
      <h1 style={{ marginTop: 16 }}>Workflow Visualizer</h1>
      <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginBottom: 20 }}>
        Every rule saved in the Business Rules Engine, grouped by the event that triggers it, showing
        its condition and the actions it runs in order.
      </p>

      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <span className="tag">{rules.data?.length ?? 0} workflow rule{(rules.data?.length ?? 0) === 1 ? '' : 's'}</span>
        <span className="tag">{triggerCount} distinct trigger{triggerCount === 1 ? '' : 's'}</span>
        <span className="tag">{enabledCount} enabled</span>
        <span className="tag">{taskNodeCount} task-creating node{taskNodeCount === 1 ? '' : 's'}</span>
      </div>

      {rules.isLoading && <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</span>}

      {rules.data?.length === 0 && (
        <div className="field-group" style={{ textAlign: 'center', padding: '48px 28px' }}>
          <h3 style={{ marginBottom: 10 }}>No workflows saved yet</h3>
          <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', maxWidth: 440, margin: '0 auto' }}>
            Author a rule in the Business Rules Engine and save it to the rule library — it'll show up
            here as a trigger → condition → action node chain.
          </p>
        </div>
      )}

      {Object.entries(groups).map(([trigger, groupRules]) => (
        <div key={trigger} style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--accent-tint)', borderRadius: 10, padding: '12px 16px', marginBottom: 14, flexWrap: 'wrap' }}>
            <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 12.5, fontWeight: 700, color: 'var(--accent)', background: 'var(--surface)', padding: '5px 12px', borderRadius: 20, border: '1px solid var(--accent)' }}>
              {trigger}
            </span>
            <span style={{ fontSize: 12.5, color: 'var(--accent)' }}>fires {groupRules.length} rule{groupRules.length === 1 ? '' : 's'} below, in order</span>
          </div>
          {groupRules.map((rule) => <RuleBranch key={rule.id} rule={rule} />)}
        </div>
      ))}

      {(executionLog.data?.length ?? 0) > 0 && (
        <div className="field-group" style={{ marginTop: 8 }}>
          <div className="section-label">Recent execution log</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {executionLog.data!.slice(0, 20).map((entry) => (
              <div key={entry.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)', fontSize: 12.5 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--ink-soft)', fontSize: 11.5, marginBottom: 3 }}>
                  <span>{entry.trigger}</span>
                  <span>{new Date(entry.performed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                </div>
                <div>
                  {entry.matched ? (
                    <span style={{ color: 'var(--good)' }}>✓ {entry.rule_name}</span>
                  ) : (
                    <span style={{ color: 'var(--ink-soft)' }}>skipped — {entry.rule_name} (condition false)</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
