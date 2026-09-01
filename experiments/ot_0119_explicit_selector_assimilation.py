from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0118_retained_selector_assimilation_audit.py"; BASE_SHA256="20f341716860323b0502915a93580e189d9815f6e794bdcd117f6075f118b112"
PARENT_OBJECT_SHA256="3ad82e07c8bc455d2cb84b9818a614e326432c5d12f4e2981d1033843fbda4a9"; PARENT_DIGEST="597fd631b365952423cb1908a7bb201af0116b4a2e707bd1a07514cf93205786"
SELECTOR_BINDING="b03f52963b7ed38bd4274fcf68e2f180cb6fd6dda274fc2d9491c622cbe024f6"; WORLD_RECEIPT="9f14488008551dfb113bffd0e65846d3508317b1ac7855465ca3ca55ddac2667"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0118 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0119_frozen_ot0118",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
prior18=load_base(); prior17=prior18.previous; base=prior17.base; kernel=prior17.kernel

def load_inputs(p82,repo,store,destination):
    raw,aggregate,parent=prior18.load_inputs(p82,repo,store,destination); pm,pp=p82.materialize(repo,store,"OT-0118","unchanged-open-subject-after-retained-audit-rejection.json")
    exact_parent=json.loads(pp.read_text())
    if pm["sha256"]!=PARENT_OBJECT_SHA256 or exact_parent!=parent or parent["artifact_digest"]!=PARENT_DIGEST: raise RuntimeError("wrong OT-0118 parent")
    binding=aggregate["selector_revision"]["binding"]; world=aggregate["world"]
    if binding["binding_digest"]!=SELECTOR_BINDING or world["receipt_digest"]!=WORLD_RECEIPT or not world["passed"]: raise RuntimeError("wrong retained selector world")
    return parent,binding,world

