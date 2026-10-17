import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { AssessmentDefinition, AssessmentResult, AuditLogEntry, BusinessRule, CareNote, Case, CarePlanResponse, Goal, IntegratedCarePlan, IntegratedCarePlanResponse, Intervention, Notification, OnboardingProgress, Patient, PatientAssessmentSummary, PatientDocument, PatientDocumentDetail, PatientStaffAssignment, Problem, Program, RuleExecutionLogEntry, RuleFireResult, RuleTestResult, Staff, SuggestedPgi, Task } from '../types';

export function usePrograms() {
  return useQuery({
    queryKey: ['programs'],
    queryFn: () => api.get<Program[]>('/api/programs'),
  });
}

export interface QuestionLibraryItem {
  id: string;
  category: string;
  program_id: number | null;
  label: string;
  field_type: string;
  options: { value: string; label: string }[] | string[] | null;
}

export function useQuestionLibrary(programKey: string | null) {
  return useQuery({
    queryKey: ['question-library', programKey],
    queryFn: () =>
      api.get<QuestionLibraryItem[]>(
        programKey ? `/api/question-library?program=${programKey}` : '/api/question-library'
      ),
  });
}

export function useAssessments(programKey: string | null) {
  return useQuery({
    queryKey: ['assessments', programKey],
    queryFn: () =>
      api.get<AssessmentDefinition[]>(
        programKey ? `/api/assessments?program=${programKey}` : '/api/assessments'
      ),
  });
}

export function useAssessmentDetail(key: string | null, patientId?: string | null) {
  return useQuery({
    queryKey: ['assessment-detail', key, patientId],
    queryFn: () =>
      api.get<AssessmentDefinition>(
        `/api/assessments/${key}${patientId ? `?patient_id=${patientId}` : ''}`
      ),
    enabled: !!key,
  });
}

export function useCase(caseId: string | null) {
  return useQuery({
    queryKey: ['case', caseId],
    queryFn: () => api.get<Case>(`/api/cases/${caseId}`),
    enabled: !!caseId,
  });
}

export function useUpdateCaseContext(caseId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (context: Record<string, string>) => {
      if (!caseId) throw new Error('No active case.');
      return api.patch<Case>(`/api/cases/${caseId}/context`, { context });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    },
  });
}

export interface PaginatedPatients {
  items: Patient[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function usePatients(
  search: string,
  page: number = 1,
  includeInactive: boolean = false,
  sortBy: string = 'created_at',
  sortOrder: 'asc' | 'desc' = 'desc',
  eligibilityStatus?: string,
  programStatus?: string,
  careTeamStaffId?: string,
  riskLevel?: string,
) {
  return useQuery({
    queryKey: ['patients', search, page, includeInactive, sortBy, sortOrder, eligibilityStatus, programStatus, careTeamStaffId, riskLevel],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      params.set('page', String(page));
      if (includeInactive) params.set('include_inactive', 'true');
      params.set('sort_by', sortBy);
      params.set('sort_order', sortOrder);
      if (eligibilityStatus) params.set('eligibility_status', eligibilityStatus);
      if (programStatus) params.set('program_status', programStatus);
      if (careTeamStaffId) params.set('care_team_staff_id', careTeamStaffId);
      if (riskLevel) params.set('risk_level', riskLevel);
      return api.get<PaginatedPatients>(`/api/patients?${params.toString()}`);
    },
  });
}

export function usePatient(patientId: string | null) {
  return useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => api.get<Patient>(`/api/patients/${patientId}`),
    enabled: !!patientId,
  });
}

export function useLogContact(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contactDate?: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<Patient>(`/api/patients/${patientId}/log-contact`, { contact_date: contactDate });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] });
    },
  });
}

export function useDeactivatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ patientId, reason }: { patientId: string; reason?: string }) =>
      api.post<Patient>(`/api/patients/${patientId}/deactivate`, { reason }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] }),
  });
}

export function useReactivatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patientId: string) => api.post<Patient>(`/api/patients/${patientId}/reactivate`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] }),
  });
}

export function useCompleteProgram(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<Patient>(`/api/patients/${patientId}/complete-program`, {});
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['onboarding-progress', patientId] });
    },
  });
}

