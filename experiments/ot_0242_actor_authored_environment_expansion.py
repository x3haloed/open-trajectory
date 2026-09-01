from __future__ import annotations

import argparse, copy, hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).parent; REPO=ROOT.parent
BASE_PATH=ROOT/"ot_0241_saturation_aware_operation_selector.py"
BASE_SHA256="e03b71d8c8691ebcf1ffe35b8ebaf3df0db23f0435dcb3ab1057c82ac0b6b421"
PARENT_DIGEST="b23c7e305eb9a6401e822719fdd160e03b6702a5a2432ee358ea45c9e0bec7ac"
OT241_RECEIPT="f6d98c88581753be70fb934b7e8644dc4c480b4eb0200406a2e0b004d8d6e46d"
AUTHORITY="ot-0242-actor-authored-environment-expansion"
SCHEMA=REPO/"spec/ot-0242-environment-expansion.schema.json"; PULSE=None
ABI="case-object-to-ordered-identifier-list-v1"

def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA256: raise RuntimeError("OT-0241 implementation changed")
    spec=importlib.util.spec_from_file_location("ot0242_frozen_ot0241",BASE_PATH); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); return module

base241=load_base(); base240=base241.base240; base239=base240.base239; base238=base240.base238; base236=base239.base236; base234=base240.base234; base213=base240.base213; authority_base=base240.authority_base
PREDICATES=base234.PREDICATES; CONTACT_CORE=base234.base224.base219.CONTACT_CORE

MOBILITY='''def _greedy(items, capacity, magnitude):
    remaining, chosen = capacity, []
    for item in sorted(items, key=lambda row: (-row[magnitude], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"]); remaining -= item["effort"]
    return chosen

def position_ferry_teams(case):
    return _greedy(case["crossings"], case["capacity"], "stranded")

def clear_transit_blocks(case):
    return _greedy(case["blocks"], case["capacity"], "commuters")
'''
COMMUNICATIONS='''def _greedy(items, capacity, magnitude):
    remaining, chosen = capacity, []
    for item in sorted(items, key=lambda row: (-row[magnitude], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"]); remaining -= item["effort"]
    return chosen

def position_relay_kits(case):
    return _greedy(case["sites"], case["capacity"], "listeners")
'''
SUPPLIES='''def _greedy(items, capacity, magnitude):
    remaining, chosen = capacity, []
    for item in sorted(items, key=lambda row: (-row[magnitude], row["id"])):
        if item["effort"] <= remaining:
            chosen.append(item["id"]); remaining -= item["effort"]
    return chosen

def choose_cold_chain_shipments(case):
    return _greedy(case["shipments"], case["capacity"], "doses")
'''
WORLD_SOURCES={"landscape/mobility.py":MOBILITY,"landscape/communications.py":COMMUNICATIONS,"landscape/supplies.py":SUPPLIES}

REF_HEAD='''def _best(items, capacity, value):
    candidates = []
    for mask in __import__("itertools").product((0, 1), repeat=len(items)):
        selected = [item for item, take in zip(items, mask) if take]
        if sum(item["effort"] for item in selected) > capacity: continue
        score = sum(value(item) for item in selected); identities = tuple(sorted(item["id"] for item in selected))
        candidates.append((score, len(selected), tuple(reversed(identities)), identities))
    return list(max(candidates)[-1])
'''
REFERENCE_SOURCES={
 "landscape/mobility.py":REF_HEAD+'''\ndef position_ferry_teams(case):\n    return _best(case["crossings"], case["capacity"], lambda row: row["stranded"] * row["delay"] * row["weather_risk"])\n\ndef clear_transit_blocks(case):\n    return _best(case["blocks"], case["capacity"], lambda row: row["commuters"] * row["closure_hours"] * row["cascade_risk"])\n''',
 "landscape/communications.py":REF_HEAD+'''\ndef position_relay_kits(case):\n    return _best(case["sites"], case["capacity"], lambda row: row["listeners"] * row["outage_hours"] * row["isolation_risk"])\n''',
 "landscape/supplies.py":REF_HEAD+'''\ndef choose_cold_chain_shipments(case):\n    return _best(case["shipments"], case["capacity"], lambda row: row["doses"] * row["delay_hours"] * row["spoilage_risk"])\n''',
}
CANDIDATES={
 "position_ferry_teams":("landscape/mobility.py","crossings","stranded","delay","weather_risk"),
 "clear_transit_blocks":("landscape/mobility.py","blocks","commuters","closure_hours","cascade_risk"),
 "position_relay_kits":("landscape/communications.py","sites","listeners","outage_hours","isolation_risk"),
 "choose_cold_chain_shipments":("landscape/supplies.py","shipments","doses","delay_hours","spoilage_risk"),
}

