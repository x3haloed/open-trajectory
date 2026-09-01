from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, random, secrets, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0120_grounded_opening_renewal.py"; BASE_SHA256="4b0f02654eabdccdd2f10d4664da4fad3bf103c5d3fdbaf61b6d6d5a457bbc86"; PARENT_OBJECT_SHA256="d61bccfadb8008803f5a701d1853af288de63696b2076d5abc251729a6995ec0"; PARENT_DIGEST="94bad6975b902e6e181ff125ea58c44c2c8c090f11c534f74351691f3ccf124f"; PROMOTED_SELECTOR="b03f52963b7ed38bd4274fcf68e2f180cb6fd6dda274fc2d9491c622cbe024f6"; AUTHOR_SCHEMA=REPO/"spec/ot-0117-selector-reviser.schema.json"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0120 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0121_frozen_ot0120",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module
previous=load_base(); prior19=previous.previous; prior18=prior19.prior18; prior17=previous.prior17; base=previous.base; kernel=prior17.kernel

def load_inputs(p82,repo,store,destination):
    pm,pp=p82.materialize(repo,store,"OT-0120","open-subject-with-world-improved-selector.json"); parent=json.loads(pp.read_text())
    if pm["sha256"]!=PARENT_OBJECT_SHA256 or parent["artifact_digest"]!=PARENT_DIGEST: raise RuntimeError("wrong OT-0120 parent")
    raw17,aggregate17,_=prior18.load_inputs(p82,repo,store,destination); a_hidden=json.loads((raw17/"hidden-portfolios.json").read_text()); promoted=parent["allocation_machinery"][-1]
    if promoted["binding_digest"]!=PROMOTED_SELECTOR: raise RuntimeError("wrong promoted selector")
    return parent,promoted["source"],a_hidden,aggregate17["world"]

def contact(identifier,expansion,regret,floors,coordination,volatility,resilience,carry):
    return {"id":identifier,"world_valid":True,"world_contact":True,"held_repeat":False,"reversible":True,"completed_floors":floors,"predicted_expansion":float(expansion),"public_regret":float(regret),"coordination_load":float(coordination),"recovery_volatility":float(volatility),"resilience_margin":float(resilience),"resilience_carry_cost":float(carry)}

def outcome(option):
    prior=prior17.outcome({k:v for k,v in option.items() if k!="resilience_carry_cost"}); carry=option["resilience_carry_cost"]*option["resilience_margin"]; return {"failure_cost":prior["failure_cost"],"realized_carry_cost":carry,"realized_utility":prior["realized_utility"]-carry}

def portfolio(index,contradiction,offset=0):
    stem=f"later-{index:02d}"; floors=["recovery-safety","resource-schedule"]
    overbuilt=contact(f"{stem}-overbuilt",94+offset,40,floors,2,2,30,4 if contradiction else 0); calibrated=contact(f"{stem}-calibrated",84+offset,30,floors,4,3,9,1 if contradiction else 0); reserve=contact(f"{stem}-reserve",76+offset,20,["recovery-safety"],2,2,6,1 if contradiction else 0)
    return {"portfolio_id":f"later-portfolio-{index:02d}","regime":"contradiction" if contradiction else "prior-floor","contacts":[overbuilt,calibrated,reserve]}

def public_rows():
    rows=[]
    for i,c in enumerate((True,False,True,True,False,True),1): item=portfolio(i,c,i%2); item["outcomes"]={x["id"]:outcome(x) for x in item["contacts"]}; rows.append(item)
    return rows

def hidden_rows(seed):
    g=random.Random(int.from_bytes(seed,"big")); regimes=[True]*8+[False]*4; g.shuffle(regimes); rows=[]
    for i,c in enumerate(regimes,101): item=portfolio(i,c,g.randint(-3,3)); g.shuffle(item["contacts"]); rows.append(item)
    return rows

