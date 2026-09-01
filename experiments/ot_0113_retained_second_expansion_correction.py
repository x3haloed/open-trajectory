from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, secrets, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath
from typing import Any

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0112_retained_generic_expansion_recurrence.py"; BASE_SHA256="1c320d225d69a280a2fcdf212704a7916ce601e17ee947f71044173f8687ab64"
RUN_SHA256="0b2366d45d5ef2eb395c9bbe65ff6ea6150616a65e14ab76ed98d6d54a228340"; AGGREGATE_SHA256="98ef56895b7c00360da040de0fc25b8246927877e1d787a98f8893995bf9fd24"
PARENT_OBJECT_SHA256="cb1dd1523b992b6b8f1ecdf72b746f3412843b633d57f6cc06e563ca67263fcb"; PARENT_DIGEST="a17ee73828db76ca2f384bb2a1dced9fd12cb22590fbfac028e2106ba635e67b"
PATCH_DIGEST="00e20a61ecb479182a7d0c2b5696cab89faa2b6e9a04615dde615bc2401c682a"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0112 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0113_frozen_ot0112",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
prior=load_base(); kernel=prior.prior; base=prior.base

def load_parent(p82,repo,store):
    manifest,path=p82.materialize(repo,store,"OT-0112","open-subject-after-first-generic-expansion.json")
    if manifest["sha256"]!=PARENT_OBJECT_SHA256: raise RuntimeError("wrong OT-0112 parent")
    return json.loads(path.read_text())

def extract(path,destination):
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        for member in members:
            parts=PurePosixPath(member.name).parts
            if not parts or parts[0]!="OT-0112" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk(): raise RuntimeError("unsafe OT-0112 archive")
        archive.extractall(destination,members=members)
    return destination/"OT-0112"

def load_inputs(p82,repo,store,destination):
    rm,rp=p82.materialize(repo,store,"OT-0112","retained-generic-recurrence-run.json"); am,ap=p82.materialize(repo,store,"OT-0112","retained-generic-recurrence-aggregate.json")
    if rm["sha256"]!=RUN_SHA256 or am["sha256"]!=AGGREGATE_SHA256: raise RuntimeError("wrong OT-0112 inputs")
    aggregate=json.loads(ap.read_text()); raw=extract(rp,destination); workspace=raw/"cycle-2-package-author/actor-workspace"
    package={"interface":json.loads((workspace/"interface.json").read_text()),"contact":json.loads((workspace/"contact.json").read_text()),"operation_source":(workspace/"operation.py").read_text(),"conformance_source":(workspace/"conformance.py").read_text()}
    return aggregate,package

def normalize_spec(spec:Any):
    if not isinstance(spec,dict): return None
    value=copy.deepcopy(spec); declaration=value.get("reversible_projection")
    if isinstance(declaration,dict) and 1<=len(declaration)<=8 and all(isinstance(k,str) and kernel.FIELD_RE.fullmatch(k) and isinstance(v,str) and v.strip() for k,v in declaration.items()): value["reversible_projection"]=True
    elif not kernel.declaration_valid(declaration): return None
    instantiated=f"parent_score - {value.get('new_context_field')} * {value.get('new_option_field')}"
    if value.get("score_composition")==instantiated: value["score_composition"]=kernel.COMPOSITION
    return value

def current_tip(p82,parent,repo,store):
    tip=kernel.load_initial_tip(p82,repo,store); package=parent["interface_package_chain"][-1]
    if package["binding_digest"]!="5a4f52d7f031591874415be73ece7d3a860d5241f26b3a210b02e757e8026500": raise RuntimeError("wrong parent package chain")
    return kernel.advance_tip(tip,package)

def bind_package(p82,parent,tip,selection,aggregate,raw):
    spec=normalize_spec(raw["interface"]); audit=aggregate["cycles"][1]["package_author"]["audit"]
    valid=bool(spec and kernel.valid_spec(spec,tip,selection["continuation_action"]["action_target"]) and kernel.validate_contact(spec,tip,raw["contact"])[0] and kernel.load_named(raw["operation_source"],"choose_extension") and kernel.load_named(raw["conformance_source"],"validate_contact") and audit["patch_digest"]==PATCH_DIGEST and audit["exact_changes"] and audit["truthful"] and audit["trace_regime"]["accepted"] and audit["denial_classification_v2"]["accepted"])
    if not valid:return None
    body={"authority":"ot-0113-retained-second-extension-package","source_subject_digest":parent["artifact_digest"],"continuation_binding_digest":selection["binding_digest"],"parent_package_binding_digest":tip["binding_digest"],"source_actor_patch_digest":PATCH_DIGEST,**raw}
    return {**body,"binding_digest":p82.digest(body)}

def disagreement(tip,package):
    return kernel.public_agreement(normalize_spec(package["interface"]),tip,package["contact"],kernel.load_named(package["conformance_source"],"validate_contact"))

