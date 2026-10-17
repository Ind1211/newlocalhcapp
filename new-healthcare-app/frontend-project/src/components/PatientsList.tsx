import { useEffect, useRef, useState } from 'react';
import { usePatients, useCreatePatient, usePrograms, useStaffList } from '../hooks/useApi';
import type { ClinicalProgram, Patient } from '../types';

function ProgramTag({ program }: { program: ClinicalProgram }) {
  return (
    <span className="tag tag-accent">
      {program.icon ? `${program.icon} ` : ''}{program.label}
    </span>
  );
}

function AddPatientModal({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Patient) => void }) {
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [programKeys, setProgramKeys] = useState<string[]>([]);
  const [payorName, setPayorName] = useState('');
  const [memberId, setMemberId] = useState('');
  const [groupNumber, setGroupNumber] = useState('');
  const [eligibilityStatus, setEligibilityStatus] = useState('unverified');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [email, setEmail] = useState('');
  const [addressLine1, setAddressLine1] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [preferredContactMethod, setPreferredContactMethod] = useState('');
  const [preferredLanguage, setPreferredLanguage] = useState('');
  const [riskLevel, setRiskLevel] = useState('');
  const programs = usePrograms();
  const createPatient = useCreatePatient();

  const toggleProgram = (key: string) =>
    setProgramKeys((keys) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]));

  const handleSubmit = () => {
    if (!name.trim()) return;
    createPatient.mutate(
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
      },
      { onSuccess: (p) => onCreated(p) }
    );
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 50,
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto',
        animation: 'step-in 0.15s ease',
      }}
      onClick={onClose}
    >
      <div
        style={{ background: 'var(--surface)', borderRadius: 14, width: '100%', maxWidth: 520, border: '1px solid var(--line)', boxShadow: 'var(--shadow-md)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 22px', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0 }}>Add Patient</h3>
          <button className="btn" onClick={onClose} style={{ padding: '4px 8px' }} aria-label="Close">✕</button>
        </div>
        <div style={{ padding: 22, maxHeight: '70vh', overflowY: 'auto' }}>
          <div className="field-group">
            <div className="field-row">
              <div className="field-label">Full name</div>
              <input className="field-input" style={{ maxWidth: 240 }} placeholder="e.g. Marcus Delgado" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="field-row">
              <div className="field-label">Date of birth</div>
              <input className="field-input" type="date" style={{ maxWidth: 180 }} value={dob} onChange={(e) => setDob(e.target.value)} />
            </div>
          </div>

          <div className="field-group">
            <div className="section-label">Clinical Programs</div>
            <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 10 }}>
              A patient can be in more than one — pick every program that genuinely applies.
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
              <input className="field-input" style={{ maxWidth: 220 }} placeholder="e.g. Aetna" value={payorName} onChange={(e) => setPayorName(e.target.value)} />
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

          {createPatient.isError && (
            <div className="result-card critical" style={{ marginTop: 16 }}>
              <div className="result-headline">{(createPatient.error as Error).message}</div>
            </div>
          )}
        </div>
        <div style={{ padding: '16px 22px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!name.trim() || createPatient.isPending} onClick={handleSubmit}>
            {createPatient.isPending && <span className="spinner" />}
            {createPatient.isPending ? 'Adding…' : 'Add Patient'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function PatientsList({
  onSelectPatient,
  onBulkImport,
}: {
  onSelectPatient: (p: Patient) => void;
  onBulkImport: () => void;
}) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [eligibilityFilter, setEligibilityFilter] = useState('');
  const [programStatusFilter, setProgramStatusFilter] = useState('');
  const [careTeamFilter, setCareTeamFilter] = useState('');
  const [riskLevelFilter, setRiskLevelFilter] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showFilterMenu, setShowFilterMenu] = useState(false);
  const filterMenuRef = useRef<HTMLDivElement>(null);
  const staffList = useStaffList();
  const patients = usePatients(
    search, page, includeInactive, sortBy, sortOrder,
    eligibilityFilter || undefined, programStatusFilter || undefined, careTeamFilter || undefined, riskLevelFilter || undefined,
  );

  const activeFilterCount = [includeInactive, eligibilityFilter, programStatusFilter, careTeamFilter, riskLevelFilter].filter(Boolean).length;

  const clearAllFilters = () => {
    setIncludeInactive(false);
    setEligibilityFilter('');
    setProgramStatusFilter('');
    setCareTeamFilter('');
    setRiskLevelFilter('');
    setPage(1);
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (filterMenuRef.current && !filterMenuRef.current.contains(e.target as Node)) setShowFilterMenu(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchChange = (value: string) => {
    setSearch(value);
    setPage(1); // a new search invalidates whatever page we were on
  };

  // Every filter/sort change resets to page 1 — staying on page 3 of a result
  // set that just changed shape entirely would show a confusing, arbitrary slice.
  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
    setPage(1);
  };

  const sortIndicator = (column: string) => (sortBy === column ? (sortOrder === 'asc' ? ' ▲' : ' ▼') : '');

  const openPatient = (p: Patient) => onSelectPatient(p);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, gap: 16, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0 }}>My Patients</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={onBulkImport}>Bulk Import</button>
          <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>+ Add Patient</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20 }} ref={filterMenuRef}>
        <input
          type="text"
          className="field-input"
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Search by name, MRN, or clinical program…"
          style={{ maxWidth: 420, flex: 1 }}
        />
        <div style={{ position: 'relative' }}>
          <button
            className="btn" onClick={() => setShowFilterMenu((o) => !o)}
            style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', padding: '9px 12px' }}
            aria-label="Filters"
            title="Filters"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 4h18l-7 8v6l-4 2v-8L3 4z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            </svg>
            {activeFilterCount > 0 && (
              <span
                style={{
                  position: 'absolute', top: -4, right: -4, background: 'var(--accent)', color: '#fff',
                  borderRadius: '50%', fontSize: 10, fontWeight: 700, minWidth: 16, height: 16,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px',
                }}
              >
                {activeFilterCount}
              </span>
            )}
          </button>

        {showFilterMenu && (
          <div
            style={{
              position: 'absolute', top: '100%', right: 0, marginTop: 8, width: 420,
              background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 12,
              boxShadow: 'var(--shadow-md)', zIndex: 50, padding: 18,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <span style={{ fontWeight: 700, fontSize: 13.5 }}>Filters</span>
              {activeFilterCount > 0 && (
                <button className="btn" style={{ fontSize: 11, padding: '3px 8px' }} onClick={clearAllFilters}>Clear all</button>
              )}
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', color: 'var(--ink-soft)', marginBottom: 16 }}>
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => { setIncludeInactive(e.target.checked); setPage(1); }}
              />
              Show deactivated patients
            </label>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px 16px' }}>
              <div>
                <div className="section-label" style={{ marginBottom: 4 }}>Eligibility</div>
                <select
                  className="field-input" style={{ width: '100%', maxWidth: 'none' }}
                  value={eligibilityFilter}
                  onChange={(e) => { setEligibilityFilter(e.target.value); setPage(1); }}
                >
                  <option value="">All</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="pending">Pending</option>
                  <option value="unverified">Unverified</option>
                </select>
              </div>

              <div>
                <div className="section-label" style={{ marginBottom: 4 }}>Program Status</div>
                <select
                  className="field-input" style={{ width: '100%', maxWidth: 'none' }}
                  value={programStatusFilter}
                  onChange={(e) => { setProgramStatusFilter(e.target.value); setPage(1); }}
                >
                  <option value="">All</option>
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                </select>
              </div>

              <div>
                <div className="section-label" style={{ marginBottom: 4 }}>Risk Level</div>
                <select
                  className="field-input" style={{ width: '100%', maxWidth: 'none' }}
                  value={riskLevelFilter}
                  onChange={(e) => { setRiskLevelFilter(e.target.value); setPage(1); }}
                >
                  <option value="">All</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>

              <div>
                <div className="section-label" style={{ marginBottom: 4 }}>Care Team Member</div>
                <select
                  className="field-input" style={{ width: '100%', maxWidth: 'none' }}
                  value={careTeamFilter}
                  onChange={(e) => { setCareTeamFilter(e.target.value); setPage(1); }}
                >
                  <option value="">All</option>
                  {staffList.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            </div>
          </div>
        )}
        </div>
      </div>

      {patients.isError && (
        <div className="result-card critical">
          <div className="result-headline">Could not load patients: {(patients.error as Error).message}</div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th style={{ cursor: 'pointer' }} onClick={() => handleSort('name')}>Patient{sortIndicator('name')}</th>
            <th>MRN</th>
            <th style={{ cursor: 'pointer' }} onClick={() => handleSort('dob')}>Date of Birth{sortIndicator('dob')}</th>
            <th>Clinical Programs</th>
            <th>Care Team</th>
            <th>Assessments</th>
            <th style={{ cursor: 'pointer' }} onClick={() => handleSort('open_tasks')}>Tasks{sortIndicator('open_tasks')}</th>
            <th style={{ cursor: 'pointer' }} onClick={() => handleSort('risk_level')}>Risk{sortIndicator('risk_level')}</th>
            <th>Payor</th>
            <th>Eligibility</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {patients.isLoading && (
            <tr>
              <td colSpan={10} style={{ textAlign: 'center', padding: '32px 12px', color: 'var(--ink-soft)' }}>
                <span className="spinner" />Loading patients…
              </td>
            </tr>
          )}
          {patients.data && patients.data.items.length === 0 && (
            <tr>
              <td colSpan={10}>
                <div className="empty-state">
                  <div className="empty-title">{search ? 'No matches' : 'No patients yet'}</div>
                  <div className="empty-detail">
                    {search ? `Nothing matches "${search}" — try a different name, MRN, or program.` : 'Add your first patient to get started.'}
                  </div>
                </div>
              </td>
            </tr>
          )}
          {patients.data?.items.map((p) => (
            <tr
              key={p.id}
              className="clickable-row"
              style={{ opacity: p.is_active ? 1 : 0.55 }}
              tabIndex={0}
              role="button"
              onClick={() => openPatient(p)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  openPatient(p);
                }
              }}
            >
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                  {!p.is_active && <span className="tag tag-critical" style={{ fontSize: 10.5 }}>Deactivated</span>}
                </div>
              </td>
              <td style={{ fontFamily: "'Inter', sans-serif", color: 'var(--ink-soft)' }}>{p.mrn}</td>
              <td style={{ fontFamily: "'Inter', sans-serif", color: 'var(--ink-soft)' }}>{p.dob ?? '—'}</td>
              <td>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {p.clinical_programs.length > 0
                    ? p.clinical_programs.map((prog) => <ProgramTag key={prog.key} program={prog} />)
                    : p.care_pathway && <span className="tag tag-neutral">{p.care_pathway} (legacy)</span>}
                </div>
              </td>
              <td style={{ fontSize: 12.5 }}>
                {p.care_team.length === 0 ? (
                  <span style={{ color: 'var(--ink-soft)' }}>—</span>
                ) : p.care_team.length === 1 ? (
                  p.care_team[0].name
                ) : (
                  `${p.care_team[0].name} +${p.care_team.length - 1}`
                )}
              </td>
              <td>
                {p.assessments_total === 0 ? (
                  <span style={{ color: 'var(--ink-soft)', fontSize: 12.5 }}>—</span>
                ) : (
                  <span
                    className={`tag ${p.assessments_completed === p.assessments_total ? 'tag-good' : 'tag-caution'}`}
                  >
                    {p.assessments_completed}/{p.assessments_total}
                  </span>
                )}
              </td>
              <td>
                {p.open_tasks_count > 0 ? (
                  <span className="tag tag-critical">{p.open_tasks_count} open</span>
                ) : (
                  <span style={{ color: 'var(--ink-soft)', fontSize: 12.5 }}>—</span>
                )}
              </td>
              <td>
                {p.risk_level ? (
                  <span
                    className={`tag ${p.risk_level === 'critical' || p.risk_level === 'high' ? 'tag-critical' : p.risk_level === 'medium' ? 'tag-caution' : 'tag-good'}`}
                    style={{ textTransform: 'uppercase', fontSize: 10.5 }}
                  >
                    {p.risk_level}
                  </span>
                ) : (
                  <span style={{ color: 'var(--ink-soft)', fontSize: 12.5 }}>—</span>
                )}
              </td>
              <td style={{ fontSize: 12.5, color: 'var(--ink-soft)' }}>{p.payor_name ?? '—'}</td>
              <td>
                {p.eligibility_status ? (
                  <span
                    className={`tag ${p.eligibility_status === 'active' ? 'tag-good' : p.eligibility_status === 'inactive' ? 'tag-critical' : 'tag-caution'}`}
                    style={{ textTransform: 'capitalize' }}
                  >
                    {p.eligibility_status}
                  </span>
                ) : (
                  <span style={{ color: 'var(--ink-soft)', fontSize: 12.5 }}>—</span>
                )}
              </td>
              <td style={{ textAlign: 'right', color: 'var(--ink-soft)' }}>›</td>
            </tr>
          ))}
        </tbody>
      </table>

      {patients.data && patients.data.total_pages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 20 }}>
          <button className="btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Previous</button>
          <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>
            Page {patients.data.page} of {patients.data.total_pages} · {patients.data.total} patient{patients.data.total === 1 ? '' : 's'}
          </span>
          <button className="btn" disabled={page >= patients.data.total_pages} onClick={() => setPage((p) => p + 1)}>Next →</button>
        </div>
      )}

      {showAddModal && (
        <AddPatientModal
          onClose={() => setShowAddModal(false)}
          onCreated={(p) => {
            setShowAddModal(false);
            onSelectPatient(p);
          }}
        />
      )}
    </div>
  );
}
