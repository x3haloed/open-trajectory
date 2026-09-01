from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, random, secrets, sys, time
from pathlib import Path
from typing import Any

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0116_retained_assimilation_target_abi.py"; BASE_SHA256="613ad08c96137cfacfe5e2c7ecdb1335fe9c199c52749b53ac5320befee822dd"
RUN_SHA256="e956a542579cb4c1235a106f6589f2af21d5166cdea5377f7db6f20b7cf5dd15"; AGGREGATE_SHA256="0676a19faa415571cf31f6ac39249c197fd728698868108a129bd6c805991062"; PARENT_OBJECT_SHA256="3ad82e07c8bc455d2cb84b9818a614e326432c5d12f4e2981d1033843fbda4a9"
PARENT_DIGEST="597fd631b365952423cb1908a7bb201af0116b4a2e707bd1a07514cf93205786"
AUTHOR_SCHEMA=REPO/"spec/ot-0117-selector-reviser.schema.json"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0116 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0117_frozen_ot0116",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
previous=load_base(); prior15=previous.previous; prior14=previous.prior14; prior=previous.prior; kernel=previous.kernel; base=previous.base

def load_parent(p82,repo,store):
    rm,_=p82.materialize(repo,store,"OT-0116","retained-third-expansion-promotion-run.json"); am,ap=p82.materialize(repo,store,"OT-0116","retained-third-expansion-promotion-aggregate.json"); pm,pp=p82.materialize(repo,store,"OT-0116","open-subject-after-third-generic-expansion.json")
    if rm["sha256"]!=RUN_SHA256 or am["sha256"]!=AGGREGATE_SHA256 or pm["sha256"]!=PARENT_OBJECT_SHA256: raise RuntimeError("wrong OT-0116 inputs")
    aggregate=json.loads(ap.read_text()); parent=json.loads(pp.read_text())
    if not aggregate["operational_transition_passed"] or parent["artifact_digest"]!=PARENT_DIGEST: raise RuntimeError("wrong OT-0116 subject")
    return parent

def outcome(option):
    composition=1 if len(option["completed_floors"])>=2 else 0
    shortfall=max(0.0,option["coordination_load"]+option["recovery_volatility"]-option["resilience_margin"])
    failure=5.0*shortfall; utility=option["predicted_expansion"]+0.5*option["public_regret"]+20.0*composition-failure
    return {"failure_cost":failure,"realized_utility":utility}

def contact(identifier,expansion,regret,floors,coordination,volatility,resilience):
    return {"id":identifier,"world_valid":True,"world_contact":True,"held_repeat":False,"reversible":True,"completed_floors":floors,"predicted_expansion":float(expansion),"public_regret":float(regret),"coordination_load":float(coordination),"recovery_volatility":float(volatility),"resilience_margin":float(resilience)}

def portfolio(index,stress,offset=0):
    stem=f"p{index:02d}"; floors=["recovery-safety","resource-schedule"]
    fragile=contact(f"{stem}-fragile",94+offset,40,floors,10+(index%3),8+(index%2),2 if stress else 30)
    balanced=contact(f"{stem}-balanced",80+offset,30,floors,3+(index%2),3,12)
    reserve=contact(f"{stem}-reserve",76+offset,22,["recovery-safety"],1,2,8)
    return {"portfolio_id":f"portfolio-{index:02d}","contacts":[fragile,balanced,reserve],"regime":"stress" if stress else "floor"}

def public_observations():
    rows=[]
    for index,stress in enumerate((True,False,True,True,False,True),1):
        item=portfolio(index,stress,index%2); item["outcomes"]={row["id"]:outcome(row) for row in item["contacts"]}; rows.append(item)
    return rows

def hidden_portfolios(seed):
    generator=random.Random(int.from_bytes(seed,"big")); regimes=[True]*8+[False]*4; generator.shuffle(regimes); rows=[]
    for index,stress in enumerate(regimes,101):
        item=portfolio(index,stress,generator.randint(-3,3)); generator.shuffle(item["contacts"]); rows.append(item)
    return rows

def load_selector(source): return kernel.load_named(source,"select")