export function useReopenProgram(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<Patient>(`/api/patients/${patientId}/reopen-program`, {});
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['onboarding-progress', patientId] });
    },
  });
}

export function usePatientAuditLog(patientId: string | null) {
  return useQuery({
    queryKey: ['audit-log', patientId],
    queryFn: () => api.get<AuditLogEntry[]>(`/api/patients/${patientId}/audit-log`),
    enabled: !!patientId,
  });
}

export function usePatientAssessments(patientId: string | null) {
  return useQuery({
    queryKey: ['patient-assessments', patientId],
    queryFn: () => api.get<PatientAssessmentSummary[]>(`/api/patients/${patientId}/assessments`),
    enabled: !!patientId,
  });
}

export function usePatientCase(patientId: string | null) {
  return useQuery({
    queryKey: ['patient-case', patientId],
    queryFn: () => api.get<{ id: string; context: Record<string, string> | null }>(`/api/patients/${patientId}/case`),
    enabled: !!patientId,
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name: string;
      dob?: string;
      mrn?: string;
      clinical_program_keys?: string[];
      payor_name?: string;
      member_id?: string;
      group_number?: string;
      eligibility_status?: string;
      phone_number?: string;
      email?: string;
      address_line1?: string;
      city?: string;
      state?: string;
      zip_code?: string;
      preferred_contact_method?: string;
      preferred_language?: string;
      risk_level?: string;
    }) => api.post<Patient>('/api/patients', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
}

export function useUpdatePatient(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      name?: string;
      dob?: string;
      clinical_program_keys?: string[];
      payor_name?: string;
      member_id?: string;
      group_number?: string;
      eligibility_status?: string;
      phone_number?: string;
      email?: string;
      address_line1?: string;
      city?: string;
      state?: string;
      zip_code?: string;
      preferred_contact_method?: string;
      preferred_language?: string;
      risk_level?: string;
      expected_updated_at?: string;
    }) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.patch<Patient>(`/api/patients/${patientId}`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] });
      queryClient.invalidateQueries({ queryKey: ['onboarding-progress', patientId] });
    },
  });
}

export interface BulkImportResult {
  created: { row: number; name: string; mrn: string }[];
  errors: { row: number; name: string | null; error: string }[];
  created_count: number;
  error_count: number;
}

export function usePatientDocuments(patientId: string | null) {
  return useQuery({
    queryKey: ['patient-documents', patientId],
    queryFn: () => api.get<PatientDocument[]>(`/api/patients/${patientId}/documents`),
    enabled: !!patientId,
  });
}

export function useUploadDocument(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      if (!patientId) throw new Error('No patient selected.');
      const formData = new FormData();
      formData.append('file', file);
      return api.postFile<PatientDocument>(`/api/patients/${patientId}/documents`, formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-documents', patientId] });
    },
  });
}

export function useCreateVoiceNote(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<PatientDocumentDetail>(`/api/patients/${patientId}/voice-notes`, { text });
    },
    onSuccess: () => {
      // Same query key as regular document uploads — a voice note IS a real
      // PatientDocument row from this point on, so the existing Documents tab
      // (and anything else reading this list) picks it up automatically.
      queryClient.invalidateQueries({ queryKey: ['patient-documents', patientId] });
    },
  });
}

export function useUpdateVoiceNote(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ documentId, text }: { documentId: string; text: string }) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.patch<PatientDocumentDetail>(`/api/patients/${patientId}/voice-notes/${documentId}`, { text });
    },
    onSuccess: (_, { documentId }) => {
      queryClient.invalidateQueries({ queryKey: ['patient-documents', patientId] });
      queryClient.invalidateQueries({ queryKey: ['document-detail', patientId, documentId] });
    },
  });
}