def evaluate(source,rows):
    selector=prior17.load_selector(source); out=[]
    for item in rows:
        original=copy.deepcopy(item["contacts"]); utilities={x["id"]:outcome(x)["realized_utility"] for x in item["contacts"]}; oracle=max(item["contacts"],key=lambda x:(utilities[x["id"]],x["id"]))["id"]
        try: selected=selector(copy.deepcopy(item["contacts"])) if selector else None
        except Exception: selected=None
        valid=selected in utilities and original==item["contacts"]; regret=utilities[oracle]-utilities[selected] if valid else 1000000.0; out.append({"portfolio_id":item["portfolio_id"],"regime":item["regime"],"selected_id":selected,"oracle_id":oracle,"selected_utility":utilities.get(selected),"oracle_utility":utilities[oracle],"regret":regret,"input_unchanged":original==item["contacts"],"passed":valid and selected==oracle})
    return {"rows":out,"correct_count":sum(x["passed"] for x in out),"floor_correct_count":sum(x["passed"] for x in out if x["regime"]=="prior-floor"),"total_regret":sum(x["regret"] for x in out)}

def author_seed(run,parent,promoted,a_receipt):
    path=run/"selector-corrector-seed"; path.mkdir(); (path/"subject-opening.json").write_text(json.dumps({"subject_digest":parent["artifact_digest"],"active_pursuit":parent["active_pursuit"],"continuation":parent["continuation"]},indent=2,sort_keys=True)+"\n"); (path/"promoted-selector.py").write_text(promoted); (path/"selector.py").write_text(promoted); (path/"public-later-observations.json").write_text(json.dumps(public_rows(),indent=2,sort_keys=True)+"\n"); (path/"prior-world-receipt.json").write_text(json.dumps(a_receipt,indent=2,sort_keys=True)+"\n")
    contract={"export":"select(contacts) -> one contact id","new_observable_field":"resilience_carry_cost","prior_compatibility":"prior contacts omit resilience_carry_cost; treat omission as zero","input_mutation":False,"source_constraints":"no imports, classes, globals, nonlocals, with statements, or double-underscore names","available_builtins":sorted(kernel.foundation.SAFE_BUILTINS)}; (path/"selector-contract.json").write_text(json.dumps(contract,indent=2,sort_keys=True)+"\n"); (path/"mutation-envelope.json").write_text(json.dumps({"editable":["selector.py"],"immutable":["promoted-selector.py","subject-opening.json","public-later-observations.json","prior-world-receipt.json","selector-contract.json"]},indent=2,sort_keys=True)+"\n"); (path/"README.md").write_text("Correct the promoted selector from the later objective outcomes while preserving prior-contact compatibility. Edit only selector.py, inspect the diff, and report truthfully.\n"); return path

def revise(p82,context,run,parent,promoted,a_receipt):
    label="selector-corrector"; seed=author_seed(run,parent,promoted,a_receipt); output,base_audit,workspace,_=context.run_actor(label,seed,AUTHOR_SCHEMA,"Correct selector.py from the exact promoted selector and later objective outcomes. Preserve prior compatibility, change no other file, inspect the diff, and report truthfully.")
    try: source=(workspace/"selector.py").read_text(); immutable=(workspace/"promoted-selector.py").read_text()==promoted
    except OSError: source=""; immutable=False
    public=evaluate(source,public_rows()); valid=bool(immutable and source!=promoted and prior17.load_selector(source) and all(x["selected_id"] and x["input_unchanged"] for x in public["rows"])); audit=context.audit_actor(label,output,base_audit,valid,["selector.py"]); binding=None
    if audit["conformant"]:
        body={"authority":"ot-0121-contradiction-corrected-selector","source_subject_digest":parent["artifact_digest"],"parent_selector_digest":hashlib.sha256(promoted.encode()).hexdigest(),"actor_patch_digest":audit["patch_digest"],"selector_source":source,"public_later_digest":p82.digest(public_rows()),"public_execution":public}; binding={**body,"binding_digest":p82.digest(body)}; (context.evidence(label)/"bound-selector.json").write_text(json.dumps(binding,indent=2,sort_keys=True)+"\n")
    return {"output":output,"audit":audit,"public_execution":public,"binding":binding}

