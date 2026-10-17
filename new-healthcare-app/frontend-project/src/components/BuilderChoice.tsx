export function BuilderChoice({
  onChooseForm,
  onChooseUpload,
  onBack,
}: {
  onChooseForm: () => void;
  onChooseUpload: () => void;
  onBack: () => void;
}) {
  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back
      </a>
      <h1 style={{ margin: '16px 0 4px' }}>Build a custom assessment</h1>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0, marginBottom: 20 }}>
        Two ways to define one — pick whichever fits how you already work. It will show up
        under "Custom" in every case.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
        <button className="assessment-card" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={onChooseForm}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
            <div className="title">Build with a form</div>
            <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 99, background: 'var(--accent-tint)', color: 'var(--accent)', whiteSpace: 'nowrap' }}>
              Guided
            </span>
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 8 }}>
            Add questions one at a time — group them into sections, choose from several field
            types, set up "show only if" logic, and see a live preview as you go. Best if you're
            starting from scratch.
          </div>
        </button>

        <button className="assessment-card" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={onChooseUpload}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
            <div className="title">Upload or paste a template</div>
            <span style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 8px', borderRadius: 99, background: 'var(--caution-tint)', color: 'var(--caution)', whiteSpace: 'nowrap' }}>
              JSON
            </span>
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 8 }}>
            Already have a structured template — from another system, a colleague, or written
            by hand? Drop in the JSON and we'll validate, normalize, and preview it. Best if
            you're porting something that already exists.
          </div>
        </button>
      </div>
    </div>
  );
}
