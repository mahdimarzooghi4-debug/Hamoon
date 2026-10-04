import assert from "node:assert/strict";

import {
  accessForPath,
  canUseCasework,
  canUseLearningGovernance,
} from "../.tmp-auth-test/access.js";

const caseworker = { roles: ["CASEWORKER"] };
const admin = { roles: ["ADMIN"] };
const auditor = { roles: ["SECURITY_AUDITOR"] };
const mixed = { roles: ["CASEWORKER", "ADMIN"] };

assert.equal(accessForPath("/", null), "allowed");
assert.equal(accessForPath("/auth/callback", null), "allowed");
assert.equal(
  accessForPath("/work-queue", null),
  "authentication-required",
);
assert.equal(
  accessForPath("/households/household-1", null),
  "authentication-required",
);

assert.equal(accessForPath("/work-queue", caseworker), "allowed");
assert.equal(accessForPath("/households", caseworker), "allowed");
assert.equal(
  accessForPath("/admin/learning", caseworker),
  "forbidden",
);

assert.equal(accessForPath("/admin/learning", admin), "allowed");
assert.equal(accessForPath("/work-queue", admin), "forbidden");
assert.equal(
  accessForPath("/admin/learning", auditor),
  "forbidden",
);

assert.equal(canUseCasework(mixed), true);
assert.equal(canUseLearningGovernance(mixed), true);