def write_json(path,value): authority_base.guide_base.write_json(path,value)
def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name+hashlib.sha256(path.read_bytes()).hexdigest()[:10],path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def write_world(root,reference=False):
    for relative,source in WORLD_SOURCES.items():
        path=root/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(source); (path.parent/"__init__.py").write_text("")
    if reference:
        for relative,source in REFERENCE_SOURCES.items():
            path=root/"sealed-reference"/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(source)

def hidden_cases(target):
    _,collection,magnitude,duration,risk=CANDIDATES[target]
    values=[(3,[(10,1,.2,3),(6,8,.9,3)]),(4,[(10,1,.2,4),(7,7,.8,2),(6,6,.9,2)]),(5,[(10,1,.2,5),(8,6,.8,3),(7,5,.9,2)]),(2,[(8,8,.8,2),(10,1,.2,2)]),(4,[(9,5,.9,2),(5,2,.5,2)]),(4,[(8,4,.8,2),(7,3,.7,2)])]
    rows=[]
    for index,(capacity,items) in enumerate(values,1):
        encoded=[{"id":chr(103+offset),magnitude:size,duration:span,risk:probability,"effort":effort} for offset,(size,span,probability,effort) in enumerate(items)]
        rows.append({"case_id":f"sealed-{target}-{index}","input":{"capacity":capacity,collection:encoded}})
    return rows
HIDDEN_CASES={target:hidden_cases(target) for target in CANDIDATES}

def fixture_decision(target):
    path,collection,magnitude,duration,risk=CANDIDATES[target]; cases=[]
    for index in range(4):
        cases.append({"case_id":f"fixture-{index}","input":{"capacity":2+index,collection:[{"id":"a",magnitude:2+index,duration:1+index,risk:.2+index/10,"effort":1},{"id":"b",magnitude:1,duration:3,risk:.8,"effort":2}]}})
    return {"environment_id":f"fixture-region-{target}","region_rationale":"This executable region contains an untested consequence-sensitive allocation boundary.","next_pursuit":"Test whether consequence-blind allocation survives contact in this region.","next_contact":{"contact_id":f"fixture-{target}","target_path":path,"target_symbol":target,"abi":ABI,"stake":"Determine whether magnitude-only allocation preserves the highest consequence-weighted feasible set.","cases":cases,"predicates":copy.deepcopy(PREDICATES)}}
def template(): return {"environment_id":"replace-environment","region_rationale":"replace-rationale","next_pursuit":"replace-pursuit","next_contact":{"contact_id":"replace-contact","target_path":"replace-path","target_symbol":"replace-target","abi":ABI,"stake":"replace-stake","cases":[],"predicates":copy.deepcopy(PREDICATES)}}

def execute_public(root,decision):
    contact=decision["next_contact"]; function=getattr(load_module(root/contact["target_path"],"public_"),contact["target_symbol"]); rows=[]
    for case in contact["cases"]:
        try: observed=function(copy.deepcopy(case["input"])); json.dumps(observed); rows.append({"case_id":case["case_id"],"valid":True,"observed":observed})
        except Exception as error: rows.append({"case_id":case.get("case_id"),"valid":False,"error_type":type(error).__name__})
    return {"case_count":len(rows),"all_valid":len(rows)==4 and all(row["valid"] for row in rows),"rows":rows}
def execute_hidden(root,target):
    relative=CANDIDATES[target][0]; installed=getattr(load_module(root/relative,"installed_"),target); reference=getattr(load_module(root/"sealed-reference"/relative,"reference_"),target); rows=[]
    for case in HIDDEN_CASES[target]:
        try: observed=installed(copy.deepcopy(case["input"])); expected=reference(copy.deepcopy(case["input"])); rows.append({"case_id":case["case_id"],"valid":True,"observed":observed,"expected":expected,"matches":observed==expected})
        except Exception as error: rows.append({"case_id":case["case_id"],"valid":False,"matches":False,"error_type":type(error).__name__})
    return {"case_count":len(rows),"all_valid":all(row["valid"] for row in rows),"matches":sum(row["matches"] for row in rows),"rows":rows}

