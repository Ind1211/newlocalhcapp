import { useRef, useState } from 'react';
import { useBulkImportPatients } from '../hooks/useApi';

const SAMPLE_CSV = `name,dob,mrn,clinical_programs,payor_name,member_id,group_number,eligibility_status,phone_number,email,address_line1,city,state,zip_code,preferred_contact_method,preferred_language,risk_level
Jane Doe,1975-04-12,,kidney,Aetna,AET100200,GRP01,active,555-0100,jane@example.com,123 Main St,Springfield,IL,62701,phone,English,medium
John Smith,1968-09-30,,kidney;cardiology,UnitedHealth,UHC300400,GRP02,pending,555-0200,john@example.com,456 Oak Ave,Springfield,IL,62702,email,Spanish,high`;

export function BulkImportPatients({ onBack }: { onBack: () => void }) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const bulkImport = useBulkImportPatients();

  const handleFile = (file: File) => {
    setSelectedFile(file);
  };

  const handleDownloadSample = () => {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample-patients.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back to patients
      </a>
      <h1 style={{ margin: '16px 0 4px' }}>Bulk Import Patients</h1>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0, marginBottom: 20 }}>
        Upload a CSV to add many patients at once. Each row goes through the exact
        same setup as adding one manually — a mandatory intake gets auto-assigned
        for every patient created this way, and any clinical programs listed get
        attached for real, not just as a label.
      </p>

      <div className="field-group">
        <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--ink-soft)', marginBottom: 10 }}>
          CSV format
        </div>
        <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0 }}>
          Required column: <code>name</code>. Optional: <code>dob</code> (YYYY-MM-DD),{' '}
          <code>mrn</code> (auto-generated if blank), <code>clinical_programs</code>{' '}
          (semicolon-separated program keys, e.g. <code>kidney;cardiology</code>),{' '}
          <code>payor_name</code>, <code>member_id</code>, <code>group_number</code>,{' '}
          <code>eligibility_status</code>, <code>phone_number</code>, <code>email</code>,{' '}
          <code>address_line1</code>, <code>city</code>, <code>state</code>, <code>zip_code</code>,{' '}
          <code>preferred_contact_method</code> (phone/email/portal/mail),{' '}
          <code>preferred_language</code>, and <code>risk_level</code> (low/medium/high/critical).
        </p>
        <button className="btn" onClick={handleDownloadSample}>
          Download sample CSV
        </button>
      </div>

      <div className="field-group">
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const file = e.dataTransfer.files?.[0];
            if (file) handleFile(file);
          }}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: '2px dashed var(--line)', borderRadius: 10, padding: 24, textAlign: 'center', cursor: 'pointer',
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            {selectedFile ? selectedFile.name : 'Drag and drop a .csv file here'}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 4 }}>
            or <span style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'underline' }}>click to browse</span>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />

        <button
          className="btn btn-primary"
          style={{ marginTop: 14 }}
          disabled={!selectedFile || bulkImport.isPending}
          onClick={() => selectedFile && bulkImport.mutate(selectedFile)}
        >
          {bulkImport.isPending ? 'Importing…' : 'Import Patients'}
        </button>
      </div>

      {bulkImport.isError && (
        <div className="result-card critical">
          <div className="result-headline">{(bulkImport.error as Error).message}</div>
        </div>
      )}

      {bulkImport.isSuccess && (
        <div className={`result-card ${bulkImport.data.error_count > 0 ? 'warning' : 'good'}`}>
          <div className="result-headline">
            {bulkImport.data.created_count} patient{bulkImport.data.created_count === 1 ? '' : 's'} created
            {bulkImport.data.error_count > 0 ? `, ${bulkImport.data.error_count} row(s) failed` : ''}.
          </div>
          {bulkImport.data.created.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Created</div>
              <ul style={{ fontSize: 13, margin: '6px 0 0', paddingLeft: 18 }}>
                {bulkImport.data.created.map((c) => (
                  <li key={c.row}>{c.name} — {c.mrn}</li>
                ))}
              </ul>
            </div>
          )}
          {bulkImport.data.errors.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Failed rows</div>
              <ul style={{ fontSize: 13, margin: '6px 0 0', paddingLeft: 18 }}>
                {bulkImport.data.errors.map((e) => (
                  <li key={e.row}>Row {e.row} ({e.name || 'no name'}): {e.error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
