import { useCompleteProgram, useOnboardingProgress, useReopenProgram } from '../hooks/useApi';

export function OnboardingProgressStepper({ patientId }: { patientId: string }) {
  const progress = useOnboardingProgress(patientId);
  const completeProgram = useCompleteProgram(patientId);
  const reopenProgram = useReopenProgram(patientId);

  if (progress.isLoading || !progress.data) return null;

  const isCompleted = progress.data.program_status === 'completed';

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div className="section-label" style={{ marginBottom: 0 }}>Care Journey</div>
        {isCompleted ? (
          <button className="btn" style={{ fontSize: 11.5, marginLeft: 'auto' }} disabled={reopenProgram.isPending} onClick={() => reopenProgram.mutate()}>
            Reopen Program
          </button>
        ) : (
          <button className="btn" style={{ fontSize: 11.5, marginLeft: 'auto' }} disabled={completeProgram.isPending} onClick={() => completeProgram.mutate()}>
            Mark Program Completed
          </button>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', rowGap: 20, paddingTop: 10 }}>
        {progress.data.steps.map((step, i) => {
          // The most recently completed milestone — the last real ✓ in the
          // sequence, not the final step in the list (which usually isn't
          // complete at all). This is what gets the pulse: "this is where
          // things currently stand," the standard meaning for this kind of
          // indicator, distinct from the literal last item in the array.
          const isMostRecentlyCompleted = step.complete && !progress.data!.steps[i + 1]?.complete;
          return (
            <div key={step.key} style={{ display: 'flex', alignItems: 'flex-start', flex: i < progress.data!.steps.length - 1 ? 1 : undefined }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 84 }}>
                <div
                  style={{
                    width: 30, height: 30, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, fontWeight: 700, flexShrink: 0, position: 'relative',
                    background: step.complete ? 'var(--heading-color)' : 'var(--surface)',
                    color: step.complete ? '#fff' : 'var(--ink-soft)',
                    border: step.complete ? 'none' : '1px solid var(--line)',
                    animation: isMostRecentlyCompleted ? 'milestone-pulse 2s ease-out infinite' : undefined,
                  }}
                >
                  {step.complete ? '✓' : i + 1}
                </div>
                <div style={{ fontSize: 11, textAlign: 'center', marginTop: 6, color: step.complete ? 'var(--ink)' : 'var(--ink-soft)', fontWeight: step.complete ? 600 : 400, maxWidth: 90 }}>
                  {step.label}
                </div>
              </div>
              {i < progress.data!.steps.length - 1 && (
                <div style={{ height: 1, flex: 1, background: 'var(--line)', marginTop: 15, minWidth: 16 }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