export function useDeleteDocument(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.delete(`/api/patients/${patientId}/documents/${documentId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-documents', patientId] });
    },
  });
}

export function useDocumentDetail(patientId: string | null, documentId: string | null) {
  return useQuery({
    queryKey: ['document-detail', patientId, documentId],
    queryFn: () => api.get<PatientDocumentDetail>(`/api/patients/${patientId}/documents/${documentId}`),
    enabled: !!patientId && !!documentId,
  });
}

export function useRetryExtraction(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<PatientDocumentDetail>(`/api/patients/${patientId}/documents/${documentId}/retry-extraction`, {});
    },
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: ['patient-documents', patientId] });
      queryClient.invalidateQueries({ queryKey: ['document-detail', patientId, documentId] });
    },
  });
}

export interface AutoFillSuggestion {
  value: string;
  source: string;
}

export function useAutoFillFromDocuments(patientId: string | null) {
  return useMutation({
    mutationFn: (assessmentDefinitionKey: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<{ suggestions: Record<string, AutoFillSuggestion> }>(
        `/api/patients/${patientId}/documents/auto-fill?assessment_definition_key=${assessmentDefinitionKey}`,
        {}
      );
    },
  });
}

export function useOnboardingProgress(patientId: string | null) {
  return useQuery({
    queryKey: ['onboarding-progress', patientId],
    queryFn: () => api.get<OnboardingProgress>(`/api/patients/${patientId}/onboarding-progress`),
    enabled: !!patientId,
  });
}

export function usePatientCareNotes(patientId: string | null) {
  return useQuery({
    queryKey: ['care-notes', patientId],
    queryFn: () => api.get<CareNote[]>(`/api/patients/${patientId}/care-notes`),
    enabled: !!patientId,
  });
}

export function useCreateCareNote(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<CareNote>(`/api/patients/${patientId}/care-notes`, { content });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['care-notes', patientId] }),
  });
}

export function useDeleteCareNote(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.delete(`/api/patients/${patientId}/care-notes/${noteId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['care-notes', patientId] }),
  });
}

export function usePatientTasks(patientId: string | null) {
  return useQuery({
    queryKey: ['tasks', patientId],
    queryFn: () => api.get<Task[]>(`/api/patients/${patientId}/tasks`),
    enabled: !!patientId,
  });
}

export function useCreateTask(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { title: string; description?: string; assigned_to_id?: string; due_date?: string }) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<Task>(`/api/patients/${patientId}/tasks`, payload);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks', patientId] }),
  });
}

export function useUpdateTaskStatus(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: string }) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.patch<Task>(`/api/patients/${patientId}/tasks/${taskId}`, { status });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks', patientId] }),
  });
}

export function useDeleteTask(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.delete(`/api/patients/${patientId}/tasks/${taskId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks', patientId] }),
  });
}

export function usePatientPgi(patientId: string | null) {
  return useQuery({
    queryKey: ['pgi', patientId],
    queryFn: () => api.get<Problem[]>(`/api/patients/${patientId}/pgi`),
    enabled: !!patientId,
  });
}

export function useCreateProblem(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (description: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<Problem>(`/api/patients/${patientId}/pgi`, { description });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pgi', patientId] }),
  });
}

export function useResolveProblem(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (problemId: string) => api.patch<Problem>(`/api/pgi/problems/${problemId}/resolve`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pgi', patientId] }),
  });
}

export function useCreateGoal(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ problemId, description, targetDate }: { problemId: string; description: string; targetDate?: string }) =>
      api.post<Goal>(`/api/pgi/problems/${problemId}/goals`, { description, target_date: targetDate }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pgi', patientId] }),
  });
}

export function useUpdateGoalStatus(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, status }: { goalId: string; status: string }) =>
      api.patch<Goal>(`/api/pgi/goals/${goalId}/status?status=${status}`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pgi', patientId] }),
  });
}

export function useCreateIntervention(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, description }: { goalId: string; description: string }) =>
      api.post<Intervention>(`/api/pgi/goals/${goalId}/interventions`, { description }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pgi', patientId] }),
  });
}

export function useUpdateInterventionStatus(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ interventionId, status }: { interventionId: string; status: string }) =>
      api.patch<Intervention>(`/api/pgi/interventions/${interventionId}/status?status=${status}`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pgi', patientId] }),
  });
}

export function useMyStaffRecord() {
  return useQuery({
    queryKey: ['my-staff-record'],
    queryFn: () => api.get<Staff | null>('/api/staff/me'),
  });
}

export function useStaffList() {
  return useQuery({
    queryKey: ['staff'],
    queryFn: () => api.get<Staff[]>('/api/staff'),
  });
}

export function useCreateStaff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { auth0_sub: string; name: string; email?: string; role: string }) =>
      api.post<Staff>('/api/staff', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
  });
}

export interface Auth0LookupResult {
  found: boolean;
  auth0_sub?: string;
  name?: string;
  email?: string;
  already_linked?: boolean;
  already_linked_status?: string | null;
}

export function useAuth0Lookup() {
  return useMutation({
    mutationFn: (email: string) => api.get<Auth0LookupResult>(`/api/staff/auth0-lookup?email=${encodeURIComponent(email)}`),
  });
}

export interface InviteStaffResult {
  staff: Staff;
  email_sent: boolean;
  email_error: string | null;
}

export function useInviteStaff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; email: string; role: string }) =>
      api.post<InviteStaffResult>('/api/staff/invite', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
  });
}

export function useUpdateStaff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ staffId, payload }: { staffId: string; payload: { name?: string; email?: string; role?: string } }) =>
      api.patch<Staff>(`/api/staff/${staffId}`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
  });
}

export function useDeactivateStaff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (staffId: string) => api.post<Staff>(`/api/staff/${staffId}/deactivate`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['staff'] }),
  });
}

export function useReactivateStaff() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (staffId: string) => api.post<Staff>(`/api/staff/${staffId}/reactivate`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['staff'] }),
  });
}

export function useResendInvite() {
  return useMutation({
    mutationFn: (staffId: string) => api.post<{ email_sent: boolean }>(`/api/staff/${staffId}/resend-invite`, {}),
  });
}

export function usePatientStaffAssignments(patientId: string | null) {
  return useQuery({
    queryKey: ['patient-staff', patientId],
    queryFn: () => api.get<PatientStaffAssignment[]>(`/api/staff/patients/${patientId}/assignments`),
    enabled: !!patientId,
  });
}

export function useAssignStaff(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { staff_id: string; role_on_patient: string }) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<PatientStaffAssignment>(`/api/staff/patients/${patientId}/assignments`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-staff', patientId] });
    },
  });
}

export function useRemoveStaffAssignment(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.delete(`/api/staff/patients/${patientId}/assignments/${assignmentId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-staff', patientId] });
    },
  });
}

