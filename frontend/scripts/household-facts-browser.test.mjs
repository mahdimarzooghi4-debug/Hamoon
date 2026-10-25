/**
 * Local-only, authenticated Chromium QA for household fact correction.
 * Runs against the CI's real Compose web/API/PostgreSQL/Keycloak stack.
 * Never run against Production. No intercepted/mocked API, static access token,
 * direct-grant login, real family data, or external identities.
 */
import assert from "node:assert/strict";
import { randomBytes, randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const WEB = "http://localhost:3000";
const KEYCLOAK = "http://localhost:8081";
const REALM = "hamoon-local";
const artifacts = new URL("../browser-qa-artifacts/", import.meta.url);
const createdUsers = [];
let browser;

function fail(message, response) {
  return new Error(`${message}: HTTP ${response.status()}`);
}

async function adminToken() {
  const form = new URLSearchParams({
    grant_type: "password",
    client_id: "admin-cli",
    username: process.env.HAMOON_LOCAL_KEYCLOAK_ADMIN ?? "admin",
    password: process.env.HAMOON_LOCAL_KEYCLOAK_PASSWORD ?? "admin",
  });
  const response = await fetch(`${KEYCLOAK}/realms/master/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  assert.equal(response.status, 200, "Local-only Keycloak admin token required");
  const result = await response.json();
  assert.equal(typeof result.access_token, "string");
  return result.access_token;
}

async function adminRequest(path, options = {}) {
  const response = await fetch(`${KEYCLOAK}/admin/realms/${REALM}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${await adminToken()}`,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  return response;
}

async function provisionCaseworker() {
  const username = `qa-caseworker-${randomUUID()}`;
  const password = randomBytes(30).toString("base64url");
  const created = await adminRequest("/users", {
    method: "POST",
    body: JSON.stringify({
      username,
      enabled: true,
      emailVerified: false,
      requiredActions: [],
      credentials: [{ type: "password", value: password, temporary: false }],
    }),
  });
  assert.equal(created.status, 201, "Temporary local Keycloak user creation failed");
  const location = created.headers.get("location");
  assert.ok(location, "Keycloak did not return user Location");
  const id = location.split("/").at(-1);
  assert.ok(id, "Keycloak user ID missing");
  createdUsers.push(id);

  const roleResponse = await adminRequest("/roles/CASEWORKER");
  assert.equal(roleResponse.status, 200);
  const role = await roleResponse.json();
  const assigned = await adminRequest(`/users/${id}/role-mappings/realm`, {
    method: "POST",
    body: JSON.stringify([role]),
  });
  assert.equal(assigned.status, 204, "CASEWORKER role assignment failed");
  return { username, password };
}

async function login(page, user) {
  await page.goto(`${WEB}/households`);
  await page.getByRole("button", { name: "ورود سازمانی" }).first().click();
  await page.locator("#username").waitFor({ timeout: 45000 });
  await page.locator("#username").fill(user.username);
  await page.locator("#password").fill(user.password);
  await page.locator("#kc-login").click();
  try {
    await page.waitForURL(
      (url) => url.origin === WEB && (url.pathname === "/households" || url.pathname === "/households/"),
      { timeout: 30000, waitUntil: "domcontentloaded" },
    );
  } catch {
    // Capture only synthetic UI; mask password and never log callback query tokens.
    await page.screenshot({
      path: new URL("oidc-login-diagnostic.png", artifacts).pathname,
      mask: [page.locator("#password")],
    });
    const location = new URL(page.url());
    const errors = await page.locator("#input-error, #kc-error-message, [role=alert]")
      .allInnerTexts().catch(() => []);
    throw new Error(
      `OIDC browser did not return to /households; path=${location.origin}${location.pathname}; alerts=${JSON.stringify(errors.slice(0, 3))}`,
    );
  }
  await page.waitForFunction(() => Boolean(sessionStorage.getItem("hamoon.access_token")));
  // This is a real PKCE-issued session; the token is never printed or persisted.
  const token = await page.evaluate(() => sessionStorage.getItem("hamoon.access_token"));
  assert.ok(token);
  return token;
}

async function api(page, token, path, { method = "GET", data, expected = 200 } = {}) {
  const response = await page.request.fetch(`${WEB}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    ...(data === undefined ? {} : { data }),
  });
  assert.equal(response.status(), expected, `${method} ${path} returned unexpected status`);
  return expected === 204 ? null : response.json();
}

