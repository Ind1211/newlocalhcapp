import { useState } from 'react';
import {
  useAuth0Lookup, useCreateStaff, useDeactivateStaff, useInviteStaff, useMyStaffRecord, useReactivateStaff,
  useResendInvite, useStaffList, useUpdateStaff,
} from '../hooks/useApi';
import type { Staff } from '../types';

export const ROLE_LABELS: Record<string, string> = {
  care_manager: 'Care Manager',
  nurse: 'Nurse',
  provider: 'Healthcare Provider',
  admin: 'Admin',
};

function InviteStaffForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('nurse');
  const invite = useInviteStaff();

  const handleSubmit = () => {
    if (!name.trim() || !email.trim()) return;
    invite.mutate({ name: name.trim(), email: email.trim(), role });
  };

  if (invite.isSuccess) {
    return (
      <div className="field-group">
        <div className={`result-card ${invite.data.email_sent ? 'good' : 'warning'}`} style={{ marginTop: 0 }}>
          <div className="result-headline">
            {invite.data.staff.name}'s account was created.{' '}
            {invite.data.email_sent
              ? 'A password-setup email has been sent to ' + invite.data.staff.email + '.'
              : "The account exists, but the invite email couldn't be sent — use \"Resend Invite\" below once you close this."}
          </div>
        </div>
        <button className="btn" style={{ marginTop: 12 }} onClick={onDone}>Done</button>
      </div>
    );
  }

  return (
    <div className="field-group">
      <div className="section-label">Invite Staff Member</div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 14 }}>
        Creates a real account for them and emails them a link to set their own password —
        no need to create anything in Auth0 yourself first.
      </p>
      <div className="field-row">
        <div className="field-label">Full name</div>
        <input className="field-input" style={{ maxWidth: 260 }} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Marcus Iyer" />
      </div>
      <div className="field-row">
        <div className="field-label">Email</div>
        <input className="field-input" style={{ maxWidth: 260 }} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="marcus@example.com" />
      </div>
      <div className="field-row">
        <div className="field-label">Role</div>
        <select className="field-input" style={{ maxWidth: 260 }} value={role} onChange={(e) => setRole(e.target.value)}>
          {Object.entries(ROLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {invite.isError && (
        <div className="result-card critical" style={{ marginTop: 12 }}>
          <div className="result-headline">{(invite.error as Error).message}</div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button className="btn" onClick={onDone}>Cancel</button>
        <button
          className="btn btn-primary"
          disabled={!name.trim() || !email.trim() || invite.isPending}
          onClick={handleSubmit}
        >
          {invite.isPending && <span className="spinner" />}
          {invite.isPending ? 'Creating account…' : 'Send Invite'}
        </button>
      </div>
    </div>
  );
}

function LinkExistingAccountForm({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('nurse');
  const lookup = useAuth0Lookup();
  const createStaff = useCreateStaff();

  const handleLookup = () => {
    if (!email.trim()) return;
    lookup.mutate(email.trim());
  };

  const handleLink = () => {
    if (!lookup.data?.found || !lookup.data.auth0_sub) return;
    createStaff.mutate({
      auth0_sub: lookup.data.auth0_sub,
      name: lookup.data.name ?? email.trim(),
      email: lookup.data.email ?? email.trim(),
      role,
    });
  };

  if (createStaff.isSuccess) {
    return (
      <div className="field-group">
        <div className="result-card good" style={{ marginTop: 0 }}>
          <div className="result-headline">{createStaff.data.name}'s existing Auth0 account is now linked as staff.</div>
        </div>
        <button className="btn" style={{ marginTop: 12 }} onClick={onDone}>Done</button>
      </div>
    );
  }

  return (
    <div className="field-group">
      <div className="section-label">Link an Existing Auth0 Account</div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 14 }}>
        For someone who already has a real Auth0 account — most often because their Staff record
        was removed at some point without their actual account ever being deleted. This finds
        that real account by email and registers it directly; it does not create a new one.
      </p>
      <div className="field-row">
        <div className="field-label">Email</div>
        <div style={{ display: 'flex', gap: 8, flex: 1 }}>
          <input
            className="field-input" style={{ maxWidth: 260 }} value={email}
            onChange={(e) => { setEmail(e.target.value); lookup.reset(); }}
            placeholder="marcus@example.com"
          />
          <button className="btn" style={{ fontSize: 12.5 }} disabled={!email.trim() || lookup.isPending} onClick={handleLookup}>
            {lookup.isPending ? 'Looking up…' : 'Look Up'}
          </button>
        </div>
      </div>

      {lookup.data && !lookup.data.found && (
        <div className="result-card warning" style={{ marginTop: 4 }}>
          <div className="result-headline" style={{ fontSize: 12.5 }}>
            No Auth0 account exists for this email. Use "Invite Staff Member" instead to create a brand new one.
          </div>
        </div>
      )}

      {lookup.data?.found && lookup.data.already_linked && (
        <div className="result-card critical" style={{ marginTop: 4 }}>
          <div className="result-headline" style={{ fontSize: 12.5 }}>
            This account is already registered as staff (status: {lookup.data.already_linked_status}).
            {lookup.data.already_linked_status === 'inactive' && ' Use "Reactivate" on their existing row below instead of linking again.'}
          </div>
        </div>
      )}

      {lookup.data?.found && !lookup.data.already_linked && (
        <>
          <div className="result-card good" style={{ marginTop: 4, marginBottom: 14 }}>
            <div className="result-headline" style={{ fontSize: 12.5 }}>
              Found: {lookup.data.name} ({lookup.data.email})
            </div>
          </div>
          <div className="field-row">
            <div className="field-label">Role</div>
            <select className="field-input" style={{ maxWidth: 260 }} value={role} onChange={(e) => setRole(e.target.value)}>
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
        </>
      )}

      {(lookup.isError || createStaff.isError) && (
        <div className="result-card critical" style={{ marginTop: 12 }}>
          <div className="result-headline">{((lookup.error || createStaff.error) as Error).message}</div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <button className="btn" onClick={onDone}>Cancel</button>
        {lookup.data?.found && !lookup.data.already_linked && (
          <button className="btn btn-primary" disabled={createStaff.isPending} onClick={handleLink}>
            {createStaff.isPending && <span className="spinner" />}
            {createStaff.isPending ? 'Linking…' : 'Link This Account'}
          </button>
        )}
      </div>
    </div>
  );
}

function EditStaffRow({ staff, onDone }: { staff: Staff; onDone: () => void }) {
  const [name, setName] = useState(staff.name);
  const [email, setEmail] = useState(staff.email ?? '');
  const [role, setRole] = useState<string>(staff.role);
  const update = useUpdateStaff();

  return (
    <tr>
      <td colSpan={4} style={{ padding: 12, background: 'var(--canvas)' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input className="field-input" style={{ maxWidth: 260 }} value={name} onChange={(e) => setName(e.target.value)} />
          <input className="field-input" style={{ maxWidth: 260 }} value={email} onChange={(e) => setEmail(e.target.value)} />
          <select className="field-input" style={{ maxWidth: 260 }} value={role} onChange={(e) => setRole(e.target.value)}>
            {Object.entries(ROLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button className="btn" style={{ fontSize: 12 }} onClick={onDone}>Cancel</button>
          <button
            className="btn btn-primary"
            style={{ fontSize: 12 }}
            disabled={update.isPending}
            onClick={() => update.mutate({ staffId: staff.id, payload: { name, email, role } }, { onSuccess: onDone })}
          >
            {update.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
        {update.isError && <div style={{ fontSize: 12, color: 'var(--critical)', marginTop: 8 }}>{(update.error as Error).message}</div>}
      </td>
    </tr>
  );
}

function StaffRow({ staff }: { staff: Staff }) {
  const [editing, setEditing] = useState(false);
  const deactivate = useDeactivateStaff();
  const reactivate = useReactivateStaff();
  const resendInvite = useResendInvite();
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  if (editing) return <EditStaffRow staff={staff} onDone={() => setEditing(false)} />;

  return (
    <tr style={{ opacity: staff.status === 'inactive' ? 0.55 : 1 }}>
      <td style={{ fontWeight: 600 }}>{staff.name}</td>
      <td><span className="tag tag-accent">{ROLE_LABELS[staff.role] ?? staff.role}</span></td>
      <td style={{ color: 'var(--ink-soft)' }}>{staff.email ?? '—'}</td>
      <td><span className={`tag ${staff.status === 'active' ? 'tag-good' : 'tag-critical'}`}>{staff.status}</span></td>
      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
        <button className="btn" style={{ fontSize: 11, padding: '4px 8px', marginRight: 4 }} onClick={() => setEditing(true)}>Edit</button>
        {staff.status === 'active' ? (
          <button
            className="btn"
            style={{ fontSize: 11, padding: '4px 8px', marginRight: 4 }}
            disabled={deactivate.isPending}
            onClick={() => deactivate.mutate(staff.id)}
          >
            Deactivate
          </button>
        ) : (
          <button
            className="btn"
            style={{ fontSize: 11, padding: '4px 8px', marginRight: 4 }}
            disabled={reactivate.isPending}
            onClick={() => reactivate.mutate(staff.id)}
          >
            Reactivate
          </button>
        )}
        {staff.email && (
          <button
            className="btn"
            style={{ fontSize: 11, padding: '4px 8px' }}
            disabled={resendInvite.isPending}
            onClick={() => resendInvite.mutate(staff.id, { onSuccess: () => setResendMessage('Sent') })}
          >
            {resendMessage ?? 'Resend Invite'}
          </button>
        )}
      </td>
    </tr>
  );
}

export function StaffManagement({ onBack }: { onBack: () => void }) {
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);
  const myRecord = useMyStaffRecord();
  const staffList = useStaffList();

  // A real, expected state — not an error — for someone whose Auth0 login works
  // but who hasn't been registered as staff yet. Every write endpoint on the
  // backend already enforces this same check independently; this is just the
  // frontend explaining why nothing else on this screen will work for them yet.
  if (myRecord.data === null) {
    return (
      <div>
        <a className="back-link" onClick={onBack}>← Back to patients</a>
        <div className="empty-state" style={{ marginTop: 20 }}>
          <div className="empty-title">Not yet registered as staff</div>
          <div className="empty-detail">
            Your account is authenticated, but isn't linked to a staff record yet.
            Ask an existing staff member or admin to add you.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <a className="back-link" onClick={onBack}>← Back to patients</a>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '16px 0 20px' }}>
        <h1 style={{ margin: 0 }}>Staff</h1>
        {!showInviteForm && !showLinkForm && (
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => setShowLinkForm(true)}>Link Existing Account</button>
            <button className="btn btn-primary" onClick={() => setShowInviteForm(true)}>+ Invite Staff Member</button>
          </div>
        )}
      </div>

      {showInviteForm && <InviteStaffForm onDone={() => setShowInviteForm(false)} />}
      {showLinkForm && <LinkExistingAccountForm onDone={() => setShowLinkForm(false)} />}

      {staffList.isLoading && <div className="empty-state"><span className="spinner" />Loading staff…</div>}

      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Role</th>
            <th>Email</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {staffList.data?.map((s) => <StaffRow key={s.id} staff={s} />)}
        </tbody>
      </table>
    </div>
  );
}