def seed(prior89,run,parent,binding,world):
    path=run/"explicit-selector-assimilation-seed"; path.mkdir(); passed=[row for row in world["revised"]["rows"] if row["passed"]]; portfolio_ids=[row["portfolio_id"] for row in passed]; selected_ids=[row["selected_id"] for row in passed]
    consequence={"subject_position":base.active_position(parent),"selector_binding":binding,"world_receipt":world}; (path/"subject-contact-consequence.json").write_text(json.dumps(consequence,indent=2,sort_keys=True)+"\n"); (path/"grounding-contract.json").write_text(json.dumps({"settled_case_ids_namespace":"portfolio_id","accepted_passed_portfolio_ids":portfolio_ids,"selected_contact_ids_not_valid_as_settled_case_ids":selected_ids},indent=2,sort_keys=True)+"\n")
    (path/"assimilation.json").write_text(json.dumps(base.assimilation_template(),indent=2,sort_keys=True)+"\n"); (path/"successor-opening.json").write_text(json.dumps(prior89.successor_template(),indent=2,sort_keys=True)+"\n"); (path/"successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(),indent=2,sort_keys=True)+"\n"); (path/"continuation-action.json").write_text(json.dumps(kernel.foundation.prior.prior.action_template(),indent=2,sort_keys=True)+"\n"); (path/"continuation-action-contract.json").write_text(json.dumps({"exact_keys":sorted(kernel.ACTION_KEYS),"action_kinds":["registered-contact","registry-extension","surrender"],"registry-extension":"new lowercase hyphenated target, 3 to 128 characters","surrender":"target exactly none"},indent=2,sort_keys=True)+"\n"); (path/"revised-selector.py").write_text(binding["selector_source"]); editable=["assimilation.json","successor-opening.json","continuation-action.json"]; (path/"mutation-envelope.json").write_text(json.dumps({"editable":editable,"immutable":["revised-selector.py","subject-contact-consequence.json","grounding-contract.json"]},indent=2,sort_keys=True)+"\n"); (path/"README.md").write_text("Assimilate the exact retained selector comparison. Use portfolio ids from grounding-contract.json in settled_case_ids. Preserve selector bytes, edit exactly the three JSON files, inspect the diff, and report truthfully.\n"); return path,portfolio_ids

def run_actor(prior89,p82,context,run,parent,binding,world):
    path,accepted=seed(prior89,run,parent,binding,world); label="explicit-selector-assimilation"; output,base_audit,workspace,_=context.run_actor(label,path,kernel.ASSIMILATOR_SCHEMA,"Assimilate the exact selector comparison using the explicit grounding contract. Preserve selector bytes, edit exactly the three JSON files, inspect the diff, and report truthfully.")
    try: assimilation=json.loads((workspace/"assimilation.json").read_text()); opening=json.loads((workspace/"successor-opening.json").read_text()); action=json.loads((workspace/"continuation-action.json").read_text()); retained=(workspace/"revised-selector.py").read_text()==binding["selector_source"] and json.loads((workspace/"grounding-contract.json").read_text())["accepted_passed_portfolio_ids"]==accepted
    except (OSError,json.JSONDecodeError): assimilation=opening=action=None; retained=False
    cited=set(assimilation.get("settled_case_ids",[])) if isinstance(assimilation,dict) else set(); valid=bool(base.valid_assimilation(assimilation) and prior89.valid_successor(opening) and prior18.previous.previous.repaired_action_valid(action,parent) and retained and cited and cited.issubset(set(accepted)) and (action["action_kind"]=="surrender" or opening["next_opening"]!=base.active_position(parent)["continuation"]["next_opening"]))
    audit=context.audit_actor(label,output,base_audit,valid,["assimilation.json","successor-opening.json","continuation-action.json"]); clean=bool(audit["conformant"] and not audit["denial_classification_v2"]["sandbox_violation_retained"]); binding_out=None
    if clean:
        body={"authority":"ot-0119-explicit-selector-assimilation","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":binding["binding_digest"],"world_receipt_digest":world["receipt_digest"],"actor_patch_digest":audit["patch_digest"],"selector_retention_derived":retained,"grounding_contract_digest":p82.digest(accepted),"assimilation":assimilation,"successor_opening":opening,"continuation_action":action}; binding_out={**body,"binding_digest":p82.digest(body)}; (context.evidence(label)/"bound-assimilation.json").write_text(json.dumps(binding_out,indent=2,sort_keys=True)+"\n")
    return {"output":output,"audit":audit,"grounded":bool(cited and cited.issubset(set(accepted))),"selector_retention_derived":retained,"binding":binding_out}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0119").resolve(); prior92=base.mechanism.load_prior(); _,_,prior89,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store)
    with tempfile.TemporaryDirectory() as directory: parent,binding,world=load_inputs(p82,repo,store,Path(directory))
    checks={"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"parent_sounding":runtime.identity_conforms(parent),"selector_exact":binding["binding_digest"]==SELECTOR_BINDING,"world_exact":world["receipt_digest"]==WORLD_RECEIPT,"comparison_exact":world["revised"]["correct_count"]==12 and world["revised"]["total_regret"]==0 and world["inherited"]["correct_count"]==4 and world["inherited"]["total_regret"]==548}; checks["passed"]=all(checks.values())
    if args.preflight_only: print(json.dumps({"base_sha256":BASE_SHA256,"checks":checks},indent=2,sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0119 evidence")
    run.mkdir(parents=True); (run/"fixture-conformance.json").write_text(json.dumps(checks,indent=2,sort_keys=True)+"\n"); context=prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); started=time.time(); assimilation=run_actor(prior89,p82,context,run,parent,binding,world); current=parent; promotion=None
    if assimilation["binding"]: current,promotion=prior17.promote(p82,parent,binding,world,assimilation["binding"])
    operational=bool(promotion and runtime.identity_conforms(current)); result={"authority":"ot-0119-explicit-selector-assimilation-driver","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":binding["binding_digest"],"world_receipt_digest":world["receipt_digest"],"assimilation":p82.compact(assimilation),"promotion":promotion,"operational_transition_passed":operational,"observer_disposition":"promoted" if operational else "rejected","subject_disposition":current["continuation"]["status"],"final_subject_digest":current["artifact_digest"],"continuation_action":current["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":current["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if operational else 2
if __name__=="__main__": raise SystemExit(main())