def admit(p82,run,parent,tip,package):
    seed=secrets.token_bytes(32); (run/"hidden-seed.bin").write_bytes(seed); spec=normalize_spec(package["interface"]); hidden=kernel.derive_hidden(spec,tip,seed); (run/"hidden-cases.json").write_text(json.dumps(hidden,indent=2,sort_keys=True)+"\n")
    assessment=kernel.assess(spec,tip,package["contact"],package["operation_source"],package["conformance_source"],hidden); body={"authority":"ot-0113-independent-retained-extension-admission","source_subject_digest":parent["artifact_digest"],"package_binding_digest":package["binding_digest"],"private_seed_digest":hashlib.sha256(seed).hexdigest(),"derivation_attempt":1,"hidden_cases_digest":p82.digest(hidden),"assessment":assessment,"admitted":assessment["passed"]}; receipt={**body,"receipt_digest":p82.digest(body)}; (run/"admission-receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n"); return receipt

def fixtures(p82,parent,tip,selection,aggregate,raw):
    spec=normalize_spec(raw["interface"]); package=bind_package(p82,parent,tip,selection,aggregate,raw); failed=[r["fixture"] for r in disagreement(tip,package)["rows"] if not r["passed"]] if package else []
    boolean={**raw["interface"],"reversible_projection":True,"score_composition":kernel.COMPOSITION}; string={**boolean,"reversible_projection":"zero recovers parent"}; empty={**boolean,"reversible_projection":{}}
    result={"base_kernel":kernel.fixture_conformance(kernel.load_initial_tip(p82,REPO,REPO/".evidence"))["passed"],"source_target_rejected":not aggregate["two_cycle_target_passed"],"source_cycle_one_promoted":aggregate["promoted_cycle_count"]==1,"parent_exact":aggregate["final_subject_digest"]==parent["artifact_digest"],"structured_declaration_admitted":bool(spec and kernel.valid_spec(spec,tip,selection["continuation_action"]["action_target"])),"boolean_admitted":bool(normalize_spec(boolean)),"string_admitted":bool(normalize_spec(string)),"empty_object_rejected":normalize_spec(empty) is None,"exact_contact_valid":bool(spec and kernel.validate_contact(spec,tip,raw["contact"])[0]),"exact_disagreement_inherited_bound":failed==["inherited-field-out-of-bounds"],"package_bound":bool(package)}; result["passed"]=all(result.values()); return result,package

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0113").resolve(); prior92=base.mechanism.load_prior(); _,_,prior89,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store); parent=load_parent(p82,repo,store); tip=current_tip(p82,parent,repo,store); selection=kernel.extract_action(p82,parent)
    with tempfile.TemporaryDirectory() as directory: aggregate,raw=load_inputs(p82,repo,store,Path(directory))
    checked,package=fixtures(p82,parent,tip,selection,aggregate,raw); public=disagreement(tip,package) if package else None
    if args.preflight_only:
        out={"parent_digest":parent["artifact_digest"],"base_sha256":BASE_SHA256,"run_sha256":RUN_SHA256,"aggregate_sha256":AGGREGATE_SHA256,"fixtures":checked,"retained_package_binding":package["binding_digest"] if package else None}; print(json.dumps(out,indent=2,sort_keys=True)); return 0 if checked["passed"] and runtime.identity_conforms(parent) else 2
    if run.exists(): raise SystemExit("preserve existing OT-0113 evidence")
    run.mkdir(parents=True); (run/"fixture-conformance.json").write_text(json.dumps(checked,indent=2,sort_keys=True)+"\n"); (run/"bound-retained-package.json").write_text(json.dumps(package,indent=2,sort_keys=True)+"\n"); (run/"public-disagreement.json").write_text(json.dumps(public,indent=2,sort_keys=True)+"\n")
    if not checked["passed"]: raise SystemExit("pre-actor conformance failed")
    context=prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); started=time.time(); correction=kernel.maybe_correct(p82,context,run,2,parent,tip,package); corrected=correction["binding"]; admission=admit(p82,run,parent,tip,corrected) if corrected else None; world=kernel.world_contact(p82,2,corrected,admission) if admission and admission["admitted"] else None; assimilation=kernel.run_assimilation(prior89,p82,context,run,2,parent,tip,corrected,admission,world) if world and world["all_cases_passed"] else None; current=parent; promotion=None
    if assimilation and assimilation["binding"]: current,promotion=kernel.promote(p82,parent,selection,corrected,admission,world,assimilation["binding"])
    operational=bool(promotion and runtime.identity_conforms(current)); result={"authority":"ot-0113-retained-second-expansion-correction-driver","source_subject_digest":parent["artifact_digest"],"retained_package_binding":package,"public_disagreement":public,"correction":p82.compact(correction),"admission":p82.compact(admission) if admission else None,"world":world,"assimilation":p82.compact(assimilation) if assimilation else None,"promotion":promotion,"operational_transition_passed":operational,"observer_disposition":"promoted" if operational else "rejected","subject_disposition":current["continuation"]["status"],"final_subject_digest":current["artifact_digest"],"continuation_action":current["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":current["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if operational else 2
if __name__=="__main__": raise SystemExit(main())
