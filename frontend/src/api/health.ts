import { requestJson } from "./client";

export interface HealthResponse {
  status: "alive" | "ready" | "degraded";
  service: string;
  environment: string;
}

export function getReadiness(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health/ready", { auth: false });
}
