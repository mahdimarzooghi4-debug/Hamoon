import { requestJson } from "./client";

export type EvidenceType =
  | "DOCUMENT"
  | "IMAGE"
  | "PROVIDER_REPORT"
  | "ASSESSMENT_ATTACHMENT"
  | "OTHER";

export type EvidenceSensitivity =
  | "INTERNAL"
  | "CONFIDENTIAL"
  | "SENSITIVE_PERSONAL"
  | "HIGHLY_SENSITIVE";

export type EvidenceScanStatus = "PENDING" | "SCANNING" | "CLEAN" | "FAILED" | "INFECTED";

export type EvidenceLifecycleStatus =
  | "PENDING_UPLOAD"
  | "UPLOADED"
  | "SCANNING"
  | "AVAILABLE"
  | "UPLOAD_FAILED"
  | "SCAN_FAILED"
  | "QUARANTINED"
  | "REJECTED"
  | "ARCHIVED";

export interface EvidenceRecord {
  id: string;
  household_id: string;
  evidence_type: EvidenceType;
  title: string;
  media_type: string;
  expected_size_bytes: number;
  size_bytes: number | null;
  sha256: string | null;
  sensitivity_class: EvidenceSensitivity;
  scan_status: EvidenceScanStatus;
  lifecycle_status: EvidenceLifecycleStatus;
  version: number;
  recorded_at: string;
  finalized_at: string | null;
}

interface DataResponse<T> {
  data: T;
}

export interface InitEvidenceUploadInput {
  evidence_type: EvidenceType;
  title: string;
  description: string | null;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sensitivity_class: EvidenceSensitivity;
}

export interface InitEvidenceUploadResult {
  evidence: EvidenceRecord;
  upload_session_id: string;
  upload_url: string;
  expires_at: string;
}

export interface EvidenceDownloadTarget {
  evidence_id: string;
  download_url: string;
  expires_at: string;
  media_type: string;
}

export async function getHouseholdEvidence(
  householdId: string,
  limit = 200,
): Promise<EvidenceRecord[]> {
  const response = await requestJson<DataResponse<EvidenceRecord[]>>(
    `/api/v1/households/${encodeURIComponent(householdId)}/evidence?limit=${limit}`,
  );
  return response.data;
}

export async function initEvidenceUpload(
  householdId: string,
  input: InitEvidenceUploadInput,
): Promise<InitEvidenceUploadResult> {
  const response = await requestJson<DataResponse<InitEvidenceUploadResult>>(
    `/api/v1/households/${encodeURIComponent(householdId)}/evidence/uploads`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return response.data;
}

/**
 * Upload bytes using the short-lived, single-use capability returned by the API.
 * The capability URL is the authority for this request; no bearer token is needed.
 */
export async function uploadEvidenceContent(
  uploadUrl: string,
  file: File,
  mediaType: string,
): Promise<EvidenceRecord> {
  const response = await requestJson<DataResponse<EvidenceRecord>>(
    uploadUrl,
    {
      method: "PUT",
      auth: false,
      headers: { "Content-Type": mediaType },
      body: file,
    },
  );
  return response.data;
}

export async function finalizeEvidence(
  evidenceId: string,
  expectedSha256: string,
): Promise<EvidenceRecord> {
  const response = await requestJson<DataResponse<EvidenceRecord>>(
    `/api/v1/evidence/${encodeURIComponent(evidenceId)}/finalize`,
    {
      method: "POST",
      body: JSON.stringify({ expected_sha256: expectedSha256 }),
    },
  );
  return response.data;
}

export async function getEvidenceDownloadTarget(
  evidenceId: string,
): Promise<EvidenceDownloadTarget> {
  const response = await requestJson<DataResponse<EvidenceDownloadTarget>>(
    `/api/v1/evidence/${encodeURIComponent(evidenceId)}/download`,
  );
  return response.data;
}
