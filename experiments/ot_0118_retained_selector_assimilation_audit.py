from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0117_world_grounded_selector_expansion.py"; BASE_SHA256="c8c5cecd6b86f5b3550d2539038092558902b1e9b0cc8444c75ee91f0796b772"
RUN_SHA256="7bcf18e0fa7454bdc1efc401616ff715786ec58889a71705612ca2d1723f144e"; AGGREGATE_SHA256="e53f0fb02a409d15ac64a7ff8c03b67671914cf46df6b6c553d32068a1b88bca"; PARENT_OBJECT_SHA256="3ad82e07c8bc455d2cb84b9818a614e326432c5d12f4e2981d1033843fbda4a9"
PARENT_DIGEST="597fd631b365952423cb1908a7bb201af0116b4a2e707bd1a07514cf93205786"; SELECTOR_PATCH="0e4d183d9c43867955eb01e4dc70a6f3fc5f5213a9130f0ab01f3234bb544d00"; ASSIMILATION_PATCH="7ac8a7a6c0dc06b93641f4784a09fa14f8a7f55bbc1744c991c0a0de1efb1dfc"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0117 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0118_frozen_ot0117",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
previous=load_base(); base=previous.base

def extract(path,destination):
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        for member in members:
            parts=PurePosixPath(member.name).parts
            if not parts or parts[0]!="OT-0117" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk(): raise RuntimeError("unsafe OT-0117 archive")
        archive.extractall(destination,members=members)
    return destination/"OT-0117"

def load_inputs(p82,repo,store,destination):
    rm,rp=p82.materialize(repo,store,"OT-0117","world-grounded-selector-improvement-run.json"); am,ap=p82.materialize(repo,store,"OT-0117","world-grounded-selector-improvement-aggregate.json"); pm,pp=p82.materialize(repo,store,"OT-0117","unchanged-open-subject-after-assimilation-audit-stop.json")
    if rm["sha256"]!=RUN_SHA256 or am["sha256"]!=AGGREGATE_SHA256 or pm["sha256"]!=PARENT_OBJECT_SHA256: raise RuntimeError("wrong OT-0117 inputs")
    return extract(rp,destination),json.loads(ap.read_text()),json.loads(pp.read_text())

def inspect(p82,repo,store,destination):
    raw,aggregate,parent=load_inputs(p82,repo,store,destination); author=aggregate["selector_revision"]; world=aggregate["world"]; assimilation=aggregate["assimilation"]; aws=raw/"selector-assimilation/actor-workspace"; events=[json.loads(line) for line in (raw/"selector-assimilation/events.jsonl").read_text().splitlines() if line.strip()]; stderr=(raw/"selector-assimilation/stderr.txt").read_text(); hidden=json.loads((raw/"hidden-portfolios.json").read_text())
    source=author["binding"]["selector_source"]; parent_source=parent["allocation_machinery"][-1]["source"]; revised=previous.evaluate(source,hidden); inherited=previous.evaluate(parent_source,hidden)
    commands=[row.get("item",{}).get("command","") for row in events if row.get("type")=="item.completed" and row.get("item",{}).get("type")=="command_execution"]
    outputs=[row.get("item",{}).get("aggregated_output","") for row in events if row.get("type")=="item.completed" and row.get("item",{}).get("type")=="command_execution"]
    denied_command_observed=any("shasum" in command for command in commands); equivalent_cmp=any("cmp -s revised-selector.py" in command for command in commands) and any("selector bytes: unchanged" in output for output in outputs)
    denied_warning=stderr.count("recorded sandbox violation: resource=filesystem backend=seatbelt reason=policy_denied path=unknown")==1
    audit=assimilation["audit"]; trace_clean=bool(audit["trace_regime"]["accepted"] and audit["exact_changes"] and audit["truthful"] and not audit["denial_classification_v2"]["protected_path_named"] and not audit["denial_classification_v2"]["outside_file_changes"])
    retained=(aws/"revised-selector.py").read_text()==source; a=json.loads((aws/"assimilation.json").read_text()); opening=json.loads((aws/"successor-opening.json").read_text()); action=json.loads((aws/"continuation-action.json").read_text()); prior92=base.mechanism.load_prior(); _,_,prior89,_=base.mechanism.prior_chain(prior92); passed_ids={r["portfolio_id"] for r in world["revised"]["rows"] if r["passed"]}; cited=set(a.get("settled_case_ids",[]))
    checks={"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"source_rejected":not aggregate["operational_transition_passed"],"selector_patch_exact":author["audit"]["patch_digest"]==SELECTOR_PATCH,"selector_author_clean":author["audit"]["conformant"],"world_recomputed":revised==world["revised"] and inherited==world["inherited"],"comparison_exact":revised["correct_count"]==12 and revised["total_regret"]==0 and revised["floor_correct_count"]==4 and inherited["correct_count"]==4 and inherited["total_regret"]==548,"assimilation_patch_exact":audit["patch_digest"]==ASSIMILATION_PATCH,"assimilation_trace_complete":trace_clean,"selector_retained":retained,"assimilation_valid":base.valid_assimilation(a),"opening_valid":prior89.valid_successor(opening),"action_valid":previous.previous.repaired_action_valid(action,parent),"citations_grounded":bool(cited and cited.issubset(passed_ids)),"one_denied_warning":denied_warning,"equivalent_cmp_observed":equivalent_cmp,"denied_command_and_target_observed":denied_command_observed}
    checks["materiality_rule_passed"]=bool(checks["one_denied_warning"] and checks["equivalent_cmp_observed"] and checks["denied_command_and_target_observed"]); checks["promotion_gate_passed"]=all(checks.values())
    return parent,checks,{"commands":commands,"stderr_denial_count":1 if denied_warning else 0,"denied_command_observed":denied_command_observed,"equivalent_cmp_observed":equivalent_cmp}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0118").resolve(); prior92=base.mechanism.load_prior(); _,_,_,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store)
    with tempfile.TemporaryDirectory() as directory: parent,checks,trace=inspect(p82,repo,store,Path(directory))
    preflight={"base_sha256":BASE_SHA256,"run_sha256":RUN_SHA256,"aggregate_sha256":AGGREGATE_SHA256,"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"runtime_sounding":runtime.identity_conforms(parent)}
    if args.preflight_only: print(json.dumps(preflight,indent=2,sort_keys=True)); return 0 if all(preflight.values()) else 2
    if run.exists(): raise SystemExit("preserve existing OT-0118 evidence")
    run.mkdir(parents=True); started=time.time(); result={"authority":"ot-0118-retained-selector-assimilation-audit","source_subject_digest":parent["artifact_digest"],"reconstruction_checks":checks,"trace_materiality":trace,"operational_transition_passed":False,"observer_disposition":"rejected","subject_disposition":parent["continuation"]["status"],"final_subject_digest":parent["artifact_digest"],"continuation_action":parent["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":parent["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(parent,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 2
if __name__=="__main__": raise SystemExit(main())
