from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0270_standing_scanner_independent_package_contact.py"; BASE_SHA256="04cfafa453e3be47a3eb489b2d923b29d306c5962104335963a4da574d976b2e"
PARENT="ee66f4df4d9970e1c689e16bcabf1d3e6d47e87afd9f2f051298118cc4c1aacc"; RECEIPT="fdee3f2f1b3152bbafe25341317658d25ce5812d0d2bb6436d5e5170c1ede265"; AUTH="ot-0276-asterfall-fourth-wake"
def load():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("base changed")
    s=importlib.util.spec_from_file_location("ot0276_base",BASE_PATH); m=importlib.util.module_from_spec(s); sys.modules[s.name]=m; s.loader.exec_module(m); return m
b=load(); guide=b.authority_base.guide_base
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo",type=Path,default=REPO); ap.add_argument("--store",type=Path); ap.add_argument("--evidence-root",type=Path); ap.add_argument("--preflight-only",action="store_true"); a=ap.parse_args()
    l=guide.load_base(); repo=a.repo.resolve(); store=(a.store or repo/".evidence").resolve(); run=(a.evidence_root or store/"runs/OT-0276").resolve(); p92=l.base.mechanism.load_prior(); _,_,_,p82=l.base.mechanism.prior_chain(p92); runtime=p82.load_runtime(repo,store)
    subject=l.selector_base.load_artifact(p82,repo,store,"OT-0274","open-subject-at-fourth-standing-feed-wait.json"); package=l.selector_base.load_artifact(p82,repo,store,"OT-0275","independent-asterfall-world-package.json"); result=l.selector_base.load_artifact(p82,repo,store,"OT-0275","post-mechanism-independent-world-aggregate.json")
    obs=b.scan(subject,package,p82); final,reused=b.compile_offer(subject,obs,p82); empty=b.base267.scan_feed(subject,[],p82.digest)
    c={"parent_exact_wait":subject["artifact_digest"]==PARENT and b.derive(subject,p82)=="wait-provider","package_exact":result["receipt_digest"]==RECEIPT,"scanner_found":obs["status"]=="world-available","wait_discharged":not reused and final["active_world_stream_wait"] is None and len(final["world_stream_wait_discharge_receipts"])==4,"non_authoritative":all(final["active_streamed_world_offer"][k] is False for k in ("selection_authority","scoring_authority","admission_authority","outcome_authority","actor_authority")),"no_ledger_epoch_change":final["local_frontier_ledger"]==subject["local_frontier_ledger"] and final["actor_authored_environment_epochs"]==subject["actor_authored_environment_epochs"],"next_expansion":b.derive(final,p82)=="expand-environment","empty_no_wake":empty["status"]=="empty","conformant":runtime.identity_conforms(final)}; c["passed"]=all(c.values()); out={"authority":AUTH,"source_subject_digest":subject["artifact_digest"],"checks":c,"observer_disposition":"promoted" if c["passed"] else "rejected","final_subject_digest":final["artifact_digest"],"fresh_actor_count":0}; out["receipt_digest"]=p82.digest(out)
    if a.preflight_only: print(json.dumps(out,indent=2,sort_keys=True)); return 0 if c["passed"] else 2
    if run.exists(): raise SystemExit("preserve evidence")
    run.mkdir(parents=True); guide.write_json(run/"scanner-observation.json",obs); guide.write_json(run/"final-full-subject.json",final); guide.write_json(run/"aggregate.json",out); print(json.dumps(out,indent=2,sort_keys=True)); return 0 if c["passed"] else 2
if __name__=="__main__": raise SystemExit(main())