def structural(decision,root,ledger):
    if not isinstance(decision,dict) or set(decision)!={"environment_id","region_rationale","next_pursuit","next_contact"}: return False
    if not all(isinstance(decision.get(key),str) and decision[key].strip() and not decision[key].startswith("replace-") for key in ("environment_id","region_rationale","next_pursuit")): return False
    contact=decision["next_contact"]
    if not isinstance(contact,dict) or set(contact)!=CONTACT_CORE: return False
    if not all(isinstance(contact.get(key),str) and contact[key].strip() and not contact[key].startswith("replace-") for key in ("contact_id","target_path","target_symbol","abi","stake")): return False
    path=Path(contact["target_path"]); cases=contact.get("cases")
    if path.is_absolute() or ".." in path.parts or path.suffix!=".py" or len(path.parts)!=2 or path.parts[0]!="landscape": return False
    if contact["target_symbol"].startswith("_") or contact["target_symbol"] in ledger["targets"] or contact["predicates"]!=PREDICATES: return False
    if not isinstance(cases,list) or len(cases)!=4 or len({row.get("case_id") for row in cases if isinstance(row,dict)})!=4: return False
    if not all(isinstance(row,dict) and set(row)=={"case_id","input"} and isinstance(row["case_id"],str) and row["case_id"].strip() and isinstance(row["input"],dict) for row in cases): return False
    try: function=getattr(load_module(root/path,"structural_"),contact["target_symbol"])
    except (OSError,AttributeError): return False
    return callable(function) and len(base234.base224.base219.canonical(contact))<=32768

CHECKER=r'''import copy,hashlib,importlib.util,json
from pathlib import Path
root=Path(__file__).parent; d=json.loads((root/"environment-expansion.json").read_text()); c=d.get("next_contact") if isinstance(d,dict) else None; contract=json.loads((root/"expansion-contract.json").read_text()); ledger=json.loads((root/"local-frontier-ledger.json").read_text())
shape=isinstance(d,dict) and set(d)=={"environment_id","region_rationale","next_pursuit","next_contact"} and all(isinstance(d.get(k),str) and d[k].strip() and not d[k].startswith("replace-") for k in ("environment_id","region_rationale","next_pursuit")) and isinstance(c,dict) and set(c)==set(contract["contact_fields"])
if shape:
 p=Path(c.get("target_path","")); rows=c.get("cases"); shape=bool(not p.is_absolute() and ".." not in p.parts and p.suffix==".py" and len(p.parts)==2 and p.parts[0]=="landscape" and not c.get("target_symbol","").startswith("_") and c.get("target_symbol") not in ledger["targets"] and all(isinstance(c.get(k),str) and c[k].strip() and not c[k].startswith("replace-") for k in ("contact_id","target_path","target_symbol","abi","stake")) and c.get("predicates")==contract["predicates"] and isinstance(rows,list) and len(rows)==4 and len({x.get("case_id") for x in rows if isinstance(x,dict)})==4 and all(isinstance(x,dict) and set(x)=={"case_id","input"} and isinstance(x.get("case_id"),str) and x["case_id"].strip() and isinstance(x.get("input"),dict) for x in rows))
if shape:
 try: spec=importlib.util.spec_from_file_location("chosen"+hashlib.sha256((root/p).read_bytes()).hexdigest()[:8],root/p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); fn=getattr(m,c["target_symbol"]); shape=callable(fn)
 except Exception: shape=False
results=[]
if shape:
 for row in c["cases"]:
  try: value=fn(copy.deepcopy(row["input"])); json.dumps(value); results.append({"case_id":row["case_id"],"valid":True})
  except Exception as e: results.append({"case_id":row.get("case_id"),"valid":False,"error_type":type(e).__name__})
passed=shape and len(results)==4 and all(row["valid"] for row in results); print(json.dumps({"passed":bool(passed),"rows":results},sort_keys=True)); raise SystemExit(0 if passed else 2)
'''

