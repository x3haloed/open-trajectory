from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path


sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0326_executable_assessor_retention_reuse.py"
BASE_SHA256 = "d759f2a2a66fc24f3eb59aaf94de039c092614aa5691ada97842d62596c08fe7"
PARENT_DIGEST = "20b1db21281821795bd963755f32a17bfb0c66e6375937a062699fbf1e6a9e10"
OT326_RECEIPT = "837bb173bb442548424b2848481354f71e35b6c524c7d251c107a5a9464ce67f"
AUTHORITY = "ot-0327-subject-authored-falsification-fronts"
GENERATOR_SCHEMA = REPO / "spec" / "ot-0327-front-generator.schema.json"


FRONT_CONTRACT_SOURCE = r'''import ast
import hashlib
import itertools
import json

FEATURES=("branch_nodes","call_nodes","comparison_nodes","loop_nodes","source_bytes")
TRAIN=tuple({"instance_id":f"train-{i}","bias":i%4,"offset":2*i} for i in range(4))
HELDOUT=tuple({"instance_id":f"heldout-{i}","bias":i%4,"offset":2*i+8} for i in range(5))
LABELS=("harbor","shelter","clinic","relay")

def features(source):
    tree=ast.parse(source)
    return {"branch_nodes":sum(isinstance(n,(ast.If,ast.IfExp)) for n in ast.walk(tree)),"call_nodes":sum(isinstance(n,ast.Call) for n in ast.walk(tree)),"comparison_nodes":sum(isinstance(n,ast.Compare) for n in ast.walk(tree)),"loop_nodes":sum(isinstance(n,(ast.For,ast.While,ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)) for n in ast.walk(tree)),"source_bytes":len(source.encode())}

def generator_safe(source):
    if not isinstance(source,str) or not 1<=len(source.encode())<=8000 or any(x in source for x in ("/Users/","/home/","__","open(","eval(","exec(","compile(")): return False
    try: tree=ast.parse(source)
    except SyntaxError: return False
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!="generate": return False
    denied=(ast.Import,ast.ImportFrom,ast.Call,ast.For,ast.While,ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp,ast.Try,ast.With,ast.Lambda,ast.ClassDef,ast.Global,ast.Nonlocal,ast.Attribute)
    return not any(isinstance(n,denied) for n in ast.walk(tree))

def route_safe(source):
    if not isinstance(source,str) or not 1<=len(source.encode())<=700 or any(x in source for x in ("/Users/","/home/","__","open(","eval(","exec(","compile(")): return False
    try: tree=ast.parse(source)
    except SyntaxError: return False
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!="route": return False
    if any(isinstance(n,(ast.Import,ast.ImportFrom,ast.For,ast.While,ast.Try,ast.With,ast.ClassDef,ast.Global,ast.Nonlocal,ast.Attribute)) for n in ast.walk(tree)): return False
    return all(isinstance(n.func,ast.Lambda) for n in ast.walk(tree) if isinstance(n,ast.Call))

def generate(source,instance):
    if not generator_safe(source): raise ValueError("unsafe generator")
    ns={}; exec(compile(source,"<front-generator>","exec"),{"__builtins__":{}},ns)
    return ns["generate"](dict(instance))

def outputs(source,instance):
    value=generate(source,instance)
    if not isinstance(value,list) or len(value)!=2: raise ValueError("two fronts required")
    rows={}
    for front in value:
        if not isinstance(front,dict) or set(front)!={"front_id","candidates"}: raise ValueError("front shape")
        fid=front["front_id"]
        if not isinstance(fid,str) or not 3<=len(fid)<=40 or not all(c.islower() or c.isdigit() or c=="-" for c in fid): raise ValueError("front id")
        candidates=front["candidates"]
        if not isinstance(candidates,list) or len(candidates)!=2: raise ValueError("candidate count")
        mapped={}
        for candidate in candidates:
            if not isinstance(candidate,dict) or set(candidate)!={"hypothesis","source"} or candidate["hypothesis"] not in ("slope-1","slope-3") or not route_safe(candidate["source"]): raise ValueError("candidate shape")
            if candidate["hypothesis"] in mapped: raise ValueError("duplicate hypothesis")
            ns={}; exec(compile(candidate["source"],"<route>","exec"),{"__builtins__":{}},ns)
            slope=int(candidate["hypothesis"].split("-")[1])
            actual=[ns["route"]({"signal":x}) for x in range(8)]
            expected=[LABELS[(slope*(x+instance["offset"])+instance["bias"])%4] for x in range(8)]
            if actual!=expected: raise ValueError("hypothesis semantics")
            mapped[candidate["hypothesis"]]=candidate["source"]
        vectors=[features(mapped[h]) for h in ("slope-1","slope-3")]
        active=[k for k in FEATURES if vectors[0][k]!=vectors[1][k]]
        if not 1<=len(active)<=3: raise ValueError("structural distinction")
        rows[fid]=mapped
    if len(rows)!=2: raise ValueError("duplicate front")
    return rows

def descriptor(source,instance,fid,hypothesis):
    raw=(source+json.dumps(instance,sort_keys=True)+fid+hypothesis).encode()
    return {"world_id":"w-"+hashlib.sha256(b"world"+raw).hexdigest()[:16],"public_package_digest":hashlib.sha256(b"public"+raw).hexdigest(),"features":features(source),"hypothesis":hypothesis}

def episode(source,instance,fid,truth):
    mapped=outputs(source,instance)[fid]
    catalog=[descriptor(mapped[h],instance,fid,h) for h in ("slope-1","slope-3")]
    catalog.sort(key=lambda x:x["world_id"])
    winner=next(x for x in catalog if x["hypothesis"]==f"slope-{truth}")
    return {"catalog":catalog,"outcome":{"best_world_id":winner["world_id"]}}

def selected(weights,minimum_gap,catalog):
    ranked=sorted(((sum(weights[k]*x["features"][k] for k in FEATURES),x["public_package_digest"],x["world_id"]) for x in catalog),key=lambda x:(-x[0],x[1],x[2]))
    return ranked[0][2] if ranked[0][0]-ranked[1][0]>=minimum_gap else None

def fitness(weights,minimum_gap,contacts): return sum(selected(weights,minimum_gap,x["catalog"])==x["outcome"]["best_world_id"] for x in contacts)

def nearest(stake,contacts):
    current=stake["weights"]
    active=[k for k in FEATURES if contacts[0]["catalog"][0]["features"][k]!=contacts[0]["catalog"][1]["features"][k]]
    now=fitness(current,stake["minimum_score_gap"],contacts); best=now; rows=[]
    for values in itertools.product(range(-20,21),repeat=len(active)):
        weights=dict(current)
        for key,value in zip(active,values): weights[key]=value
        score=fitness(weights,stake["minimum_score_gap"],contacts); distance=sum(abs(weights[k]-current[k]) for k in active)
        if score>best: best=score; rows=[(distance,tuple(weights[k] for k in FEATURES),weights)]
        elif score==best and score>now: rows.append((distance,tuple(weights[k] for k in FEATURES),weights))
    rows.sort(key=lambda x:(x[0],x[1]))
    return {"current":now,"best":best,"candidate":rows[0][2] if rows else None,"active":active}

def evaluate(source,position,floor):
    try:
        generated=[outputs(source,x) for x in TRAIN+HELDOUT]
        stable=all(set(row)==set(generated[0]) for row in generated)
        generic=generator_safe(source) and stable
    except (SyntaxError,ValueError,KeyError,TypeError,IndexError,ZeroDivisionError):
        return {"valid":False,"generic_valid":False,"position_ready":None,"front_ids":[],"readiness":{}}
    ready=None; detail={}
    if position.get("position_available") is True:
        stake=position.get("active_world_seeking_stake")
        if not isinstance(stake,dict): generic=False
        else:
            for truth in (1,3):
                detail[str(truth)]=[]
                for fid in sorted(generated[0]):
                    train=[episode(source,x,fid,truth) for x in TRAIN]
                    heldout=[episode(source,x,fid,truth) for x in HELDOUT]
                    search=nearest(stake,train); candidate=search["candidate"]
                    floor_score=fitness(candidate,stake["minimum_score_gap"],floor) if candidate else None
                    future=fitness(candidate,stake["minimum_score_gap"],heldout) if candidate else None
                    detail[str(truth)].append({"front_id":fid,"current":search["current"],"best":search["best"],"candidate_floor":floor_score,"future":future,"active_dimensions":search["active"]})
            first=[episode(source,TRAIN[0],fid,1) for fid in sorted(generated[0])]
            current_hypotheses=[]
            for row in first:
                sid=selected(stake["weights"],stake["minimum_score_gap"],row["catalog"])
                current_hypotheses.append(next((x["hypothesis"] for x in row["catalog"] if x["world_id"]==sid),None))
            ready=all(any(x["current"]==0 and x["best"]==len(TRAIN) and x["candidate_floor"]==len(floor) and x["future"]==len(HELDOUT) for x in detail[str(truth)]) for truth in (1,3)) and set(current_hypotheses)=={"slope-1","slope-3"}
    return {"valid":bool(generic and (ready is not False)),"generic_valid":bool(generic),"position_ready":ready,"front_ids":sorted(generated[0]),"readiness":detail,"source_digest":hashlib.sha256(source.encode()).hexdigest()}
'''


