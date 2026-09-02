from __future__ import annotations
import argparse, copy, hashlib, importlib.util, json, secrets, sys
from pathlib import Path

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0312_priority_selected_vs_blind_downstream.py"
BASE_SHA256="d7248ce79812aee7832a6ce18fd586a83be169672bf481a5e0c12a92d1a407eb"
PARENT_DIGEST="9a6f94bad7216699b383c5a687e30fa25a73d4480609fb11be69bf73b7c6d0e3"
OT312_RECEIPT="8299accefc8cf29ee1f86faac53feb59b3569eb9d75c9db1bb1e56795864b77b"
AUTHORITY="ot-0313-consequence-driven-selector-revision"
SCHEMA=REPO/"spec/ot-0313-selector-revision.schema.json"
RULE_KEYS={"version","ranking_signal","minimum_observations","minimum_rate_gap","on_insufficient_evidence","accepted_outcome","rationale"}
INCUMBENT={"version":1,"ranking_signal":"structural-score","minimum_observations":0,"minimum_rate_gap":3,"on_insufficient_evidence":"structural-fallback","accepted_outcome":"hard-endpoint","rationale":"Rank unseen worlds by the active stake's fixed public structural score."}

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0312 changed")
    spec=importlib.util.spec_from_file_location("ot0313_frozen_ot0312",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
base312=load_base(); b=base312.b; base236=base312.base270.base236
write_json=base312.write_json

def setup(args):
    lineage=b.authority_base.guide_base.load_base(); selector,core,base130=lineage.selector_base,lineage.base,lineage.base130
    repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0313").resolve(); _,_,_,p82=core.mechanism.prior_chain(core.mechanism.load_prior()); runtime=p82.load_runtime(repo,store)
    parent=selector.load_artifact(p82,repo,store,"OT-0312","open-stake-subject-after-downstream-comparison.json"); result312=selector.load_artifact(p82,repo,store,"OT-0312","priority-selected-vs-blind-downstream-aggregate.json")
    return repo,run,p82,runtime,parent,result312,core,base130

def valid_rule(rule):
    return bool(isinstance(rule,dict) and set(rule)==RULE_KEYS and isinstance(rule["version"],int) and rule["version"] in {1,2} and rule["ranking_signal"] in {"structural-score","consequence-success-rate"} and isinstance(rule["minimum_observations"],int) and 0<=rule["minimum_observations"]<=4 and isinstance(rule["minimum_rate_gap"],int) and 0<=rule["minimum_rate_gap"]<=100 and rule["on_insufficient_evidence"] in {"wait","structural-fallback"} and rule["accepted_outcome"]=="hard-endpoint" and isinstance(rule["rationale"],str) and 1<=len(rule["rationale"])<=1000)

def structural(catalog):
    rows=sorted(catalog,key=lambda r:(-r["structural_score"],r["world_id"])); return rows[0]["world_id"] if len(rows)==1 or rows[0]["structural_score"]-rows[1]["structural_score"]>=3 else None

def select(rule,catalog,receipts,context_id):
    if not valid_rule(rule): return None
    if rule["ranking_signal"]=="structural-score": return structural(catalog)
    ids={r["world_id"] for r in catalog}; counts={i:[0,0] for i in ids}
    for receipt in receipts:
        if not (isinstance(receipt,dict) and receipt.get("outcome_authority") is True and receipt.get("context_id")==context_id and receipt.get("world_id") in ids and receipt.get("outcome") in {"hard-endpoint","failed-endpoint"}): continue
        counts[receipt["world_id"]][1]+=1; counts[receipt["world_id"]][0]+=receipt["outcome"]==rule["accepted_outcome"]
    if any(total<rule["minimum_observations"] for _,total in counts.values()): return structural(catalog) if rule["on_insufficient_evidence"]=="structural-fallback" else None
    rates=sorted(((100*success/total if total else 0,world) for world,(success,total) in counts.items()),reverse=True)
    if len(rates)>1 and rates[0][0]-rates[1][0]<rule["minimum_rate_gap"]: return None
    if len(rates)>1 and rates[0][0]==rates[1][0]: return None
    return rates[0][1]

def token(seed,label): return hashlib.sha256(bytes.fromhex(seed)+label.encode()).hexdigest()[:16]
def anchors(seed):
    left="w-"+token(seed,"left"); right="w-"+token(seed,"right"); context="c-"+token(seed,"context"); stale="c-"+token(seed,"stale")
    def cat(high): return [{"world_id":left,"structural_score":90 if high==left else 10},{"world_id":right,"structural_score":90 if high==right else 10}]
    def receipt(world,outcome,ctx=context,authority=True): return {"world_id":world,"context_id":ctx,"outcome":outcome,"outcome_authority":authority}
    return [
      {"id":"no-evidence","catalog":cat(left),"receipts":[],"context_id":context,"expected":None},
      {"id":"left-supported-structural-decoy","catalog":cat(right),"receipts":[receipt(left,"hard-endpoint"),receipt(left,"hard-endpoint"),receipt(right,"failed-endpoint"),receipt(right,"failed-endpoint")],"context_id":context,"expected":left},
      {"id":"right-supported-structural-decoy","catalog":cat(left),"receipts":[receipt(right,"hard-endpoint"),receipt(right,"hard-endpoint"),receipt(left,"failed-endpoint"),receipt(left,"failed-endpoint")],"context_id":context,"expected":right},
      {"id":"equal-evidence","catalog":cat(left),"receipts":[receipt(left,"hard-endpoint"),receipt(left,"failed-endpoint"),receipt(right,"hard-endpoint"),receipt(right,"failed-endpoint")],"context_id":context,"expected":None},
      {"id":"stale-misbound","catalog":cat(right),"receipts":[receipt(left,"hard-endpoint",stale),receipt(right,"failed-endpoint",stale),receipt("w-"+token(seed,"other"),"hard-endpoint"),receipt(left,"hard-endpoint",context,False)],"context_id":context,"expected":None}]

def score(rule,cases):
    rows=[{"case_id":case["id"],"selected":select(rule,case["catalog"],case["receipts"],case["context_id"]),"expected":case["expected"]} for case in cases]
    for row in rows: row["passed"]=row["selected"]==row["expected"]
    return {"pass_count":sum(r["passed"] for r in rows),"case_count":len(rows),"rows":rows}

def consequence(parent,result312,p82,withheld):
    if withheld: return {"authority":AUTHORITY+"-withheld-control","source_subject_digest":parent["artifact_digest"],"outcome_withheld":True}
    body={"authority":AUTHORITY+"-selection-fitness-contact","source_subject_digest":parent["artifact_digest"],"source_ot0312_receipt_digest":result312["receipt_digest"],"stake_world_id":result312["stake_branch"]["world_id"],"blind_world_id":result312["blind_branch"]["world_id"],"stake_hard_endpoint":result312["stake_branch"]["hard_endpoint"],"blind_hard_endpoint":result312["blind_branch"]["hard_endpoint"],"consequence":"downstream-tie","selection_superiority":False,"outcome_authority":True}
    return {**body,"receipt_digest":p82.digest(body)}

CHECKER='''import json\nfrom pathlib import Path\nRULE_KEYS={keys!r}\ndef valid(r):\n return isinstance(r,dict) and set(r)==RULE_KEYS and isinstance(r["version"],int) and r["version"] in {{1,2}} and r["ranking_signal"] in {{"structural-score","consequence-success-rate"}} and isinstance(r["minimum_observations"],int) and 0<=r["minimum_observations"]<=4 and isinstance(r["minimum_rate_gap"],int) and 0<=r["minimum_rate_gap"]<=100 and r["on_insufficient_evidence"] in {{"wait","structural-fallback"}} and r["accepted_outcome"]=="hard-endpoint" and isinstance(r["rationale"],str) and 1<=len(r["rationale"])<=1000\nr=json.loads(Path("selector-revision.json").read_text()); print(json.dumps({{"valid":valid(r)}})); raise SystemExit(0 if valid(r) else 2)\n'''.format(keys=RULE_KEYS)

def seed_actor(root,parent,result312,p82,withheld):
    seed=root/"seed"; seed.mkdir(parents=True); write_json(seed/"selector-revision.json",INCUMBENT); write_json(seed/"selection-consequence.json",consequence(parent,result312,p82,withheld)); write_json(seed/"subject-selection-projection.json",{"source_subject_digest":parent["artifact_digest"],"active_world_seeking_stake":parent["active_world_seeking_stake"],"active_selection_rule":INCUMBENT}); write_json(seed/"selector-rule-contract.json",{"editable":["selector-revision.json"],"fields":sorted(RULE_KEYS),"ranking_signal":["structural-score","consequence-success-rate"],"minimum_observations":[0,4],"minimum_rate_gap":[0,100],"on_insufficient_evidence":["wait","structural-fallback"],"accepted_outcome":"hard-endpoint"}); (seed/"check_revision.py").write_text(CHECKER)
    immutable=["selection-consequence.json","subject-selection-projection.json","selector-rule-contract.json","check_revision.py","mutation-envelope.json","README.md"]; write_json(seed/"mutation-envelope.json",{"editable":["selector-revision.json"],"immutable":immutable})
    (seed/"README.md").write_text("Continue from the exact subject selection projection. Inspect the available completed contact. Decide whether it warrants a bounded selection-machinery revision or retention. The future catalogs, outcomes, identities, evaluator, and sibling are unavailable. Edit only selector-revision.json if revising; run python3 check_revision.py and inspect the exact diff.\n")
    return seed

def output_valid(output,changed):
    return bool(isinstance(output,dict) and set(output)=={"action","files_changed","note"} and isinstance(output.get("note"),str) and ((output["action"]=="revise-selection-machinery" and output["files_changed"]==["selector-revision.json"] and changed) or (output["action"]=="retain-selection-machinery" and output["files_changed"]==[] and not changed)))

def run_actor(context,p82,root,parent,result312,withheld):
    seed=root/"seed"; seed=seed if seed.exists() else seed_actor(root,parent,result312,p82,withheld); stem="selector-revision-withheld" if withheld else "selector-revision-consequence"; label=stem; index=2
    while (context.evidence(label)/"events.jsonl").exists(): label=f"{stem}-transport-{index:02d}"; index+=1
    output,audit0,workspace,_=context.run_actor(label,seed,SCHEMA,(seed/"README.md").read_text().strip())
    try:
        rule=json.loads((workspace/"selector-revision.json").read_text()); immutable=json.loads((seed/"mutation-envelope.json").read_text())["immutable"]; immutable_ok=all((workspace/n).read_bytes()==(seed/n).read_bytes() for n in immutable); changed=rule!=INCUMBENT
    except (OSError,ValueError,KeyError,TypeError): rule=None; immutable_ok=False; changed=False
    semantic=immutable_ok and valid_rule(rule) and output_valid(output,changed); expected=["selector-revision.json"] if changed else []; audit=context.audit_actor(label,output,audit0,semantic,expected); trace=(context.evidence(label)/"events.jsonl").read_text(); normalized=base236.classify_retained(audit,trace); accepted=bool(semantic and base236.g10(normalized))
    return {"accepted":accepted,"rule":rule,"changed":changed,"output":output,"audit":audit,"g10_disposition":accepted,"workspace_evaluation":{"immutable_ok":immutable_ok,"semantic":semantic}}

def compile_child(parent,actor,evaluation,p82):
    body={"authority":AUTHORITY+"-machinery-revision","source_subject_digest":parent["artifact_digest"],"actor_patch_digest":actor["audit"]["patch_digest"],"prior_rule":INCUMBENT,"candidate_rule":actor["rule"],"heldout_score":evaluation,"admission_authority":False,"outcome_authority":False}; receipt={**body,"receipt_digest":p82.digest(body)}; child=copy.deepcopy(parent); child.pop("artifact_digest",None); child["selection_machinery_revisions"]=[*child.get("selection_machinery_revisions",[]),receipt]; child["active_selection_machinery"]=receipt; child["continuation"]={**child["continuation"],"status":"open"}; return p82.seal(child),receipt

def preflight(root,p82,runtime,parent,result312):
    root.mkdir(parents=True,exist_ok=True); cases=anchors("00"*32); good={"version":2,"ranking_signal":"consequence-success-rate","minimum_observations":2,"minimum_rate_gap":1,"on_insufficient_evidence":"wait","accepted_outcome":"hard-endpoint","rationale":"fixture"}; bad=copy.deepcopy(good); bad["ranking_signal"]="unknown"
    checks={"base_hash_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256,"exact_parent":parent["artifact_digest"]==PARENT_DIGEST and result312["receipt_digest"]==OT312_RECEIPT and result312["observer_disposition"]=="rejected" and result312["stake_branch"]["hard_endpoint"] and result312["blind_branch"]["hard_endpoint"],"representative_rule_5_of_5":score(good,cases)["pass_count"]==5,"incumbent_at_most_2_of_5":score(INCUMBENT,cases)["pass_count"]<=2,"malformed_rejected":not valid_rule(bad),"forged_authority_ignored":select(good,cases[-1]["catalog"],[{"world_id":cases[-1]["catalog"][0]["world_id"],"context_id":cases[-1]["context_id"],"outcome":"hard-endpoint","outcome_authority":False}],cases[-1]["context_id"]) is None,"exact_open_conformant":parent["continuation"]["status"]=="open" and runtime.identity_conforms(parent)}; checks["passed"]=all(checks.values()); result={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"fixture_seed_digest":p82.digest("00"*32),"representative_score":score(good,cases),"incumbent_score":score(INCUMBENT,cases),"checks":checks}; result["receipt_digest"]=p82.digest(result); write_json(root/"fixture-conformance.json",result); return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo,run,p82,runtime,parent,result312,core,base130=setup(args)
    retained=run/"preflight/fixture-conformance.json"; fixtures=json.loads(retained.read_text()) if retained.exists() else preflight(run/"preflight",p82,runtime,parent,result312)
    if args.preflight_only: print(json.dumps(fixtures,indent=2,sort_keys=True)); return 0 if fixtures["checks"]["passed"] else 2
    if not fixtures["checks"]["passed"] or (run/"aggregate.json").exists(): raise SystemExit("OT-0313 unavailable")
    seed_path=run/"private-anchor-seed.json"
    if seed_path.exists(): seed=json.loads(seed_path.read_text())["seed"]
    else: seed=secrets.token_hex(32); write_json(seed_path,{"seed":seed,"seed_digest":p82.digest(seed)})
    cases=anchors(seed); context=b.base274.context_for(core,base130,runtime,run/"actors",repo)
    candidate=run_actor(context,p82,run/"candidate",parent,result312,False); candidate_score=score(candidate["rule"],cases) if candidate["accepted"] else None; incumbent_score=score(INCUMBENT,cases)
    operational=bool(candidate["accepted"] and candidate["changed"] and candidate_score["pass_count"]==5 and incumbent_score["pass_count"]<=2)
    child,revision=(compile_child(parent,candidate,candidate_score,p82) if operational else (parent,None)); write_json(run/"candidate-operational-subject.json",child)
    withheld=run_actor(context,p82,run/"withheld",parent,result312,True); withheld_score=score(withheld["rule"],cases) if withheld["accepted"] else None
    causal=bool(operational and not (withheld["accepted"] and withheld["changed"] and withheld_score["pass_count"]==5))
    checks={"preflight_passed":fixtures["checks"]["passed"],"private_seed_postfreeze":True,"candidate_actor_clean":candidate["accepted"],"candidate_beats_incumbent":operational,"operational_child_sealed_before_control":(run/"candidate-operational-subject.json").exists(),"withheld_actor_clean":withheld["accepted"],"causal_generation_control":causal,"child_open_conformant":child["continuation"]["status"]=="open" and runtime.identity_conforms(child)}; checks["passed"]=all(checks.values())
    aggregate={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"source_ot0312_receipt_digest":result312["receipt_digest"],"private_anchor_seed_digest":p82.digest(seed),"candidate_actor":candidate,"candidate_score":candidate_score,"incumbent_score":incumbent_score,"machinery_revision_receipt":revision,"withheld_actor":withheld,"withheld_score":withheld_score,"checks":checks,"operational_transition_passed":operational,"causal_machinery_refinement_supported":causal,"observer_disposition":"promoted" if checks["passed"] else "rejected","subject_disposition":child["continuation"]["status"],"final_subject_digest":child["artifact_digest"],"fresh_actor_count":2}; aggregate["receipt_digest"]=p82.digest(aggregate); write_json(run/"aggregate.json",aggregate); write_json(run/"final-full-subject.json",child); print(json.dumps(aggregate,indent=2,sort_keys=True)); return 0 if checks["passed"] else 2

if __name__=="__main__": raise SystemExit(main())