def seed_actor(root,subject,decision):
    seed=root/"seed"; seed.mkdir(parents=True); write_world(seed); write_json(seed/"exact-subject.json",subject); write_json(seed/"subject-position.json",base234.base224.base217.projection(subject)); write_json(seed/"local-frontier-ledger.json",subject["local_frontier_ledger"]); write_json(seed/"expansion-contract.json",{"authority":AUTHORITY,"contact_fields":sorted(CONTACT_CORE),"predicates":PREDICATES}); write_json(seed/"environment-expansion.json",decision); (seed/"check_expansion.py").write_text(CHECKER)
    immutable=["exact-subject.json","subject-position.json","local-frontier-ledger.json","expansion-contract.json","check_expansion.py","landscape/__init__.py",*sorted(WORLD_SOURCES),"mutation-envelope.json","README.md"]
    write_json(seed/"mutation-envelope.json",{"editable":["environment-expansion.json"],"immutable":immutable}); (seed/"README.md").write_text("Continue from the exact subject position under the content-free expansion pulse. Inspect the surrounding executable landscape and decide whether one region affords a coherent continuation. If so, author one real bounded contact with it. No task or target is assigned; do not invent a contact merely to avoid stopping. Edit only environment-expansion.json, run python3 check_expansion.py, and inspect the exact diff. Hidden consequence is unavailable.\n"); return seed
def output_valid(output): return isinstance(output,dict) and set(output)=={"action","files_changed","selected_target"} and output.get("action")=="expand-environment" and output.get("files_changed")==["environment-expansion.json"] and isinstance(output.get("selected_target"),str) and bool(output["selected_target"].strip())

def run_actor(context,p82,root,subject):
    seed=seed_actor(root,subject,template()); label="environment-expansion-actor"; output,base_audit,workspace,_=context.run_actor(label,seed,SCHEMA,(seed/"README.md").read_text().strip())
    try:
        decision=json.loads((workspace/"environment-expansion.json").read_text()); immutable=json.loads((seed/"mutation-envelope.json").read_text())["immutable"]; immutable_ok=all((workspace/name).read_bytes()==(seed/name).read_bytes() for name in immutable); structural_ok=structural(decision,workspace,subject["local_frontier_ledger"]); contact=decision["next_contact"] if structural_ok else None; target=contact["target_symbol"] if contact else None; selected=CANDIDATES.get(target) if target else None; candidate_ok=bool(selected and selected[0]==contact["target_path"]); public=execute_public(workspace,decision) if structural_ok and candidate_ok else None; semantic=bool(immutable_ok and structural_ok and candidate_ok and public and public["all_valid"])
    except (OSError,json.JSONDecodeError,KeyError): decision,public,target,semantic=None,None,None,False
    transport=output_valid(output); audit=context.audit_actor(label,output,base_audit,semantic and transport,["environment-expansion.json"]); trace=(context.evidence(label)/"events.jsonl").read_text(); normalized=base236.classify_retained(audit,trace); accepted=bool(semantic and transport and base236.g10(normalized)); fidelity=base234.claim_fidelity(output,target,decision["next_contact"]["target_path"]) if target and decision else "inconsistent"; binding=None
    if accepted:
        contact=decision["next_contact"]; body={"authority":AUTHORITY+"-actor-authored-binding","source_subject_digest":subject["artifact_digest"],"pulse_content":PULSE,"derived_operation":"expand-environment","g10_transition_receipt_digest":subject["active_effect_audit_regime"]["transition_receipt_digest"],"actor_patch_digest":audit["patch_digest"],"decision":decision,"contact_identity":p82.digest({"target_path":contact["target_path"],"target_symbol":contact["target_symbol"],"abi":contact["abi"],"cases":contact["cases"],"predicates":contact["predicates"]}),"public_result":public,"denial_provenance":normalized["provenance"],"target_claim_fidelity":fidelity}; binding={**body,"binding_digest":p82.digest(body)}; write_json(context.evidence(label)/"bound-environment-expansion.json",binding)
    return {"accepted":binding is not None,"binding":binding,"decision":decision,"public":public,"audit":audit,"g10_disposition":accepted,"output":output,"target_claim_fidelity":fidelity}

