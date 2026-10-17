// These deliberately mirror app/schemas.py field-for-field. Keeping them in sync by
// hand is the tradeoff of not sharing a single language across the stack — worth
// naming directly rather than pretending this file updates itself.

export interface Program {
  id: number;
  key: string;
  label: string;
  icon: string | null;
}

export interface FieldOption {
  value: string;
  label: string;
}

export interface FieldDef {
  name: string;
  label: string;
  // 'dropdown' is a genuinely different type from 'select' in the source data — not
  // just a naming variant. Its options are plain strings, not {value,label} objects.
  // This is the exact same mismatch that regressed twice in the original JS build;
  // FieldRenderer handles both shapes explicitly rather than assuming one.
  type: 'pill' | 'number' | 'select' | 'checkboxgroup' | 'text' | 'textarea' | 'scale' | 'dropdown' | 'date';
  options?: FieldOption[] | string[];
  unit?: string;
  placeholder?: string;
  required?: boolean;
  show_only_if?: { field: string; equals?: string; includes?: string } | null;
}

export interface StepDef {
  id: string;
  title: string;
  fields: FieldDef[];
}

export interface AssessmentDefinition {
  id: string;
  key: string;
  title: string;
  category: string;
  program_id: number;
  kind: string;
  interaction: string;
  blurb: string | null;
  is_builtin: boolean;
  active_version: number;
  fields?: { fields: FieldDef[] | null; steps: StepDef[] | null } | null;
}

export interface StaffBrief {
  id: string;
  name: string;
  role: string;
}

export interface CareNote {
  id: string;
  patient_id: string;
  author: StaffBrief | null;
  content: string;
  created_at: string;
}

export interface Task {
  id: string;
  patient_id: string;
  title: string;
  description: string | null;
  assigned_to: StaffBrief | null;
  created_by: StaffBrief | null;
  due_date: string | null;
  status: 'pending' | 'in_progress' | 'completed';
  source_rule_name: string | null;
  created_at: string;
}

export interface Intervention {
  id: string;
  goal_id: string;
  description: string;
  status: 'planned' | 'in_progress' | 'done';
  created_at: string;
}

export interface Goal {
  id: string;
  problem_id: string;
  description: string;
  target_date: string | null;
  status: 'active' | 'met' | 'not_met';
  source_rule_name: string | null;
  created_at: string;
  interventions: Intervention[];
}

export interface Problem {
  id: string;
  patient_id: string;
  description: string;
  status: 'active' | 'resolved';
  created_at: string;
  goals: Goal[];
}

export interface OnboardingStep {
  key: string;
  label: string;
  complete: boolean;
}

export interface OnboardingProgress {
  steps: OnboardingStep[];
  program_status: string;
}

export interface Staff {
  id: string;
  name: string;
  email: string | null;
  role: 'care_manager' | 'nurse' | 'provider' | 'admin';
  status: string;
  created_at: string;
}

export interface PatientStaffAssignment {
  id: string;
  staff: Staff;
  role_on_patient: string;
  assigned_at: string;
}

export interface PatientDocument {
  id: string;
  patient_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  extraction_status: 'pending' | 'ok' | 'failed';
  extraction_error: string | null;
  uploaded_by: string | null;
  source: 'upload' | 'voice_note';
  uploaded_at: string;
}

export interface PatientDocumentDetail extends PatientDocument {
  extracted_text: string | null;
}

export interface ClinicalProgram {
  key: string;
  label: string;
  icon: string | null;
}

export interface Patient {
  id: string;
  internal_label: string | null;
  name: string | null;
  dob: string | null;
  mrn: string | null;
  care_pathway: string | null;
  clinical_programs: ClinicalProgram[];
  payor_name: string | null;
  member_id: string | null;
  group_number: string | null;
  eligibility_status: string | null;
  eligibility_verified_at: string | null;
  phone_number: string | null;
  email: string | null;
  address_line1: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  preferred_contact_method: 'phone' | 'email' | 'portal' | 'mail' | null;
  preferred_language: string | null;
  risk_level: 'low' | 'medium' | 'high' | 'critical' | null;
  last_contact_date: string | null;
  is_active: boolean;
  deactivated_reason: string | null;
  created_at: string;
  // Was missing entirely before this — meaning optimistic locking (built and
  // tested on the backend) had no way to actually work from the frontend at
  // all, since there was nothing here to capture and send back as the version
  // token. Two people editing the same patient at once were still silently
  // overwriting each other despite the backend-side protection existing.
  updated_at: string;
  care_team: StaffBrief[];
  assessments_completed: number;
  assessments_total: number;
  open_tasks_count: number;
}

export interface AuditLogEntry {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  performed_by: string | null;
  details: Record<string, unknown> | null;
  performed_at: string;
}

export interface Notification {
  id: string;
  type: 'task_assigned' | 'task_due_soon' | 'assessment_overdue' | 'business_rule';
  title: string;
  body: string;
  related_patient_id: string | null;
  related_entity_id: string | null;
  source_rule_name: string | null;
  is_read: boolean;
  email_sent: boolean;
  created_at: string;
}

export interface PatientAssessmentSummary {
  assigned_assessment_id: string;
  assessment_definition_key: string;
  title: string;
  source: string;
  mandatory: boolean;
  scheduled_date: string | null;
  status: 'Scheduled' | 'In Progress' | 'Completed';
  draft_answers: Record<string, unknown> | null;
  result_id: string | null;
  result_headline: string | null;
  result_severity: string | null;
}

