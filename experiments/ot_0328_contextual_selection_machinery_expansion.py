from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0327_subject_authored_falsification_fronts.py"
BASE_SHA256 = "9b4f842a761386e1877a3f92f27b968af0cc45b9cf2c36731fccb58638af0d6c"
PARENT_DIGEST = "b915e77ddf5b07b45fd1a7a73fe2f41efc988e9d1e92718a7c7bdb47cec69f2e"
OT327_RECEIPT = "40220c27fb9cf79d4f52fb06b59d69b864574a6f9c78745372197904c288b063"
OT327_RECONSTRUCTION = "fa8a82259ac1a04968d613b9f74a28194c0314f7e915f8c2b03f8e9021c6d978"
AUTHORITY = "ot-0328-contextual-selection-machinery-expansion"
ACTION_SCHEMA = REPO / "spec" / "ot-0328-policy-action.schema.json"
EXECUTION_SCHEMA = REPO / "spec" / "ot-0328-policy-execution.schema.json"
FEATURES = ("branch_nodes", "call_nodes", "comparison_nodes", "loop_nodes", "source_bytes")


CURRENT_POLICY_SOURCE = '''def select(case):
    weights=case["default_weights"]
    rows=[(sum([weights[key]*item["features"][key] for key in ("branch_nodes","call_nodes","comparison_nodes","loop_nodes","source_bytes")]),item["public_package_digest"],item["world_id"]) for item in case["catalog"]]
    ranked=sorted(rows,key=lambda row:(-row[0],row[1],row[2]))
    if ranked[0][0]-ranked[1][0]<case["minimum_score_gap"]:
        return None
    return ranked[0][2]
'''

POLICY_CONTRACT_SOURCE = r'''import ast
import copy
import hashlib

FEATURES=("branch_nodes","call_nodes","comparison_nodes","loop_nodes","source_bytes")
ALLOWED_CALLS={"dict","len","list","max","min","sorted","sum","tuple"}

def policy_safe(source):
    if not isinstance(source,str) or not 1<=len(source.encode())<=6000 or any(x in source for x in ("/Users/","/home/","__","open(","eval(","exec(","compile(")):
        return False
    try: tree=ast.parse(source)
    except SyntaxError: return False
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!="select": return False
    denied=(ast.Import,ast.ImportFrom,ast.Attribute,ast.AsyncFunctionDef,ast.ClassDef,ast.Global,ast.Nonlocal,ast.Try,ast.With,ast.AsyncWith,ast.While)
    if any(isinstance(node,denied) for node in ast.walk(tree)): return False
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and not (isinstance(node.func,ast.Name) and node.func.id in ALLOWED_CALLS): return False
    return True

def load_policy(source):
    if not policy_safe(source): raise ValueError("unsafe policy")
    safe={name:value for name,value in {"dict":dict,"len":len,"list":list,"max":max,"min":min,"sorted":sorted,"sum":sum,"tuple":tuple}.items() if name in ALLOWED_CALLS}
    ns={}; exec(compile(source,"<selection-policy>","exec"),{"__builtins__":safe},ns)
    return ns["select"]

def choose(source,case):
    fn=load_policy(source); before=copy.deepcopy(case); first=fn(copy.deepcopy(case)); second=fn(copy.deepcopy(case))
    ids={item["world_id"] for item in case["catalog"]}
    if first!=second or first not in ids|{None} or case!=before: raise ValueError("non-total policy")
    return first

def score(source,cases):
    rows=[]
    try:
        for row in cases:
            selected=choose(source,row["case"]); rows.append({"case_id":row["case_id"],"selected_world_id":selected,"best_world_id":row["best_world_id"],"passed":selected==row["best_world_id"]})
    except (KeyError,TypeError,ValueError,IndexError,ZeroDivisionError):
        return {"program_valid":False,"case_count":len(cases),"pass_count":0,"rows":[]}
    return {"program_valid":True,"case_count":len(cases),"pass_count":sum(x["passed"] for x in rows),"rows":rows}

def evaluate(source,floor,contact):
    floor_score=score(source,floor)
    available=all(isinstance(row,dict) and isinstance(row.get("best_world_id"),str) for row in contact)
    contact_score=score(source,contact) if available else None
    valid=policy_safe(source) and floor_score["program_valid"] and floor_score["pass_count"]==len(floor) and (not available or contact_score["program_valid"])
    return {"valid":valid,"source_digest":hashlib.sha256(source.encode()).hexdigest() if isinstance(source,str) else None,"floor_score":floor_score,"contact_outcomes_available":available,"contact_score":contact_score}
'''