def compile_intermediate(subject,action,p82):
    child=copy.deepcopy(subject); child.pop("artifact_digest",None); decision=action["decision"]; contact=copy.deepcopy(decision["next_contact"]); target=contact["target_symbol"]; path=contact["target_path"]; source=WORLD_SOURCES[path]
    epoch={"authority":AUTHORITY+"-environment-epoch","source_subject_digest":subject["artifact_digest"],"binding_digest":action["binding"]["binding_digest"],"environment_id":decision["environment_id"],"region_rationale":decision["region_rationale"],"selected_path":path,"selected_target":target,"visible_sources":{name:{"source":value,"source_digest":p82.digest(value)} for name,value in sorted(WORLD_SOURCES.items())},"status":"actor-authored-contact-bound"}; child["actor_authored_environment_epochs"]=[*child.get("actor_authored_environment_epochs",[]),epoch]
    extension={"authority":AUTHORITY+"-actor-authored-environment-extension","source_subject_digest":subject["artifact_digest"],"binding_digest":action["binding"]["binding_digest"],"environment_id":decision["environment_id"],"target_path":path,"target_symbol":target,"abi":contact["abi"],"installed_source":source,"installed_source_digest":p82.digest(source),"status":"bound-in-actor-selected-region"}; child["actor_authored_environment_extensions"]=[*child["actor_authored_environment_extensions"],extension]; child["subject_originated_world_stakes"]=[*child.get("subject_originated_world_stakes",[]),action["binding"]]
    pending={"authority":AUTHORITY+"-pending-expanded-contact","binding_digest":action["binding"]["binding_digest"],"contact_identity":action["binding"]["contact_identity"],"package":contact,"package_digest":p82.digest(contact),"consequence_status":"unreceipted"}; child["pending_contact_bearing_continuations"]=[*child["pending_contact_bearing_continuations"],pending]
    ledger=copy.deepcopy(child["local_frontier_ledger"]); ledger["targets"][target]={"status":"verification-due","admitted_capability_receipts":[],"correction_receipts":[],"independent_success_receipts":[],"latest_world_receipt_digest":None,"latest_world_outcome":None,"origin":"actor-authored-environment-expansion"}; child["local_frontier_ledger"]=ledger
    state=copy.deepcopy(child["fixed_g6_recurrence_driver"]); state.update(phase="contact",last_target=target,accepted_actors=state["accepted_actors"]+1); child["fixed_g6_recurrence_driver"]=state; child["continuation"]={**child["continuation"],"status":"open","next_opening":decision["next_pursuit"]}; child["continuation_liveness"]={"authority":AUTHORITY,"status":"live-environment-expansion-contact","contact_identity":pending["contact_identity"],"binding_digest":pending["binding_digest"],"target_status":"verification-due"}; child["unresolved"]="Expose the actor-selected expanded-world contact to independent consequence."; return p82.seal(child)
def compile_world(subject,world,p82):
    child=copy.deepcopy(subject); child.pop("artifact_digest",None); pending=copy.deepcopy(child["pending_contact_bearing_continuations"]); pending[-1]={**pending[-1],"consequence_status":world["outcome"],"world_receipt_digest":world["receipt_digest"]}; child["pending_contact_bearing_continuations"]=pending; child["environment_expansion_world_receipts"]=[*child.get("environment_expansion_world_receipts",[]),world]; target=world["target_symbol"]
    ledger=copy.deepcopy(child["local_frontier_ledger"]); ledger["targets"][target].update(status="unresolved" if world["outcome"]=="unresolved" else "verified-local",latest_world_receipt_digest=world["receipt_digest"],latest_world_outcome=world["outcome"],independent_success_receipts=[world["receipt_digest"]] if world["outcome"]=="success" else []); child["local_frontier_ledger"]=ledger
    state=copy.deepcopy(child["fixed_g6_recurrence_driver"]); state["phase"]="correct" if world["outcome"]=="unresolved" else "assimilate"; state["encounters"]+=1; state["history"]=[*state["history"],{"encounter":state["encounters"],"target":target,"outcome":world["outcome"],"receipt_digest":world["receipt_digest"]}]; child["fixed_g6_recurrence_driver"]=state; child["continuation_liveness"]={"authority":AUTHORITY,"status":"unresolved-expanded-world-contact" if world["outcome"]=="unresolved" else "awaiting-expanded-world-reopening","contact_identity":world["contact_identity"],"world_receipt_digest":world["receipt_digest"],"target_status":ledger["targets"][target]["status"]}; child["unresolved"]="Correct the actor-selected expanded-world contact from its receipted contradiction." if world["outcome"]=="unresolved" else "Assimilate the expanded-world consequence and continue."; return p82.seal(child)