def evaluate(source,portfolios):
    selector=load_selector(source); rows=[]
    for item in portfolios:
        original=copy.deepcopy(item["contacts"]); utilities={row["id"]:outcome(row)["realized_utility"] for row in item["contacts"]}; oracle=max(item["contacts"],key=lambda row:(utilities[row["id"]],row["id"]))["id"]
        try: selected=selector(copy.deepcopy(item["contacts"])) if selector else None
        except Exception: selected=None
        valid=selected in utilities and original==item["contacts"]; regret=utilities[oracle]-utilities[selected] if valid else 1000000.0
        rows.append({"portfolio_id":item["portfolio_id"],"regime":item["regime"],"selected_id":selected,"oracle_id":oracle,"selected_utility":utilities.get(selected),"oracle_utility":utilities[oracle],"regret":regret,"input_unchanged":original==item["contacts"],"passed":valid and selected==oracle})
    return {"rows":rows,"correct_count":sum(r["passed"] for r in rows),"floor_correct_count":sum(r["passed"] for r in rows if r["regime"]=="floor"),"total_regret":sum(r["regret"] for r in rows)}

def author_seed(run,parent,parent_source):
    seed=run/"selector-reviser-seed"; seed.mkdir(); opening=kernel.extract_action(NoneProxy(),parent) if False else parent["actor_originated_pursuit_openings"][-1]
    (seed/"subject-opening.json").write_text(json.dumps({"subject_digest":parent["artifact_digest"],"active_pursuit":parent["active_pursuit"],"continuation":parent["continuation"],"originated_opening":opening},indent=2,sort_keys=True)+"\n")
    (seed/"parent-selector.py").write_text(parent_source); (seed/"selector.py").write_text(parent_source)
    (seed/"public-observations.json").write_text(json.dumps(public_observations(),indent=2,sort_keys=True)+"\n")
    contract={"export":"select(contacts) -> one contact id","contact_exact_keys":sorted(contact("id",1,1,[],1,1,1)),"ids":"return an id present in the supplied portfolio","input_mutation":False,"source_constraints":"no imports, classes, globals, nonlocals, with statements, or double-underscore names","available_builtins":sorted(kernel.foundation.SAFE_BUILTINS)}
    (seed/"selector-contract.json").write_text(json.dumps(contract,indent=2,sort_keys=True)+"\n"); (seed/"mutation-envelope.json").write_text(json.dumps({"editable":["selector.py"],"immutable":["parent-selector.py","subject-opening.json","public-observations.json","selector-contract.json"]},indent=2,sort_keys=True)+"\n")
    (seed/"README.md").write_text("Revise the inherited selector from the observed portfolio consequences so it selects better future contacts under the subject's resilience opening. Edit only selector.py, preserve the input, inspect the diff, and report truthfully.\n"); return seed

def run_author(p82,context,run,parent,parent_source):
    label="selector-reviser"; seed=author_seed(run,parent,parent_source); output,base_audit,workspace,_=context.run_actor(label,seed,AUTHOR_SCHEMA,"Revise selector.py from the exact subject opening and public outcome observations. Change no other file, inspect the diff, and report truthfully.")
    try: source=(workspace/"selector.py").read_text(); immutable=(workspace/"parent-selector.py").read_text()==parent_source and json.loads((workspace/"public-observations.json").read_text())==public_observations()
    except (OSError,json.JSONDecodeError): source=""; immutable=False
    public=evaluate(source,public_observations()); valid=bool(immutable and source!=parent_source and load_selector(source) and all(r["input_unchanged"] and r["selected_id"] for r in public["rows"]) and output.get("selector_symbol")=="select")
    audit=context.audit_actor(label,output,base_audit,valid,["selector.py"]); binding=None
    if audit["conformant"]:
        body={"authority":"ot-0117-world-grounded-selector-revision","source_subject_digest":parent["artifact_digest"],"parent_selector_digest":hashlib.sha256(parent_source.encode()).hexdigest(),"actor_patch_digest":audit["patch_digest"],"selector_source":source,"public_observation_digest":p82.digest(public_observations()),"public_execution":public}; binding={**body,"binding_digest":p82.digest(body)}; (context.evidence(label)/"bound-selector.json").write_text(json.dumps(binding,indent=2,sort_keys=True)+"\n")
    return {"output":output,"audit":audit,"binding":binding,"public_execution":public}

