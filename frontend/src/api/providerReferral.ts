import { requestJson, ApiError } from "./client";
import type { Intervention, InterventionType } from "./prescriptions";
import type { PGORVariable } from "./households";

export type MatchEligibility = "ELIGIBLE" | "INELIGIBLE";
export type CapacityStatus = "AVAILABLE" | "FULL" | "UNAVAILABLE" | "UNKNOWN";

export interface ProviderMatchContextFact {
  fact_id: string;
  fact_type: string;
  projection_version: number;
  effective_from: string;
}

export interface ProviderMatchServiceType {
  service_type: string;
  service_titles: string[];
  active_service_count: number;
}

export interface ProviderMatchContext {
  intervention_id: string;
  intervention_type: InterventionType;
  target_pgor_variable: PGORVariable;
  household_context_version: number;
  service_types: ProviderMatchServiceType[];
  shareable_facts: ProviderMatchContextFact[];
}

export interface ProviderMatchCandidate {
  provider_id: string;
  provider_name: string;
  provider_service_id: string;
  service_title: string;
  eligibility: MatchEligibility;
  capacity_status: CapacityStatus;
  reasons: string[];
}

export interface ProviderMatch {
  provider_match_id: string;
  intervention_id: string;
  ai_decision_id: string | null;
  service_type: string;
  household_context_version: number;
  matching_policy_version: string;
  generated_at: string;
  candidates: ProviderMatchCandidate[];
}

export type ReferralStatus =
  | "READY"
  | "SENT"
  | "ACCEPTED"
  | "WAITING_CAPACITY"
  | "NEEDS_INFORMATION"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "REJECTED"
  | "NO_RESPONSE"
  | "CANCELLED";

export interface ReferralDataItem {
  id: string;
  data_category: string;
  source_fact_id: string | null;
  snapshot_value: unknown;
  purpose: string;
  authorization_basis: string | null;
  shared_at: string | null;
}

export interface Referral {
  id: string;
  household_id: string;
  intervention_id: string;
  provider_match_id: string;
  provider_selection_id: string;
  provider_id: string;
  provider_name: string;
  provider_service_id: string;
  service_title: string;
  human_decision_id: string | null;
  learning_signal_id: string | null;
  status: ReferralStatus;
  priority: string;
  version: number;
  response_due_at: string | null;
  external_referral_id: string | null;
  created_at: string;
  data_items: ReferralDataItem[];
}

export interface ReferralEvent {
  id: string;
  referral_version: number;
  from_status: ReferralStatus;
  to_status: ReferralStatus;
  occurred_at: string;
  recorded_at: string;
  source: string;
  reason_code: string | null;
  external_event_id: string | null;
}

interface InterventionListResponse {
  data: Intervention[];
}
interface MatchContextResponse {
  data: ProviderMatchContext;
}
interface ProviderMatchResponse {
  data: ProviderMatch;
}
interface ReferralResponse {
  data: Referral;
}
interface ReferralTimelineResponse {
  data: ReferralEvent[];
}
interface SendReferralResponse {
  data: {
    referral_id: string;
    dispatch_id: string;
    status: ReferralStatus;
    version: number;
    dispatch_status: string;
    replayed: boolean;
  };
}

export async function listHouseholdInterventions(
  householdId: string,
): Promise<Intervention[]> {
  const response = await requestJson<InterventionListResponse>(
    `/api/v1/households/${encodeURIComponent(householdId)}/interventions`,
  );
  return response.data;
}

export async function getProviderMatchContext(
  interventionId: string,
): Promise<ProviderMatchContext> {
  const response = await requestJson<MatchContextResponse>(
    `/api/v1/interventions/${encodeURIComponent(interventionId)}/provider-match-context`,
  );
  return response.data;
}

export async function getLatestProviderMatch(
  interventionId: string,
): Promise<ProviderMatch | null> {
  try {
    const response = await requestJson<ProviderMatchResponse>(
      `/api/v1/interventions/${encodeURIComponent(interventionId)}/provider-match`,
    );
    return response.data;
  } catch (error: unknown) {
    if (
      error instanceof ApiError &&
      error.status === 404 &&
      error.code === "PROVIDER_MATCH_NOT_FOUND"
    ) {
      return null;
    }
    throw error;
  }
}

export async function runProviderMatch(
  interventionId: string,
  serviceType: string,
  householdContextVersion: number,
): Promise<ProviderMatch> {
  const response = await requestJson<ProviderMatchResponse>(
    `/api/v1/interventions/${encodeURIComponent(interventionId)}/match-providers`,
    {
      method: "POST",
      body: JSON.stringify({
        service_type: serviceType,
        household_context_version: householdContextVersion,
      }),
    },
  );
  return response.data;
}

export async function getLatestReferral(
  interventionId: string,
): Promise<Referral | null> {
  try {
    const response = await requestJson<ReferralResponse>(
      `/api/v1/interventions/${encodeURIComponent(interventionId)}/referral`,
    );
    return response.data;
  } catch (error: unknown) {
    if (
      error instanceof ApiError &&
      error.status === 404 &&
      error.code === "REFERRAL_NOT_FOUND"
    ) {
      return null;
    }
    throw error;
  }
}

export async function createReferral(
  interventionId: string,
  input: {
    providerId: string;
    providerServiceId: string;
    priority: string;
    responseDueAt: string | null;
    sharedFacts: Array<{ sourceFactId: string; purpose: string }>;
  },
): Promise<Referral> {
  const response = await requestJson<ReferralResponse>(
    `/api/v1/interventions/${encodeURIComponent(interventionId)}/referrals`,
    {
      method: "POST",
      body: JSON.stringify({
        provider_id: input.providerId,
        provider_service_id: input.providerServiceId,
        priority: input.priority,
        response_due_at: input.responseDueAt,
        shared_data_items: input.sharedFacts.map((item) => ({
          source_fact_id: item.sourceFactId,
          purpose: item.purpose,
        })),
      }),
    },
  );
  return response.data;
}

export async function sendReferral(
  referral: Referral,
  idempotencyKey: string,
): Promise<SendReferralResponse["data"]> {
  const response = await requestJson<SendReferralResponse>(
    `/api/v1/referrals/${encodeURIComponent(referral.id)}/send`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ expected_version: referral.version }),
    },
  );
  return response.data;
}

export async function getReferralEvents(
  referralId: string,
): Promise<ReferralEvent[]> {
  const response = await requestJson<ReferralTimelineResponse>(
    `/api/v1/referrals/${encodeURIComponent(referralId)}/events`,
  );
  return response.data;
}