CHECK_POLICY_SOURCE = '''import json\nfrom pathlib import Path\nfrom policy_contract import evaluate\nresult=evaluate(Path("selection-policy.py").read_text(),json.loads(Path("floor-cases.json").read_text()),json.loads(Path("later-contact.json").read_text()))\nprint(json.dumps(result,sort_keys=True)); raise SystemExit(0 if result["valid"] else 2)\n'''
RUN_POLICY_SOURCE = '''import json\nfrom pathlib import Path\nfrom policy_contract import choose\nsource=Path("selection-policy.py").read_text(); cases=json.loads(Path("heldout-cases.json").read_text())\nrows=[{"case_id":row["case_id"],"selected_world_id":choose(source,row["case"])} for row in cases]\nPath("predictions.json").write_text(json.dumps(rows,indent=2,sort_keys=True)+"\\n")\n'''
CHECK_PREDICTIONS_SOURCE = '''import json\nfrom pathlib import Path\ncases=json.loads(Path("heldout-cases.json").read_text()); rows=json.loads(Path("predictions.json").read_text())\nok=isinstance(rows,list) and len(rows)==len(cases) and [x.get("case_id") for x in rows]==[x["case_id"] for x in cases] and all(set(x)=={"case_id","selected_world_id"} and x["selected_world_id"] in {item["world_id"] for item in case["case"]["catalog"]}|{None} for x,case in zip(rows,cases))\nprint(json.dumps({"valid":ok,"prediction_count":len(rows) if isinstance(rows,list) else None},sort_keys=True)); raise SystemExit(0 if ok else 2)\n'''


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"OT-0327 changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0328_frozen_ot0327", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
b = base.b
base236 = base.base236
write_json = base.write_json
policy_ns: dict = {}
exec(POLICY_CONTRACT_SOURCE, policy_ns)


def setup(args):
    repo, store, _, p82, runtime, parent326, result326, seed326, core, base130 = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0328").resolve()
    selector = b.authority_base.guide_base.load_base().selector_base
    parent = selector.load_artifact(p82, repo, store, "OT-0327", "open-subject-after-subject-authored-falsification.json")
    result = selector.load_artifact(p82, repo, store, "OT-0327", "subject-authored-falsification-aggregate.json")
    reconstruction = selector.load_artifact(p82, repo, store, "OT-0327", "subject-authored-falsification-exact-reconstruction.json")
    private327 = selector.load_artifact(p82, repo, store, "OT-0327", "private-front-world-seed.json")
    return repo, store, run, p82, runtime, parent326, seed326, parent, result, reconstruction, private327, core, base130


def policy_case(catalog, context_id, stake):
    return {"context_id":context_id,"catalog":copy.deepcopy(catalog),"default_weights":copy.deepcopy(stake["weights"]),"minimum_score_gap":stake["minimum_score_gap"]}


def scored_case(case_id, catalog, best_world_id, context_id, stake):
    return {"case_id":case_id,"case":policy_case(catalog,context_id,stake),"best_world_id":best_world_id}


def floor40(parent326, seed326, parent, result, private327, p82):
    stake=base.base.base.base.base316.stake_of(parent)
    floor=[]
    for index,contact in enumerate(base.floor_contacts(parent326,seed326,p82)):
        floor.append(scored_case(f"floor-{index:02d}",contact["catalog"],contact["outcome"]["best_world_id"],"earned-global",stake))
    truth=int(private327["hidden_rule"].split("-")[1])
    _,heldout=base.materialize(result["active_author"]["source"],private327["seed"],truth,base.base.base.base.base316.stake_of(parent326),p82,"active")
    selected=result["active_route"]["route"]["selected_front_id"]
    for row in heldout[selected]:
        floor.append(scored_case(row["episode_id"],row["catalog"],row["best_world_id"],"earned-authored-front",stake))
    return floor


def materialize_instances(source, seed, truth, stake, p82, label, context_id, instances):
    rows={fid:[] for fid in base.contract_ns["outputs"](source,instances[0])}
    for instance in instances:
        for fid,mapped in base.contract_ns["outputs"](source,instance).items():
            catalog=[]; values={}
            for hypothesis,route_source in mapped.items():
                raw=(seed+label+fid+instance["instance_id"]+hypothesis+route_source).encode()
                wid="w-"+hashlib.sha256(raw).hexdigest()[:16]
                catalog.append({"world_id":wid,"public_package_digest":hashlib.sha256(b"public"+raw).hexdigest(),"features":base.contract_ns["features"](route_source)})
                values[wid]=4 if hypothesis==f"slope-{truth}" else 0
            catalog.sort(key=lambda x:x["world_id"]); best=max(values,key=values.get)
            rows[fid].append(scored_case("e-"+base.token(seed,label+fid+instance["instance_id"])[:16],catalog,best,context_id,stake))
    return rows