def world_contact(p82,run,parent_source,binding):
    seed=secrets.token_bytes(32); (run/"hidden-seed.bin").write_bytes(seed); portfolios=hidden_portfolios(seed); (run/"hidden-portfolios.json").write_text(json.dumps(portfolios,indent=2,sort_keys=True)+"\n")
    revised=evaluate(binding["selector_source"],portfolios); inherited=evaluate(parent_source,portfolios); passed=bool(revised["correct_count"]>=10 and revised["floor_correct_count"]==4 and inherited["correct_count"]<=6 and revised["total_regret"]<=inherited["total_regret"]/4 and all(r["input_unchanged"] for r in revised["rows"]+inherited["rows"]))
    body={"authority":"ot-0117-independent-portfolio-world","selector_binding_digest":binding["binding_digest"],"private_seed_digest":hashlib.sha256(seed).hexdigest(),"derivation_attempt":1,"hidden_portfolio_digest":p82.digest(portfolios),"revised":revised,"inherited":inherited,"passed":passed}; receipt={**body,"receipt_digest":p82.digest(body)}; (run/"world-receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n"); return receipt

def assimilation_seed(prior89,run,parent,binding,world):
    seed=run/"selector-assimilation-seed"; seed.mkdir(); (seed/"subject-contact-consequence.json").write_text(json.dumps({"subject_position":base.active_position(parent),"selector_binding":binding,"world_receipt":world},indent=2,sort_keys=True)+"\n")
    (seed/"assimilation.json").write_text(json.dumps(base.assimilation_template(),indent=2,sort_keys=True)+"\n"); (seed/"successor-opening.json").write_text(json.dumps(prior89.successor_template(),indent=2,sort_keys=True)+"\n"); (seed/"successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(),indent=2,sort_keys=True)+"\n"); (seed/"continuation-action.json").write_text(json.dumps(kernel.foundation.prior.prior.action_template(),indent=2,sort_keys=True)+"\n")
    (seed/"continuation-action-contract.json").write_text(json.dumps({"exact_keys":sorted(kernel.ACTION_KEYS),"action_kinds":["registered-contact","registry-extension","surrender"],"registry-extension":"new lowercase hyphenated target, 3 to 128 characters","surrender":"target exactly none"},indent=2,sort_keys=True)+"\n"); (seed/"revised-selector.py").write_text(binding["selector_source"]); editable=["assimilation.json","successor-opening.json","continuation-action.json"]; (seed/"mutation-envelope.json").write_text(json.dumps({"editable":editable,"immutable":["revised-selector.py","subject-contact-consequence.json"]},indent=2,sort_keys=True)+"\n"); (seed/"README.md").write_text("Assimilate the held-out selector comparison and decide what remains worth pursuing. Preserve the selector bytes, edit exactly the three JSON files, inspect the diff, and report truthfully.\n"); return seed

def run_assimilation(prior89,p82,context,run,parent,binding,world):
    label="selector-assimilation"; seed=assimilation_seed(prior89,run,parent,binding,world); output,base_audit,workspace,_=context.run_actor(label,seed,kernel.ASSIMILATOR_SCHEMA,"Assimilate the completed selector comparison and bind the next continuation. Preserve selector bytes, edit exactly the three JSON files, inspect the diff, and report truthfully.")
    try: assimilation=json.loads((workspace/"assimilation.json").read_text()); opening=json.loads((workspace/"successor-opening.json").read_text()); action=json.loads((workspace/"continuation-action.json").read_text()); retained=(workspace/"revised-selector.py").read_text()==binding["selector_source"]
    except (OSError,json.JSONDecodeError): assimilation=opening=action=None; retained=False
    valid=bool(base.valid_assimilation(assimilation) and prior89.valid_successor(opening) and previous.repaired_action_valid(action,parent) and retained and (action["action_kind"]=="surrender" or opening["next_opening"]!=base.active_position(parent)["continuation"]["next_opening"]))
    audit=context.audit_actor(label,output,base_audit,valid,["assimilation.json","successor-opening.json","continuation-action.json"]); passed_ids={r["portfolio_id"] for r in world["revised"]["rows"] if r["passed"]}; cited=set(assimilation.get("settled_case_ids",[])) if isinstance(assimilation,dict) else set(); grounded=bool(audit["conformant"] and cited and cited.issubset(passed_ids)); result=None
    if grounded:
        body={"authority":"ot-0117-world-grounded-selector-assimilation","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":binding["binding_digest"],"world_receipt_digest":world["receipt_digest"],"actor_patch_digest":audit["patch_digest"],"selector_retention_derived":retained,"assimilation":assimilation,"successor_opening":opening,"continuation_action":action}; result={**body,"binding_digest":p82.digest(body)}; (context.evidence(label)/"bound-assimilation.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return {"output":output,"audit":audit,"grounded":grounded,"binding":result,"selector_retention_derived":retained}

def promote(p82,parent,binding,world,assimilation):
    child=copy.deepcopy(parent); child.pop("artifact_digest",None); action=assimilation["continuation_action"]; opening=assimilation["successor_opening"]; receipt_body={"authority":"world-promoted-selector-refinement","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":binding["binding_digest"],"world_receipt_digest":world["receipt_digest"],"assimilation_binding_digest":assimilation["binding_digest"],"continuation_action":action}; receipt={**receipt_body,"receipt_digest":p82.digest(receipt_body)}
    child["allocation_machinery"]=[*child.get("allocation_machinery",[]),{"authority":"ot-0117-world-grounded-selector","source":binding["selector_source"],"source_digest":hashlib.sha256(binding["selector_source"].encode()).hexdigest(),"binding_digest":binding["binding_digest"],"world_receipt_digest":world["receipt_digest"]}]; child["selector_refinement_receipts"]=[*child.get("selector_refinement_receipts",[]),receipt]; child["pursuit_assimilations"]=[*child.get("pursuit_assimilations",[]),{"receipt":receipt,"assimilation":assimilation["assimilation"]}]; child["actor_originated_pursuit_openings"]=[*child.get("actor_originated_pursuit_openings",[]),{"authority":"ot-0117-selector-opening","binding_digest":assimilation["binding_digest"],"opening":opening,"continuation_action":action}]; child["active_pursuit"]={"authority":"ot-0117-selector-opening","selected_area":action["action_target"],"next_pursuit":opening["next_opening"],"world_receipt_digest":world["receipt_digest"]}; child["continuation"]={**child["continuation"],"status":"closed" if action["action_kind"]=="surrender" else "open","next_opening":opening["next_opening"]}; child["unresolved"]=opening["continuation_after_contact"]; child["runtime"]="sounding"; return p82.seal(child),receipt

class NoneProxy: pass

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0117").resolve(); prior92=base.mechanism.load_prior(); _,_,prior89,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store); parent=load_parent(p82,repo,store); parent_source=parent["allocation_machinery"][-1]["source"]
    public=public_observations(); parent_public=evaluate(parent_source,public); checked={"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"parent_sounding":runtime.identity_conforms(parent),"bound_resilience_opening":"resilience-extension" in parent["active_pursuit"]["selected_area"],"parent_selector_loads":bool(load_selector(parent_source)),"public_count":len(public)==6,"public_outcomes_exact":all(row["outcomes"]=={option["id"]:outcome(option) for option in row["contacts"]} for row in public),"parent_public_executes":all(row["input_unchanged"] and row["selected_id"] for row in parent_public["rows"])}; checked["passed"]=all(checked.values())
    if args.preflight_only: print(json.dumps({"base_sha256":BASE_SHA256,"parent_digest":parent["artifact_digest"],"checks":checked},indent=2,sort_keys=True)); return 0 if checked["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0117 evidence")
    run.mkdir(parents=True); (run/"fixture-conformance.json").write_text(json.dumps(checked,indent=2,sort_keys=True)+"\n");
    if not checked["passed"]: raise SystemExit("pre-actor conformance failed")
    context=prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); started=time.time(); authored=run_author(p82,context,run,parent,parent_source); world=world_contact(p82,run,parent_source,authored["binding"]) if authored["binding"] else None; assimilation=run_assimilation(prior89,p82,context,run,parent,authored["binding"],world) if world and world["passed"] else None; current=parent; promotion=None
    if assimilation and assimilation["binding"]: current,promotion=promote(p82,parent,authored["binding"],world,assimilation["binding"])
    operational=bool(promotion and runtime.identity_conforms(current)); result={"authority":"ot-0117-world-grounded-selector-expansion-driver","source_subject_digest":parent["artifact_digest"],"selector_revision":p82.compact(authored),"world":world,"assimilation":p82.compact(assimilation) if assimilation else None,"promotion":promotion,"operational_transition_passed":operational,"observer_disposition":"promoted" if operational else "rejected","subject_disposition":current["continuation"]["status"],"final_subject_digest":current["artifact_digest"],"continuation_action":current["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":current["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if operational else 2
if __name__=="__main__": raise SystemExit(main())
