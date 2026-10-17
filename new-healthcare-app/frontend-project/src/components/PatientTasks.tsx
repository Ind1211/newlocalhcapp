import { useState } from 'react';
import { useCreateTask, useDeleteTask, usePatientTasks, useStaffList, useUpdateTaskStatus } from '../hooks/useApi';

const STATUS_LABELS: Record<string, string> = { pending: 'Pending', in_progress: 'In Progress', completed: 'Completed' };

function formatDate(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function AddTaskForm({ patientId, onDone }: { patientId: string; onDone: () => void }) {
  const [title, setTitle] = useState('');
  const [assignedTo, setAssignedTo] = useState('');
  const [dueDate, setDueDate] = useState('');
  const staffList = useStaffList();
  const createTask = useCreateTask(patientId);

  const handleSubmit = () => {
    if (!title.trim()) return;
    createTask.mutate(
      { title: title.trim(), assigned_to_id: assignedTo || undefined, due_date: dueDate || undefined },
      { onSuccess: onDone }
    );
  };

  return (
    <div style={{ marginBottom: 16, padding: 12, background: 'var(--canvas)', borderRadius: 8 }}>
      <div className="field-row" style={{ borderBottom: 'none', paddingTop: 0 }}>
        <div className="field-label">Title</div>
        <input className="field-input" style={{ maxWidth: 240 }} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Call patient re: symptoms" />
      </div>
      <div className="field-row" style={{ borderBottom: 'none' }}>
        <div className="field-label">Assign to</div>
        <select className="field-input" style={{ maxWidth: 220 }} value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)}>
          <option value="">Unassigned</option>
          {staffList.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div className="field-row" style={{ borderBottom: 'none' }}>
        <div className="field-label">Due date</div>
        <input className="field-input" type="date" style={{ maxWidth: 180 }} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </div>
      {createTask.isError && (
        <div style={{ fontSize: 12, color: 'var(--critical)', marginTop: 6 }}>{(createTask.error as Error).message}</div>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <button className="btn" style={{ fontSize: 12 }} onClick={onDone}>Cancel</button>
        <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={!title.trim() || createTask.isPending} onClick={handleSubmit}>
          {createTask.isPending ? 'Adding…' : 'Add Task'}
        </button>
      </div>
    </div>
  );
}

export function PatientTasks({ patientId }: { patientId: string }) {
  const tasks = usePatientTasks(patientId);
  const updateStatus = useUpdateTaskStatus(patientId);
  const deleteTask = useDeleteTask(patientId);
  const [showAddForm, setShowAddForm] = useState(false);

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Tasks</div>
        {!showAddForm && <button className="btn" style={{ fontSize: 12 }} onClick={() => setShowAddForm(true)}>+ Add Task</button>}
      </div>

      {showAddForm && <AddTaskForm patientId={patientId} onDone={() => setShowAddForm(false)} />}

      {tasks.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}
      {tasks.data && tasks.data.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>No tasks yet.</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {tasks.data?.map((task) => (
          <div key={task.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10, opacity: task.status === 'completed' ? 0.6 : 1 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, textDecoration: task.status === 'completed' ? 'line-through' : 'none' }}>{task.title}</div>
                {task.source_rule_name && (
                  <span className="tag tag-accent" style={{ fontSize: 10 }} title={`Created automatically by the rule "${task.source_rule_name}"`}>
                    ⚡ Automated
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 2 }}>
                {task.assigned_to ? task.assigned_to.name : 'Unassigned'}
                {task.due_date ? ` · Due ${formatDate(task.due_date)}` : ''}
              </div>
            </div>
            <select
              className="field-input"
              style={{ maxWidth: 130, fontSize: 12, padding: '5px 8px' }}
              value={task.status}
              onChange={(e) => updateStatus.mutate({ taskId: task.id, status: e.target.value })}
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <button className="btn" style={{ fontSize: 10.5, padding: '4px 8px' }} onClick={() => deleteTask.mutate(task.id)}>✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