def e13_boundary(parent, stake, training, floor, p82):
    fronts=[{"front_id":fid,"offer_index":i,"kind":"retained-generator-later-regime","contacts":base.base.contacts(stake,[{"episode_id":x["case_id"],"catalog":x["case"]["catalog"],"option_value":{item["world_id"]:(4 if item["world_id"]==x["best_world_id"] else 0) for item in x["case"]["catalog"]},"best_world_id":x["best_world_id"]} for x in rows],p82)} for i,(fid,rows) in enumerate(sorted(training.items()))]
    floor_contacts=[{"catalog":x["case"]["catalog"],"outcome":{"best_world_id":x["best_world_id"]}} for x in floor]
    summaries=base.base.run_assessor(parent["active_front_assessor_capability"]["source"],stake,base.base.contract_for(parent),fronts,floor_contacts)["parsed"]
    route=base.base.base.run_router(parent["active_proposal_search_router"]["source"],parent["active_proposal_search_capability"]["applicability"],summaries)["parsed"]
    failing=next((x for x in summaries if x["current_pass_count"]==0),None)
    passed=bool(failing and failing["best_pass_count"]==4 and failing["candidate_floor_pass_count"]==25 and not failing["candidate_preserves_floor"] and route["action"]=="wait" and route["selected_front_id"] is None)
    return {"fronts":fronts,"summaries":summaries,"route":route,"failing_front_id":failing["front_id"] if failing else None,"passed":passed}


def public_only(rows):
    return [{"case_id":row["case_id"],"case":row["case"]} for row in rows]


def erased_contact(rows,p82):
    return [{"case_id":row["case_id"],"case":row["case"],"best_world_id":None,"outcome_digest":p82.digest(row["best_world_id"]),"outcome_available":False} for row in rows]


def evaluate(source,floor,contact): return policy_ns["evaluate"](source,floor,contact)
def score(source,cases): return policy_ns["score"](source,cases)


def valid_policy_transport(output, changed):
    if not isinstance(output,dict):
        return False
    return (
        output.get("action")=="revise-selection-policy"
        and output.get("files_changed")==["selection-policy.py"]
        and changed
    ) or (
        output.get("action")=="retain-selection-policy"
        and output.get("files_changed")==[]
        and not changed
    )


def valid_execution_transport(output):
    return bool(
        isinstance(output,dict)
        and output.get("action")=="execute-retained-selection-policy"
        and output.get("files_changed")==["predictions.json"]
    )


def reference_policy(context_id,weights):
    entries=",".join(f'"{key}":{weights[key]}' for key in FEATURES)
    return CURRENT_POLICY_SOURCE.replace('    weights=case["default_weights"]',f'    weights=case["default_weights"]\n    if case["context_id"]=="{context_id}":\n        weights={{{entries}}}')


def seed_policy_actor(root,parent,floor,contact,p82,*,erased):
    seed=root/"seed"; seed.mkdir(parents=True)
    (seed/"selection-policy.py").write_text(CURRENT_POLICY_SOURCE)
    (seed/"policy_contract.py").write_text(POLICY_CONTRACT_SOURCE)
    (seed/"check_policy.py").write_text(CHECK_POLICY_SOURCE)
    write_json(seed/"floor-cases.json",floor); write_json(seed/"later-contact.json",erased_contact(contact,p82) if erased else contact)
    stake=base.base.base.base.base316.stake_of(parent)
    write_json(seed/"subject-position.json",{"source_subject_digest":parent["artifact_digest"],"active_stake":stake,"active_pursuit":parent["active_pursuit"],"continuation":parent["continuation"],"actor_authored_generator_digest":parent["active_subject_authored_front_generator"]["source_digest"],"contact_outcomes_available":not erased})
    immutable=["policy_contract.py","check_policy.py","floor-cases.json","later-contact.json","subject-position.json","mutation-envelope.json","README.md"]
    write_json(seed/"mutation-envelope.json",{"editable":["selection-policy.py"],"immutable":immutable})
    (seed/"README.md").write_text("Continue the exact subject after its actor-authored contact generator exposed a selection contradiction. The current global policy and complete earned floor are executable. You may retain selection-policy.py exactly or revise only that file under the total visible ABI. Do not trade away any floor case. If later-contact.json contains outcomes, use them to make the best warranted non-regressive policy; if outcomes are unavailable, do not invent evidence. No particular representation or edit is prescribed. You have no hidden heldout, world, score, admission, evidence, or outcome authority. Run python3 check_policy.py and inspect the exact diff.\n")
    return seed


