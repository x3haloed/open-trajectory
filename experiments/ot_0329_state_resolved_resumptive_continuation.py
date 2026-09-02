from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0328_contextual_selection_machinery_expansion.py"
BASE_SHA256="fe9f211301ca7ca2ff5a442a4169d615b704847ce92a0f9c587bcfdffe1c2cf3"
DRIVER_PATH=ROOT/"ot_0310_state_driven_multi_operation_continuation.py"
DRIVER_SHA256="df069b4382ce2bbef7d9bab3dd469b7a7da121fef7c69922d3ddbbe02464ca1e"
PARENT_DIGEST="fce8e08a9404f43bc82d65ee479e326040ac2dea6eb65335c719e0ea0f05501d"
OT328_RECEIPT="fb9a937399e91e6bc98196bb785e094e651a386339b89725fea3c4a7f00d9c95"
OT328_RECONSTRUCTION="6640e5bea2632ef0f3ac2cd079ed11cda8e8aae7e5aabcd98f633f0b50fc746b"
AUTHORITY="ot-0329-state-resolved-resumptive-continuation"
MAX_OPERATIONS=8; MAX_ACTORS=4; PULSE=None


def load_module(name,path,digest):
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual!=digest: raise RuntimeError(f"frozen source changed: {path.name} {actual}")
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); return module


base=load_module("ot0329_frozen_ot0328",BASE_PATH,BASE_SHA256)
driver=load_module("ot0329_frozen_ot0310",DRIVER_PATH,DRIVER_SHA256)
write_json=base.write_json
for module in (driver,driver.base309,driver.base308,driver.base307): module.AUTHORITY=AUTHORITY
driver.b.AUTHORITY=AUTHORITY; driver.b.base274.AUTHORITY=AUTHORITY; driver.b.base274.MAX_CALLS=MAX_ACTORS
driver.b.base274.base273.AUTHORITY=AUTHORITY; driver.b.base274.base271.AUTHORITY=AUTHORITY
driver.b.base272.base252.AUTHORITY=AUTHORITY; driver.b.base272.base245.AUTHORITY=AUTHORITY; driver.b.base272.base270.AUTHORITY=AUTHORITY
driver.PULSE=PULSE


def setup(args):
    repo,store,_,p82,runtime,parent326,seed326,parent327,result327,reconstruction327,private327,core,base130=base.setup(args)
    run=(args.evidence_root or store/"runs/OT-0329").resolve(); selector=base.b.authority_base.guide_base.load_base().selector_base
    load=lambda exp,name:selector.load_artifact(p82,repo,store,exp,name)
    parent=load("OT-0328","open-subject-after-contextual-selection-expansion.json")
    result=load("OT-0328","contextual-selection-machinery-expansion-aggregate.json")
    reconstruction=load("OT-0328","contextual-selection-machinery-expansion-exact-reconstruction.json")
    packages=[load("OT-0305",f"subject-blind-provider-{index:02d}-world-package.json") for index in range(1,5)]
    result280=load("OT-0280","import-stable-world-evaluator-aggregate.json")
    return repo,store,run,p82,runtime,parent,result,reconstruction,packages,result280,core,base130


