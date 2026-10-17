import { useState } from 'react';
import { useDeactivatePatient, useReactivatePatient, useUpdatePatient, usePrograms } from '../hooks/useApi';
import type { Patient } from '../types';

export function EditPatientModal({
  patient,
  onClose,
  onUpdated,
}: {
  patient: Patient;
  onClose: () => void;
  onUpdated: (p: Patient) => void;
}) {
  const [name, setName] = useState(patient.name ?? '');
  const [dob, setDob] = useState(patient.dob ?? '');
  const [programKeys, setProgramKeys] = useState<string[]>(patient.clinical_programs.map((p) => p.key));
  const [payorName, setPayorName] = useState(patient.payor_name ?? '');
  const [memberId, setMemberId] = useState(patient.member_id ?? '');
  const [groupNumber, setGroupNumber] = useState(patient.group_number ?? '');
  const [eligibilityStatus, setEligibilityStatus] = useState(patient.eligibility_status ?? 'unverified');
  const [phoneNumber, setPhoneNumber] = useState(patient.phone_number ?? '');
  const [email, setEmail] = useState(patient.email ?? '');
  const [addressLine1, setAddressLine1] = useState(patient.address_line1 ?? '');
  const [city, setCity] = useState(patient.city ?? '');
  const [state, setState] = useState(patient.state ?? '');
  const [zipCode, setZipCode] = useState(patient.zip_code ?? '');
  const [preferredContactMethod, setPreferredContactMethod] = useState(patient.preferred_contact_method ?? '');
  const [preferredLanguage, setPreferredLanguage] = useState(patient.preferred_language ?? '');
  const [riskLevel, setRiskLevel] = useState(patient.risk_level ?? '');
  const programs = usePrograms();
  const updatePatient = useUpdatePatient(patient.id);
  const deactivatePatient = useDeactivatePatient();
  const reactivatePatient = useReactivatePatient();
  const [showDeactivateConfirm, setShowDeactivateConfirm] = useState(false);
  const [deactivateReason, setDeactivateReason] = useState('');

  const toggleProgram = (key: string) =>
    setProgramKeys((keys) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]));

  const handleSubmit = () => {
    if (!name.trim()) return;
    updatePatient.mutate(
      {
        name: name.trim(),
        dob: dob || undefined,
        clinical_program_keys: programKeys,
        payor_name: payorName || undefined,
        member_id: memberId || undefined,
        group_number: groupNumber || undefined,
        eligibility_status: eligibilityStatus || undefined,
        phone_number: phoneNumber || undefined,
        email: email || undefined,
        address_line1: addressLine1 || undefined,
        city: city || undefined,
        state: state || undefined,
        zip_code: zipCode || undefined,
        preferred_contact_method: preferredContactMethod || undefined,
        preferred_language: preferredLanguage || undefined,
        risk_level: riskLevel || undefined,
        // Captured when this form opened (patient.updated_at, from the prop) —
        // if the real, current value in the database has moved on since then,
        // someone else edited this patient in between and the save is
        // rejected rather than silently overwriting their change.
        expected_updated_at: patient.updated_at,
      },
      { onSuccess: (updated) => onUpdated(updated) }
    );
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 50,
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto',
      }}
      onClick={onClose}
    >
      <div
        style={{ background: 'var(--surface)', borderRadius: 14, width: '100%', maxWidth: 520, border: '1px solid var(--line)', boxShadow: 'var(--shadow-md)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 22px', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0 }}>Edit Patient</h3>
          <button className="btn" onClick={onClose} style={{ padding: '4px 8px' }} aria-label="Close">✕</button>
        </div>
        <div style={{ padding: 22, maxHeight: '70vh', overflowY: 'auto' }}>
          <div className="field-group">
            <div className="field-row">
              <div className="field-label">Full name</div>
              <input className="field-input" style={{ maxWidth: 240 }} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="field-row">
              <div className="field-label">Date of birth</div>
              <input className="field-input" type="date" style={{ maxWidth: 180 }} value={dob} onChange={(e) => setDob(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">MRN</div>
              <span style={{ fontSize: 13.5, fontFamily: "'Inter', sans-serif", color: 'var(--ink-soft)' }}>
                {patient.mrn} <span style={{ fontSize: 11 }}>(not editable)</span>
              </span>
            </div>
          </div>

          <div className="field-group">
            <div className="section-label">Clinical Programs</div>
            <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 10 }}>
              Unchecking a program removes it — this is a real, deliberate change, not just a display filter.
            </p>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              {programs.data?.map((p) => (
                <label key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13.5, cursor: 'pointer' }}>
                  <input type="checkbox" checked={programKeys.includes(p.key)} onChange={() => toggleProgram(p.key)} />
                  {p.icon} {p.label}
                </label>
              ))}
            </div>
          </div>

          <div className="field-group">
            <div className="section-label">Payor &amp; Eligibility</div>
            <div className="field-row">
              <div className="field-label">Payor</div>
              <input className="field-input" style={{ maxWidth: 220 }} value={payorName} onChange={(e) => setPayorName(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">Member ID</div>
              <input className="field-input" style={{ maxWidth: 220 }} value={memberId} onChange={(e) => setMemberId(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">Group number</div>
              <input className="field-input" style={{ maxWidth: 220 }} value={groupNumber} onChange={(e) => setGroupNumber(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">Eligibility status</div>
              <select className="field-input" style={{ maxWidth: 180 }} value={eligibilityStatus} onChange={(e) => setEligibilityStatus(e.target.value)}>
                <option value="unverified">Unverified</option>
                <option value="pending">Pending</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          </div>

          <div className="field-group">
            <div className="section-label">Contact Information</div>
            <div className="field-row">
              <div className="field-label">Phone</div>
              <input className="field-input" style={{ maxWidth: 200 }} value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">Email</div>
              <input className="field-input" type="email" style={{ maxWidth: 240 }} value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label">Address</div>
              <input className="field-input" style={{ maxWidth: 240 }} placeholder="Street address" value={addressLine1} onChange={(e) => setAddressLine1(e.target.value)} />
            </div>
            <div className="field-row">
              <div className="field-label" />
              <div style={{ display: 'flex', gap: 8 }}>
                <input className="field-input" style={{ maxWidth: 130 }} placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
                <input className="field-input" style={{ maxWidth: 70 }} placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
                <input className="field-input" style={{ maxWidth: 90 }} placeholder="ZIP" value={zipCode} onChange={(e) => setZipCode(e.target.value)} />
              </div>
            </div>
            <div className="field-row">
              <div className="field-label">Preferred contact</div>
              <select className="field-input" style={{ maxWidth: 160 }} value={preferredContactMethod} onChange={(e) => setPreferredContactMethod(e.target.value)}>
                <option value="">Not set</option>
                <option value="phone">Phone</option>
                <option value="email">Email</option>
                <option value="portal">Portal</option>
                <option value="mail">Mail</option>
              </select>
            </div>
            <div className="field-row">
              <div className="field-label">Preferred language</div>
              <input className="field-input" style={{ maxWidth: 160 }} value={preferredLanguage} onChange={(e) => setPreferredLanguage(e.target.value)} />
            </div>
          </div>

          <div className="field-group">
            <div className="section-label">Risk Level</div>
            <select className="field-input" style={{ maxWidth: 180 }} value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
              <option value="">Not assessed</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div className="field-group" style={{ borderTop: '1px solid var(--line)', paddingTop: 16 }}>
            <div className="section-label" style={{ color: 'var(--critical)' }}>
              {patient.is_active ? 'Deactivate Patient' : 'Patient is Deactivated'}
            </div>
            {patient.is_active ? (
              showDeactivateConfirm ? (
                <>
                  <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0 }}>
                    This is a soft delete — all history (assessments, documents, notes, tasks) stays intact.
                    The patient just disappears from the default roster until reactivated.
                  </p>
                  <input
                    className="field-input" style={{ maxWidth: 320, marginBottom: 10 }}
                    placeholder="Reason (optional) — e.g. Discharged, Transferred, Duplicate entry"
                    value={deactivateReason} onChange={(e) => setDeactivateReason(e.target.value)}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn" onClick={() => setShowDeactivateConfirm(false)}>Cancel</button>
                    <button
                      className="btn btn-primary" style={{ background: 'var(--critical)', borderColor: 'var(--critical)' }}
                      disabled={deactivatePatient.isPending}
                      onClick={() => deactivatePatient.mutate(
                        { patientId: patient.id, reason: deactivateReason || undefined },
                        { onSuccess: (updated) => onUpdated(updated) }
                      )}
                    >
                      {deactivatePatient.isPending ? 'Deactivating…' : 'Confirm Deactivation'}
                    </button>
                  </div>
                </>
              ) : (
                <button className="btn" style={{ fontSize: 12.5 }} onClick={() => setShowDeactivateConfirm(true)}>
                  Deactivate this patient
                </button>
              )
            ) : (
              <>
                {patient.deactivated_reason && (
                  <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0 }}>Reason: {patient.deactivated_reason}</p>
                )}
                <button
                  className="btn btn-primary" style={{ fontSize: 12.5 }}
                  disabled={reactivatePatient.isPending}
                  onClick={() => reactivatePatient.mutate(patient.id, { onSuccess: (updated) => onUpdated(updated) })}
                >
                  {reactivatePatient.isPending ? 'Reactivating…' : 'Reactivate this patient'}
                </button>
              </>
            )}
          </div>

          {updatePatient.isError && (
            <div className="result-card critical" style={{ marginTop: 16 }}>
              <div className="result-headline">{(updatePatient.error as Error).message}</div>
            </div>
          )}
        </div>
        <div style={{ padding: '16px 22px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!name.trim() || updatePatient.isPending} onClick={handleSubmit}>
            {updatePatient.isPending && <span className="spinner" />}
            {updatePatient.isPending ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
