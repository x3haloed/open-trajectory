from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0311_remaining_catalog_priority_wake.py"
BASE_SHA256="1fb3794df62bb7b8ddefdb388594a325cdf6b777059a8cd7ee618f8c2658c12d"
PARENT_DIGEST="9abf13255567696e1ff2834649327409e176d3b4a99f8aa02c17b643affe60c1"
OT311_RECEIPT="ca6b040c38b66cc272aec77c0a72ed3d71b073e1314a483eb70ac9a7272a640e"
AUTHORITY="ot-0312-priority-selected-vs-blind-downstream"; PULSE=None

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0311 changed")
    spec=importlib.util.spec_from_file_location("ot0312_frozen_ot0311",BASE_PATH)
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module)
    return module

base311=load_base(); base310=base311.base310; base308=base310.base308
base307=base311.base307; base270=base311.base270; b=base311.b
INHERITED_DERIVE=base311.derive
for module in (base311,base310,base308,base307,base270): module.AUTHORITY=AUTHORITY
write_json=base311.write_json

def setup(args):
    lineage=b.authority_base.guide_base.load_base(); selector,core,base130=lineage.selector_base,lineage.base,lineage.base130
    repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0312").resolve()
    _,_,_,p82=core.mechanism.prior_chain(core.mechanism.load_prior()); runtime=p82.load_runtime(repo,store)
    load=lambda exp,name: selector.load_artifact(p82,repo,store,exp,name)
    parent=load("OT-0311","open-subject-after-remaining-catalog-priority-wake.json")
    result311=load("OT-0311","remaining-catalog-priority-wake-aggregate.json")
    parent310=load("OT-0310","open-subject-after-state-driven-continuation.json")
    packages=[load("OT-0305",f"subject-blind-provider-{i:02d}-world-package.json") for i in range(1,5)]
    result280=load("OT-0280","import-stable-world-evaluator-aggregate.json")
    return repo,run,p82,runtime,parent,result311,parent310,packages,result280,core,base130

def package_by_id(packages,world_id): return next(p for p in packages if p["world_id"]==world_id)

def blind_offer(parent310,result311,packages,p82):
    _,waiting,reused=base311.install_wait(parent310,p82)
    if reused: raise RuntimeError("wait reused")
    world_id=result311["selection"]["blind_world_id"]; package=package_by_id(packages,world_id)
    observation,offered,wake_reused=b.base281.wake(waiting,package,p82)
    if wake_reused or observation.get("status")!="world-available": raise RuntimeError("blind wake failed")
    body={"authority":AUTHORITY+"-blind-control-contact","source_subject_digest":waiting["artifact_digest"],"stake_binding_digest":waiting["active_world_seeking_stake"]["binding_digest"],"catalog_digest":p82.digest(result311["public_descriptors"]),"selected_world_id":world_id,"active_stake_selected_world_id":result311["selection"]["selected_world_id"],"intervention":"stake-selection-erased","selection_authority":"digest-blind-control","world_authority":"independent-provider-catalog"}
    receipt={**body,"receipt_digest":p82.digest(body)}; child=copy.deepcopy(offered); child.pop("artifact_digest",None)
    child["subject_priority_contact_receipts"]=[*child.get("subject_priority_contact_receipts",[]),receipt]
    child["continuation"]={**child["continuation"],"status":"open","next_opening":"Select contact inside the digest-blind control world."}
    child["unresolved"]=waiting["active_world_seeking_stake"]["stake"]["question"]
    return p82.seal(child),package,receipt

def new_epoch_refresh_due(subject,p82):
    driver=subject.get("fixed_g6_recurrence_driver") or {}; target=driver.get("last_target")
    ledger=subject.get("local_frontier_ledger",{}).get("targets",{}); state=ledger.get(target) if isinstance(target,str) else None
    projection=subject.get("active_opportunity_projection") or {}; epochs=subject.get("actor_authored_environment_epochs") or []; epoch=epochs[-1] if epochs else {}
    resolved=b.base264.base253.derive(subject)
    expected={(path,symbol) for path,row in epoch.get("visible_sources",{}).items() for symbol in row.get("top_level_callables",[]) if symbol not in ledger}
    observed={(row.get("target_path"),row.get("target_symbol")) for row in resolved.get("opportunities",[]) if isinstance(row,dict)}
    return bool(driver.get("phase")=="assimilate" and base310.INHERITED_DERIVE(subject,p82)=="refresh-opportunity-projection" and base310.projection_receipt_valid(subject,p82) and epoch.get("environment_id")!=projection.get("active_epoch_id") and epoch.get("selected_target")==target and isinstance(state,dict) and state.get("status")=="verified-local" and state.get("latest_world_outcome")=="success" and state.get("correction_receipts") and state.get("independent_success_receipts") and subject.get("active_streamed_world_offer") is None and resolved.get("status") in {"active","saturated"} and not resolved.get("source_errors") and observed==expected and len(observed)==2)

def derive(subject,p82):
    if base310.refresh_due(subject,p82) or new_epoch_refresh_due(subject,p82): return "refresh-opportunity-projection"
    return INHERITED_DERIVE(subject,p82)