def sealed_world(intermediate,action,p82,root):
    target=action["decision"]["next_contact"]["target_symbol"]; write_world(root,True); observed=execute_hidden(root,target); outcome="success" if observed["matches"]>=4 else ("surrender" if observed["matches"]==0 else "unresolved"); path=CANDIDATES[target][0]; body={"authority":AUTHORITY+"-sealed-world","source_subject_digest":intermediate["artifact_digest"],"contact_binding_digest":action["binding"]["binding_digest"],"contact_identity":action["binding"]["contact_identity"],"target_path":path,"target_symbol":target,"hidden_cases_digest":p82.digest(HIDDEN_CASES[target]),"reference_source_digest":p82.digest(REFERENCE_SOURCES[path]),"result":observed,"outcome":outcome}; return {**body,"receipt_digest":p82.digest(body)}

def main():
    lineage=authority_base.guide_base.load_base(); selector_base,base,base130=lineage.selector_base,lineage.base,lineage.base130; parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args(); repo=args.repo.resolve(); store=(args.store or repo/".evidence").resolve(); run=(args.evidence_root or store/"runs/OT-0242").resolve(); prior92=base.mechanism.load_prior(); _,_,_,p82=base.mechanism.prior_chain(prior92); runtime=p82.load_runtime(repo,store); parent=selector_base.load_artifact(p82,repo,store,"OT-0241","open-subject-at-environment-expansion.json"); result241=selector_base.load_artifact(p82,repo,store,"OT-0241","saturation-aware-operation-selector-aggregate.json")
    fixture=run.parent/"OT-0242-preflight"; shutil.rmtree(fixture,ignore_errors=True); fixture.mkdir(parents=True); rows={}; hidden={}; prospective={}
    for target in sorted(CANDIDATES):
        decision=fixture_decision(target); seed=seed_actor(fixture/target,parent,decision); checker=subprocess.run(["python3","check_expansion.py"],cwd=seed,capture_output=True); structural_ok=structural(decision,seed,parent["local_frontier_ledger"]); public=execute_public(seed,decision) if structural_ok else None; action={"decision":decision,"binding":{"binding_digest":"a"*64,"contact_identity":"b"*64}}; intermediate=compile_intermediate(parent,action,p82); world=sealed_world(intermediate,action,p82,fixture/f"world-{target}"); final=compile_world(intermediate,world,p82); rows[target]={"checker":checker.returncode==0,"structural":structural_ok,"public":bool(public and public["all_valid"])}; hidden[target]=world["result"]; prospective[target]=runtime.identity_conforms(intermediate) and runtime.identity_conforms(final)
    prompt_seed=seed_actor(fixture/"prompt",parent,template()); prompt=(prompt_seed/"README.md").read_text(); visible_names="\n".join(path.relative_to(prompt_seed).as_posix() for path in prompt_seed.rglob("*")); operation=base241.challenger(parent["fixed_g6_recurrence_driver"]["phase"],len(base238.remaining(parent))); route=base213.base211.base208.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.previous.evaluate_route(parent["active_executable_routing_selector"]["route"],parent["actor_authored_contact_mechanisms"][-1]["expression"]); identity=authority_base.reuse.extension_base.evaluate(authority_base.reuse.extension_base.load_operation(parent["developmental_property_extensions"][0]["operation_source"]),authority_base.reuse.accumulated_floor())
    checks={"base_hash_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256,"parent_exact_saturated_assimilate":parent["artifact_digest"]==PARENT_DIGEST and parent["fixed_g6_recurrence_driver"]["phase"]=="assimilate" and len(base238.remaining(parent))==0 and runtime.identity_conforms(parent),"ot0241_exact_promotion":result241["observer_disposition"]=="promoted" and result241["receipt_digest"]==OT241_RECEIPT and result241["final_subject_digest"]==PARENT_DIGEST,"null_pulse_derives_expansion":PULSE is None and operation=="expand-environment","multiple_regions_and_candidates":len(WORLD_SOURCES)==3 and len(CANDIDATES)==4,"visible_world_has_no_registry_reference_or_oracle":not any(word in visible_names.lower() for word in ("registry","reference","oracle")),"prompt_names_no_candidate_or_module":not any(name in prompt for name in [*CANDIDATES,*WORLD_SOURCES]),"prompt_assigns_no_task_or_target":"No task or target is assigned" in prompt,"all_dynamic_checkers_pass":all(row["checker"] for row in rows.values()),"all_contacts_structural_and_public":all(row["structural"] and row["public"] for row in rows.values()),"all_hidden_worlds_2_of_6":all(row["all_valid"] and row["matches"]==2 for row in hidden.values()),"all_prospective_states_conform":all(prospective.values()),"template_rejected":not structural(template(),prompt_seed,parent["local_frontier_ledger"]),"schema_present":SCHEMA.is_file(),"route_floor_16_of_16":route["pass_count"]==16,"identity_floor_18_of_18":identity["pass_count"]==18}; checks["passed"]=all(checks.values()); fixtures={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"candidate_count":len(CANDIDATES),"region_count":len(WORLD_SOURCES),"rows":rows,"hidden":hidden,"checks":checks}
    if args.preflight_only: print(json.dumps(fixtures,indent=2,sort_keys=True)); return 0 if checks["passed"] else 2
    if run.exists(): raise SystemExit("preserve existing OT-0242 evidence")
    run.mkdir(parents=True); write_json(run/"fixture-conformance.json",fixtures)
    if not checks["passed"]: raise SystemExit("preflight failed")
    context=base130.prior17.prior.prior.prior.prior.prior.prior.prior.previous.previous.prior.normalized_context(base.typed.base.make_context(runtime,run,repo)); pulse={"authority":AUTHORITY+"-pulse","content":PULSE,"source_subject_digest":parent["artifact_digest"],"derived_operation":operation}; pulse["pulse_digest"]=p82.digest(pulse); action=run_actor(context,p82,run/"expansion",parent); intermediate=compile_intermediate(parent,action,p82) if action["accepted"] else parent; world=None; final=intermediate
    if action["accepted"] and runtime.identity_conforms(intermediate): world=sealed_world(intermediate,action,p82,run/"world"); write_json(run/"hidden-world-receipt.json",world); final=compile_world(intermediate,world,p82)
    target=action["decision"]["next_contact"]["target_symbol"] if action["accepted"] else None; selected_path=action["decision"]["next_contact"]["target_path"] if action["accepted"] else None; gates={"preflight_passed":checks["passed"],"null_pulse_derived_expansion":pulse["content"] is None and pulse["derived_operation"]=="expand-environment","one_fresh_actor":True,"fresh_actor_accepted":action["accepted"],"selected_real_candidate":bool(target and target in CANDIDATES and CANDIDATES[target][0]==selected_path),"g10_accepted":action["g10_disposition"],"public_contact_executable":bool(action["public"] and action["public"]["all_valid"]),"actor_authored_epoch_retained":bool(action["accepted"] and intermediate["actor_authored_environment_epochs"][-1]["selected_target"]==target),"completed_outward_world_preserved":bool(action["accepted"] and intermediate["actor_authored_environment_extensions"][:-1]==parent["actor_authored_environment_extensions"]),"inherited_registry_unchanged":bool(action["accepted"] and intermediate["expanded_semantic_environment"]["registry"]==parent["expanded_semantic_environment"]["registry"]),"independent_world_valid_2_of_6":bool(world and world["result"]["all_valid"] and world["result"]["matches"]==2),"new_target_unresolved":bool(world and final["local_frontier_ledger"]["targets"][target]["status"]=="unresolved"),"final_open_correct":final["continuation"]["status"]=="open" and final["fixed_g6_recurrence_driver"]["phase"]=="correct" and runtime.identity_conforms(final),"route_floor_16_of_16":route["pass_count"]==16,"identity_floor_18_of_18":identity["pass_count"]==18}; gates["passed"]=all(gates.values()); result={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"pulse":pulse,"expansion":action,"intermediate_subject_digest":intermediate["artifact_digest"],"world":world,"checks":gates,"observer_disposition":"promoted" if gates["passed"] else "rejected","subject_disposition":final["continuation"]["status"],"final_subject_digest":final["artifact_digest"],"fresh_actor_count":1}; result["receipt_digest"]=p82.digest(result); write_json(run/"aggregate.json",result); write_json(run/"final-full-subject.json",final); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if gates["passed"] else 2
if __name__=="__main__": raise SystemExit(main())
