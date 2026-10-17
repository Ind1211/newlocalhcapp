import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAssessments } from '../hooks/useApi';
import { BuilderChoice } from './BuilderChoice';
import { CustomAssessmentBuilder } from './CustomAssessmentBuilder';
import { TemplateUpload } from './TemplateUpload';
import type { AssessmentDefinition } from '../types';

// Custom assessment definitions are global — reusable across any patient, not tied
// to one — so managing them (edit/history/delete) is its own screen, separate from
// any single patient's assigned-assessment list. Creating one here saves the
// definition to the library without assigning it to anyone — that happens later,
// from any patient's "+ New Assessment" menu, same as picking a built-in template.
export function ManageCustomAssessments({
  onBack,
  onEdit,
  onViewHistory,
}: {
  onBack: () => void;
  onEdit: (a: AssessmentDefinition) => void;
  onViewHistory: (a: AssessmentDefinition) => void;
}) {
  const assessments = useAssessments(null);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [createMode, setCreateMode] = useState<'none' | 'choice' | 'form' | 'upload'>('none');
  const queryClient = useQueryClient();
  const deleteMutation = useMutation({
    mutationFn: (key: string) => api.delete(`/api/assessments/custom/${key}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assessments'] });
      setConfirmingDelete(null);
    },
    onError: () => {
      // Deliberately does NOT clear confirmingDelete here — the confirm/cancel
      // row stays visible so the error message below has something to attach
      // to, and the person doesn't have to re-click Delete to see why it failed.
    },
  });

  // category === 'Custom' is the real distinction for "built via this screen" —
  // is_builtin alone isn't enough, since real program-tagged templates (like
  // the dementia assessments) are also deliberately is_builtin=False so they
  // stay editable, without being custom assessments a user built here.
  const custom = (assessments.data ?? []).filter((a) => a.category === 'Custom');

  if (createMode === 'choice') {
    return (
      <BuilderChoice
        onChooseForm={() => setCreateMode('form')}
        onChooseUpload={() => setCreateMode('upload')}
        onBack={() => setCreateMode('none')}
      />
    );
  }
  if (createMode === 'form') {
    return (
      <CustomAssessmentBuilder
        onBack={() => setCreateMode('choice')}
        onSaved={() => {
          queryClient.invalidateQueries({ queryKey: ['assessments'] });
          setCreateMode('none');
        }}
      />
    );
  }
  if (createMode === 'upload') {
    return (
      <TemplateUpload
        onBack={() => setCreateMode('choice')}
        onSaved={() => {
          queryClient.invalidateQueries({ queryKey: ['assessments'] });
          setCreateMode('none');
        }}
      />
    );
  }

  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back to patients
      </a>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: 16, marginBottom: 4, gap: 16, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0 }}>Custom Assessments</h1>
        <button className="btn btn-primary" onClick={() => setCreateMode('choice')}>+ Create Custom Assessment</button>
      </div>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 8, marginBottom: 20 }}>
        These are reusable across any patient — editing one saves a new version;
        earlier versions and any results already recorded against them stay intact.
      </p>

      {assessments.isLoading && <div className="empty-state">Loading…</div>}

      {custom.length === 0 && !assessments.isLoading && (
        <div className="empty-state">No custom assessments built yet — use "+ Create Custom Assessment" above to build one.</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {custom.map((a) => (
          <div className="assessment-card" key={a.key} style={{ cursor: 'default' }}>
            <div className="title">{a.title}</div>
            {a.blurb && <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 4 }}>{a.blurb}</div>}

            {confirmingDelete === a.key ? (
              <div style={{ marginTop: 12 }}>
                {deleteMutation.isError && deleteMutation.variables === a.key && (
                  <div className="result-card critical" style={{ marginBottom: 8, padding: '8px 12px' }}>
                    <div className="result-headline" style={{ fontSize: 12.5 }}>
                      {(deleteMutation.error as Error).message}
                    </div>
                  </div>
                )}
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 12.5, color: 'var(--critical)', flex: 1 }}>Delete this?</span>
                  <button className="btn" onClick={() => setConfirmingDelete(null)}>Cancel</button>
                  <button
                    className="btn"
                    style={{ background: 'var(--critical)', color: '#fff', borderColor: 'var(--critical)' }}
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(a.key)}
                  >
                    {deleteMutation.isPending ? 'Deleting…' : 'Confirm delete'}
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
                <button className="btn" onClick={() => onEdit(a)}>Edit</button>
                <button className="btn" onClick={() => onViewHistory(a)}>History</button>
                <button className="btn" onClick={() => setConfirmingDelete(a.key)}>Delete</button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