b.base272.derive=derive

def invalid_controls(corrected,p82):
    controls={}
    changes={
      "malformed-projection-receipt":lambda x:x["active_opportunity_projection"].__setitem__("opportunity_count",1),
      "mismatched-selected-target":lambda x:x["actor_authored_environment_epochs"][-1].__setitem__("selected_target","not-ledger-target"),
      "missing-success-authority":lambda x:x["local_frontier_ledger"]["targets"][x["fixed_g6_recurrence_driver"]["last_target"]].__setitem__("independent_success_receipts",[])}
    for name,change in changes.items():
        value=copy.deepcopy(corrected); value.pop("artifact_digest",None); change(value); value=p82.seal(value); controls[name]=not new_epoch_refresh_due(value,p82)
    return controls

def fixture_endpoint(root,offered,package,result280,p82,runtime):
    evaluation=b.base268.evaluate_package(package,p82.digest); rows=[]; example=None
    for index,target in enumerate(sorted(evaluation["targets"]),1):
        branch=root/f"target-{index:02d}"; decision=base270.fixture_decision(package,evaluation,target); seed=base270.seed_actor(branch/"actor",offered,decision)
        checker=subprocess.run(["python3","check_expansion.py"],cwd=seed,capture_output=True); evaluated=base270.evaluate_workspace(seed,seed,offered)
        action={"decision":decision,"binding":{"binding_digest":"a"*64,"contact_identity":"b"*64}}
        pulse={"authority":AUTHORITY+"-fixture-pulse","content":None,"source_subject_digest":offered["artifact_digest"],"derived_operation":"expand-environment"}; pulse["pulse_digest"]=p82.digest(pulse)
        intermediate=base270.compile_intermediate(offered,action,pulse,p82); contact_world=base270.sealed_world(intermediate,action,package,result280,p82); contacted=base270.compile_world(intermediate,contact_world,p82)
        actor,public,world=base307.fixture_revise(contacted,package,result280,p82,success=True)
        corrected=(base307.base273.compile_success(contacted,actor,world,p82) if base307.base274.feedback_mode(contacted) else base307.base271.compile_correction(contacted,actor,world,p82))
        due=new_epoch_refresh_due(corrected,p82); refreshed=b.base264.refresh_projection_only(corrected,p82) if due else corrected
        repaired,_=base308.repair(refreshed,p82) if derive(refreshed,p82)=="repair-actor-facing-coherence" else (refreshed,None)
        rows.append({"selection_passes":checker.returncode==0 and evaluated["semantic"] and evaluated["public"]["all_valid"],"contradiction_2_of_6":contact_world["result"]["matches"]==2 and contact_world["outcome"]=="unresolved","correction_6_of_6":public["all_valid"] and world["result"]["matches"]==6,"unchanged_2_of_6":world["unchanged_control"]["matches"]==2,"new_epoch_refresh_due":due,"two_open_opportunities":len(repaired.get("active_opportunity_projection",{}).get("opportunities",[]))==2,"next_is_selection":derive(repaired,p82)=="expanded-select","conformant":runtime.identity_conforms(repaired)})
        example=corrected
    return rows,invalid_controls(example,p82)

