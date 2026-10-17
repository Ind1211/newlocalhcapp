import { useState } from 'react';
import { useAssessments, useAssignAssessment, useMyStaffRecord } from '../hooks/useApi';
import { BuilderChoice } from './BuilderChoice';
import { CustomAssessmentBuilder } from './CustomAssessmentBuilder';
import { TemplateUpload } from './TemplateUpload';
import type { AssessmentDefinition } from '../types';

export function NewAssessmentModal({
  patientId,
  patientProgramKeys,
  onClose,
  onAssigned,
}: {
  patientId: string;
  patientProgramKeys: string[];
  onClose: () => void;
  onAssigned: () => void;
}) {
  const [tab, setTab] = useState<'template' | 'custom'>('template');
  const [customMode, setCustomMode] = useState<'choice' | 'form' | 'upload'>('choice');
  const [search, setSearch] = useState('');
  // Defaults to the patient's own clinical programs — reuses the backend's own
  // multi-program filter (?program=kidney,cardiology) rather than re-implementing
  // that logic client-side. "Show all" is one click away, not hidden.
  const [showAllPrograms, setShowAllPrograms] = useState(patientProgramKeys.length === 0);
  const [markMandatory, setMarkMandatory] = useState(false);
  const programFilter = showAllPrograms || patientProgramKeys.length === 0 ? null : patientProgramKeys.join(',');
  const builtIns = useAssessments(programFilter);
  const assign = useAssignAssessment(patientId);
  const myStaff = useMyStaffRecord();
  const isAdmin = myStaff.data?.role === 'admin';

  const filtered = (builtIns.data ?? [])
    .filter((a) => !search || a.title.toLowerCase().includes(search.toLowerCase()) || a.category.toLowerCase().includes(search.toLowerCase()));

  const handlePickTemplate = (a: AssessmentDefinition) => {
    assign.mutate(
      { assessment_definition_key: a.key, title_override: a.title, source: 'template', scheduled_date: new Date().toISOString().slice(0, 10), mandatory: markMandatory },
      { onSuccess: onAssigned }
    );
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 50,
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center', overflowY: 'auto',
        padding: tab === 'custom' ? '16px' : '40px 20px',
      }}
      onClick={tab === 'template' ? onClose : undefined}
    >
      <div
        style={{
          background: 'var(--surface)', borderRadius: 14, width: '100%', border: '1px solid var(--line)',
          maxWidth: tab === 'custom' ? 'none' : 620,
          height: tab === 'custom' ? 'calc(100vh - 32px)' : undefined,
          display: tab === 'custom' ? 'flex' : undefined,
          flexDirection: tab === 'custom' ? 'column' : undefined,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '18px 22px', borderBottom: '1px solid var(--line)', flexShrink: 0 }}>
          <h3 style={{ margin: 0 }}>New Assessment</h3>
          <button className="btn" onClick={onClose} style={{ padding: '4px 8px' }}>✕</button>
        </div>

        <div style={{ padding: 22, overflowY: 'auto', flex: tab === 'custom' ? 1 : undefined, maxHeight: tab === 'custom' ? undefined : '70vh' }}>
          <div style={{ display: 'flex', gap: 6, background: 'var(--accent-tint)', borderRadius: 9, padding: 4, marginBottom: 18 }}>
            <button
              className="btn"
              style={{ flex: 1, background: tab === 'template' ? 'var(--surface)' : 'transparent', border: 'none' }}
              onClick={() => setTab('template')}
            >
              From Template
            </button>
            {isAdmin && (
              <button
                className="btn"
                style={{ flex: 1, background: tab === 'custom' ? 'var(--surface)' : 'transparent', border: 'none' }}
                onClick={() => setTab('custom')}
              >
                Build Custom
              </button>
            )}
          </div>

          {tab === 'template' ? (
            <div>
              {patientProgramKeys.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, fontSize: 12.5 }}>
                  <span style={{ color: 'var(--ink-soft)' }}>
                    {showAllPrograms ? 'Showing all assessments' : "Showing this patient's programs only"}
                  </span>
                  <button className="btn" style={{ padding: '3px 10px', fontSize: 12 }} onClick={() => setShowAllPrograms((s) => !s)}>
                    {showAllPrograms ? 'Show patient\'s programs only' : 'Show all'}
                  </button>
                </div>
              )}
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search assessments…"
                style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--line)', borderRadius: 20, fontSize: 13.5, marginBottom: 10 }}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--ink-soft)', cursor: 'pointer', marginBottom: 14 }}>
                <input type="checkbox" checked={markMandatory} onChange={(e) => setMarkMandatory(e.target.checked)} />
                Mark as mandatory for this patient's program
              </label>
              {assign.isError && (
                <div className="result-card critical" style={{ marginBottom: 12 }}>
                  <div className="result-headline">{(assign.error as Error).message}</div>
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 360, overflowY: 'auto' }}>
                {filtered.map((a) => (
                  <button
                    key={a.key}
                    onClick={() => handlePickTemplate(a)}
                    disabled={assign.isPending}
                    className="assessment-card"
                    style={{ textAlign: 'left', width: '100%', cursor: 'pointer' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: 13.5 }}>{a.title}</div>
                      {a.category === 'Custom' && <span className="tag tag-accent" style={{ fontSize: 10 }}>Custom</span>}
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 2 }}>{a.category}</div>
                  </button>
                ))}
                {filtered.length === 0 && !builtIns.isLoading && (
                  <div className="empty-state">No assessments match "{search}".</div>
                )}
              </div>
            </div>
          ) : !isAdmin ? (
            <div className="empty-state">Building custom assessments is limited to admins.</div>
          ) : (
            <>
              {assign.isError && (
                <div className="result-card critical" style={{ marginBottom: 12 }}>
                  <div className="result-headline">{(assign.error as Error).message}</div>
                </div>
              )}
              {customMode === 'choice' && (
                <BuilderChoice
                  onChooseForm={() => setCustomMode('form')}
                  onChooseUpload={() => setCustomMode('upload')}
                  onBack={onClose}
                />
              )}
              {customMode === 'form' && (
                <CustomAssessmentBuilder
                  onBack={() => setCustomMode('choice')}
                  onSaved={(key) => {
                    assign.mutate(
                      { assessment_definition_key: key, source: 'custom', scheduled_date: new Date().toISOString().slice(0, 10) },
                      { onSuccess: onAssigned }
                    );
                  }}
                />
              )}
              {customMode === 'upload' && (
                <TemplateUpload
                  onBack={() => setCustomMode('choice')}
                  onSaved={(key) => {
                    assign.mutate(
                      { assessment_definition_key: key, source: 'custom', scheduled_date: new Date().toISOString().slice(0, 10) },
                      { onSuccess: onAssigned }
                    );
                  }}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