export interface Case {
  id: string;
  patient_id: string;
  label: string | null;
  context: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

// Extracted directly from the checkpoint's snapshotFieldMeta() — same 16 fields,
// same grouping, same units. This is what gets filled once and prefilled everywhere.
export interface SnapshotFieldMeta {
  key: string;
  label: string;
  unit?: string;
  program: 'general' | 'kidney' | 'cardiology';
}

export const SNAPSHOT_FIELD_META: SnapshotFieldMeta[] = [
  { key: 'age', label: 'Age', unit: 'yrs', program: 'general' },
  { key: 'sex', label: 'Sex', program: 'general' },
  { key: 'heightCm', label: 'Height', unit: 'cm', program: 'general' },
  { key: 'weightKg', label: 'Weight', unit: 'kg', program: 'general' },
  { key: 'sbp', label: 'SBP', unit: 'mmHg', program: 'general' },
  { key: 'dbp', label: 'DBP', unit: 'mmHg', program: 'general' },
  { key: 'egfr', label: 'eGFR', unit: 'mL/min', program: 'kidney' },
  { key: 'acr', label: 'ACR', unit: 'mg/g', program: 'kidney' },
  { key: 'creatinine', label: 'Creatinine', unit: 'mg/dL', program: 'kidney' },
  { key: 'hemoglobin', label: 'Hemoglobin', unit: 'g/dL', program: 'kidney' },
  { key: 'potassium', label: 'Potassium', unit: 'mmol/L', program: 'kidney' },
  { key: 'bicarbonate', label: 'Bicarbonate', unit: 'mmol/L', program: 'kidney' },
  { key: 'ejectionFraction', label: 'Ejection fraction', unit: '%', program: 'cardiology' },
  { key: 'troponin', label: 'Troponin', unit: 'ng/mL', program: 'cardiology' },
  { key: 'bnp', label: 'BNP', unit: 'pg/mL', program: 'cardiology' },
  { key: 'ldl', label: 'LDL cholesterol', unit: 'mg/dL', program: 'cardiology' },
];

// Mirrors prefillFromSnapshot() exactly: only fills a field if the assessment's own
// answers don't already have a value for it — never overwrites something the user
// already entered.
export function prefillFromSnapshot(
  context: Record<string, string> | null | undefined,
  answers: Record<string, unknown>
): Record<string, unknown> {
  if (!context) return answers;
  const result = { ...answers };
  for (const field of SNAPSHOT_FIELD_META) {
    const val = context[field.key];
    const existing = result[field.key];
    if (val !== undefined && val !== '' && (existing === undefined || existing === '')) {
      result[field.key] = val;
    }
  }
  return result;
}

export type Severity = 'good' | 'caution' | 'warning' | 'critical';

export interface ResultMetric {
  label: string;
  value: number | string;
  unit?: string;
}

export interface ResultFlag {
  text: string;
  severity: Severity;
}

export interface SuggestedPathwayItem {
  moduleId: string;
  mandatory: boolean;
  priority: number;
  reasons: string[];
}

export interface ComputedResult {
  headline: string;
  headlineSeverity: Severity;
  metrics: ResultMetric[];
  flags: ResultFlag[];
  notes: string;
  // Only present on basic_intake's result — everything else leaves this undefined.
  suggestedPathway?: SuggestedPathwayItem[];
}

export interface CarePlan {
  stageSummary: string;
  redFlags: string[];
  referral: { needed: boolean; urgency: 'routine' | 'soon' | 'urgent'; reason: string };
  monitoring: { frequency: string; labsToTrend: string[] };
  medications: string[];
  lifestyle: string[];
  patientEducation: string[];
  caveats: string;
  suggestedAssessments: string[];
}

export interface IntegratedCarePlan {
  summary: string;
  keyFindings: string[];
  actionItems: { text: string; priority: 'high' | 'medium' | 'low' }[];
  caveats: string;
}

export interface SuggestedPgiIntervention {
  description: string;
}
export interface SuggestedPgiGoal {
  description: string;
  interventions: string[];
}
export interface SuggestedPgiProblem {
  description: string;
  goals: SuggestedPgiGoal[];
}
export interface SuggestedPgi {
  problems: SuggestedPgiProblem[];
}

export interface IntegratedCarePlanResponse {
  completedCount: number;
  documentCount: number;
  carePlan: IntegratedCarePlan;
  suggestedPgi: SuggestedPgi;
}

export interface CarePlanResponse {
  staging: ComputedResult;
  carePlan: CarePlan;
}

export interface AssessmentResult {
  id: string;
  case_id: string;
  assessment_definition_id: string;
  version_used: number;
  answers: Record<string, unknown>;
  result: ComputedResult;
  completed_at: string;
}

export type ConditionNode =
  | { type: 'cmp'; left: string; op: string; right: string }
  | { type: 'and' | 'or'; left: ConditionNode; right: ConditionNode }
  | { type: 'not'; child: ConditionNode };

export interface RuleAction {
  type: 'CREATE_TASK' | 'UPDATE_STATUS' | 'ADD_GOAL' | 'SEND_NOTIFICATION' | 'TRANSITION' | 'ESCALATE_RISK';
  [key: string]: string;
}

export interface BusinessRule {
  id: string;
  name: string;
  trigger: string;
  dsl_text: string;
  condition_tree: ConditionNode;
  actions: RuleAction[];
  governance: 'clinical' | 'operational';
  enabled: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface RuleTestResult {
  name: string;
  trigger: string;
  condition_result: boolean;
  actions: { action: RuleAction; summary: string }[];
}

export interface RuleFireResult {
  trigger: string;
  rules_checked: number;
  rules_matched: number;
  fired: { rule_id: string; rule_name: string; actions: { action: RuleAction; summary: string }[] }[];
}

export interface RuleExecutionLogEntry {
  id: string;
  rule_id: string | null;
  rule_name: string | null;
  trigger: string;
  patient_id: string | null;
  event_payload: Record<string, unknown>;
  matched: boolean;
  actions_executed: string[] | null;
  performed_at: string;
}