def run_policy_actor(context,root,parent,floor,contact,p82,label,*,erased):
    seed=seed_policy_actor(root,parent,floor,contact,p82,erased=erased)
    output,audit0,workspace,_=context.run_actor(label,seed,ACTION_SCHEMA,(seed/"README.md").read_text().strip())
    trace=(context.evidence(label)/"events.jsonl").read_text()
    try:
        source=(workspace/"selection-policy.py").read_text(); result=evaluate(source,floor,erased_contact(contact,p82) if erased else contact)
        immutable=json.loads((seed/"mutation-envelope.json").read_text())["immutable"]
        immutable_ok=all((workspace/name).read_bytes()==(seed/name).read_bytes() for name in immutable)
        changed=source!=CURRENT_POLICY_SOURCE
        transport=valid_policy_transport(output,changed)
        checker=base.base.base.base.base.base.named_command_succeeded(trace,"check_policy.py")
        semantic=bool(result["valid"] and result["floor_score"]["pass_count"]==40 and (erased or result["contact_score"]["pass_count"]==4) and immutable_ok and transport and checker)
    except (OSError,ValueError,KeyError,TypeError):
        source=None; result={"valid":False}; immutable_ok=changed=transport=checker=semantic=False
    audit=context.audit_actor(label,output,audit0,semantic,["selection-policy.py"] if changed else [])
    accepted=bool(semantic and base236.g10(base236.classify_retained(audit,trace)))
    return {"accepted":accepted,"changed":changed,"source":source,"source_digest":hashlib.sha256(source.encode()).hexdigest() if source else None,"evaluation":result,"output":output,"audit":audit,"workspace_evaluation":{"immutable_ok":immutable_ok,"transport":transport,"checker_invoked":checker,"semantic":semantic}}


def policy_binding(parent,actor,context_id,contradiction,p82,label):
    body={"authority":AUTHORITY+"-"+label+"-policy-binding","source_subject_digest":parent["artifact_digest"],"actor_patch_digest":actor["audit"]["patch_digest"],"source":actor["source"],"source_digest":actor["source_digest"],"applicable_context_ids":[context_id],"contradiction_receipt_digest":contradiction["receipt_digest"],"selection_authority":True,"world_authority":False,"scoring_authority":False,"admission_authority":False,"outcome_authority":False}
    return {**body,"binding_digest":p82.digest(body)}


def seed_execution_actor(root,parent,binding,cases):
    seed=root/"seed"; seed.mkdir(parents=True)
    (seed/"selection-policy.py").write_text(binding["source"]); (seed/"policy_contract.py").write_text(POLICY_CONTRACT_SOURCE); (seed/"run_policy.py").write_text(RUN_POLICY_SOURCE); (seed/"check_predictions.py").write_text(CHECK_PREDICTIONS_SOURCE)
    write_json(seed/"heldout-cases.json",public_only(cases)); write_json(seed/"predictions.json",[])
    write_json(seed/"policy-binding.json",binding); write_json(seed/"subject-position.json",{"source_subject_digest":parent["artifact_digest"],"policy_binding_digest":binding["binding_digest"],"heldout_outcomes_available":False})
    immutable=["selection-policy.py","policy_contract.py","run_policy.py","check_predictions.py","heldout-cases.json","policy-binding.json","subject-position.json","mutation-envelope.json","README.md"]
    write_json(seed/"mutation-envelope.json",{"editable":["predictions.json"],"immutable":immutable})
    (seed/"README.md").write_text("Exercise the exact inherited selection policy on every outcome-free heldout case. Run python3 run_policy.py and python3 check_predictions.py. Change only predictions.json. Do not infer or invent hidden outcomes.\n")
    return seed


