from utils.rules_engine import evaluate_rule


def test_rules_engine_evaluates_basic_expressions():
    ctx = {
        'auth': {'uid': 'alice', 'role': 'admin'},
        'resource': {'data': {'owner': 'alice'}},
        'request': {'data': {'status': 'open'}, 'headers': {'x-plan': 'gold'}},
    }

    assert evaluate_rule("auth.uid == resource.data.owner", ctx)
    assert evaluate_rule("auth.role in ['admin', 'owner']", ctx)
    assert evaluate_rule("request['data']['status'] == 'open'", ctx)
    assert not evaluate_rule("auth.uid == 'bob'", ctx)


def test_rules_engine_rejects_unsafe_nodes():
    assert not evaluate_rule("__import__('os').system('id') == 0", {})
    assert not evaluate_rule("(lambda x: x)(1) == 1", {})
