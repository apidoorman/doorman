from __future__ import annotations

import os
import uuid
import random
import string
from datetime import datetime, timedelta

from utils import password_util
from utils.database import (
    api_collection,
    endpoint_collection,
    group_collection,
    role_collection,
    subscriptions_collection,
    token_def_collection,
    user_token_collection,
    user_collection,
)
from utils.metrics_util import metrics_store, MinuteBucket
from utils.token_util import encrypt_value


def _rand_choice(seq):
    return random.choice(seq)


def _rand_word(min_len=4, max_len=10) -> str:
    length = random.randint(min_len, max_len)
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def _rand_name() -> str:
    firsts = ["alex","casey","morgan","sam","taylor","riley","jamie","jordan","drew","quinn","kyle","parker","blake","devon"]
    lasts = ["lee","kim","patel","garcia","nguyen","williams","brown","davis","miller","wilson","moore","taylor","thomas"]
    return f"{_rand_choice(firsts)}.{_rand_choice(lasts)}"


def _rand_domain() -> str:
    return _rand_choice(["example.com","acme.io","contoso.net","demo.dev"])    


def _rand_password() -> str:
    upp = _rand_choice(string.ascii_uppercase)
    low = ''.join(random.choices(string.ascii_lowercase, k=8))
    dig = ''.join(random.choices(string.digits, k=4))
    spc = _rand_choice('!@#$%^&*()-_=+[]{};:,.<>?/')
    tail = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    raw = upp + low + dig + spc + tail
    return ''.join(random.sample(raw, len(raw)))


def ensure_roles() -> list[str]:
    roles = [("developer", dict(manage_apis=True, manage_endpoints=True, manage_subscriptions=True, manage_tokens=True, view_logs=True)),
             ("analyst", dict(view_logs=True, export_logs=True)),
             ("viewer", dict(view_logs=True)),
             ("ops", dict(manage_gateway=True, view_logs=True, export_logs=True, manage_security=True))]
    created = []
    for role_name, extra in roles:
        if not role_collection.find_one({"role_name": role_name}):
            doc = {"role_name": role_name, "role_description": f"{role_name} role"}
            doc.update({k: bool(v) for k, v in extra.items()})
            role_collection.insert_one(doc)
        created.append(role_name)
    return ["admin", *created]