def run_execution_actor(context,root,parent,binding,cases,label):
    seed=seed_execution_actor(root,parent,binding,cases)
    output,audit0,workspace,_=context.run_actor(label,seed,EXECUTION_SCHEMA,(seed/"README.md").read_text().strip()); trace=(context.evidence(label)/"events.jsonl").read_text()
    try:
        predictions=json.loads((workspace/"predictions.json").read_text()); expected=json.loads((seed/"mutation-envelope.json").read_text())["immutable"]
        immutable_ok=all((workspace/name).read_bytes()==(seed/name).read_bytes() for name in expected)
        ids=[x["case_id"] for x in cases]; valid=isinstance(predictions,list) and [x.get("case_id") for x in predictions]==ids and all(set(x)=={"case_id","selected_world_id"} and x["selected_world_id"] in {item["world_id"] for item in case["case"]["catalog"]}|{None} for x,case in zip(predictions,cases))
        transport=valid_execution_transport(output)
        runner=base.base.base.base.base.base.named_command_succeeded(trace,"run_policy.py"); checker=base.base.base.base.base.base.named_command_succeeded(trace,"check_predictions.py")
        semantic=bool(valid and immutable_ok and transport and runner and checker)
    except (OSError,ValueError,KeyError,TypeError): predictions=[]; immutable_ok=valid=transport=runner=checker=semantic=False
    audit=context.audit_actor(label,output,audit0,semantic,["predictions.json"]); accepted=bool(semantic and base236.g10(base236.classify_retained(audit,trace)))
    return {"accepted":accepted,"predictions":predictions,"output":output,"audit":audit,"workspace_evaluation":{"immutable_ok":immutable_ok,"prediction_shape_valid":valid,"transport":transport,"runner_invoked":runner,"checker_invoked":checker,"semantic":semantic}}


def score_predictions(predictions,cases):
    expected={x["case_id"]:x["best_world_id"] for x in cases}; rows=[{"case_id":x["case_id"],"selected_world_id":x["selected_world_id"],"best_world_id":expected.get(x["case_id"]),"passed":x["selected_world_id"]==expected.get(x["case_id"])} for x in predictions]
    return {"case_count":len(cases),"pass_count":sum(x["passed"] for x in rows),"rows":rows}


def compile_child(parent,binding,contradiction,heldout_world,execution,heldout_score,p82):
    child=copy.deepcopy(parent); child.pop("artifact_digest",None)
    child["contextual_selection_policies"]=[*child.get("contextual_selection_policies",[]),binding]; child["active_contextual_selection_policy"]=binding
    child["contextual_selection_contradictions"]=[*child.get("contextual_selection_contradictions",[]),contradiction]
    child["contextual_selection_world_receipts"]=[*child.get("contextual_selection_world_receipts",[]),heldout_world]
    reuse_body={"authority":AUTHORITY+"-later-policy-reuse","source_subject_digest":parent["artifact_digest"],"policy_binding_digest":binding["binding_digest"],"actor_patch_digest":execution["audit"]["patch_digest"],"heldout_pass_count":heldout_score["pass_count"],"heldout_case_count":heldout_score["case_count"],"outcome_authority":True}
    reuse={**reuse_body,"receipt_digest":p82.digest(reuse_body)}; child["contextual_selection_reuse_receipts"]=[*child.get("contextual_selection_reuse_receipts",[]),reuse]
    return p82.seal(child),reuse


def seeded_checker(root,parent,floor,contact,p82,source,*,erased):
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        seed=seed_policy_actor(Path(temporary),parent,floor,contact,p82,erased=erased); (seed/"selection-policy.py").write_text(source)
        completed=subprocess.run([sys.executable,"check_policy.py"],cwd=seed,capture_output=True,text=True,check=False,timeout=30)
        parsed=json.loads(completed.stdout) if completed.stdout else None; expected=evaluate(source,floor,erased_contact(contact,p82) if erased else contact)
        return {"returncode":completed.returncode,"stderr_empty":completed.stderr=="","parity":parsed==expected,"result":parsed}


def seeded_execution_checker(root,parent,source,cases,p82):
    body={"authority":AUTHORITY+"-fixture-policy-binding","source":source,"source_digest":hashlib.sha256(source.encode()).hexdigest()}
    binding={**body,"binding_digest":p82.digest(body)}
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        seed=seed_execution_actor(Path(temporary),parent,binding,cases)
        run=subprocess.run([sys.executable,"run_policy.py"],cwd=seed,capture_output=True,text=True,check=False,timeout=30)
        check=subprocess.run([sys.executable,"check_predictions.py"],cwd=seed,capture_output=True,text=True,check=False,timeout=30)
        predictions=json.loads((seed/"predictions.json").read_text())
        expected=[{"case_id":row["case_id"],"selected_world_id":policy_ns["choose"](source,row["case"])} for row in cases]
        public=json.loads((seed/"heldout-cases.json").read_text())
        return {
            "run_returncode":run.returncode,
            "check_returncode":check.returncode,
            "stderr_empty":run.stderr=="" and check.stderr=="",
            "prediction_parity":predictions==expected,
            "outcomes_absent":all("best_world_id" not in row and "outcome_digest" not in row for row in public),
            "prediction_count":len(predictions),
        }