export function useBulkImportPatients() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.postFile<BulkImportResult>('/api/patients/bulk-import', formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
}

export function useLatestResult(caseId: string | null, assessmentDefinitionKey: string | null) {
  return useQuery({
    queryKey: ['latest-result', caseId, assessmentDefinitionKey],
    queryFn: () =>
      api.get<{ answers: Record<string, unknown>; completed_at: string } | null>(
        `/api/cases/${caseId}/results/latest?assessment_definition_key=${assessmentDefinitionKey}`
      ),
    enabled: !!caseId && !!assessmentDefinitionKey,
  });
}

export function useResult(resultId: string | null) {
  return useQuery({
    queryKey: ['result', resultId],
    queryFn: () => api.get<AssessmentResult>(`/api/results/${resultId}`),
    enabled: !!resultId,
  });
}

export function useGenerateIntegratedCarePlan(patientId: string | null) {
  return useMutation({
    mutationFn: () => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<IntegratedCarePlanResponse>(`/api/patients/${patientId}/integrated-care-plan`, {});
    },
  });
}

export function useSuggestPgiFromPlan(patientId: string | null) {
  return useMutation({
    mutationFn: (plan: IntegratedCarePlan) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<{ suggestedPgi: SuggestedPgi }>(`/api/patients/${patientId}/suggest-pgi-from-plan`, plan);
    },
  });
}

export function useConfirmPathway(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: { module_id: string; mandatory: boolean }[]) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post<{ assigned: number }>(`/api/patients/${patientId}/confirm-pathway`, { items });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-assessments', patientId] });
    },
  });
}

export function useSaveDraft(patientId: string | null, assignedAssessmentId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (answers: Record<string, unknown>) => {
      if (!patientId || !assignedAssessmentId) throw new Error('Missing patient or assessment.');
      return api.patch(`/api/patients/${patientId}/assigned-assessments/${assignedAssessmentId}/draft`, { answers });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-assessments', patientId] });
    },
  });
}

export function useAssignAssessment(patientId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { assessment_definition_key: string; title_override?: string; source: string; scheduled_date?: string; mandatory?: boolean }) => {
      if (!patientId) throw new Error('No patient selected.');
      return api.post(`/api/patients/${patientId}/assign-assessment`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-assessments', patientId] });
    },
  });
}

