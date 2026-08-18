import { useMemo, useState } from "react";
import snapshotJson from "../public/data/demo-snapshot.json";
import cloudStatusJson from "../public/data/cloud-status.json";
import type { Asset, CloudStatus, Edge, Snapshot } from "./types";

const data = snapshotJson as Snapshot;
const cloud = cloudStatusJson as CloudStatus;
type View = "overview"|"incident"|"lineage"|"catalog"|"cloud";
const nav:{id:View;label:string;mark:string}[]=[
  {id:"overview",label:"Overview",mark:"OV"},{id:"incident",label:"Incident center",mark:"DQ"},
  {id:"lineage",label:"Lineage explorer",mark:"LN"},{id:"catalog",label:"Data catalog",mark:"CT"},
  {id:"cloud",label:"Cloud control plane",mark:"CL"},
];
const money=(value:number)=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(value);
const date=(value:string)=>new Intl.DateTimeFormat("en-US",{month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit",timeZone:"UTC",timeZoneName:"short"}).format(new Date(value));

function Stat({label,value,detail,tone=""}:{label:string;value:string;detail:string;tone?:string}){
  return <article className={`stat ${tone}`}><span>{label}</span><strong>{value}</strong><p>{detail}</p></article>;
}

function Overview({setView}:{setView:(view:View)=>void}){
  const max=Math.max(...data.monthly_kpis.map(k=>k.confirmed_loss),1);
  const latest=data.monthly_kpis.at(-1);
  const pass=Math.round(data.summary.quality_checks_passed/data.summary.quality_checks*100);
  return <div className="stack">
    <section className="hero-grid">
      <div className="hero">
        <span className="eyebrow"><i className="dot"/> Governed data operations</span>
        <h1>Trust every answer<br/>back to its source.</h1>
        <p>GovernAI makes quality controls, lineage, privacy, and downstream impact visible across a simulated banking data platform.</p>
        <div className="actions"><button className="primary" onClick={()=>setView("incident")}>Inspect quality incident <b>→</b></button><button onClick={()=>setView("lineage")}>Explore lineage</button></div>
      </div>
      <article className="spotlight">
        <div className="spot-top"><span>CONTROL ACTIVATED</span><small>{data.incident.incident_id}</small></div>
        <div className="shield">✓</div><h2>Contamination prevented</h2>
        <p>{data.incident.quarantined_rows} source rows stopped before publish. The warehouse stayed on its last known-good version.</p>
        <div className="compare"><div><span>Before</span><b>{data.incident.warehouse_rows_before.toLocaleString()}</b></div><i>→</i><div><span>After</span><b>{data.incident.warehouse_rows_after.toLocaleString()}</b></div></div>
        <button onClick={()=>setView("incident")}>View machine evidence ↗</button>
      </article>
    </section>
    <section className="stats">
      <Stat label="Accepted transactions" value={data.summary.accepted_transactions.toLocaleString()} detail="Current governed fact table"/>
      <Stat label="Quality controls passing" value={`${pass}%`} detail={`${data.summary.quality_checks_passed} of ${data.summary.quality_checks} executed checks`} tone="safe"/>
      <Stat label="Protected downstream" value={`${data.summary.protected_downstream_assets}`} detail="Assets in incident blast radius" tone="safe"/>
      <Stat label="Classified columns" value={`${data.summary.classified_columns}`} detail={`${data.summary.direct_identifier_columns} direct identifiers governed`}/>
    </section>
    <section className="overview-grid">
      <article className="panel trend">
        <Heading eyebrow="Executed KPI mart" title="Confirmed loss trend" badge="Monthly · USD"/>
        <div className="bars" aria-label="Monthly confirmed loss bar chart">
          {data.monthly_kpis.map(k=><div className="bar-col" key={k.month}><span>{money(k.confirmed_loss)}</span><div className="track"><i style={{height:`${Math.max(3,k.confirmed_loss/max*100)}%`}}/></div><b>{new Date(`${k.month}-02T00:00:00Z`).toLocaleDateString("en-US",{month:"short",timeZone:"UTC"})}</b></div>)}
        </div>
        <div className="chart-foot"><span>Latest month</span><b>{latest?money(latest.confirmed_loss):"—"}</b><span>{latest?.affected_transactions??0} affected · {latest?.loss_rate_bps.toFixed(1)} bps</span></div>
      </article>
      <article className="panel model"><Heading eyebrow="Model lineage" title="Loss forecast baseline" badge="Verified" safe/>
        {data.forecast&&<><div className="forecast"><strong>{money(data.forecast.predicted_loss)}</strong><span>{data.forecast.forecast_month}</span></div>
        <dl><div><dt>Method</dt><dd>Ordinary least squares</dd></div><div><dt>Training points</dt><dd>{data.forecast.training_points} months</dd></div><div><dt>Version</dt><dd><code>{data.forecast.model_version}</code></dd></div></dl>
        <p className="limit"><b>Known limitation</b>Six simulated monthly observations make this a lineage demonstration—not a production forecast.</p></>}
      </article>
    </section>
    <section className="run-strip panel"><div><span>Last trusted transaction run</span><b>{data.freshness.last_good_run_id}</b></div><div><span>Published</span><b>{date(data.freshness.last_good_run_at)}</b></div><div><span>Freshness SLA</span><b>{data.freshness.sla}</b></div><div><span>Source evidence</span><code>{data.freshness.source_sha256.slice(0,18)}…</code></div></section>
  </div>;
}

function Heading({eyebrow,title,badge,safe=false}:{eyebrow:string;title:string;badge?:string;safe?:boolean}){
  return <div className="heading"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>{badge&&<span className={safe?"badge safe-badge":"badge"}>{badge}</span>}</div>;
}
function Title({eyebrow,title,description,tag}:{eyebrow:string;title:string;description:string;tag:string}){
  return <section className="title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div><span>{tag}</span></section>;
}

function Incident({setView}:{setView:(view:View)=>void}){
  const assets=data.assets.filter(a=>data.incident.impacted_asset_ids.includes(a.asset_id));
  return <div className="stack"><Title eyebrow={`${data.incident.incident_id} · fail-closed policy`} title="Quality incident center" description="Evidence for a deliberately corrupted batch and every product it could have contaminated." tag="● Quarantined"/>
    <section className="incident-banner"><div className="bang">!</div><div><span>CRITICAL SOURCE CONTRACT FAILED</span><h2>{data.incident.title}</h2><p>{data.incident.explanation}</p></div><div className="incident-count"><strong>{data.incident.quarantined_rows}</strong><span>rows isolated</span></div></section>
    <section className="flow">{[["01","Detected",`${data.incident.critical_violation_count} critical rules failed`],["02","Quarantined",`${data.incident.quarantined_rows} records isolated`],["03","Publish blocked",`${data.incident.accepted_rows} records accepted`],["04","Impact traced",`${data.incident.impacted_asset_ids.length} assets protected`]].map(([n,t,d],i)=><div key={n}><span>{n}</span><p><b>{t}</b><small>{d}</small></p>{i<3&&<i>→</i>}</div>)}</section>
    <section className="incident-grid">
      <article className="panel checks"><Heading eyebrow="Machine-recorded evidence" title="Failed quality checks" badge={`${data.incident.failed_checks.length} rules`}/><div>{data.incident.failed_checks.map(c=><div className="check" key={c.rule_id}><span>×</span><p><b>{c.description}</b><code>{c.rule_id}</code></p><aside><strong>{c.failed_rows}</strong><small>failing row</small></aside></div>)}</div></article>
      <article className="panel isolation"><Heading eyebrow="Atomicity proof" title="Warehouse unchanged" badge="Protected" safe/><div className="equal"><div><span>Fact rows before</span><b>{data.incident.warehouse_rows_before.toLocaleString()}</b></div><i>=</i><div><span>Fact rows after</span><b>{data.incident.warehouse_rows_after.toLocaleString()}</b></div></div>
        <dl><div><dt>Run ID</dt><dd><code>{data.incident.run_id}</code></dd></div><div><dt>Source</dt><dd>{data.incident.source_file}</dd></div><div><dt>Policy</dt><dd><code>{data.incident.policy}</code></dd></div><div><dt>SHA-256</dt><dd><code>{data.incident.source_sha256.slice(0,17)}…</code></dd></div></dl></article>
    </section>
    <section className="panel impact"><Heading eyebrow="Lineage-derived blast radius" title="Assets protected by the quality gate"/><button onClick={()=>setView("lineage")}>Open graph →</button><div>{assets.map((a,i)=><article key={a.asset_id}><span>{String(i+1).padStart(2,"0")}</span><p><b>{a.display_name}</b><code>{a.asset_id}</code></p><i>PROTECTED</i></article>)}</div></section>
  </div>;
}

const layers=["source","validated","curated","product","model","consumption"];
const xpos:Record<string,number>={source:24,validated:210,curated:396,product:582,model:768,consumption:954};
function split(label:string):[string,string]{const words=label.split(" ");if(label.length<21)return[label,""];const m=Math.ceil(words.length/2);return[words.slice(0,m).join(" "),words.slice(m).join(" ")];}
function LineageGraph(){
  const [selected,setSelected]=useState(data.incident.source_asset_id);
  const impacted=new Set([data.incident.source_asset_id,...data.incident.impacted_asset_ids]);
  const positions=useMemo(()=>{const map=new Map<string,{x:number;y:number}>();for(const layer of layers){const list=data.assets.filter(a=>a.layer===layer),space=500/Math.max(list.length,1);list.forEach((a,i)=>map.set(a.asset_id,{x:xpos[layer],y:95+space*i}));}return map;},[]);
  const asset=data.assets.find(a=>a.asset_id===selected)!;
  const connected=data.lineage_edges.filter(e=>e.upstream_asset_id===selected||e.downstream_asset_id===selected);
  return <div className="lineage panel"><div className="graph-head"><Heading eyebrow="Interactive dependency map" title="Transaction trust path"/><p><span className="red-dot"/>Source incident <span className="green-dot"/>Protected downstream</p></div><div className="graph-scroll"><svg viewBox="0 0 1125 650" role="img" aria-label="GovernAI data lineage graph"><defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z"/></marker></defs>
    {layers.map(l=><text key={l} x={xpos[l]+68} y="36" textAnchor="middle" className="layer-label">{l.toUpperCase()}</text>)}
    {data.lineage_edges.map((e:Edge)=>{const from=positions.get(e.upstream_asset_id),to=positions.get(e.downstream_asset_id);if(!from||!to)return null;const hi=impacted.has(e.upstream_asset_id)&&impacted.has(e.downstream_asset_id),x1=from.x+148,y1=from.y+42,x2=to.x,y2=to.y+42,c=Math.max(35,(x2-x1)*.48);return <path key={e.edge_id} className={hi?"edge hi":"edge"} d={`M${x1} ${y1} C${x1+c} ${y1},${x2-c} ${y2},${x2} ${y2}`} markerEnd="url(#arr)"/>;})}
    {data.assets.map((a:Asset)=>{const p=positions.get(a.asset_id);if(!p)return null;const incident=a.asset_id===data.incident.source_asset_id,protectedNode=data.incident.impacted_asset_ids.includes(a.asset_id),[one,two]=split(a.display_name);return <g key={a.asset_id} transform={`translate(${p.x} ${p.y})`} className={`node ${incident?"incident":""} ${protectedNode?"protected":""} ${selected===a.asset_id?"selected":""}`} tabIndex={0} role="button" onClick={()=>setSelected(a.asset_id)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" ")setSelected(a.asset_id)}}><rect width="148" height="84" rx="13"/><text x="13" y="20" className="node-type">{a.asset_type.replace("_"," ").toUpperCase()}</text><text x="13" y="43" className="node-title"><tspan x="13">{one}</tspan>{two&&<tspan x="13" dy="15">{two}</tspan>}</text>{incident&&<circle cx="132" cy="17" r="5"/>}{protectedNode&&<text x="132" y="21" className="tick">✓</text>}</g>;})}
  </svg></div><div className="inspector"><div><span className="asset-pill">{asset.layer}</span><h3>{asset.display_name}</h3><p>{asset.description}</p><code>{asset.asset_id}</code></div><dl><div><dt>Owner</dt><dd>{asset.owner}</dd></div><div><dt>Sensitivity</dt><dd>{asset.sensitivity}</dd></div><div><dt>Freshness SLA</dt><dd>{asset.freshness_sla}</dd></div><div><dt>Rows</dt><dd>{asset.row_count===null?"Virtual asset":asset.row_count.toLocaleString()}</dd></div></dl><aside><span>CONNECTED TRANSFORMATIONS</span>{connected.length?connected.map(e=><p key={e.edge_id}><b>{e.transformation_type.replaceAll("_"," ")}</b> — {e.transformation_description}</p>):<p>Select a downstream asset to inspect its transformation.</p>}</aside></div></div>;
}
function Lineage(){return <div className="stack"><Title eyebrow={`${data.lineage_edges.length} registered transformations`} title="Lineage explorer" description="Select a node to inspect ownership, sensitivity, row count, and the exact transformation connecting it." tag={`${data.assets.length} assets`}/><LineageGraph/><div className="info"><b>i</b><p><strong>How impact is computed:</strong> a breadth-first traversal of stored directed edges begins at <code>{data.incident.source_asset_id}</code>. Highlighted nodes are derived, not hand-selected in the interface.</p></div></div>;}