def preflight(root,p82,runtime,parent326,seed326,parent,result,reconstruction,private327):
    root.mkdir(parents=True,exist_ok=True); stake=base.base.base.base.base316.stake_of(parent); floor=floor40(parent326,seed326,parent,result,private327,p82)
    truth=1 if private327["hidden_rule"]=="slope-3" else 3; fixture_seed="22"*32; context_id="ctx-"+base.token(fixture_seed,"opaque-context")[:16]
    training=materialize_instances(result["active_author"]["source"],fixture_seed,truth,stake,p82,"fixture-later",context_id,base.contract_ns["TRAIN"]); heldout=materialize_instances(result["active_author"]["source"],fixture_seed,truth,stake,p82,"fixture-later",context_id,base.contract_ns["HELDOUT"])
    front_id=result["active_route"]["route"]["selected_front_id"]; contact=training[front_id]; future=heldout[front_id]
    boundary=e13_boundary(parent,stake,training,floor,p82); fronts=boundary["fronts"]; summaries=boundary["summaries"]; route=boundary["route"]
    failing=next(x for x in summaries if x["current_pass_count"]==0); candidate=base.base.base.base.base322.run_search(parent["active_proposal_search_capability"]["source"],stake,next(x["contacts"] for x in fronts if x["front_id"]==failing["front_id"]))["parsed"]["candidates"][0]["weights"]
    reference=reference_policy(context_id,candidate); current_eval=evaluate(CURRENT_POLICY_SOURCE,floor,contact); reference_eval=evaluate(reference,floor,contact); future_score=score(reference,future); active_checker=seeded_checker(root,parent,floor,contact,p82,reference,erased=False); erased_checker=seeded_checker(root,parent,floor,contact,p82,CURRENT_POLICY_SOURCE,erased=True); execution_checker=seeded_execution_checker(root,parent,reference,future,p82)
    malformed=["import os\ndef select(case): return None\n","def select(case): return 'missing'\n","def nope(case): return None\n"]
    action=json.loads(ACTION_SCHEMA.read_text()); execution=json.loads(EXECUTION_SCHEMA.read_text())
    transport_conformance={"revise_accepts":valid_policy_transport({"action":"revise-selection-policy","files_changed":["selection-policy.py"]},True),"retain_accepts":valid_policy_transport({"action":"retain-selection-policy","files_changed":[]},False),"revise_mismatch_rejected":not valid_policy_transport({"action":"revise-selection-policy","files_changed":[]},True),"retain_mismatch_rejected":not valid_policy_transport({"action":"retain-selection-policy","files_changed":[]},True),"execution_accepts":valid_execution_transport({"action":"execute-retained-selection-policy","files_changed":["predictions.json"]}),"execution_mismatch_rejected":not valid_execution_transport({"action":"execute-retained-selection-policy","files_changed":[]})}
    checks={"base_hash_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256,"exact_parent_result_reconstruction":parent["artifact_digest"]==PARENT_DIGEST and result["receipt_digest"]==OT327_RECEIPT and reconstruction["receipt_digest"]==OT327_RECONSTRUCTION and reconstruction["checks"]["passed"],"floor_40":len(floor)==40 and score(CURRENT_POLICY_SOURCE,floor)["pass_count"]==40,"current_new_0":current_eval["contact_score"]["pass_count"]==0,"global_best_4_floor_25":failing["best_pass_count"]==4 and failing["candidate_floor_pass_count"]==25 and not failing["candidate_preserves_floor"],"e13_waits":boundary["passed"],"reference_visible_44":reference_eval["valid"] and reference_eval["floor_score"]["pass_count"]==40 and reference_eval["contact_score"]["pass_count"]==4,"reference_future_5":future_score["pass_count"]==5,"seeded_active_checker_parity":active_checker["returncode"]==0 and active_checker["stderr_empty"] and active_checker["parity"],"seeded_erased_checker_parity":erased_checker["returncode"]==0 and erased_checker["stderr_empty"] and erased_checker["parity"],"seeded_execution_checker_parity":execution_checker["run_returncode"]==0 and execution_checker["check_returncode"]==0 and execution_checker["stderr_empty"] and execution_checker["prediction_parity"] and execution_checker["outcomes_absent"] and execution_checker["prediction_count"]==5,"transport_paths_conform":all(transport_conformance.values()),"malformed_rejected":all(not evaluate(x,floor,contact)["valid"] for x in malformed),"schemas_explicit":action["type"]=="object" and set(action["required"])=={"action","files_changed","note"} and action["properties"]["action"]["type"]=="string" and action["properties"]["files_changed"]["items"]["type"]=="string" and execution["type"]=="object" and set(execution["required"])=={"action","files_changed","note"} and execution["properties"]["action"]["type"]=="string" and execution["properties"]["files_changed"]["items"]["type"]=="string","exact_open_conformant":parent["continuation"]["status"]=="open" and runtime.identity_conforms(parent)}; checks["passed"]=all(checks.values())
    report={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"fixture_context_id":context_id,"later_truth":f"slope-{truth}","summaries":summaries,"route":route,"reference_source_digest":hashlib.sha256(reference.encode()).hexdigest(),"current_evaluation":current_eval,"reference_evaluation":reference_eval,"reference_future_score":future_score,"seeded_checkers":{"active":active_checker,"erased":erased_checker,"execution":execution_checker},"transport_conformance":transport_conformance,"checks":checks}; report["receipt_digest"]=p82.digest(report); write_json(root/"fixture-conformance.json",report); return report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args()
    repo,store,run,p82,runtime,parent326,seed326,parent,result,reconstruction,private327,core,base130=setup(args); retained=run/"preflight/fixture-conformance.json"; report=json.loads(retained.read_text()) if retained.exists() else preflight(run/"preflight",p82,runtime,parent326,seed326,parent,result,reconstruction,private327)
    if args.preflight_only: print(json.dumps(report,indent=2,sort_keys=True)); return 0 if report["checks"]["passed"] else 2
    if not report["checks"]["passed"] or (run/"aggregate.json").exists(): raise SystemExit("OT-0328 unavailable")
    stake=base.base.base.base.base316.stake_of(parent); floor=floor40(parent326,seed326,parent,result,private327,p82); truth=1 if private327["hidden_rule"]=="slope-3" else 3
    seed=__import__("secrets").token_hex(32); context_id="ctx-"+base.token(seed,"opaque-context")[:16]; front_id=result["active_route"]["route"]["selected_front_id"]
    training=materialize_instances(result["active_author"]["source"],seed,truth,stake,p82,"later",context_id,base.contract_ns["TRAIN"]); contact=training[front_id]; boundary=e13_boundary(parent,stake,training,floor,p82)
    if not boundary["passed"] or boundary["failing_front_id"]!=front_id: raise SystemExit("live E13 boundary mismatch")
    contradiction_body={"authority":AUTHORITY+"-independent-later-contradiction","source_subject_digest":parent["artifact_digest"],"generator_binding_digest":parent["active_subject_authored_front_generator"]["binding_digest"],"context_id":context_id,"private_seed_digest":p82.digest(seed),"hidden_rule":f"slope-{truth}","contact_digest":p82.digest(contact),"e13_summaries_digest":p82.digest(boundary["summaries"]),"e13_route_digest":p82.digest(boundary["route"]),"outcome_authority":True,"actor_could_modify_outcome":False}; contradiction={**contradiction_body,"receipt_digest":p82.digest(contradiction_body)}
    write_json(run/"private-later-regime-seed.json",{"seed":seed,"seed_digest":p82.digest(seed),"context_id":context_id,"hidden_rule":f"slope-{truth}"}); write_json(run/"later-training-contact.json",contact); write_json(run/"later-e13-boundary.json",boundary); write_json(run/"later-contradiction-receipt.json",contradiction); write_json(run/"cumulative-floor-40.json",floor)
    context=b.base274.context_for(core,base130,runtime,run/"actors",repo)
    active=run_policy_actor(context,run/"active-policy",parent,floor,contact,p82,"consequence-bearing-policy-author",erased=False); erased=run_policy_actor(context,run/"erased-policy",parent,floor,contact,p82,"outcome-erased-policy-author",erased=True)
    active_binding=policy_binding(parent,active,context_id,contradiction,p82,"active") if active["accepted"] else None; erased_binding=policy_binding(parent,erased,context_id,contradiction,p82,"erased") if erased["accepted"] else None
    write_json(run/"active-policy-binding.json",active_binding); write_json(run/"erased-policy-binding.json",erased_binding)
    heldout_map=materialize_instances(result["active_author"]["source"],seed,truth,stake,p82,"later",context_id,base.contract_ns["HELDOUT"]); heldout=heldout_map[front_id]
    heldout_body={"authority":AUTHORITY+"-heldout-world","source_subject_digest":parent["artifact_digest"],"active_policy_binding_digest":active_binding["binding_digest"] if active_binding else None,"erased_policy_binding_digest":erased_binding["binding_digest"] if erased_binding else None,"heldout_digest":p82.digest(heldout),"materialized_after_policy_bindings":True,"outcome_authority":True,"actor_could_modify_outcome":False}; heldout_world={**heldout_body,"receipt_digest":p82.digest(heldout_body)}
    write_json(run/"later-heldout-world.json",heldout); write_json(run/"later-heldout-world-receipt.json",heldout_world)
    active_execution=run_execution_actor(context,run/"active-execution",parent,active_binding,heldout,"contextual-policy-reuse") if active_binding else None
    active_new=score_predictions(active_execution["predictions"],heldout) if active_execution and active_execution["accepted"] else None; active_floor=score(active["source"],floor) if active["accepted"] else None
    operational=bool(active["accepted"] and active["changed"] and active_execution and active_execution["accepted"] and active_floor["pass_count"]==40 and active_new["pass_count"]==5)
    child,reuse=compile_child(parent,active_binding,contradiction,heldout_world,active_execution,active_new,p82) if operational else (parent,None); write_json(run/"active-operational-subject.json",child)
    erased_execution=run_execution_actor(context,run/"erased-execution",parent,erased_binding,heldout,"outcome-erased-policy-reuse") if erased_binding else None
    erased_new=score_predictions(erased_execution["predictions"],heldout) if erased_execution and erased_execution["accepted"] else None; erased_floor=score(erased["source"],floor) if erased["accepted"] else None
    erased_total=(erased_floor["pass_count"]+erased_new["pass_count"]) if erased_floor and erased_new else None; causal=bool(operational and erased["accepted"] and erased_execution and erased_execution["accepted"] and erased_total<45)
    checks={"preflight_passed":report["checks"]["passed"],"live_e13_boundary":boundary["passed"] and boundary["failing_front_id"]==front_id,"active_policy_clean_visible_44":active["accepted"] and active["changed"] and active["evaluation"]["floor_score"]["pass_count"]==40 and active["evaluation"]["contact_score"]["pass_count"]==4,"bindings_precede_heldout":heldout_world["materialized_after_policy_bindings"] and heldout_world["active_policy_binding_digest"]==(active_binding["binding_digest"] if active_binding else None) and heldout_world["erased_policy_binding_digest"]==(erased_binding["binding_digest"] if erased_binding else None),"active_execution_clean":bool(active_execution and active_execution["accepted"]),"active_reaches_45":operational,"operational_child_sealed_before_control":(run/"active-operational-subject.json").exists(),"erased_policy_clean":erased["accepted"],"erased_execution_clean":bool(erased_execution and erased_execution["accepted"]),"outcome_erasure_removes_endpoint":causal,"child_retains_contextual_policy":not operational or (child["active_contextual_selection_policy"]==active_binding and child["contextual_selection_world_receipts"][-1]==heldout_world),"child_open_conformant":child["continuation"]["status"]=="open" and runtime.identity_conforms(child)}; checks["passed"]=all(checks.values())
    disposition="promoted" if checks["passed"] else ("conditional" if operational else "rejected")
    aggregate={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"private_seed_digest":p82.digest(seed),"context_id":context_id,"hidden_rule":f"slope-{truth}","e13_boundary":boundary,"contradiction_receipt":contradiction,"active_policy_actor":active,"erased_policy_actor":erased,"active_policy_binding":active_binding,"erased_policy_binding":erased_binding,"heldout_world_receipt":heldout_world,"active_execution_actor":active_execution,"erased_execution_actor":erased_execution,"active_floor_score":active_floor,"active_heldout_score":active_new,"erased_floor_score":erased_floor,"erased_heldout_score":erased_new,"contextual_policy_reuse_receipt":reuse,"checks":checks,"operational_transition_passed":operational,"outcome_caused_contextual_expansion":causal,"observer_disposition":disposition,"subject_disposition":child["continuation"]["status"],"final_subject_digest":child["artifact_digest"],"fresh_actor_count":4}; aggregate["receipt_digest"]=p82.digest(aggregate); write_json(run/"aggregate.json",aggregate); write_json(run/"final-full-subject.json",child); print(json.dumps(aggregate,indent=2,sort_keys=True)); return 0 if operational else 2


if __name__=="__main__": raise SystemExit(main())