export function useGenerateCarePlan(caseId: string | null) {
  return useMutation({
    mutationFn: (answers: Record<string, unknown>) => {
      if (!caseId) throw new Error('No active case.');
      return api.post<CarePlanResponse>(`/api/cases/${caseId}/ckd-care-plan`, { answers });
    },
  });
}

export function useSubmitResult(caseId: string | null, patientId?: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { assessment_definition_key: string; answers: Record<string, unknown> }) => {
      if (!caseId) throw new Error('No active case — create one first.');
      return api.post<AssessmentResult>(`/api/cases/${caseId}/results`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case-results', caseId] });
      // A submitted result can trigger the rules engine — escalating risk,
      // creating a task, sending a notification, all server-side, in the
      // same request. Without invalidating these too, the risk badge and
      // notifications only ever updated on a navigation remount or manual
      // refresh (whatever happened to force a fresh fetch), not
      // immediately when the actual change happened.
      if (patientId) {
        queryClient.invalidateQueries({ queryKey: ['patient', patientId] });
        queryClient.invalidateQueries({ queryKey: ['tasks', patientId] });
        queryClient.invalidateQueries({ queryKey: ['rule-execution-log', patientId] });
      }
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
    },
  });
}

export function useNotifications(unreadOnly: boolean = false) {
  return useQuery({
    queryKey: ['notifications', unreadOnly],
    queryFn: () => api.get<Notification[]>(`/api/notifications${unreadOnly ? '?unread_only=true' : ''}`),
    refetchInterval: 60_000, // a real, working "check periodically while the app is open" mechanism — no push infrastructure exists, so polling is the honest, working substitute
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => api.get<{ count: number }>('/api/notifications/unread-count'),
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: string) => api.patch<Notification>(`/api/notifications/${notificationId}/read`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
    },
  });
}

export function useMarkAllRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/api/notifications/mark-all-read', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
    },
  });
}

export function useCheckDueNotifications() {
  return useMutation({
    mutationFn: () => api.post<{ notifications_created: number }>('/api/notifications/check-due', {}),
  });
}

export function useBusinessRules() {
  return useQuery({
    queryKey: ['business-rules'],
    queryFn: () => api.get<BusinessRule[]>('/api/business-rules'),
  });
}

export function useCreateBusinessRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { dsl_text: string; governance: string }) =>
      api.post<BusinessRule>('/api/business-rules', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['business-rules'] }),
  });
}

export function useEditBusinessRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, dsl_text, governance }: { ruleId: string; dsl_text: string; governance: string }) =>
      api.patch<BusinessRule>(`/api/business-rules/${ruleId}`, { dsl_text, governance }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['business-rules'] }),
  });
}

export function useEnableBusinessRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, confirmed }: { ruleId: string; confirmed: boolean }) =>
      api.patch<BusinessRule>(`/api/business-rules/${ruleId}/enable`, { confirmed }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['business-rules'] }),
  });
}

export function useDisableBusinessRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) => api.patch<BusinessRule>(`/api/business-rules/${ruleId}/disable`, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['business-rules'] }),
  });
}

export function useDeleteBusinessRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) => api.delete(`/api/business-rules/${ruleId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['business-rules'] }),
  });
}

export function useTestRuleInIsolation() {
  return useMutation({
    mutationFn: (payload: { dsl_text: string; tenant?: object; event?: object; state?: object; patient_id?: string }) =>
      api.post<RuleTestResult>('/api/business-rules/test', payload),
  });
}

export function useFireEventManually() {
  return useMutation({
    mutationFn: (payload: { trigger: string; tenant?: object; event?: object; state?: object; patient_id: string; dry_run: boolean }) =>
      api.post<RuleFireResult>('/api/business-rules/fire-event', payload),
  });
}

export function useRuleExecutionLog(patientId?: string) {
  return useQuery({
    queryKey: ['rule-execution-log', patientId],
    queryFn: () => {
      const params = patientId ? `?patient_id=${patientId}` : '';
      return api.get<RuleExecutionLogEntry[]>(`/api/business-rules/execution-log${params}`);
    },
  });
}