def world(p82,run,promoted,binding,a_hidden):
    seed=secrets.token_bytes(32); (run/"hidden-later-seed.bin").write_bytes(seed); later=hidden_rows(seed); (run/"hidden-later-portfolios.json").write_text(json.dumps(later,indent=2,sort_keys=True)+"\n"); corrected=evaluate(binding["selector_source"],later); unchanged=evaluate(promoted,later); replay=prior17.evaluate(binding["selector_source"],a_hidden); passed=bool(corrected["correct_count"]>=10 and corrected["floor_correct_count"]==4 and unchanged["correct_count"]<=6 and corrected["total_regret"]<=unchanged["total_regret"]/4 and replay["correct_count"]>=10 and replay["floor_correct_count"]==4 and replay["total_regret"]<=137); body={"authority":"ot-0121-independent-contradictory-world","selector_binding_digest":binding["binding_digest"],"private_seed_digest":hashlib.sha256(seed).hexdigest(),"derivation_attempt":1,"later_portfolio_digest":p82.digest(later),"corrected":corrected,"unchanged_promoted":unchanged,"prior_hidden_replay":replay,"passed":passed}; receipt={**body,"receipt_digest":p82.digest(body)}; (run/"world-receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n"); return receipt

def assimilation_seed(prior89,run,parent,binding,world):
    path=run/"correction-assimilation-seed"; path.mkdir(); accepted=[x["portfolio_id"] for x in world["corrected"]["rows"] if x["passed"]]; (path/"subject-contact-consequence.json").write_text(json.dumps({"subject_position":base.active_position(parent),"selector_binding":binding,"world_receipt":world},indent=2,sort_keys=True)+"\n"); (path/"grounding-contract.json").write_text(json.dumps({"settled_case_ids_namespace":"portfolio_id","accepted_passed_portfolio_ids":accepted},indent=2,sort_keys=True)+"\n"); (path/"assimilation.json").write_text(json.dumps(base.assimilation_template(),indent=2,sort_keys=True)+"\n"); (path/"successor-opening.json").write_text(json.dumps(prior89.successor_template(),indent=2,sort_keys=True)+"\n"); (path/"successor-opening-contract.json").write_text(json.dumps(prior89.successor_contract(),indent=2,sort_keys=True)+"\n"); (path/"continuation-action.json").write_text(json.dumps(kernel.foundation.prior.prior.action_template(),indent=2,sort_keys=True)+"\n"); (path/"continuation-action-contract.json").write_text(json.dumps({"exact_keys":sorted(kernel.ACTION_KEYS),"action_kinds":["registered-contact","registry-extension","surrender"],"registry-extension":"new lowercase hyphenated target, 3 to 128 characters","surrender":"target exactly none"},indent=2,sort_keys=True)+"\n"); (path/"corrected-selector.py").write_text(binding["selector_source"]); (path/"mutation-envelope.json").write_text(json.dumps({"editable":["assimilation.json","successor-opening.json","continuation-action.json"],"immutable":["corrected-selector.py","subject-contact-consequence.json","grounding-contract.json"]},indent=2,sort_keys=True)+"\n"); (path/"README.md").write_text("Assimilate the contradictory selector correction using portfolio ids from the grounding contract. Preserve selector bytes, edit the three JSON files, inspect the diff, and report truthfully.\n"); return path,set(accepted)