async function assertNoHorizontalOverflow(page, label) {
  const geometry = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
  assert.ok(
    geometry.document <= geometry.viewport + 1,
    `${label} horizontal overflow: ${JSON.stringify(geometry)}`,
  );
}

async function run() {
  assert.equal(process.env.CI, "true", "Browser QA is restricted to isolated CI");
  await mkdir(artifacts, { recursive: true });
  const caseworker = await provisionCaseworker();
  const otherCaseworker = await provisionCaseworker();
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "fa-IR",
    timezoneId: "Asia/Tehran",
  });
  const page = await context.newPage();
  const token = await login(page, caseworker);
  const code = `QA-BROWSER-${randomUUID()}`;
  const created = await api(page, token, "/api/v1/households", {
    method: "POST",
    data: { case_code: code },
    expected: 201,
  });
  const householdId = created.data.id;
  const root = `/api/v1/households/${householdId}`;
  const sources = await api(page, token, "/api/v1/data-sources");
  const source = sources.data.find((item) => item.code === "HOUSEHOLD_DECLARATION");
  assert.ok(source, "Authoritative local migration data source missing");
  const effective = new Date().toISOString();
  const initial = await api(page, token, `${root}/facts`, {
    method: "POST",
    data: {
      fact_type: "QA_BROWSER_FACT",
      value_type: "CODE",
      value: "QA_BEFORE",
      source_id: source.id,
      source_detail: "synthetic local browser QA",
      effective_from: effective,
    },
    expected: 201,
  });
  assert.equal(initial.data.validation_status, "PENDING_VALIDATION");
  await api(page, token, `${root}/facts/${initial.data.id}/validation`, {
    method: "POST",
    data: {
      to_status: "VALIDATED",
      expected_validation_version: 1,
      reason_code: "QA_REVIEW",
      reason_text: "Synthetic initial human-review fixture",
    },
  });
  const acceptedInitial = await api(page, token, `${root}/accepted-state/QA_BROWSER_FACT/resolve`, {
    method: "POST",
    data: {
      fact_id: initial.data.id,
      expected_projection_version: 0,
      reason_code: "QA_REVIEW",
      reason_text: "Synthetic initial explicit acceptance",
    },
  });
  assert.equal(acceptedInitial.data.projection_version, 1);

  await page.goto(`${WEB}/households/${householdId}/facts`);
  await page.getByRole("heading", { name: "اصلاح و اعتبارسنجی اطلاعات" }).waitFor();
  await page.getByLabel("نوع واقعیت").selectOption("QA_BROWSER_FACT");
  await page.getByText("QA_BEFORE", { exact: true }).first().waitFor();
  await assertNoHorizontalOverflow(page, "desktop");
  await page.screenshot({ path: new URL("correction-desktop-before.png", artifacts).pathname, fullPage: true });

  await page.getByLabel("مقدار پیشنهادی جدید · کد").fill("QA_AFTER");
  await page.getByLabel("منبع فعال داده").selectOption(source.id);
  await page.getByLabel("تاریخ اثر · ISO 8601 با منطقه زمانی").fill(effective);
  await page.getByRole("button", { name: "مدرک جدید" }).click();
  await page.getByLabel("توضیح مستند دلیل").fill("Synthetic browser correction, human review required");
  await page.getByRole("button", { name: "ثبت واقعیت در انتظار بررسی" }).click();
  await page.getByText(/در انتظار اعتبارسنجی ثبت شد/).waitFor();

  const pendingFacts = await api(page, token, `${root}/facts`);
  const correction = pendingFacts.data.find((item) => item.value === "QA_AFTER");
  assert.ok(correction, "Browser did not persist proposed correction");
  assert.equal(correction.supersedes_fact_id, initial.data.id);
  assert.equal(correction.correction_reason_code, "NEW_EVIDENCE");
  assert.equal(correction.correction_reason_text, "Synthetic browser correction, human review required");
  assert.equal(correction.validation_status, "PENDING_VALIDATION");
  const stillAccepted = await api(page, token, `${root}/accepted-state`);
  assert.equal(stillAccepted.data.find((item) => item.fact_type === "QA_BROWSER_FACT").fact_id, initial.data.id);

  await page.getByRole("button", { name: "تأیید اعتبار" }).click();
  await page.getByText(/اعتبارسنجی انسانی ثبت شد/).waitFor();
  const afterValidation = await api(page, token, `${root}/accepted-state`);
  assert.equal(afterValidation.data.find((item) => item.fact_type === "QA_BROWSER_FACT").fact_id, initial.data.id);
  await page.getByRole("checkbox", { name: /انتخاب این واقعیت به‌عنوان Accepted State/ }).check();
  await page.getByRole("button", { name: "انتخاب صریح به‌عنوان داده پذیرفته‌شده" }).click();
  await page.getByText(/با تصمیم صریح انسانی/).waitFor();
  const finalAccepted = await api(page, token, `${root}/accepted-state`);
  const current = finalAccepted.data.find((item) => item.fact_type === "QA_BROWSER_FACT");
  assert.equal(current.fact_id, correction.id);
  assert.equal(current.projection_version, 2);

  const history = await api(page, token, `${root}/accepted-state/QA_BROWSER_FACT/history`);
  assert.equal(history.data[0].new_fact_id, correction.id);
  assert.equal(history.data[0].previous_fact_id, initial.data.id);
  await page.getByText("تاریخچه پذیرش داده").waitFor();
  await page.screenshot({ path: new URL("correction-desktop-accepted.png", artifacts).pathname, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await assertNoHorizontalOverflow(page, "mobile");
  await page.screenshot({ path: new URL("correction-mobile-accepted.png", artifacts).pathname, fullPage: true });

  const stale = await api(page, token, `${root}/facts`, {
    method: "POST",
    data: {
      fact_type: "QA_BROWSER_FACT",
      value_type: "CODE",
      value: "QA_STALE",
      source_id: source.id,
      effective_from: effective,
      supersedes_fact_id: initial.data.id,
      expected_accepted_projection_version: 1,
      correction_reason_code: "NEW_EVIDENCE",
      correction_reason_text: "Synthetic stale reference",
    },
    expected: 409,
  });
  assert.equal(stale.detail.code, "VERSION_CONFLICT");
  const unchangedFacts = await api(page, token, `${root}/facts`);
  assert.equal(unchangedFacts.data.length, 2, "Stale write must not create a fact");

  const otherContext = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const otherPage = await otherContext.newPage();
  const otherToken = await login(otherPage, otherCaseworker);
  const forbidden = await api(otherPage, otherToken, `${root}/facts`, { expected: 404 });
  assert.equal(forbidden.detail.code, "RESOURCE_NOT_FOUND");
  await otherPage.goto(`${WEB}/households/${householdId}/facts`);
  await otherPage.getByText("پرونده در دسترس نیست", { exact: true }).waitFor();
  assert.equal(await otherPage.getByText("QA_AFTER", { exact: true }).count(), 0);
  await otherContext.close();
  await context.close();
  process.stdout.write("PASS: real OIDC PKCE, isolated PostgreSQL correction, human gates, stale 409, cross-caseworker masked 404, desktop/mobile screenshots.\\n");
}

try {
  await run();
} catch (error) {
  process.stderr.write(`Browser QA failed: ${error instanceof Error ? error.message : String(error)}\\n`);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  for (const id of createdUsers) {
    try {
      await adminRequest(`/users/${id}`, { method: "DELETE" });
    } catch {
      // The CI stack and database are destroyed; no local QA identity survives.
    }
  }
}