def seed_groups(n: int, api_keys: list[str]) -> list[str]:
    names = []
    for i in range(n):
        gname = f"team-{_rand_word(3,6)}-{i}"
        if group_collection.find_one({"group_name": gname}):
            names.append(gname)
            continue
        access = sorted(set(random.sample(api_keys, k=min(len(api_keys), random.randint(1, max(1, len(api_keys)//3))))) ) if api_keys else []
        group_collection.insert_one({"group_name": gname, "group_description": f"Auto group {gname}", "api_access": access})
        names.append(gname)
    for base in ("ALL", "admin"):
        if not group_collection.find_one({"group_name": base}):
            group_collection.insert_one({"group_name": base, "group_description": f"{base} group", "api_access": []})
        if base not in names:
            names.append(base)
    return names


def seed_users(n: int, roles: list[str], groups: list[str]) -> list[str]:
    usernames = []
    for i in range(n):
        uname = f"{_rand_name()}_{i}"
        email = f"{uname.replace('.', '_')}@{_rand_domain()}"
        if user_collection.find_one({"username": uname}):
            usernames.append(uname)
            continue
        hashed = password_util.hash_password(_rand_password())
        ugrps = sorted(set(random.sample(groups, k=min(len(groups), random.randint(1, min(3, max(1, len(groups))))))))
        role = _rand_choice(roles)
        user_collection.insert_one({
            "username": uname,
            "email": email,
            "password": hashed,
            "role": role,
            "groups": ugrps,
            "rate_limit_duration": random.randint(100, 10000),
            "rate_limit_duration_type": _rand_choice(["minute","hour","day"]),
            "throttle_duration": random.randint(1000, 100000),
            "throttle_duration_type": _rand_choice(["second","minute"]),
            "throttle_wait_duration": random.randint(100, 10000),
            "throttle_wait_duration_type": _rand_choice(["seconds","minutes"]),
            "custom_attributes": {"dept": _rand_choice(["sales","eng","support","ops"])},
            "active": True,
            "ui_access": _rand_choice([True, False])
        })
        usernames.append(uname)
    return usernames


def seed_apis(n: int, roles: list[str], groups: list[str]) -> list[tuple[str,str]]:
    pairs = []
    for i in range(n):
        name = _rand_choice(["customers","orders","billing","weather","news","crypto","search","inventory","shipping","payments","alerts","metrics","recommendations"]) + f"-{_rand_word(3,6)}"
        ver = _rand_choice(["v1","v2","v3"])
        if api_collection.find_one({"api_name": name, "api_version": ver}):
            pairs.append((name, ver))
            continue
        api_id = str(uuid.uuid4())
        doc = {
            "api_name": name,
            "api_version": ver,
            "api_description": f"Auto API {name}/{ver}",
            "api_allowed_roles": sorted(set(random.sample(roles, k=min(len(roles), random.randint(1, min(3, len(roles))))))),
            "api_allowed_groups": sorted(set(random.sample(groups, k=min(len(groups), random.randint(1, min(5, len(groups))))))),
            "api_servers": [f"http://localhost:{8000+random.randint(0,999)}"],
            "api_type": "REST",
            "api_allowed_retry_count": random.randint(0, 3),
            "api_id": api_id,
            "api_path": f"/{name}/{ver}",
        }
        api_collection.insert_one(doc)
        pairs.append((name, ver))
    return pairs


def seed_endpoints(apis: list[tuple[str,str]], per_api: int) -> None:
    methods = ["GET","POST","PUT","DELETE","PATCH"]
    bases = ["/status","/health","/items","/items/{id}","/search","/reports","/export","/metrics","/list","/detail/{id}"]
    for (name, ver) in apis:
        created = set()
        for _ in range(per_api):
            m = _rand_choice(methods)
            u = _rand_choice(bases)
            key = (m, u)
            if key in created:
                continue
            created.add(key)
            if endpoint_collection.find_one({"api_name": name, "api_version": ver, "endpoint_method": m, "endpoint_uri": u}):
                continue
            endpoint_collection.insert_one({
                "api_name": name,
                "api_version": ver,
                "endpoint_method": m,
                "endpoint_uri": u,
                "endpoint_description": f"{m} {u} for {name}",
                "api_id": api_collection.find_one({"api_name": name, "api_version": ver}).get("api_id"),
                "endpoint_id": str(uuid.uuid4()),
            })


def seed_tokens() -> list[str]:
    groups = ["ai-basic","ai-pro","maps-basic","maps-pro","news-tier","weather-tier"]
    tiers_catalog = [
        {"tier_name": "basic", "tokens": 100, "input_limit": 100, "output_limit": 100, "reset_frequency": "monthly"},
        {"tier_name": "pro", "tokens": 1000, "input_limit": 500, "output_limit": 500, "reset_frequency": "monthly"},
        {"tier_name": "enterprise", "tokens": 10000, "input_limit": 2000, "output_limit": 2000, "reset_frequency": "monthly"},
    ]
    created = []
    for g in groups:
        if token_def_collection.find_one({"api_token_group": g}):
            created.append(g)
            continue
        tiers = random.sample(tiers_catalog, k=random.randint(1, 3))
        token_def_collection.insert_one({
            "api_token_group": g,
            "api_key": encrypt_value(uuid.uuid4().hex),
            "api_key_header": _rand_choice(["x-api-key","authorization","x-token"]),
            "token_tiers": tiers,
        })
        created.append(g)
    return created


def seed_user_tokens(usernames: list[str], token_groups: list[str]) -> None:
    pick_users = random.sample(usernames, k=min(len(usernames), max(1, len(usernames)//2))) if usernames else []
    for u in pick_users:
        users_tokens = {}
        for g in random.sample(token_groups, k=random.randint(1, min(3, len(token_groups)))):
            users_tokens[g] = {
                "tier_name": _rand_choice(["basic","pro","enterprise"]),
                "available_tokens": random.randint(10, 10000),
                "reset_date": (datetime.utcnow() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "user_api_key": encrypt_value(uuid.uuid4().hex),
            }
        existing = user_token_collection.find_one({"username": u})
        if existing:
            user_token_collection.update_one({"username": u}, {"$set": {"users_tokens": users_tokens}})
        else:
            user_token_collection.insert_one({"username": u, "users_tokens": users_tokens})


def seed_subscriptions(usernames: list[str], apis: list[tuple[str,str]]) -> None:
    api_keys = [f"{a}/{v}" for a, v in apis]
    for u in usernames:
        subs = sorted(set(random.sample(api_keys, k=random.randint(1, min(5, len(api_keys))))) ) if api_keys else []
        existing = subscriptions_collection.find_one({"username": u})
        if existing:
            subscriptions_collection.update_one({"username": u}, {"$set": {"apis": subs}})
        else:
            subscriptions_collection.insert_one({"username": u, "apis": subs})


def seed_logs(n: int, usernames: list[str], apis: list[tuple[str,str]]) -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(base_dir, '..'))
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, "doorman.log")
    methods = ["GET","POST","PUT","DELETE","PATCH"]
    uris = ["/status","/list","/items","/items/123","/search?q=test","/export","/metrics"]
    now = datetime.now()
    with open(log_path, "a", encoding="utf-8") as lf:
        for _ in range(n):
            api = _rand_choice(apis) if apis else ("demo","v1")
            method = _rand_choice(methods)
            uri = _rand_choice(uris)
            ts = (now - timedelta(seconds=random.randint(0, 3600))).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
            rid = str(uuid.uuid4())
            user = _rand_choice(usernames) if usernames else "admin"
            port = random.randint(10000, 65000)
            msg = f"{rid} | Username: {user} | From: 127.0.0.1:{port} | Endpoint: {method} /{api[0]}/{api[1]}{uri} | Total time: {random.randint(5,500)}ms"
            lf.write(f"{ts} - doorman.gateway - INFO - {msg}\n")


def seed_protos(n: int, apis: list[tuple[str,str]]) -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(base_dir, '..'))
    proto_dir = os.path.join(base_dir, "proto")
    gen_dir = os.path.join(base_dir, "generated")
    os.makedirs(proto_dir, exist_ok=True)
    os.makedirs(gen_dir, exist_ok=True)
    picked = random.sample(apis, k=min(n, len(apis))) if apis else []
    for name, ver in picked:
        key = f"{name}_{ver}".replace('-', '_')
        svc = ''.join([p.capitalize() for p in name.split('-')])
        content = f'''syntax = "proto3";

package {key};

service {svc}Service {{
  rpc GetStatus (StatusRequest) returns (StatusReply) {{}}
}}

message StatusRequest {{
  string id = 1;
}}

message StatusReply {{
  string status = 1;
  string message = 2;
}}
'''
        path = os.path.join(proto_dir, f"{key}.proto")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def seed_metrics(usernames: list[str], apis: list[tuple[str,str]], minutes: int = 400) -> None:
    now = datetime.utcnow()
    for i in range(minutes, 0, -1):
        minute_start = int(((now - timedelta(minutes=i)).timestamp()) // 60) * 60
        b = MinuteBucket(start_ts=minute_start)
        count = random.randint(0, 50)
        for _ in range(count):
            dur = random.uniform(10, 400)
            status = _rand_choice([200,200,200,201,204,400,401,403,404,500])
            b.add(dur, status)
            metrics_store.total_requests += 1
            metrics_store.total_ms += dur
            metrics_store.status_counts[status] += 1
            u = _rand_choice(usernames) if usernames else None
            if u:
                metrics_store.username_counts[u] += 1
            if apis:
                metrics_store.api_counts[f"rest:{_rand_choice(apis)[0]}"] += 1
        metrics_store._buckets.append(b)


def run_seed(users=30, apis=12, endpoints=5, groups=6, protos=5, logs=1000, seed=None):
    if seed is not None:
        random.seed(seed)
    roles = ensure_roles()
    api_pairs = seed_apis(apis, roles, ["ALL","admin"])  
    group_names = seed_groups(groups, [f"{a}/{v}" for a, v in api_pairs])
    usernames = seed_users(users, roles, group_names)
    seed_endpoints(api_pairs, endpoints)
    token_groups = seed_tokens()
    seed_user_tokens(usernames, token_groups)
    seed_subscriptions(usernames, api_pairs)
    seed_logs(logs, usernames, api_pairs)
    seed_protos(protos, api_pairs)
    seed_metrics(usernames, api_pairs)
    return {
        'users': user_collection.count_documents({}),
        'apis': api_collection.count_documents({}),
        'endpoints': endpoint_collection.count_documents({}),
        'groups': group_collection.count_documents({}),
        'roles': role_collection.count_documents({}),
        'subscriptions': subscriptions_collection.count_documents({}),
        'token_defs': token_def_collection.count_documents({}),
        'user_tokens': user_token_collection.count_documents({}),
    }

