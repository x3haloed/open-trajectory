from __future__ import annotations

import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0111_generic_interface_expansion_recurrence.py"
BASE_SHA256="5c3413f22f0cfd40a4b92693dba77bcb84da681d0dcd933d7880375d74825b67"
RUN_SHA256="199fede2ee3c8fd9f8b48f81bdf8ffd19c0a91cf2a71142c8dcfb6202e35a9d8"
AGGREGATE_SHA256="5c7e2c440bb0098a35cf4fb8f1cf06e9a5ea8955da7c4811db514f198f45afa9"
PACKAGE_DIGEST="5a4f52d7f031591874415be73ece7d3a860d5241f26b3a210b02e757e8026500"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0111 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0112_frozen_ot0111",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
prior=load_base(); base=prior.base

def extract(path,destination):
    with tarfile.open(path) as archive:
        members=archive.getmembers()
        for member in members:
            parts=PurePosixPath(member.name).parts
            if not parts or parts[0]!="OT-0111" or member.name.startswith("/") or ".." in parts or member.issym() or member.islnk(): raise RuntimeError("unsafe OT-0111 archive")
        archive.extractall(destination,members=members)
    return destination/"OT-0111"

def load_inputs(p82,repo,store,destination):
    rm,rp=p82.materialize(repo,store,"OT-0111","stopped-generic-expansion-run.json"); am,ap=p82.materialize(repo,store,"OT-0111","stopped-generic-expansion-aggregate.json")
    if rm["sha256"]!=RUN_SHA256 or am["sha256"]!=AGGREGATE_SHA256: raise RuntimeError("wrong OT-0111 inputs")
    raw=extract(rp,destination); aggregate=json.loads(ap.read_text()); package=json.loads((raw/"cycle-1-package-author/bound-package.json").read_text()); admission=json.loads((raw/"cycle-1-admission-receipt.json").read_text())
    return aggregate,package,admission

def fixtures(p82,subject,tip,aggregate,package,admission):
    world=prior.world_contact(p82,1,package,admission); synthetic={**subject,"interface_registry_extensions":[*subject.get("interface_registry_extensions",[]),{"interface_id":"synthetic-extension"}]}
    result={"base_kernel":prior.fixture_conformance(tip)["passed"],"source_rejected":not aggregate["two_cycle_target_passed"],"parent_unchanged":aggregate["final_subject_digest"]==subject["artifact_digest"],"exact_package":package["binding_digest"]==PACKAGE_DIGEST,"package_admitted":admission["admitted"] and admission["assessment"]["passed"],"world_reconstructs":world["all_cases_passed"],"registered_lookup_parent":len(prior.registered(subject))>=3,"registered_lookup_successor":"synthetic-extension" in prior.registered(synthetic)}
    result["passed"]=all(result.values()); return result,world

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args()
    repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0112").resolve(); prior92=base.mechanism.load_prior(); _,_,prior89,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store)
    subject=prior.load_parent(p82,repo,store); tip=prior.load_initial_tip(p82,repo,store); selection=prior.extract_action(p82,subject)
    with tempfile.TemporaryDirectory() as directory: aggregate,package,admission=load_inputs(p82,repo,store,Path(directory))
    checked,world=fixtures(p82,subject,tip,aggregate,package,admission)
    if args.preflight_only:
        out={"parent_digest":subject["artifact_digest"],"base_sha256":BASE_SHA256,"run_sha256":RUN_SHA256,"aggregate_sha256":AGGREGATE_SHA256,"fixtures":checked,"world_receipt_digest":world["receipt_digest"]}; print(json.dumps(out,indent=2,sort_keys=True)); return 0 if checked["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0112 evidence")
    run.mkdir(parents=True); (run/"fixture-conformance.json").write_text(json.dumps(checked,indent=2,sort_keys=True)+"\n"); (run/"retained-world-receipt.json").write_text(json.dumps(world,indent=2,sort_keys=True)+"\n")
    if not checked["passed"]: raise SystemExit("pre-actor conformance failed")
    context=prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); started=time.time(); cycles=[]
    assimilation=prior.run_assimilation(prior89,p82,context,run,1,subject,tip,package,admission,world); current=subject; promotion=None
    if assimilation["binding"]: current,promotion=prior.promote(p82,subject,selection,package,admission,world,assimilation["binding"])
    passed=bool(promotion and runtime.identity_conforms(current)); cycles.append({"cycle":1,"retained_package":package,"admission":admission,"world":world,"assimilation":p82.compact(assimilation),"promotion":promotion,"passed":passed,"successor_digest":current["artifact_digest"]})
    if passed: (run/"sealed-cycle-1-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n")
    current_tip=prior.advance_tip(tip,package); next_selection=prior.extract_action(p82,current) if passed else None
    if passed and next_selection and next_selection["continuation_action"]["action_kind"]=="registry-extension":
        authored=prior.run_author(p82,context,run,2,current,current_tip,next_selection); raw=authored["binding"]; corrected=prior.maybe_correct(p82,context,run,2,current,current_tip,raw) if raw else None; package2=corrected["binding"] if corrected else None; admission2=prior.admit(p82,run,2,current,current_tip,package2) if package2 else None; world2=prior.world_contact(p82,2,package2,admission2) if admission2 and admission2["admitted"] else None; assimilation2=prior.run_assimilation(prior89,p82,context,run,2,current,current_tip,package2,admission2,world2) if world2 and world2["all_cases_passed"] else None; promotion2=None
        if assimilation2 and assimilation2["binding"]: current,promotion2=prior.promote(p82,current,next_selection,package2,admission2,world2,assimilation2["binding"])
        passed2=bool(promotion2 and runtime.identity_conforms(current)); cycles.append({"cycle":2,"package_author":p82.compact(authored),"correction":p82.compact(corrected) if corrected else None,"admission":p82.compact(admission2) if admission2 else None,"world":world2,"assimilation":p82.compact(assimilation2) if assimilation2 else None,"promotion":promotion2,"passed":passed2,"successor_digest":current["artifact_digest"]})
        if passed2: (run/"sealed-cycle-2-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n")
    operational=len(cycles)==2 and all(row["passed"] for row in cycles); result={"authority":"ot-0112-retained-generic-expansion-recurrence-driver","source_subject_digest":subject["artifact_digest"],"cycles":cycles,"promoted_cycle_count":sum(row["passed"] for row in cycles),"two_cycle_target_passed":operational,"observer_disposition":"promoted" if operational else "rejected","subject_disposition":current["continuation"]["status"],"final_subject_digest":current["artifact_digest"],"continuation_action":current["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":current["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if operational else 2
if __name__=="__main__": raise SystemExit(main())