const rolePurpose:Record<string,string>={
  GOVAI_DATA_ENGINEER:"Inspect raw and governance evidence; operate ingestion infrastructure.",
  GOVAI_ANALYST:"Query curated dimensions, facts, and approved analytics marts only.",
  GOVAI_GOVERNANCE_ADMIN:"Manage masking policies and inspect governance evidence.",
  GOVAI_RESTRICTED_ANALYST:"Inherits analytics access plus approved unmasked PII access.",
  GOVAI_PIPELINE_ROLE:"Load accepted S3 objects into RAW and write pipeline evidence.",
  GOVAI_DBT_ROLE:"Read RAW and build governed STAGING, CURATED, and ANALYTICS objects.",
};
function CloudControl(){
  const artifactCount=Object.values(cloud.artifacts).filter(Boolean).length;
  const toolCount=Object.values(cloud.tools).filter(Boolean).length;
  const verified=cloud.live_verification_status==="VERIFIED";
  return <div className="stack cloud-page"><Title eyebrow="Phase 2 · enterprise platform boundary" title="Cloud control plane" description="Implementation evidence for the AWS S3, Snowflake, dbt, access-control, and reconciliation path—with live status kept separate from local verification." tag={verified?"● Live verified":"○ Live run not performed"}/>
    <section className={`cloud-truth ${verified?"verified":"pending"}`}><div>{verified?"✓":"!"}</div><p><span>{verified?"CLOUD EVIDENCE VERIFIED":"CREDENTIAL BOUNDARY REACHED"}</span><b>{verified?"A reconciled live run is recorded.":"AWS and Snowflake remain undeployed in this environment."}</b><small>{cloud.truth_notice}</small></p><code>{cloud.live_verification_status}</code></section>
    <section className="stats cloud-stats"><Stat label="Phase 2 artifacts" value={`${artifactCount}/${Object.keys(cloud.artifacts).length}`} detail="Terraform, dbt, SQL, and orchestrator present" tone="safe"/><Stat label="Live integrations" value={verified?"Verified":"0 verified"} detail="No cloud deployment claim without evidence"/><Stat label="Roles defined" value={`${cloud.rbac_roles.length}`} detail="Least-privilege job functions in SQL"/><Stat label="Cloud tools available" value={`${toolCount}/${Object.keys(cloud.tools).length}`} detail="Current execution environment only"/></section>
    <section className="panel cloud-flow"><Heading eyebrow="Cross-platform dependency path" title="S3 → Snowflake → dbt lineage" badge={verified?"Executed":"Defined · not executed"} safe={verified}/><div>{cloud.cloud_lineage.map((edge,index)=><article key={`${edge.from}-${edge.to}`}><span>{String(index+1).padStart(2,"0")}</span><p><b>{edge.from}</b><i>→</i><strong>{edge.to}</strong></p><small className={edge.status==="VERIFIED_LOCALLY"?"local":"pending"}>{edge.status.replaceAll("_"," ")}</small></article>)}</div></section>
    <section className="cloud-grid">
      <article className="panel zones"><Heading eyebrow="Encrypted object storage" title="S3 data-lake zones" badge="Terraform defined"/><div>{cloud.s3_zones.map(zone=><section key={zone.name}><span>{zone.name.slice(0,2).toUpperCase()}</span><p><b>{zone.name}</b><small>{zone.purpose}</small></p><i>{zone.name==="curated"?"EMPTY UNTIL EXPORT":"READY FOR LIVE RUN"}</i></section>)}</div></article>
      <article className="panel reconciliation"><Heading eyebrow="Local ↔ cloud control" title="Reconciliation gate" badge={verified?"Matched":"Awaiting evidence"} safe={verified}/><div className="recon-ring"><strong>{verified?"3/3":"—"}</strong><span>batch manifests matched</span></div><dl><div><dt>Deterministic batch ID</dt><dd>Required</dd></div><div><dt>Accepted row count</dt><dd>{verified?"Matched":"Not measured"}</dd></div><div><dt>Source SHA-256</dt><dd>{verified?"Matched":"Not measured"}</dd></div><div><dt>Unsafe continuation</dt><dd>Raises failure</dd></div></dl><p>Only a successful run with three matching audit records can change this panel to verified.</p></article>
    </section>
    <section className="panel privacy"><Heading eyebrow="Least privilege + dynamic data masking" title="RBAC and privacy controls" badge="SQL defined · live tests pending"/><div className="privacy-grid">{cloud.rbac_roles.map(role=><article key={role}><code>{role}</code><p>{rolePurpose[role]}</p></article>)}</div><footer><b>Masking intent</b><span>Name, email, phone, credit limit, amount, and confirmed loss policies are defined. Static tests passed; Snowflake role-session behavior is not yet live-verified.</span></footer></section>
    <section className="panel cloud-evidence"><div><Heading eyebrow="Quality gate reused in cloud orchestration" title="Quarantine proof survives Phase 2"/><p>The locally verified incident still isolates {data.incident.quarantined_rows} rows and protects {data.incident.impacted_asset_ids.length} downstream assets. The cloud orchestrator test proves its warehouse and dbt ports are never called for that bad batch.</p></div><div><span>RAW OBJECT</span><b>accepted for evidence</b></div><i>→</i><div><span>QUALITY CONTRACT</span><b>{data.incident.critical_violation_count} failures</b></div><i>→</i><div className="blocked"><span>QUARANTINE</span><b>publish blocked</b></div></section>
  </div>;
}

