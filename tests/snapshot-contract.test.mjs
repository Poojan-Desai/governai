import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import test from "node:test";

const path = new URL("../src/data/demo-snapshot.json", import.meta.url);
const load = async () => JSON.parse(await readFile(path,"utf8"));
const cloudPath = new URL("../src/data/cloud-status.json", import.meta.url);
const loadCloud = async () => JSON.parse(await readFile(cloudPath,"utf8"));
const appPath = new URL("../src/App.tsx", import.meta.url);
const stylesPath = new URL("../src/styles.css", import.meta.url);
const indexPath = new URL("../index.html", import.meta.url);
const socialPath = new URL("../public/og.png", import.meta.url);

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

test("bundled evidence excludes row-level direct identifiers", async () => {
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

test("experiment evidence is seeded, aggregate, and explicitly simulated", async () => {
  const data=await load();
  const experiment=data.experiment;
  assert.equal(experiment.status,"SIMULATED_LOCALLY_VERIFIED");
  assert.equal(experiment.design.analysis_population,320);
  assert.equal(experiment.design.sample_ratio_mismatch_detected,false);
  assert.deepEqual(
    [experiment.arms.control.units,experiment.arms.control.conversions,experiment.arms.treatment.units,experiment.arms.treatment.conversions],
    [172,47,148,61],
  );
  assert.equal(experiment.analysis.decision,"ADVANCE_TO_LIVE_PILOT");
  assert.equal(experiment.analysis.statistically_significant,true);
  assert.match(experiment.data_notice,/no real business lift is claimed/i);
  assert.doesNotMatch(JSON.stringify(experiment),/ACC-\d{5}/);
});

test("governed assistant answers only approved aggregate intents", async () => {
  const {assistant}=await load();
  assert.equal(assistant.status,"DETERMINISTIC_LOCAL_PROTOTYPE");
  assert.match(assistant.engine,/no LLM call/i);
  assert.equal(assistant.semantic_metrics.length,3);
  assert.equal(assistant.examples.filter(example=>example.status==="ANSWERED_FROM_APPROVED_METRIC").length,4);
  const blocked=assistant.examples.find(example=>example.status==="BLOCKED_BY_POLICY");
  assert.equal(blocked.approved_query,null);
  assert.equal(blocked.citation,null);
  for(const example of assistant.examples.filter(example=>example.approved_query)){
    assert.match(example.approved_query,/^SELECT /);
    assert.ok(example.citation?.asset_id);
    assert.equal(example.policy.dynamic_sql,false);
  }
  assert.doesNotMatch(JSON.stringify(assistant),/(ACC|CUS)-\d{5}|TXN-\d{8}/);
});

test("model governance keeps the research winner behind approvals", async () => {
  const evidence=(await load()).model_governance;
  assert.equal(evidence.status,"RESEARCH_ONLY_LOCALLY_VERIFIED");
  assert.equal(evidence.backtest.fold_count,3);
  assert.equal(evidence.backtest.research_champion,"ols_trend_challenger");
  assert.equal(evidence.backtest.decision,"RESEARCH_CHAMPION_NOT_PRODUCTION_APPROVED");
  assert.equal(evidence.drift.metrics.length,3);
  assert.equal(evidence.approval_gates.find(gate=>gate.gate==="Production deployment").status,"BLOCKED");
  assert.equal(evidence.approval_gates.find(gate=>gate.gate==="Model risk review").status,"NOT_RUN");
  assert.doesNotMatch(JSON.stringify(evidence),/(ACC|CUS)-\d{5}|TXN-\d{8}/);
});

test("portfolio shell includes recruiter story, accessibility, and social metadata", async () => {
  const [app,styles,index,social]=await Promise.all([
    readFile(appPath,"utf8"),readFile(stylesPath,"utf8"),readFile(indexPath,"utf8"),stat(socialPath),
  ]);
  assert.match(app,/A 90-second technical walkthrough/);
  assert.match(app,/Governed analytics assistant/);
  assert.match(app,/Model governance/);
  assert.match(app,/className="skip-link"/);
  assert.match(app,/aria-current=/);
  assert.match(styles,/:focus-visible/);
  assert.match(styles,/@media\(prefers-reduced-motion:reduce\)/);
  assert.match(styles,/\.mobile-nav\{justify-content:flex-start;gap:4px;overflow-x:auto/);
  assert.match(index,/GovernAI \| Data & AI Governance Portfolio/);
  assert.match(index,/property="og:image" content="\/og\.png"/);
  assert.ok(social.size>100_000);
});