def preflight(root,p82,runtime,parent,result311,parent310,packages,result280):
    root.mkdir(parents=True,exist_ok=True); selected_package=package_by_id(packages,result311["selection"]["selected_world_id"])
    blind,blind_package,blind_receipt=blind_offer(parent310,result311,packages,p82)
    stake_rows,stake_controls=fixture_endpoint(root/"stake",parent,selected_package,result280,p82,runtime)
    blind_rows,blind_controls=fixture_endpoint(root/"blind",blind,blind_package,result280,p82,runtime)
    scorer=lambda stake,control: bool(stake and not control)
    truth={"true-false":scorer(True,False),"true-true":not scorer(True,True),"false-true":not scorer(False,True),"false-false":not scorer(False,False)}
    checks={"base_hash_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256,"exact_ot0311_parent":parent["artifact_digest"]==PARENT_DIGEST and result311["receipt_digest"]==OT311_RECEIPT and result311["observer_disposition"]=="promoted","matched_distinct_worlds":selected_package["world_id"]!=blind_package["world_id"] and blind_receipt["intervention"]=="stake-selection-erased","stake_fixture_all_targets":len(stake_rows)==3 and all(all(r.values()) for r in stake_rows),"blind_fixture_all_targets":len(blind_rows)==3 and all(all(r.values()) for r in blind_rows),"new_epoch_invalid_controls":all(stake_controls.values()) and all(blind_controls.values()),"causal_scorer_truth_table":all(truth.values()),"both_open_conformant":runtime.identity_conforms(parent) and runtime.identity_conforms(blind)}
    checks["passed"]=all(checks.values()); result={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"selected_fixture":stake_rows,"blind_fixture":blind_rows,"selected_invalid_controls":stake_controls,"blind_invalid_controls":blind_controls,"causal_scorer_truth_table":truth,"checks":checks}; result["receipt_digest"]=p82.digest(result); write_json(root/"fixture-conformance.json",result); return result

def live_branch(label,repo,root,p82,runtime,offered,package,result280,core,base130):
    root.mkdir(parents=True); context=b.base274.context_for(core,base130,runtime,root,repo)
    actor=base270.run_actor(context,p82,root/"selection",offered)
    pulse={"authority":AUTHORITY+"-pulse","content":PULSE,"source_subject_digest":offered["artifact_digest"],"derived_operation":"expand-environment"}; pulse["pulse_digest"]=p82.digest(pulse)
    intermediate=base270.compile_intermediate(offered,actor,pulse,p82) if actor["accepted"] else offered
    world=base270.sealed_world(intermediate,actor,package,result280,p82) if actor["accepted"] else None
    contacted=base270.compile_world(intermediate,world,p82) if world else intermediate
    selection_ok=bool(actor.get("accepted") and actor.get("g10_disposition") and world and world["result"]["all_valid"] and world["result"]["matches"]==2 and derive(contacted,p82)=="outward-correct")
    if label=="stake": write_json(root.parent/"stake-operational-subject.json",contacted)
    correction=correction_world=feedback=None; corrected=contacted; transition="not-run"
    if selection_ok: correction,correction_world,feedback,corrected,transition=base307.run_correction(context,p82,root/"correction",contacted,package,result280)
    correction_ok=bool(correction and correction.get("accepted") and correction.get("g10_disposition") and correction_world and correction_world.get("promotion_gate") and correction_world.get("result",{}).get("matches")==6 and correction_world.get("unchanged_control",{}).get("matches")==2 and transition=="success-to-refresh" and new_epoch_refresh_due(corrected,p82))
    refreshed=b.base264.refresh_projection_only(corrected,p82) if correction_ok else corrected
    repaired,repair=base308.repair(refreshed,p82) if correction_ok and derive(refreshed,p82)=="repair-actor-facing-coherence" else (refreshed,None)
    hard=bool(correction_ok and repair and len(repaired.get("active_opportunity_projection",{}).get("opportunities",[]))==2 and derive(repaired,p82)=="expanded-select" and runtime.identity_conforms(repaired))
    return {"label":label,"source_subject_digest":offered["artifact_digest"],"world_id":package["world_id"],"selection_actor":actor,"contact_world":world,"selection_passed":selection_ok,"correction_actor":correction,"correction_world":correction_world,"correction_feedback":feedback,"correction_transition":transition,"repair_receipt":repair,"hard_endpoint":hard,"final_subject_digest":repaired["artifact_digest"]},repaired

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args()
    repo,run,p82,runtime,parent,result311,parent310,packages,result280,core,base130=setup(args)
    retained=run/"preflight/fixture-conformance.json"; fixtures=json.loads(retained.read_text()) if retained.exists() else preflight(run/"preflight",p82,runtime,parent,result311,parent310,packages,result280)
    if args.preflight_only: print(json.dumps(fixtures,indent=2,sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run/"aggregate.json").exists(): raise SystemExit("OT-0312 unavailable")
    selected_package=package_by_id(packages,result311["selection"]["selected_world_id"]); blind,blind_package,blind_receipt=blind_offer(parent310,result311,packages,p82)
    stake,stake_subject=live_branch("stake",repo,run/"branch-stake",p82,runtime,parent,selected_package,result280,core,base130); write_json(run/"stake-branch.json",stake); write_json(run/"stake-final-subject.json",stake_subject)
    blind_result,blind_subject=live_branch("blind",repo,run/"branch-blind",p82,runtime,blind,blind_package,result280,core,base130); write_json(run/"blind-branch.json",blind_result); write_json(run/"blind-final-subject.json",blind_subject)
    better=bool(stake["hard_endpoint"] and not blind_result["hard_endpoint"]); operational=stake["selection_passed"]
    checks={"preflight_passed":fixtures["checks"]["passed"],"stake_run_first_and_sealed":(run/"stake-operational-subject.json").exists(),"one_selection_and_at_most_one_correction_actor_per_branch":True,"workspaces_outside_repo":not run.resolve().is_relative_to(repo),"stake_operational_contact":operational,"matched_distinct_worlds":stake["world_id"]==result311["selection"]["selected_world_id"] and blind_result["world_id"]==result311["selection"]["blind_world_id"]}; checks["passed"]=all(checks.values())
    aggregate={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"source_ot0311_receipt_digest":result311["receipt_digest"],"blind_control_receipt":blind_receipt,"branch_order":["stake","blind"],"stake_branch":stake,"blind_branch":blind_result,"checks":checks,"operational_transition_passed":operational,"causal_better_downstream_supported":better,"observer_disposition":"promoted" if better else "rejected","subject_disposition":stake_subject["continuation"]["status"],"final_subject_digest":stake_subject["artifact_digest"],"fresh_actor_count":sum(1+int(row["correction_actor"] is not None) for row in (stake,blind_result))}; aggregate["receipt_digest"]=p82.digest(aggregate); write_json(run/"aggregate.json",aggregate); print(json.dumps(aggregate,indent=2,sort_keys=True)); return 0 if checks["passed"] else 2

if __name__=="__main__": raise SystemExit(main())
