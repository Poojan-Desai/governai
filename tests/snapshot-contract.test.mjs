import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const path = new URL("../public/data/demo-snapshot.json", import.meta.url);
const load = async () => JSON.parse(await readFile(path,"utf8"));
const cloudPath = new URL("../public/data/cloud-status.json", import.meta.url);
const loadCloud = async () => JSON.parse(await readFile(cloudPath,"utf8"));

test("snapshot comes from a completed governed run", async () => {
  const data=await load();
  assert.match(data.freshness.last_good_run_id,/^run-[a-f0-9]{16}$/);
  assert.match(data.freshness.source_sha256,/^[a-f0-9]{64}$/);
  assert.equal(data.summary.accepted_transactions,3600);
  assert.equal(data.monthly_kpis.length,6);
  assert.equal(data.forecast.method,"ordinary_least_squares");
});

test("incident proves isolation and computed impact", async () => {
  const data=await load();
  assert.equal(data.incident.status,"quarantined");
  assert.deepEqual([data.incident.source_rows,data.incident.accepted_rows,data.incident.quarantined_rows],[120,0,120]);
  assert.equal(data.incident.warehouse_rows_before,data.incident.warehouse_rows_after);
  assert.equal(data.incident.failed_checks.length,4);
  assert.ok(data.incident.impacted_asset_ids.includes("model.loss_forecast_v1"));
  assert.ok(data.incident.impacted_asset_ids.includes("dashboard.risk_operations"));
});

test("public evidence excludes row-level direct identifiers", async () => {
  const text=JSON.stringify(await load()).toLowerCase();
  assert.doesNotMatch(text,/customer\d{5}@example\.test/);
  assert.doesNotMatch(text,/synthetic customer \d{5}/);
  assert.doesNotMatch(text,/\+1-555-/);
});

test("cloud dashboard keeps implementation separate from live verification", async () => {
  const status=await loadCloud();
  assert.equal(status.implementation_status,"IMPLEMENTED_LOCALLY");
  assert.equal(status.live_verification_status,"NOT_RUN");
  assert.equal(status.credentials.values_exposed,false);
  assert.equal(status.latest_live_run,null);
  assert.equal(status.s3_zones.length,4);
  assert.ok(status.cloud_lineage.some(edge=>edge.to==="Snowflake RAW"&&edge.status==="DEFINED_NOT_EXECUTED"));
});
