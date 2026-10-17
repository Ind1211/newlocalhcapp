import { useState } from 'react';
import {
  useCreateGoal, useCreateIntervention, useCreateProblem, usePatientPgi,
  useResolveProblem, useUpdateGoalStatus, useUpdateInterventionStatus,
} from '../hooks/useApi';
import type { Goal, Intervention, Problem } from '../types';

const INTERVENTION_STATUS_LABELS: Record<string, string> = { planned: 'Planned', in_progress: 'In Progress', done: 'Done' };
const GOAL_STATUS_LABELS: Record<string, string> = { active: 'Active', met: 'Met', not_met: 'Not Met' };

function InterventionRow({ intervention, patientId }: { intervention: Intervention; patientId: string }) {
  const updateStatus = useUpdateInterventionStatus(patientId);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0 6px 20px', borderLeft: '2px solid var(--line)' }}>
      <span style={{ fontSize: 12.5, flex: 1 }}>↳ {intervention.description}</span>
      <select
        className="field-input"
        style={{ maxWidth: 110, fontSize: 11, padding: '3px 6px' }}
        value={intervention.status}
        onChange={(e) => updateStatus.mutate({ interventionId: intervention.id, status: e.target.value })}
      >
        {Object.entries(INTERVENTION_STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

function GoalBlock({ goal, patientId }: { goal: Goal; patientId: string }) {
  const updateStatus = useUpdateGoalStatus(patientId);
  const createIntervention = useCreateIntervention(patientId);
  const [showAdd, setShowAdd] = useState(false);
  const [text, setText] = useState('');

  return (
    <div style={{ padding: '8px 0 8px 14px', borderLeft: '2px solid var(--accent-tint)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>→ {goal.description}</span>
        {goal.source_rule_name && (
          <span className="tag tag-accent" style={{ fontSize: 10 }} title={`Created automatically by the rule "${goal.source_rule_name}"`}>
            ⚡ Automated
          </span>
        )}
        <select
          className="field-input"
          style={{ maxWidth: 110, fontSize: 11.5, padding: '3px 6px' }}
          value={goal.status}
          onChange={(e) => updateStatus.mutate({ goalId: goal.id, status: e.target.value })}
        >
          {Object.entries(GOAL_STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      {goal.target_date && (
        <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginTop: 2 }}>
          Target: {new Date(goal.target_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </div>
      )}

      {goal.interventions.map((iv) => <InterventionRow key={iv.id} intervention={iv} patientId={patientId} />)}

      {showAdd ? (
        <div style={{ display: 'flex', gap: 6, marginTop: 6, paddingLeft: 20 }}>
          <input className="field-input" style={{ maxWidth: 260, fontSize: 12.5 }} placeholder="New intervention…" value={text} onChange={(e) => setText(e.target.value)} />
          <button
            className="btn"
            style={{ fontSize: 11.5 }}
            disabled={!text.trim() || createIntervention.isPending}
            onClick={() => createIntervention.mutate({ goalId: goal.id, description: text.trim() }, { onSuccess: () => { setText(''); setShowAdd(false); } })}
          >
            Add
          </button>
          <button className="btn" style={{ fontSize: 11.5 }} onClick={() => setShowAdd(false)}>Cancel</button>
        </div>
      ) : (
        <button className="btn" style={{ fontSize: 11, marginTop: 6, marginLeft: 20, padding: '3px 8px' }} onClick={() => setShowAdd(true)}>
          + Intervention
        </button>
      )}
    </div>
  );
}

function ProblemCard({ problem, patientId }: { problem: Problem; patientId: string }) {
  const resolveProblem = useResolveProblem(patientId);
  const createGoal = useCreateGoal(patientId);
  const [showAdd, setShowAdd] = useState(false);
  const [text, setText] = useState('');

  return (
    <div style={{ padding: '12px 0', borderTop: '1px solid var(--line)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className={`tag ${problem.status === 'resolved' ? 'tag-good' : 'tag-critical'}`}>
          {problem.status === 'resolved' ? 'Resolved' : 'Active'}
        </span>
        <span style={{ fontSize: 14, fontWeight: 700, flex: 1 }}>{problem.description}</span>
        {problem.status === 'active' && (
          <button className="btn" style={{ fontSize: 11 }} onClick={() => resolveProblem.mutate(problem.id)}>Mark Resolved</button>
        )}
      </div>

      <div style={{ marginTop: 8 }}>
        {problem.goals.map((g) => <GoalBlock key={g.id} goal={g} patientId={patientId} />)}
      </div>

      {showAdd ? (
        <div style={{ display: 'flex', gap: 6, marginTop: 8, paddingLeft: 14 }}>
          <input className="field-input" style={{ maxWidth: 280, fontSize: 13 }} placeholder="New goal…" value={text} onChange={(e) => setText(e.target.value)} />
          <button
            className="btn"
            style={{ fontSize: 12 }}
            disabled={!text.trim() || createGoal.isPending}
            onClick={() => createGoal.mutate({ problemId: problem.id, description: text.trim() }, { onSuccess: () => { setText(''); setShowAdd(false); } })}
          >
            Add
          </button>
          <button className="btn" style={{ fontSize: 12 }} onClick={() => setShowAdd(false)}>Cancel</button>
        </div>
      ) : (
        <button className="btn" style={{ fontSize: 11.5, marginTop: 8, marginLeft: 14 }} onClick={() => setShowAdd(true)}>+ Goal</button>
      )}
    </div>
  );
}

export function PatientPgi({ patientId }: { patientId: string }) {
  const pgi = usePatientPgi(patientId);
  const createProblem = useCreateProblem(patientId);
  const [showAddProblem, setShowAddProblem] = useState(false);
  const [text, setText] = useState('');

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Problems, Goals &amp; Interventions</div>
        {!showAddProblem && <button className="btn" style={{ fontSize: 12 }} onClick={() => setShowAddProblem(true)}>+ Problem</button>}
      </div>

      {showAddProblem && (
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <input className="field-input" style={{ maxWidth: 320 }} placeholder="Describe the problem…" value={text} onChange={(e) => setText(e.target.value)} />
          <button
            className="btn btn-primary"
            style={{ fontSize: 12.5 }}
            disabled={!text.trim() || createProblem.isPending}
            onClick={() => createProblem.mutate(text.trim(), { onSuccess: () => { setText(''); setShowAddProblem(false); } })}
          >
            Add
          </button>
          <button className="btn" style={{ fontSize: 12.5 }} onClick={() => setShowAddProblem(false)}>Cancel</button>
        </div>
      )}

      {pgi.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 10 }}><span className="spinner" />Loading…</div>}
      {pgi.data && pgi.data.length === 0 && !showAddProblem && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: '10px 0 0' }}>No problems tracked yet.</p>
      )}

      {pgi.data?.map((p) => <ProblemCard key={p.id} problem={p} patientId={patientId} />)}
    </div>
  );
}
