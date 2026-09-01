from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0119_explicit_selector_assimilation.py"; BASE_SHA256="358caae4a683cae1d6a5349bce711741b6f9b7ebf29618e963256f8fd09e2913"
RUN_SHA256="61e1e5113cb81ede8bad80dd43d5fcba37c56ec57c41969608612511968c8a4a"; AGGREGATE_SHA256="3f865070310d60a6385b1ddca3e3d2e2e856c00a2f58f63e4886228a336335c5"; PARENT_OBJECT_SHA256="3ad82e07c8bc455d2cb84b9818a614e326432c5d12f4e2981d1033843fbda4a9"
PARENT_DIGEST="597fd631b365952423cb1908a7bb201af0116b4a2e707bd1a07514cf93205786"; ASSIMILATION_PATCH="4fead8c291213539730f886f7accd2d880efff2b8efea68759fa8d70175bc3e4"; SELECTOR_BINDING="b03f52963b7ed38bd4274fcf68e2f180cb6fd6dda274fc2d9491c622cbe024f6"; WORLD_RECEIPT="9f14488008551dfb113bffd0e65846d3508317b1ac7855465ca3ca55ddac2667"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0119 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0120_frozen_ot0119",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
previous=load_base(); prior17=previous.prior17; base=previous.base

def extract(path,destination):
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        for member in members:
            parts=PurePosixPath(member.name).parts
            if not parts or parts[0]!="OT-0119" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk(): raise RuntimeError("unsafe OT-0119 archive")
        archive.extractall(destination,members=members)
    return destination/"OT-0119"

def load_inputs(p82,repo,store,destination):
    rm,rp=p82.materialize(repo,store,"OT-0119","renewed-opening-selector-assimilation-run.json"); am,ap=p82.materialize(repo,store,"OT-0119","renewed-opening-selector-assimilation-aggregate.json"); pm,pp=p82.materialize(repo,store,"OT-0119","unchanged-open-subject-after-renewed-opening.json")
    if rm["sha256"]!=RUN_SHA256 or am["sha256"]!=AGGREGATE_SHA256 or pm["sha256"]!=PARENT_OBJECT_SHA256: raise RuntimeError("wrong OT-0119 inputs")
    raw=extract(rp,destination); aggregate=json.loads(ap.read_text()); parent=json.loads(pp.read_text()); consequence=json.loads((raw/"explicit-selector-assimilation-seed/subject-contact-consequence.json").read_text()); workspace=raw/"explicit-selector-assimilation/actor-workspace"
    return raw,aggregate,parent,consequence["selector_binding"],consequence["world_receipt"],workspace

def reconstruct(prior89,p82,repo,store,destination):
    raw,aggregate,parent,selector,world,workspace=load_inputs(p82,repo,store,destination); assimilation=json.loads((workspace/"assimilation.json").read_text()); opening=json.loads((workspace/"successor-opening.json").read_text()); action=json.loads((workspace/"continuation-action.json").read_text()); audit=aggregate["assimilation"]["audit"]; passed_ids={row["portfolio_id"] for row in world["revised"]["rows"] if row["passed"]}; cited=set(assimilation["settled_case_ids"]); parent_opening=base.active_position(parent)["continuation"]["next_opening"]
    checks={"source_rejected":not aggregate["operational_transition_passed"],"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"selector_exact":selector["binding_digest"]==SELECTOR_BINDING,"world_exact":world["receipt_digest"]==WORLD_RECEIPT,"machinery_improved":world["passed"] and world["revised"]["correct_count"]==12 and world["revised"]["total_regret"]==0 and world["inherited"]["correct_count"]==4 and world["inherited"]["total_regret"]==548,"floor_preserved":world["revised"]["floor_correct_count"]==world["inherited"]["floor_correct_count"]==4,"assimilation_patch_exact":audit["patch_digest"]==ASSIMILATION_PATCH,"trace_clean":bool(audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["classification"]=="clean" and not audit["denial_classification_v2"]["sandbox_violation_retained"] and audit["exact_changes"] and audit["truthful"]),"selector_retained":(workspace/"revised-selector.py").read_text()==selector["selector_source"],"assimilation_valid":base.valid_assimilation(assimilation),"opening_valid":prior89.valid_successor(opening),"action_valid":previous.prior18.previous.previous.repaired_action_valid(action,parent),"citations_exact":cited==passed_ids,"machinery_update_stated":"resilience" in assimilation["selection_rule_update"].lower(),"unresolved_contact_distinct":"does not establish" in assimilation["remaining_uncertainty"].lower() and "boundary" in assimilation["remaining_uncertainty"].lower(),"opening_renewed":opening["next_opening"]==parent_opening,"renewed_contact_matches_uncertainty":"boundary" in opening["next_opening"].lower() and bool(opening["surrender_condition"].strip())}
    checks["passed"]=all(checks.values()); binding=None
    if checks["passed"]:
        body={"authority":"ot-0120-grounded-opening-renewal-assimilation","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":selector["binding_digest"],"world_receipt_digest":world["receipt_digest"],"actor_patch_digest":audit["patch_digest"],"selector_retention_derived":True,"renewal_gate":{key:value for key,value in checks.items() if key in {"machinery_improved","citations_exact","machinery_update_stated","unresolved_contact_distinct","opening_renewed","renewed_contact_matches_uncertainty"}},"assimilation":assimilation,"successor_opening":opening,"continuation_action":action}; binding={**body,"binding_digest":p82.digest(body)}
    return parent,selector,world,checks,binding

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0120").resolve(); prior92=base.mechanism.load_prior(); _,_,prior89,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store)
    with tempfile.TemporaryDirectory() as directory: parent,selector,world,checks,binding=reconstruct(prior89,p82,repo,store,Path(directory))
    preflight={"base_sha256":BASE_SHA256,"run_sha256":RUN_SHA256,"aggregate_sha256":AGGREGATE_SHA256,"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"runtime_sounding":runtime.identity_conforms(parent)}
    if args.preflight_only: print(json.dumps(preflight,indent=2,sort_keys=True)); return 0 if all(preflight.values()) else 2
    if run.exists(): raise SystemExit("preserve existing OT-0120 evidence")
    run.mkdir(parents=True); started=time.time(); (run/"reconstruction-checks.json").write_text(json.dumps(checks,indent=2,sort_keys=True)+"\n"); current=parent; promotion=None
    if binding:
        (run/"bound-retained-assimilation.json").write_text(json.dumps(binding,indent=2,sort_keys=True)+"\n"); current,promotion=prior17.promote(p82,parent,selector,world,binding)
    operational=bool(promotion and runtime.identity_conforms(current)); result={"authority":"ot-0120-grounded-opening-renewal-driver","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":selector["binding_digest"],"world_receipt_digest":world["receipt_digest"],"reconstruction_checks":checks,"assimilation_binding_digest":binding["binding_digest"] if binding else None,"promotion":promotion,"operational_transition_passed":operational,"observer_disposition":"promoted" if operational else "rejected","subject_disposition":current["continuation"]["status"],"final_subject_digest":current["artifact_digest"],"continuation_action":current["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":current["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if operational else 2
if __name__=="__main__": raise SystemExit(main())