def assimilate(prior89,p82,context,run,parent,binding,world):
    label="correction-assimilation"; seed,accepted=assimilation_seed(prior89,run,parent,binding,world); output,base_audit,ws,_=context.run_actor(label,seed,kernel.ASSIMILATOR_SCHEMA,"Assimilate the completed contradictory selector correction and bind the next continuation. Preserve selector bytes, use portfolio ids, inspect the diff, and report truthfully.")
    try: a=json.loads((ws/"assimilation.json").read_text()); opening=json.loads((ws/"successor-opening.json").read_text()); action=json.loads((ws/"continuation-action.json").read_text()); retained=(ws/"corrected-selector.py").read_text()==binding["selector_source"]
    except (OSError,json.JSONDecodeError): a=opening=action=None; retained=False
    cited=set(a.get("settled_case_ids",[])) if isinstance(a,dict) else set(); valid=bool(base.valid_assimilation(a) and prior89.valid_successor(opening) and prior18.previous.previous.repaired_action_valid(action,parent) and retained and cited and cited.issubset(accepted)); audit=context.audit_actor(label,output,base_audit,valid,["assimilation.json","successor-opening.json","continuation-action.json"]); bound=None
    if audit["conformant"]:
        body={"authority":"ot-0121-contradictory-selector-assimilation","source_subject_digest":parent["artifact_digest"],"selector_binding_digest":binding["binding_digest"],"world_receipt_digest":world["receipt_digest"],"actor_patch_digest":audit["patch_digest"],"selector_retention_derived":retained,"assimilation":a,"successor_opening":opening,"continuation_action":action}; bound={**body,"binding_digest":p82.digest(body)}; (context.evidence(label)/"bound-assimilation.json").write_text(json.dumps(bound,indent=2,sort_keys=True)+"\n")
    return {"output":output,"audit":audit,"grounded":bool(cited and cited.issubset(accepted)),"selector_retention_derived":retained,"binding":bound}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--repo",type=Path,default=REPO); p.add_argument("--store",type=Path); p.add_argument("--evidence-root",type=Path); p.add_argument("--preflight-only",action="store_true"); args=p.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0121").resolve(); prior92=base.mechanism.load_prior(); _,_,prior89,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store)
    with tempfile.TemporaryDirectory() as d: parent,promoted,a_hidden,a_receipt=load_inputs(p82,repo,store,Path(d))
    checks={"parent_exact":parent["artifact_digest"]==PARENT_DIGEST,"parent_sounding":runtime.identity_conforms(parent),"promoted_selector_loads":bool(prior17.load_selector(promoted)),"prior_hidden_count":len(a_hidden)==12,"public_later_count":len(public_rows())==6,"later_field_present":all("resilience_carry_cost" in x for row in public_rows() for x in row["contacts"])}; checks["passed"]=all(checks.values())
    if args.preflight_only: print(json.dumps({"base_sha256":BASE_SHA256,"checks":checks},indent=2,sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0121 evidence")
    run.mkdir(parents=True); (run/"fixture-conformance.json").write_text(json.dumps(checks,indent=2,sort_keys=True)+"\n"); context=prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); started=time.time(); revision=revise(p82,context,run,parent,promoted,a_receipt); receipt=world(p82,run,promoted,revision["binding"],a_hidden) if revision["binding"] else None; assimilation=assimilate(prior89,p82,context,run,parent,revision["binding"],receipt) if receipt and receipt["passed"] else None; current=parent; promotion=None
    if assimilation and assimilation["binding"]: current,promotion=prior17.promote(p82,parent,revision["binding"],receipt,assimilation["binding"])
    operational=bool(promotion and runtime.identity_conforms(current)); result={"authority":"ot-0121-contradictory-selector-correction-driver","source_subject_digest":parent["artifact_digest"],"selector_correction":p82.compact(revision),"world":receipt,"assimilation":p82.compact(assimilation) if assimilation else None,"promotion":promotion,"operational_transition_passed":operational,"observer_disposition":"promoted" if operational else "rejected","subject_disposition":current["continuation"]["status"],"final_subject_digest":current["artifact_digest"],"continuation_action":current["actor_originated_pursuit_openings"][-1].get("continuation_action"),"next_opening":current["continuation"]["next_opening"],"elapsed_seconds":round(time.time()-started,3)}; result["receipt_digest"]=p82.digest(result); (run/"aggregate.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); (run/"final-full-subject.json").write_text(json.dumps(current,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if operational else 2
if __name__=="__main__": raise SystemExit(main())