def resolve_package(subject,packages,p82):
    projection=subject.get("active_opportunity_projection") or {}; epochs=subject.get("actor_authored_environment_epochs") or []
    if not epochs or projection.get("active_epoch_id")!=epochs[-1].get("environment_id"): raise RuntimeError("active epoch mismatch")
    matches=[package for package in packages if package.get("world_id")==projection.get("active_epoch_id")]
    if len(matches)!=1: raise RuntimeError("world package unavailable or ambiguous")
    package=matches[0]; evaluation=driver.b.base268.evaluate_package(package,p82.digest); epoch=epochs[-1]
    visible=epoch.get("visible_sources") or {}; package_visible=package.get("visible_sources") or {}
    projected={(row.get("target_path"),row.get("target_symbol")) for row in projection.get("opportunities",[]) if isinstance(row,dict)}
    available={(path,target) for target,path in evaluation.get("targets",{}).items()}
    projected_paths={path for path,_ in projected}
    internally_exact=bool(set(visible)==set(package_visible) and all(row.get("source_digest")==p82.digest(row.get("source","")) for row in visible.values()))
    live_sources_exact=all(visible.get(path,{}).get("source")==package_visible.get(path) for path in projected_paths)
    if not evaluation.get("valid") or not internally_exact or not live_sources_exact or not projected or not projected<=available: raise RuntimeError("state-resolved package does not conform")
    body={"authority":AUTHORITY+"-state-resolved-package","source_subject_digest":subject["artifact_digest"],"active_epoch_id":projection["active_epoch_id"],"epoch_binding_digest":epoch["binding_digest"],"public_package_digest":evaluation["public_package_digest"],"projected_opportunities_digest":p82.digest(projection["opportunities"]),"resolution_authority":"exact-subject-state","selection_authority":False,"world_authority":False}
    return package,{**body,"receipt_digest":p82.digest(body)}


def protected_overlay(subject):
    return {"active_contextual_selection_policy":subject.get("active_contextual_selection_policy"),"contextual_selection_policies":subject.get("contextual_selection_policies"),"contextual_selection_contradictions":subject.get("contextual_selection_contradictions"),"contextual_selection_world_receipts":subject.get("contextual_selection_world_receipts"),"contextual_selection_reuse_receipts":subject.get("contextual_selection_reuse_receipts")}


def simulate_order(root,parent,package,result280,p82,runtime,first):
    overlay=protected_overlay(parent); first_selection=driver.b.base272.selection_fixture(root/"first-selection",parent,package,result280,first["target_symbol"],p82,runtime); selected=first_selection["final"]
    _,first_public,first_world,corrected=driver.fixture_success(selected,package,result280,p82); refreshed=driver.b.base264.refresh_projection_only(corrected,p82); repaired,_=driver.base308.repair(refreshed,p82)
    remaining=repaired["active_opportunity_projection"]["opportunities"]; second=remaining[0]
    second_selection=driver.b.base272.selection_fixture(root/"second-selection",repaired,package,result280,second["target_symbol"],p82,runtime); selected_again=second_selection["final"]
    _,second_public,second_world,corrected_again=driver.fixture_success(selected_again,package,result280,p82); refreshed_again=driver.b.base264.refresh_projection_only(corrected_again,p82); final,_=driver.base308.repair(refreshed_again,p82)
    return {"first_target":first,"second_target":second,"first_selection_conformant":first_selection["conformant"],"first_public_complete":first_public["matches"]==first_public["case_count"],"first_correction_6_of_6":first_world["result"]["matches"]==6,"first_unchanged_2_of_6":first_world["unchanged_control"]["matches"]==2,"second_selection_conformant":second_selection["conformant"],"second_public_complete":second_public["matches"]==second_public["case_count"],"second_correction_6_of_6":second_world["result"]["matches"]==6,"second_unchanged_2_of_6":second_world["unchanged_control"]["matches"]==2,"both_targets_once":{first["target_symbol"],second["target_symbol"]}=={x["target_symbol"] for x in parent["active_opportunity_projection"]["opportunities"]},"final_zero_opportunities":final["active_opportunity_projection"]["opportunity_count"]==0,"final_expands_environment":driver.derive(final,p82)=="expand-environment","overlay_exact":protected_overlay(final)==overlay,"open_conformant":final["continuation"]["status"]=="open" and runtime.identity_conforms(final)}


def invalid_resolution_controls(parent,packages,p82):
    controls={}
    def alter_live_source(value):
        path=value["active_opportunity_projection"]["opportunities"][0]["target_path"]
        value["actor_authored_environment_epochs"][-1]["visible_sources"][path]["source"]="def altered(case):\n    return False\n"
    for name,change in {
        "unknown-active-epoch":lambda x:x["active_opportunity_projection"].__setitem__("active_epoch_id","unavailable-world"),
        "mismatched-latest-epoch":lambda x:x["actor_authored_environment_epochs"][-1].__setitem__("environment_id","different-world"),
        "altered-live-source":alter_live_source,
    }.items():
        value=copy.deepcopy(parent); value.pop("artifact_digest",None); change(value); value=p82.seal(value)
        try: resolve_package(value,packages,p82); rejected=False
        except RuntimeError: rejected=True
        controls[name]=rejected
    return controls