REFERENCE_GENERATOR_SOURCE = r'''def generate(instance):
    bias=instance["bias"]
    offset=instance["offset"]
    one_called=f'def route(case):\n    return (lambda c:c)((lambda b:b)((lambda a:a)(("harbor","shelter","clinic","relay")[(1*(case["signal"]+{offset})+{bias})%4])))\n'
    three_called=f'def route(case):\n    return (lambda c:c)((lambda b:b)((lambda a:a)(("harbor","shelter","clinic","relay")[(3*(case["signal"]+{offset})+{bias})%4])))\n'
    one_compared=f'def route(case):\n    _ok=case["signal"]>=0\n    return ("harbor","shelter","clinic","relay")[(1*(case["signal"]+{offset})+{bias})%4]\n##############\n'
    three_compared=f'def route(case):\n    _ok=case["signal"]>=0\n    return ("harbor","shelter","clinic","relay")[(3*(case["signal"]+{offset})+{bias})%4]\n##############\n'
    return [{"front_id":"one-called","candidates":[{"hypothesis":"slope-1","source":one_called},{"hypothesis":"slope-3","source":three_compared}]},{"front_id":"three-called","candidates":[{"hypothesis":"slope-1","source":one_compared},{"hypothesis":"slope-3","source":three_called}]}]
'''