function Catalog(){
  const [query,setQuery]=useState(""),[layer,setLayer]=useState("all"),[selected,setSelected]=useState(data.assets[0].asset_id);
  const filtered=data.assets.filter(a=>`${a.display_name} ${a.asset_id} ${a.owner}`.toLowerCase().includes(query.toLowerCase())&&(layer==="all"||a.layer===layer));
  const asset=data.assets.find(a=>a.asset_id===selected)??filtered[0];const columns=data.column_classifications.filter(c=>c.asset_id===asset?.asset_id);
  return <div className="stack"><Title eyebrow="Governed knowledge architecture" title="Data catalog" description="Search assets and inspect ownership, sensitivity, freshness, taxonomy, and masking policy." tag={`${data.summary.classified_columns} classified columns`}/><section className="catalog-controls"><label>⌕<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search asset, owner, or ID"/></label><div>{["all",...layers].map(l=><button className={layer===l?"active":""} onClick={()=>setLayer(l)} key={l}>{l}</button>)}</div></section><section className="catalog-layout"><div className="catalog-list">{filtered.map(a=><button className={`catalog-row ${asset?.asset_id===a.asset_id?"selected":""}`} onClick={()=>setSelected(a.asset_id)} key={a.asset_id}><span>{a.asset_type.slice(0,2).toUpperCase()}</span><p><b>{a.display_name}</b><code>{a.asset_id}</code></p><aside><small>OWNER</small>{a.owner}</aside><i>{a.sensitivity}</i><strong>›</strong></button>)}{!filtered.length&&<p className="empty">No assets match this filter.</p>}</div>{asset&&<aside className="catalog-detail"><span className="asset-pill">{asset.layer} · {asset.asset_type.replaceAll("_"," ")}</span><h2>{asset.display_name}</h2><code>{asset.asset_id}</code><p>{asset.description}</p><dl><div><dt>Owner</dt><dd>{asset.owner}</dd></div><div><dt>Sensitivity</dt><dd>{asset.sensitivity}</dd></div><div><dt>Freshness</dt><dd>{asset.freshness_sla}</dd></div><div><dt>Physical object</dt><dd>{asset.physical_name??"Virtual asset"}</dd></div><div><dt>Rows</dt><dd>{asset.row_count===null?"—":asset.row_count.toLocaleString()}</dd></div></dl><section><span>CLASSIFIED COLUMNS</span>{columns.length?columns.map(c=><div key={c.column_name}><b>{c.column_name}</b><small>{c.classification.replaceAll("_"," ")}</small><code>{c.masking_policy}</code></div>):<p>No column-level entries registered for this asset.</p>}</section></aside>}</section></div>;
}