def preflight(root,p82,runtime,parent,result,reconstruction,packages,result280):
    root.mkdir(parents=True,exist_ok=True); package,binding=resolve_package(parent,packages,p82); opportunities=parent["active_opportunity_projection"]["opportunities"]
    branches=[simulate_order(root/f"order-{index:02d}",parent,package,result280,p82,runtime,first) for index,first in enumerate(opportunities,1)]
    invalid=invalid_resolution_controls(parent,packages,p82); route,identity=driver.b.base272.base265.floors(parent); source=Path(__file__).read_text(); forbidden=[package["world_id"],*[row["target_path"] for row in opportunities],*[row["target_symbol"] for row in opportunities]]
    checks={"source_hashes_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256 and hashlib.sha256(DRIVER_PATH.read_bytes()).hexdigest()==DRIVER_SHA256,"exact_ot0328_parent":parent["artifact_digest"]==PARENT_DIGEST and result["receipt_digest"]==OT328_RECEIPT and reconstruction["receipt_digest"]==OT328_RECONSTRUCTION and result["checks"]["passed"] and reconstruction["checks"]["passed"],"open_identity":parent["continuation"]["status"]=="open" and runtime.identity_conforms(parent),"coherent_content_free_opening":PULSE is None and driver.derive(parent,p82)=="expanded-select" and driver.base308.coherence_state(parent,p82)["coherent"] and len(opportunities)==2,"state_resolved_binding":binding["active_epoch_id"]==parent["active_opportunity_projection"]["active_epoch_id"] and binding["resolution_authority"]=="exact-subject-state","invalid_bindings_reject":all(invalid.values()),"both_target_orders_pass":len(branches)==2 and all(all(value for key,value in row.items() if key not in {"first_target","second_target"}) for row in branches),"target_neutral_harness":all(token not in source for token in forbidden),"route_floor_16_of_16":route["pass_count"]==16,"identity_floor_18_of_18":identity["pass_count"]==18}; checks["passed"]=all(checks.values())
    report={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"package_binding":binding,"operation_budget":MAX_OPERATIONS,"actor_budget":MAX_ACTORS,"pulse":PULSE,"invalid_resolution_controls":invalid,"target_order_branches":branches,"checks":checks}; report["receipt_digest"]=p82.digest(report); write_json(root/"fixture-conformance.json",report); return report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args()
    repo,store,run,p82,runtime,parent,result,reconstruction,packages,result280,core,base130=setup(args); retained=run/"preflight/fixture-conformance.json"; fixtures=json.loads(retained.read_text()) if retained.exists() else preflight(run/"preflight",p82,runtime,parent,result,reconstruction,packages,result280)
    if args.preflight_only: print(json.dumps(fixtures,indent=2,sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run/"aggregate.json").exists(): raise SystemExit("OT-0329 unavailable")
    package,binding=resolve_package(parent,packages,p82); write_json(run/"state-resolved-package-binding.json",binding); subject=parent; overlay=protected_overlay(parent); rows=[]; actor_count=0; boundary=None
    for index in range(1,MAX_OPERATIONS+1):
        operation=driver.derive(subject,p82)
        if operation not in {"expanded-select","outward-correct","refresh-opportunity-projection",driver.base308.REPAIR_OPERATION}:
            boundary={"kind":"subject-derived-censoring-boundary","operation":operation,"after_operation_count":len(rows)}; break
        actor_needed=operation in {"expanded-select","outward-correct"}
        if actor_count+int(actor_needed)>MAX_ACTORS: boundary={"kind":"actor-budget","operation":operation,"after_operation_count":len(rows)}; break
        op_root=run/f"operation-{index:02d}"; op_root.mkdir(parents=True); row,final=driver.run_operation(index,op_root,subject,operation,repo,p82,runtime,package,result280,core,base130); row.pop("receipt_digest",None); row["state_resolved_package_receipt_digest"]=binding["receipt_digest"]; row["contextual_overlay_exact"]=protected_overlay(final)==overlay; row["checks"]["contextual_overlay_exact"]=row["contextual_overlay_exact"]; row["checks"]["passed"]=all(row["checks"].values()); row["receipt_digest"]=p82.digest(row)
        rows.append(row); actor_count+=row["fresh_actor_count"]; write_json(run/f"operation-{index:02d}-result.json",row); write_json(run/f"operation-{index:02d}-subject.json",final); subject=final
        if not row["checks"]["passed"]: boundary={"kind":"failed-operation","operation":operation,"after_operation_count":len(rows)}; break
    if boundary is None: boundary={"kind":"operation-budget","operation":driver.derive(subject,p82),"after_operation_count":len(rows)}
    operations=[row["pulse"]["derived_operation"] for row in rows]; selections=[row for row in rows if row["pulse"]["derived_operation"]=="expanded-select"]; corrections=[row for row in rows if row["pulse"]["derived_operation"]=="outward-correct"]
    selected=[row["actor"]["decision"]["next_contact"] for row in selections]; initial=parent["active_opportunity_projection"]["opportunities"]
    checks={"preflight_passed":fixtures["checks"]["passed"],"exact_state_driven_sequence":operations==["expanded-select","outward-correct","refresh-opportunity-projection",driver.base308.REPAIR_OPERATION,"expanded-select","outward-correct","refresh-opportunity-projection",driver.base308.REPAIR_OPERATION],"all_operations_pass":len(rows)==MAX_OPERATIONS and all(row["checks"]["passed"] and row["checks"]["content_free"] for row in rows),"both_targets_selected_once":sorted((x["target_path"],x["target_symbol"]) for x in selected)==sorted((x["target_path"],x["target_symbol"]) for x in initial),"two_independent_contradictions":len(selections)==2 and all(row["world"]["result"]["matches"]==2 for row in selections),"two_independent_corrections":len(corrections)==2 and all(row["world"]["result"]["matches"]==6 and row["world"]["unchanged_control"]["matches"]==2 for row in corrections),"four_fresh_actors":actor_count==MAX_ACTORS==sum(row["fresh_actor_count"] for row in rows),"derived_expand_environment_boundary":boundary=={"kind":"operation-budget","operation":"expand-environment","after_operation_count":MAX_OPERATIONS} or boundary=={"kind":"subject-derived-censoring-boundary","operation":"expand-environment","after_operation_count":MAX_OPERATIONS},"zero_remaining_opportunities":subject["active_opportunity_projection"]["opportunity_count"]==0,"contextual_overlay_exact":protected_overlay(subject)==overlay,"final_open_conformant":subject["continuation"]["status"]=="open" and runtime.identity_conforms(subject)}; checks["passed"]=all(checks.values())
    aggregate={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"source_ot0328_receipt_digest":result["receipt_digest"],"state_resolved_package_binding":binding,"pulse":PULSE,"operation_receipt_digests":[row["receipt_digest"] for row in rows],"operations":operations,"selected_targets":selected,"fresh_actor_count":actor_count,"boundary":boundary,"checks":checks,"operational_transition_passed":checks["passed"],"observer_disposition":"promoted" if checks["passed"] else "rejected","subject_disposition":subject["continuation"]["status"],"final_subject_digest":subject["artifact_digest"]}; aggregate["receipt_digest"]=p82.digest(aggregate); write_json(run/"aggregate.json",aggregate); write_json(run/"final-full-subject.json",subject); print(json.dumps(aggregate,indent=2,sort_keys=True)); return 0 if checks["passed"] else 2


if __name__=="__main__": raise SystemExit(main())
