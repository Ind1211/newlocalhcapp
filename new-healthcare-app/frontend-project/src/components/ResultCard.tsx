import type { ComputedResult } from '../types';

export function ResultCard({ result }: { result: ComputedResult }) {
  return (
    <div className={`result-card ${result.headlineSeverity}`}>
      <div className="result-headline">{result.headline}</div>

      {result.metrics.length > 0 && (
        <div className="result-metrics">
          {result.metrics.map((m) => (
            <div className="result-metric" key={m.label}>
              <div className="k">{m.label}</div>
              <div className="v">
                {m.value}
                {m.unit ? ` ${m.unit}` : ''}
              </div>
            </div>
          ))}
        </div>
      )}

      {result.flags.length > 0 && (
        <ul className="result-flags">
          {result.flags.map((f, i) => (
            <li key={i}>{f.text}</li>
          ))}
        </ul>
      )}

      {result.notes && <div className="result-notes">{result.notes}</div>}
    </div>
  );
}
