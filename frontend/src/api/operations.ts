import { requestJson } from "./client";

export type WorkItemType =
  | "REASSESSMENT"
  | "OUTCOME_REVIEW"
  | "REFERRAL_FOLLOWUP"
  | "AI_FALLBACK";

export type WorkItemStatus = "OPEN" | "CLAIMED" | "COMPLETED" | "CANCELLED";

export interface WorkItem {
  id: string;
  household_id: string;
  work_type: WorkItemType;
  resource_type: string;
  resource_id: string;
  title: string;
  reason: string;
  priority: number;
  status: WorkItemStatus;
  version: number;
  due_at: string | null;
  assigned_actor_id: string | null;
  policy_version: string | null;
  created_at: string;
  claimed_at: string | null;
}

interface WorkQueueResponse {
  data: WorkItem[];
}

interface WorkItemResponse {
  data: WorkItem;
}

export async function getWorkQueue(limit = 100): Promise<WorkItem[]> {
  const response = await requestJson<WorkQueueResponse>(
    `/api/v1/work-queue?limit=${limit}`,
  );
  return response.data;
}

export async function claimWorkItem(item: WorkItem): Promise<WorkItem> {
  const response = await requestJson<WorkItemResponse>(
    `/api/v1/work-queue/${item.id}/claim`,
    {
      method: "POST",
      body: JSON.stringify({ expected_version: item.version }),
    },
  );
  return response.data;
}
