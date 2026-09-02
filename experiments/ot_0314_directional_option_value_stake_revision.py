from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, secrets, sys
from pathlib import Path
sys.setrecursionlimit(max(sys.getrecursionlimit(),10000))

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0313_consequence_driven_selector_revision.py"
BASE_SHA256="100c5cfd89a491a13004923845276a6dc6a368f1cfbc305d3ac47600601ef294"
PARENT_DIGEST="9a6f94bad7216699b383c5a687e30fa25a73d4480609fb11be69bf73b7c6d0e3"
OT313_RECEIPT="6a7909ef3e002f2a4f58689b741f1a36d59fb8272f797de8997e3fdb43f20b8c"
AUTHORITY="ot-0314-directional-option-value-stake-revision"; SCHEMA=REPO/"spec/ot-0314-stake-revision.schema.json"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0313 changed")
    spec=importlib.util.spec_from_file_location("ot0314_frozen_ot0313",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
base313=load_base(); base312=base313.base312; base305=base312.base311.base305; b=base313.b; base236=base313.base236; write_json=base313.write_json

def setup(args):
    lineage=b.authority_base.guide_base.load_base(); selector,core,base130=lineage.selector_base,lineage.base,lineage.base130
    repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0314").resolve(); _,_,_,p82=core.mechanism.prior_chain(core.mechanism.load_prior()); runtime=p82.load_runtime(repo,store)
    parent=selector.load_artifact(p82,repo,store,"OT-0313","open-subject-after-rejected-selector-revision.json"); result313=selector.load_artifact(p82,repo,store,"OT-0313","consequence-driven-selector-revision-aggregate.json")
    return repo,run,p82,runtime,parent,result313,core,base130

def token(seed,label): return hashlib.sha256(bytes.fromhex(seed)+label.encode()).hexdigest()
def descriptor(seed,label,high,index,p82):
    source=("def route(case):\n    return \"harbor\"\n" if not high else "def route(case):\n    if case[\"signal\"] == 0:\n        return \"harbor\"\n    if case[\"signal\"] == 1:\n        return \"shelter\"\n    if case[\"signal\"] == 2:\n        return \"clinic\"\n    return \"relay\"\n")
    return {"world_id":"w-"+token(seed,label)[:16],"public_package_digest":hashlib.sha256(source.encode()+bytes.fromhex(token(seed,label))).hexdigest(),"features":base305.source_features(source)},source
def executable_option_value(source,contexts):
    namespace={}; exec(compile(source,"<sealed-option-world>","exec"),{"__builtins__":{}},namespace); route=namespace["route"]; outputs=[route(copy.deepcopy(case)) for case in contexts]; allowed={"harbor","shelter","clinic","relay"}; return len(set(outputs)) if all(value in allowed for value in outputs) else 0
def episodes(seed,p82):
    rows=[]
    for index in range(8):
        low,low_source=descriptor(seed,f"{index}-low",False,index,p82); high,high_source=descriptor(seed,f"{index}-high",True,index,p82); catalog=sorted([low,high],key=lambda r:r["world_id"]); contexts=[{"signal":value} for value in (0,1,2,3)]
        option={low["world_id"]:executable_option_value(low_source,contexts),high["world_id"]:executable_option_value(high_source,contexts)}
        rows.append({"episode_id":"e-"+token(seed,str(index))[:16],"catalog":catalog,"sealed_contexts_digest":p82.digest(contexts),"option_value":option,"best_world_id":max(option,key=option.get)})
    return rows[:3],rows[3:]

def stake_of(parent): return parent["active_world_seeking_stake"]["stake"]
def valid_candidate(parent,candidate):
    incumbent=stake_of(parent)
    if not base305.valid_stake(candidate) or set(candidate)!=set(incumbent): return False
    mutable={"weights","minimum_score_gap","rationale"}
    if any(candidate[k]!=incumbent[k] for k in incumbent if k not in mutable): return False
    return all(isinstance(v,int) and -20<=v<=20 for v in candidate["weights"].values()) and isinstance(candidate["minimum_score_gap"],int) and 0<=candidate["minimum_score_gap"]<=100 and isinstance(candidate["rationale"],str) and 1<=len(candidate["rationale"])<=2000

def select(stake,episode): return base305.choose(stake,episode["catalog"])
def training_receipts(stake,training,p82,erased=False):
    rows=[]
    for episode in training:
        choice=select(stake,episode); selection_body={"authority":AUTHORITY+"-bound-selection","episode_id":episode["episode_id"],"catalog_digest":p82.digest(episode["catalog"]),"selected_world_id":choice["selected_world_id"],"supported":choice["supported"],"selection_precedes_outcome":True}; selection={**selection_body,"receipt_digest":p82.digest(selection_body)}
        outcome_body={"authority":AUTHORITY+("-outcome-erased" if erased else "-option-value-world"),"selection_receipt_digest":selection["receipt_digest"],"episode_id":episode["episode_id"],"catalog_digest":selection["catalog_digest"],"outcome_authority":not erased,"option_value":None if erased else episode["option_value"],"best_world_id":None if erased else episode["best_world_id"],"selected_option_value":None if erased else episode["option_value"].get(choice["selected_world_id"]),"directional_error":None if erased else choice["selected_world_id"]!=episode["best_world_id"]}; outcome={**outcome_body,"receipt_digest":p82.digest(outcome_body)}
        rows.append({"catalog":episode["catalog"],"selection":selection,"outcome":outcome})
    return rows

def score(stake,heldout):
    rows=[]
    for episode in heldout:
        choice=select(stake,episode); passed=choice["supported"] and choice["selected_world_id"]==episode["best_world_id"]; rows.append({"episode_id":episode["episode_id"],"selected_world_id":choice["selected_world_id"],"best_world_id":episode["best_world_id"],"supported":choice["supported"],"passed":passed})
    return {"pass_count":sum(r["passed"] for r in rows),"case_count":len(rows),"rows":rows}

CHECKER='''import json\nfrom pathlib import Path\nr=json.loads(Path("stake-revision.json").read_text()); c=json.loads(Path("stake-revision-contract.json").read_text()); ok=set(r)==set(c["required_keys"]) and set(r.get("weights",{{}}))==set(c["weight_keys"]) and all(isinstance(v,int) and -20<=v<=20 for v in r["weights"].values()) and isinstance(r.get("minimum_score_gap"),int) and 0<=r["minimum_score_gap"]<=100 and isinstance(r.get("rationale"),str) and 1<=len(r["rationale"])<=2000 and all(r.get(k)==c["immutable_values"][k] for k in c["immutable_values"]); print(json.dumps({{"valid":ok}})); raise SystemExit(0 if ok else 2)\n'''

def seed_actor(root,parent,contacts,p82):
    seed=root/"seed"; seed.mkdir(parents=True); incumbent=stake_of(parent); write_json(seed/"stake-revision.json",incumbent); write_json(seed/"completed-selection-contacts.json",contacts)
    mutable={"weights","minimum_score_gap","rationale"}; contract={"required_keys":sorted(incumbent),"weight_keys":sorted(incumbent["weights"]),"mutable":sorted(mutable),"immutable_values":{k:v for k,v in incumbent.items() if k not in mutable},"weight_integer_range":[-20,20],"minimum_score_gap_range":[0,100]}; write_json(seed/"stake-revision-contract.json",contract); write_json(seed/"subject-position.json",{"source_subject_digest":parent["artifact_digest"],"active_stake_binding_digest":parent["active_world_seeking_stake"]["binding_digest"]}); (seed/"check_revision.py").write_text(CHECKER)
    immutable=["completed-selection-contacts.json","stake-revision-contract.json","subject-position.json","check_revision.py","mutation-envelope.json","README.md"]; write_json(seed/"mutation-envelope.json",{"editable":["stake-revision.json"],"immutable":immutable}); (seed/"README.md").write_text("Continue from the exact active world-seeking stake after completed selection contacts. Decide whether their independently owned outcomes warrant revising the bounded stake machinery or retaining it. Future catalogs, identities, outcomes, evaluator, and sibling are unavailable. Edit only stake-revision.json if revising, run python3 check_revision.py, and inspect the exact diff.\n"); return seed

def output_valid(output,changed): return bool(isinstance(output,dict) and set(output)=={"action","files_changed","note"} and isinstance(output.get("note"),str) and ((output["action"]=="revise-world-seeking-stake" and output["files_changed"]==["stake-revision.json"] and changed) or (output["action"]=="retain-world-seeking-stake" and output["files_changed"]==[] and not changed)))
def run_actor(context,p82,root,parent,contacts,label):
    seed=seed_actor(root,parent,contacts,p82); output,audit0,workspace,_=context.run_actor(label,seed,SCHEMA,(seed/"README.md").read_text().strip())
    try: candidate=json.loads((workspace/"stake-revision.json").read_text()); immutable=json.loads((seed/"mutation-envelope.json").read_text())["immutable"]; immutable_ok=all((workspace/n).read_bytes()==(seed/n).read_bytes() for n in immutable); changed=candidate!=stake_of(parent)
    except (OSError,ValueError,KeyError,TypeError): candidate=None; immutable_ok=False; changed=False
    semantic=immutable_ok and valid_candidate(parent,candidate) and output_valid(output,changed); expected=["stake-revision.json"] if changed else []; audit=context.audit_actor(label,output,audit0,semantic,expected); normalized=base236.classify_retained(audit,(context.evidence(label)/"events.jsonl").read_text()); accepted=bool(semantic and base236.g10(normalized)); return {"accepted":accepted,"candidate_stake":candidate,"changed":changed,"output":output,"audit":audit,"g10_disposition":accepted,"workspace_evaluation":{"immutable_ok":immutable_ok,"semantic":semantic}}

def compile_child(parent,actor,contacts,evaluation,p82):
    old=parent["active_world_seeking_stake"]; body={"authority":AUTHORITY+"-stake-revision-binding","source_subject_digest":parent["artifact_digest"],"prior_binding_digest":old["binding_digest"],"actor_patch_digest":actor["audit"]["patch_digest"],"stake":actor["candidate_stake"],"training_outcome_receipt_digests":[r["outcome"]["receipt_digest"] for r in contacts],"heldout_score":evaluation,"selection_authority":True,"world_authority":False,"scoring_authority":False,"admission_authority":False,"outcome_authority":False}; binding={**body,"binding_digest":p82.digest(body)}; child=copy.deepcopy(parent); child.pop("artifact_digest",None); child["world_seeking_stake_revisions"]=[*child.get("world_seeking_stake_revisions",[]),binding]; child["active_world_seeking_stake"]=binding; return p82.seal(child),binding

def preflight(root,p82,runtime,parent,result313):
    root.mkdir(parents=True,exist_ok=True); training,heldout=episodes("00"*32,p82); incumbent=stake_of(parent); good=copy.deepcopy(incumbent); good["weights"]["source_bytes"]=0; contacts=training_receipts(incumbent,training,p82); erased=training_receipts(incumbent,training,p82,True); bad=copy.deepcopy(good); bad["question"]="changed"
    checks={"base_hash_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256,"exact_parent":parent["artifact_digest"]==PARENT_DIGEST and result313["receipt_digest"]==OT313_RECEIPT and result313["observer_disposition"]=="rejected","three_directional_errors":len(contacts)==3 and all(r["selection"]["selection_precedes_outcome"] and r["outcome"]["directional_error"] for r in contacts),"erasure_removes_outcomes":all(not r["outcome"]["outcome_authority"] and r["outcome"]["option_value"] is None for r in erased),"representative_5_of_5":score(good,heldout)["pass_count"]==5,"incumbent_at_most_1_of_5":score(incumbent,heldout)["pass_count"]<=1,"immutable_change_rejected":not valid_candidate(parent,bad),"exact_open_conformant":parent["continuation"]["status"]=="open" and runtime.identity_conforms(parent)}; checks["passed"]=all(checks.values()); result={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"fixture_seed_digest":p82.digest("00"*32),"representative_score":score(good,heldout),"incumbent_score":score(incumbent,heldout),"checks":checks}; result["receipt_digest"]=p82.digest(result); write_json(root/"fixture-conformance.json",result); return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo,run,p82,runtime,parent,result313,core,base130=setup(args); retained=run/"preflight/fixture-conformance.json"; fixtures=json.loads(retained.read_text()) if retained.exists() else preflight(run/"preflight",p82,runtime,parent,result313)
    if args.preflight_only: print(json.dumps(fixtures,indent=2,sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run/"aggregate.json").exists(): raise SystemExit("OT-0314 unavailable")
    seed=secrets.token_hex(32); write_json(run/"private-world-seed.json",{"seed":seed,"seed_digest":p82.digest(seed)}); training,heldout=episodes(seed,p82); incumbent=stake_of(parent); contacts=training_receipts(incumbent,training,p82); erased_contacts=training_receipts(incumbent,training,p82,True)
    if not all(r["outcome"]["directional_error"] for r in contacts): raise RuntimeError("private training lacks directional error")
    context=b.base274.context_for(core,base130,runtime,run/"actors",repo); actor=run_actor(context,p82,run/"candidate",parent,contacts,"option-value-stake-reviser"); candidate_score=score(actor["candidate_stake"],heldout) if actor["accepted"] else None; incumbent_score=score(incumbent,heldout); operational=bool(actor["accepted"] and actor["changed"] and candidate_score["pass_count"]==5 and incumbent_score["pass_count"]<=1)
    child,binding=compile_child(parent,actor,contacts,candidate_score,p82) if operational else (parent,None); write_json(run/"candidate-operational-subject.json",child)
    erased_actor=run_actor(context,p82,run/"erased",parent,erased_contacts,"option-value-stake-reviser-erased"); erased_score=score(erased_actor["candidate_stake"],heldout) if erased_actor["accepted"] else None; causal=bool(operational and not (erased_actor["accepted"] and erased_actor["changed"] and erased_score["pass_count"]==5))
    checks={"preflight_passed":fixtures["checks"]["passed"],"private_seed_postfreeze":True,"three_directional_training_errors":all(r["outcome"]["directional_error"] for r in contacts),"candidate_actor_clean":actor["accepted"],"candidate_beats_incumbent":operational,"operational_child_sealed_before_control":(run/"candidate-operational-subject.json").exists(),"erased_actor_clean":erased_actor["accepted"],"outcome_erasure_removes_advantage":causal,"child_open_conformant":child["continuation"]["status"]=="open" and runtime.identity_conforms(child)}; checks["passed"]=all(checks.values()); aggregate={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"private_world_seed_digest":p82.digest(seed),"training_contacts":contacts,"candidate_actor":actor,"candidate_score":candidate_score,"incumbent_score":incumbent_score,"stake_revision_binding":binding,"erased_actor":erased_actor,"erased_score":erased_score,"checks":checks,"operational_transition_passed":operational,"causal_machinery_refinement_supported":causal,"observer_disposition":"promoted" if checks["passed"] else "rejected","subject_disposition":child["continuation"]["status"],"final_subject_digest":child["artifact_digest"],"fresh_actor_count":2}; aggregate["receipt_digest"]=p82.digest(aggregate); write_json(run/"aggregate.json",aggregate); write_json(run/"final-full-subject.json",child); print(json.dumps(aggregate,indent=2,sort_keys=True)); return 0 if checks["passed"] else 2
if __name__=="__main__": raise SystemExit(main())
