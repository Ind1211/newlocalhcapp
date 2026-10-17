import { useState } from 'react';
import { useAssignStaff, usePatientStaffAssignments, useRemoveStaffAssignment, useStaffList } from '../hooks/useApi';

const ROLE_LABELS: Record<string, string> = {
  care_manager: 'Care Manager',
  nurse: 'Nurse',
  provider: 'Healthcare Provider',
  admin: 'Admin',
};

function AssignStaffModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const staffList = useStaffList();
  const assign = useAssignStaff(patientId);
  const [staffId, setStaffId] = useState('');
  const [roleOnPatient, setRoleOnPatient] = useState('nurse');

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 50, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px' }}
      onClick={onClose}
    >
      <div style={{ background: 'var(--surface)', borderRadius: 14, width: '100%', maxWidth: 420, border: '1px solid var(--line)' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0 }}>Assign Staff</h3>
        </div>
        <div style={{ padding: 22 }}>
          <div className="field-row">
            <div className="field-label">Staff member</div>
            <select className="field-input" style={{ maxWidth: 220 }} value={staffId} onChange={(e) => setStaffId(e.target.value)}>
              <option value="">Select…</option>
              {staffList.data?.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div className="field-row">
            <div className="field-label">Role on this patient</div>
            <select className="field-input" style={{ maxWidth: 220 }} value={roleOnPatient} onChange={(e) => setRoleOnPatient(e.target.value)}>
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          {assign.isError && (
            <div className="result-card critical" style={{ marginTop: 12 }}>
              <div className="result-headline">{(assign.error as Error).message}</div>
            </div>
          )}
        </div>
        <div style={{ padding: '16px 22px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            disabled={!staffId || assign.isPending}
            onClick={() => assign.mutate({ staff_id: staffId, role_on_patient: roleOnPatient }, { onSuccess: onClose })}
          >
            {assign.isPending ? 'Assigning…' : 'Assign'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function PatientCareTeam({ patientId }: { patientId: string }) {
  const assignments = usePatientStaffAssignments(patientId);
  const removeAssignment = useRemoveStaffAssignment(patientId);
  const [showAssignModal, setShowAssignModal] = useState(false);

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Care Team</div>
        <button className="btn" style={{ fontSize: 12 }} onClick={() => setShowAssignModal(true)}>+ Assign Staff</button>
      </div>

      {assignments.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}

      {assignments.data && assignments.data.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>No staff assigned yet.</p>
      )}

      <table className="data-table">
        <tbody>
          {assignments.data?.map((a) => (
            <tr key={a.id}>
              <td style={{ fontWeight: 600 }}>{a.staff.name}</td>
              <td><span className="tag tag-accent">{ROLE_LABELS[a.role_on_patient] ?? a.role_on_patient}</span></td>
              <td><span className="tag tag-good">{a.staff.status}</span></td>
              <td style={{ textAlign: 'right' }}>
                <button
                  className="btn"
                  style={{ fontSize: 11.5, padding: '4px 10px' }}
                  disabled={removeAssignment.isPending}
                  onClick={() => removeAssignment.mutate(a.id)}
                >
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showAssignModal && <AssignStaffModal patientId={patientId} onClose={() => setShowAssignModal(false)} />}
    </div>
  );
}