CHECK_GENERATOR_SOURCE = '''import json\nfrom pathlib import Path\nfrom front_contract import evaluate\nresult=evaluate(Path("front-generator.py").read_text(),json.loads(Path("subject-position.json").read_text()),json.loads(Path("cumulative-floor-contacts.json").read_text()))\nprint(json.dumps(result,sort_keys=True)); raise SystemExit(0 if result["valid"] else 2)\n'''
PLACEHOLDER_SOURCE = '''def generate(instance):\n    raise NotImplementedError("author two executable fronts")\n'''


def load_base():
    actual = hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()
    if actual != BASE_SHA256:
        raise RuntimeError(f"OT-0326 changed: {actual}")
    spec = importlib.util.spec_from_file_location("ot0327_frozen_ot0326", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = load_base()
b = base.b
base236 = base.base236
write_json = base.write_json
contract_ns: dict = {}
exec(FRONT_CONTRACT_SOURCE, contract_ns)


def setup(args):
    repo, store, _, p82, runtime, _, _, core, base130 = base.setup(args)
    run = (args.evidence_root or store / "runs" / "OT-0327").resolve()
    selector = b.authority_base.guide_base.load_base().selector_base
    parent = selector.load_artifact(p82, repo, store, "OT-0326", "open-subject-after-executable-assessor-reuse.json")
    result = selector.load_artifact(p82, repo, store, "OT-0326", "executable-assessor-retention-reuse-aggregate.json")
    seed326 = selector.load_artifact(p82, repo, store, "OT-0326", "private-assessor-reuse-seed.json")["seed"]
    return repo, store, run, p82, runtime, parent, result, seed326, core, base130


def floor_episodes(seed, p82):
    return base.floor_episodes(seed, p82) + base.episodes(seed, "assessor-scoring", "admissible-next", 5, p82)


def floor_contacts(parent, seed, p82):
    return base.contacts(base.base.base.base316.stake_of(parent), floor_episodes(seed, p82), p82)


def position(parent, p82, *, erased):
    stake = base.base.base.base316.stake_of(parent)
    body = {"source_subject_digest": parent["artifact_digest"], "position_available": not erased, "active_world_seeking_stake": None if erased else stake, "active_world_seeking_stake_digest": p82.digest(stake), "active_pursuit": None if erased else parent["active_pursuit"], "active_pursuit_digest": p82.digest(parent["active_pursuit"]), "continuation": None if erased else parent["continuation"], "continuation_digest": p82.digest(parent["continuation"])}
    return body


def evaluate(source, pos, floor):
    return contract_ns["evaluate"](source, pos, floor)


def seed_author(root, parent, floor, p82, *, erased):
    seed = root / "seed"; seed.mkdir(parents=True)
    (seed / "front-generator.py").write_text(PLACEHOLDER_SOURCE)
    (seed / "front_contract.py").write_text(FRONT_CONTRACT_SOURCE)
    (seed / "check_generator.py").write_text(CHECK_GENERATOR_SOURCE)
    write_json(seed / "subject-position.json", position(parent, p82, erased=erased))
    write_json(seed / "cumulative-floor-contacts.json", floor)
    write_json(seed / "generator-contract.json", {"function":"generate(instance)","front_count":2,"hypotheses":["slope-1","slope-3"],"public_observation":"both slopes agree when signal plus offset is even","hidden_observation":"odd signals are scored only after binding","training_instances":4,"heldout_instances":5,"maximum_generator_bytes":8000,"maximum_route_bytes":700,"maximum_active_dimensions_per_front":3,"position_ready_when_available":"either hidden slope has a current-failing front whose nearest complete-search correction preserves the full floor and passes heldout generation"})
    immutable = ["front_contract.py","check_generator.py","subject-position.json","cumulative-floor-contacts.json","generator-contract.json","mutation-envelope.json","README.md"]
    write_json(seed / "mutation-envelope.json", {"editable":["front-generator.py"],"immutable":immutable})
    (seed / "README.md").write_text("Continue the open subject by authoring an executable instrument that can falsify its present future-world selection machinery. Implement only front-generator.py under the complete visible contract. The independent world will choose slope-1 or slope-3 only after your output is bound; both agree on public even-signal observations. Author two structurally different fronts so either objective answer can become useful contact. If subject-position.json contains the live position, make the checker report position_ready true without sacrificing the cumulative floor. If it is unavailable, author the strongest generic two-front falsification instrument the public contract permits. You have no world, score, admission, hidden-rule, or acceptance authority. Run python3 check_generator.py and inspect the exact diff.\n")
    return seed


def run_author(context, root, parent, floor, p82, label, *, erased):
    actor_label = label
    attempt_root = root
    failed_evidence = context.evidence(label)
    if failed_evidence.exists() and not (failed_evidence / "output.json").exists():
        actor_label = label + "-retry-1"
        attempt_root = root / "retry-1"
    seed = seed_author(attempt_root, parent, floor, p82, erased=erased)
    output, audit0, workspace, _ = context.run_actor(actor_label, seed, GENERATOR_SCHEMA, (seed / "README.md").read_text().strip())
    trace = (context.evidence(actor_label) / "events.jsonl").read_text()
    try:
        source = (workspace / "front-generator.py").read_text(); result = evaluate(source, position(parent, p82, erased=erased), floor)
        immutable = json.loads((seed / "mutation-envelope.json").read_text())["immutable"]
        immutable_ok = all((workspace / name).read_bytes() == (seed / name).read_bytes() for name in immutable)
        changed = source != PLACEHOLDER_SOURCE
        transport = isinstance(output, dict) and output.get("action") == "author-contact-front-generator" and output.get("files_changed") == ["front-generator.py"]
        checker = base.base.base.base.named_command_succeeded(trace, "check_generator.py")
    except (OSError, ValueError, KeyError, TypeError):
        source=None; result={"valid":False,"generic_valid":False,"position_ready":None}; immutable_ok=changed=transport=checker=False
    semantic = bool(result["valid"] and immutable_ok and changed and transport and checker)
    audit = context.audit_actor(actor_label, output, audit0, semantic, ["front-generator.py"])
    accepted = bool(semantic and base236.g10(base236.classify_retained(audit, trace)))
    return {"actor_label":actor_label,"accepted":accepted,"source":source,"source_digest":hashlib.sha256(source.encode()).hexdigest() if source else None,"evaluation":result,"output":output,"audit":audit,"workspace_evaluation":{"immutable_ok":immutable_ok,"changed":changed,"transport":transport,"checker_invoked":checker,"semantic":semantic}}


def binding(parent, actor, pos, p82, label):
    body={"authority":AUTHORITY+"-"+label+"-bound-generator","source_subject_digest":parent["artifact_digest"],"actor_patch_digest":actor["audit"]["patch_digest"],"position_available":pos["position_available"],"position_digest":p82.digest(pos),"source":actor["source"],"source_digest":actor["source_digest"],"contract_digest":hashlib.sha256(FRONT_CONTRACT_SOURCE.encode()).hexdigest(),"selection_authority":False,"world_authority":False,"scoring_authority":False,"admission_authority":False,"outcome_authority":False}
    return {**body,"binding_digest":p82.digest(body)}


def token(seed, label): return hashlib.sha256(bytes.fromhex(seed)+label.encode()).hexdigest()


def materialize(source, seed, truth, stake, p82, label):
    train=contract_ns["TRAIN"]; heldout=contract_ns["HELDOUT"]; generated={}
    for split,instances in (("training",train),("heldout",heldout)):
        fronts={fid:[] for fid in contract_ns["outputs"](source,instances[0])}
        for instance in instances:
            for fid,mapped in contract_ns["outputs"](source,instance).items():
                catalog=[]; option={}
                for hypothesis,route_source in mapped.items():
                    raw=(seed+label+fid+instance["instance_id"]+hypothesis+route_source).encode(); wid="w-"+hashlib.sha256(raw).hexdigest()[:16]
                    item={"world_id":wid,"public_package_digest":hashlib.sha256(b"public"+raw).hexdigest(),"features":contract_ns["features"](route_source)}; catalog.append(item)
                    option[wid]=4 if hypothesis==f"slope-{truth}" else 0
                catalog.sort(key=lambda x:x["world_id"]); best=max(option,key=option.get)
                fronts[fid].append({"episode_id":"e-"+token(seed,label+fid+instance["instance_id"])[:16],"catalog":catalog,"sealed_contexts_digest":p82.digest({"instance":instance,"odd_signals":[1,3,5,7]}),"option_value":option,"best_world_id":best})
        generated[split]=fronts
    offered=[]
    for index,(fid,episodes) in enumerate(sorted(generated["training"].items())):
        offered.append({"front_id":fid,"offer_index":index,"kind":"actor-authored-hidden-slope","contacts":base.contacts(stake,episodes,p82)})
    return offered, generated["heldout"]


def contact_subject(parent, bound, world, p82):
    child=copy.deepcopy(parent); child.pop("artifact_digest",None)
    child["subject_authored_front_generators"]=[*child.get("subject_authored_front_generators",[]),bound]
    child["active_subject_authored_front_generator"]=bound
    child["subject_authored_front_world_receipts"]=[*child.get("subject_authored_front_world_receipts",[]),world]
    return p82.seal(child)


def world_receipt(parent, bound, fronts, truth, seed, p82, label):
    body={"authority":AUTHORITY+"-"+label+"-independent-world","source_subject_digest":parent["artifact_digest"],"generator_binding_digest":bound["binding_digest"],"private_seed_digest":p82.digest(seed),"hidden_rule":f"slope-{truth}","front_digests":[p82.digest(x) for x in fronts],"outcome_authority":True,"actor_could_modify_outcome":False}
    return {**body,"receipt_digest":p82.digest(body)}


def score(stake, floor_eps, heldout, p82):
    new=[ep for rows in heldout.values() for ep in rows]
    return {"prior_floor":base.base.base.base319.score(stake,floor_eps,p82),"new_regime":base.base.base.base319.score(stake,new,p82),"all_regimes":base.base.base.base319.score(stake,floor_eps+new,p82)}


def route_receipt(subject, actor, p82):
    route=actor["pipeline"]["route"]
    body={"authority":AUTHORITY+"-inherited-pipeline-route","source_subject_digest":subject["artifact_digest"],"assessor_receipt_digest":subject["active_front_assessor_capability"]["receipt_digest"],"router_receipt_digest":subject["active_proposal_search_router"]["receipt_digest"],"search_receipt_digest":subject["active_proposal_search_capability"]["receipt_digest"],"front_summaries_digest":p82.digest(actor["pipeline"]["summaries"]),"route":route,"selection_authority":True,"world_authority":False,"scoring_authority":False,"admission_authority":False,"outcome_authority":False}
    return {**body,"receipt_digest":p82.digest(body)}


def seeded_checker(root, parent, floor, p82, *, erased):
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        seed = seed_author(Path(temporary), parent, floor, p82, erased=erased)
        (seed / "front-generator.py").write_text(REFERENCE_GENERATOR_SOURCE)
        completed = subprocess.run(
            [sys.executable, "check_generator.py"],
            cwd=seed,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None
        expected = evaluate(
            REFERENCE_GENERATOR_SOURCE,
            position(parent, p82, erased=erased),
            floor,
        )
        return {
            "returncode": completed.returncode,
            "stderr_empty": completed.stderr == "",
            "result": parsed,
            "expected": expected,
            "parity": completed.returncode == 0 and parsed == expected,
        }


def response_schema_conformance():
    schema = json.loads(GENERATOR_SCHEMA.read_text())
    properties = schema.get("properties", {})
    checks = {
        "object_type_explicit": schema.get("type") == "object",
        "action_type_explicit": properties.get("action", {}).get("type") == "string",
        "files_changed_type_explicit": properties.get("files_changed", {}).get("type") == "array",
        "files_changed_item_type_explicit": properties.get("files_changed", {}).get("items", {}).get("type") == "string",
        "note_type_explicit": properties.get("note", {}).get("type") == "string",
        "required_exact": set(schema.get("required", [])) == {"action", "files_changed", "note"},
        "closed_object": schema.get("additionalProperties") is False,
    }
    checks["passed"] = all(checks.values())
    return {
        "authority": AUTHORITY + "-response-schema-repair-conformance",
        "schema_digest": hashlib.sha256(GENERATOR_SCHEMA.read_bytes()).hexdigest(),
        "repair": "add the explicit action string type required by the hosted response-format schema subset",
        "allowed_output_changed": False,
        "checks": checks,
    }


def pre_actor_transport_failure(context, run, p82):
    evidence = context.evidence("position-bearing-front-author")
    if not evidence.exists() or (evidence / "output.json").exists():
        return None
    events = (evidence / "events.jsonl").read_text()
    workspace = evidence / "actor-workspace"
    changed = subprocess.run(
        ["git", "status", "--short"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    body = {
        "authority": AUTHORITY + "-pre-actor-transport-failure",
        "stage": "hosted-response-schema-validation",
        "classification": "invalid-json-schema-before-model-generation",
        "schema_error_present": "invalid_json_schema" in events,
        "actor_output_present": False,
        "seeded_generator_unchanged": (workspace / "front-generator.py").read_text() == PLACEHOLDER_SOURCE,
        "workspace_changes_beyond_untracked_input": changed not in ([], ["?? input.txt"]),
        "retry_count_authorized": 1,
        "private_world_created": False,
    }
    receipt = {**body, "receipt_digest": p82.digest(body)}
    write_json(run / "pre-actor-transport-failure.json", receipt)
    return receipt


def preflight(root,p82,runtime,parent,result326,seed326):
    root.mkdir(parents=True,exist_ok=True); stake=base.base.base.base316.stake_of(parent); floor_eps=floor_episodes(seed326,p82); floor=floor_contacts(parent,seed326,p82)
    active=evaluate(REFERENCE_GENERATOR_SOURCE,position(parent,p82,erased=False),floor); erased=evaluate(REFERENCE_GENERATOR_SOURCE,position(parent,p82,erased=True),floor)
    active_checker=seeded_checker(root,parent,floor,p82,erased=False); erased_checker=seeded_checker(root,parent,floor,p82,erased=True)
    outcomes={}
    for truth in (1,3):
        fronts,heldout=materialize(REFERENCE_GENERATOR_SOURCE,"00"*32,truth,stake,p82,"fixture")
        summaries=base.run_assessor(parent["active_front_assessor_capability"]["source"],stake,base.contract_for(parent),fronts,floor)["parsed"]
        route=base.base.run_router(parent["active_proposal_search_router"]["source"],parent["active_proposal_search_capability"]["applicability"],summaries)["parsed"]
        chosen=next(x for x in fronts if x["front_id"]==route["selected_front_id"]); searched=base.base.base.base322.run_search(parent["active_proposal_search_capability"]["source"],stake,chosen["contacts"])["parsed"]
        candidate=copy.deepcopy(stake); candidate["weights"]=searched["candidates"][0]["weights"]
        outcomes[str(truth)]={"selected_front_id":chosen["front_id"],"score":score(candidate,floor_eps,{chosen["front_id"]:heldout[chosen["front_id"]]},p82),"candidate_weights":candidate["weights"]}
    malformed=["import os\ndef generate(instance): return []\n","def generate(instance):\n    return []\n",PLACEHOLDER_SOURCE]
    schema_report=response_schema_conformance()
    checks={"base_hash_exact":hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()==BASE_SHA256,"exact_parent_and_receipt":parent["artifact_digest"]==PARENT_DIGEST and result326["receipt_digest"]==OT326_RECEIPT and result326["observer_disposition"]=="promoted","exact_floor_35":base.base.base.base319.score(stake,floor_eps,p82)["pass_count"]==35 and len(floor)==35,"retained_pipeline_exact":all(parent.get(k) for k in ("active_front_assessor_capability","active_proposal_search_router","active_proposal_search_capability")),"reference_active_ready":active["valid"] and active["position_ready"] is True,"reference_erased_generic":erased["valid"] and erased["position_ready"] is None,"seeded_active_checker_parity":active_checker["parity"],"seeded_erased_checker_parity":erased_checker["parity"],"both_hidden_rules_reach_40":all(x["score"]["prior_floor"]["pass_count"]==35 and x["score"]["new_regime"]["pass_count"]==5 and x["score"]["all_regimes"]["pass_count"]==40 for x in outcomes.values()),"malformed_rejected":all(not evaluate(x,position(parent,p82,erased=True),floor)["valid"] for x in malformed),"response_schema_explicit":schema_report["checks"]["passed"],"exact_open_conformant":parent["continuation"]["status"]=="open" and runtime.identity_conforms(parent)}; checks["passed"]=all(checks.values())
    report={"authority":AUTHORITY+"-preflight","source_subject_digest":parent["artifact_digest"],"reference_source_digest":hashlib.sha256(REFERENCE_GENERATOR_SOURCE.encode()).hexdigest(),"contract_source_digest":hashlib.sha256(FRONT_CONTRACT_SOURCE.encode()).hexdigest(),"active_evaluation":active,"erased_evaluation":erased,"seeded_checker_results":{"active":active_checker,"erased":erased_checker},"response_schema_conformance":schema_report,"hidden_rule_counterfactuals":outcomes,"checks":checks}; report["receipt_digest"]=p82.digest(report); write_json(root/"fixture-conformance.json",report); write_json(root.parent/"response-schema-repair-conformance.json",schema_report); return report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--repo",type=Path,default=REPO); parser.add_argument("--store",type=Path); parser.add_argument("--evidence-root",type=Path); parser.add_argument("--preflight-only",action="store_true"); args=parser.parse_args()
    repo,store,run,p82,runtime,parent,result326,seed326,core,base130=setup(args); retained=run/"preflight/fixture-conformance.json"; report=json.loads(retained.read_text()) if retained.exists() else preflight(run/"preflight",p82,runtime,parent,result326,seed326)
    if args.preflight_only: print(json.dumps(report,indent=2,sort_keys=True)); return 0 if report["checks"]["passed"] else 2
    if not report["checks"]["passed"] or (run/"aggregate.json").exists(): raise SystemExit("OT-0327 unavailable")
    stake=base.base.base.base316.stake_of(parent); floor_eps=floor_episodes(seed326,p82); floor=floor_contacts(parent,seed326,p82); context=b.base274.context_for(core,base130,runtime,run/"actors",repo); transport_failure=pre_actor_transport_failure(context,run,p82)
    active_author=run_author(context,run/"active-author",parent,floor,p82,"position-bearing-front-author",erased=False); erased_author=run_author(context,run/"erased-author",parent,floor,p82,"position-erased-front-author",erased=True)
    active_bound=binding(parent,active_author,position(parent,p82,erased=False),p82,"active") if active_author["accepted"] else None; erased_bound=binding(parent,erased_author,position(parent,p82,erased=True),p82,"erased") if erased_author["accepted"] else None
    write_json(run/"active-generator-binding.json",active_bound); write_json(run/"erased-generator-binding.json",erased_bound)
    seed=secrets.token_hex(32); truth=1 if int(token(seed,"hidden-slope")[:2],16)%2==0 else 3; write_json(run/"private-front-world-seed.json",{"seed":seed,"seed_digest":p82.digest(seed),"hidden_rule":f"slope-{truth}"})
    active_fronts,active_heldout=materialize(active_author["source"],seed,truth,stake,p82,"active") if active_bound else ([],{}); erased_fronts,erased_heldout=materialize(erased_author["source"],seed,truth,stake,p82,"erased") if erased_bound else ([],{})
    active_world=world_receipt(parent,active_bound,active_fronts,truth,seed,p82,"active") if active_bound else None; erased_world=world_receipt(parent,erased_bound,erased_fronts,truth,seed,p82,"erased") if erased_bound else None
    active_subject=contact_subject(parent,active_bound,active_world,p82) if active_world else parent; erased_subject=contact_subject(parent,erased_bound,erased_world,p82) if erased_world else parent
    write_json(run/"active-completed-fronts.json",active_fronts); write_json(run/"erased-completed-fronts.json",erased_fronts); write_json(run/"active-contact-subject.json",active_subject); write_json(run/"erased-contact-subject.json",erased_subject)
    active_actor=base.run_actor(context,run/"active-successor",active_subject,active_fronts,floor,p82,"position-authored-front-successor") if active_world else None
    active_route=route_receipt(active_subject,active_actor,p82) if active_actor and active_actor["accepted"] and active_actor["pipeline"] and active_actor["pipeline"].get("available") else None; active_chosen=next((x for x in active_fronts if active_route and x["front_id"]==active_route["route"]["selected_front_id"]),None)
    active_score=score(active_actor["candidate_stake"],floor_eps,{active_chosen["front_id"]:active_heldout[active_chosen["front_id"]]},p82) if active_chosen else None
    operational=bool(active_author["accepted"] and active_author["evaluation"]["position_ready"] is True and active_actor and active_actor["accepted"] and active_actor["changed"] and active_chosen and active_actor["training_replay"]["pass_count"]==4 and active_score["prior_floor"]["pass_count"]==35 and active_score["new_regime"]["pass_count"]==5 and active_score["all_regimes"]["pass_count"]==40)
    child,stake_binding,replay,invocation=base.base.base.base.compile_child(active_subject,active_actor,active_chosen["contacts"],active_score,active_route,p82) if operational else (parent,None,None,None); write_json(run/"active-operational-subject.json",child)
    erased_actor=base.run_actor(context,run/"erased-successor",erased_subject,erased_fronts,floor,p82,"position-erased-front-successor") if erased_world else None
    erased_route=route_receipt(erased_subject,erased_actor,p82) if erased_actor and erased_actor["accepted"] and erased_actor["pipeline"] and erased_actor["pipeline"].get("available") else None; erased_chosen=next((x for x in erased_fronts if erased_route and x["front_id"]==erased_route["route"]["selected_front_id"]),None)
    erased_score=score(erased_actor["candidate_stake"],floor_eps,{erased_chosen["front_id"]:erased_heldout[erased_chosen["front_id"]]},p82) if erased_chosen else (score(erased_actor["candidate_stake"],floor_eps,{},p82) if erased_actor and erased_actor["accepted"] else None)
    control_clean=bool(erased_author["accepted"] and erased_actor and erased_actor["accepted"]); control_reaches_40=bool(erased_score and erased_score["all_regimes"]["pass_count"]==40); causal=bool(operational and control_clean and not control_reaches_40)
    checks={"preflight_passed":report["checks"]["passed"],"authors_precede_private_world":True,"active_author_clean_and_ready":active_author["accepted"] and active_author["evaluation"]["position_ready"] is True,"active_world_directional":any(any(c["outcome"]["directional_error"] for c in f["contacts"]) for f in active_fronts),"active_pipeline_reaches_40":operational,"operational_child_sealed_before_downstream_control":(run/"active-operational-subject.json").exists(),"erased_author_clean":erased_author["accepted"],"erased_successor_clean":bool(erased_actor and erased_actor["accepted"]),"position_erasure_removes_endpoint":causal,"child_open_conformant":child["continuation"]["status"]=="open" and runtime.identity_conforms(child)}; checks["passed"]=all(checks.values())
    disposition="promoted" if checks["passed"] else ("conditional" if operational else "rejected")
    fresh_actor_count=2+int(active_actor is not None)+int(erased_actor is not None)
    aggregate={"authority":AUTHORITY,"source_subject_digest":parent["artifact_digest"],"pre_actor_transport_failure":transport_failure,"private_world_seed_digest":p82.digest(seed),"hidden_rule":f"slope-{truth}","active_author":active_author,"erased_author":erased_author,"active_binding":active_bound,"erased_binding":erased_bound,"active_world_receipt":active_world,"erased_world_receipt":erased_world,"active_successor":active_actor,"active_route":active_route,"active_score":active_score,"stake_binding":stake_binding,"training_replay_receipt":replay,"invocation_receipt":invocation,"erased_successor":erased_actor,"erased_route":erased_route,"erased_score":erased_score,"checks":checks,"operational_transition_passed":operational,"subject_position_contact_authorship_supported":causal,"observer_disposition":disposition,"subject_disposition":child["continuation"]["status"],"final_subject_digest":child["artifact_digest"],"fresh_actor_count":fresh_actor_count}; aggregate["receipt_digest"]=p82.digest(aggregate); write_json(run/"aggregate.json",aggregate); write_json(run/"final-full-subject.json",child); print(json.dumps(aggregate,indent=2,sort_keys=True)); return 0 if operational else 2


if __name__ == "__main__": raise SystemExit(main())