export default function App(){
  const [view,setView]=useState<View>("overview"),label=nav.find(n=>n.id===view)?.label;
  return <div className="app"><aside className="sidebar"><button className="brand" onClick={()=>setView("overview")}><span>G</span><p><b>Govern</b>AI<small>TRUST CONTROL PLANE</small></p></button><nav><small>WORKSPACE</small>{nav.map(n=><button className={view===n.id?"active":""} key={n.id} onClick={()=>setView(n.id)}><span>{n.mark}</span>{n.label}{n.id==="incident"&&<i>1</i>}</button>)}</nav><section className="phase"><span>PHASE 2 · LIVE GATE</span><b>Cloud platform boundary</b><p>Implementation and local contracts verified. AWS/Snowflake run not performed.</p><div><i/></div><small>Live verification pending</small></section><footer><i/> Simulated banking data</footer></aside><main><header><p><span>GovernAI</span><i>/</i><b>{label}</b></p><div><span><i/>Data current · SLA {data.freshness.sla}</span><b>{view==="cloud"?`CLOUD ${cloud.live_verification_status.replaceAll("_"," ")}`:"LOCAL VERIFIED"}</b><button title={data.data_notice}>i</button></div></header><nav className="mobile-nav">{nav.map(n=><button key={n.id} className={view===n.id?"active":""} onClick={()=>setView(n.id)}>{n.mark}</button>)}</nav><div className="content">{view==="overview"&&<Overview setView={setView}/>} {view==="incident"&&<Incident setView={setView}/>} {view==="lineage"&&<Lineage/>} {view==="catalog"&&<Catalog/>} {view==="cloud"&&<CloudControl/>}<footer className="page-footer"><span>{data.data_notice}</span><span>{view==="cloud"?`Cloud status ${date(cloud.generated_at)} · Live ${cloud.live_verification_status}`:`Snapshot ${date(data.generated_at)} · Schema ${data.schema_version}`}</span></footer></div></main></div>;
}
