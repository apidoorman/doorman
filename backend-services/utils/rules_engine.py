import ast
import operator
import logging

logger = logging.getLogger('doorman.rules')

# Allowed operators
OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
}

class SafeEvaluator(ast.NodeVisitor):
    def __init__(self, context):
        self.context = context

    def visit(self, node):
        if hasattr(self, 'visit_' + node.__class__.__name__):
            return super().visit(node)
        raise ValueError(f"Unauthorized node type: {node.__class__.__name__}")

    def visit_Module(self, node):
        return self.visit(node.body[0])

    def visit_Expr(self, node):
        return self.visit(node.value)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = type(node.op)
        if op not in OPS:
            raise ValueError(f"Unauthorized operator: {op}")
        return OPS[op](left, right)

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            op_type = type(op)
            if op_type not in OPS:
                raise ValueError(f"Unauthorized operator: {op_type}")
            if not OPS[op_type](left, right):
                return False
            left = right
        return True

    def visit_BoolOp(self, node):
        values = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        elif isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError(f"Unauthorized boolean operator: {type(node.op)}")

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        op = type(node.op)
        if op not in OPS:
            raise ValueError(f"Unauthorized unary operator: {op}")
        return OPS[op](operand)

    def visit_Constant(self, node):
        return node.value

    # Python < 3.8 compatibility for numbers/strings/etc if needed, but Constant covers most in 3.12
    def visit_Num(self, node):
        return node.n

    def visit_Str(self, node):
        return node.s

    def visit_NameConstant(self, node):
        return node.value

    def visit_Name(self, node):
        if node.id in self.context:
            return self.context[node.id]
        # Allow access to top-level context variables directly if they are dicts?
        # No, require specific top-level keys like 'auth', 'resource', 'request'
        return None

    def visit_Attribute(self, node):
        obj = self.visit(node.value)
        attr = node.attr
        if isinstance(obj, dict):
            return obj.get(attr)
        if hasattr(obj, attr):
            return getattr(obj, attr)
        return None
    
    def visit_Subscript(self, node):
        obj = self.visit(node.value)
        idx = self.visit(node.slice)
        try:
             return obj[idx]
        except Exception:
             return None

    # Handle Slice/Index for Python < 3.9 if needed, but Subscript is usually enough
    # Python 3.9+ 'slice' is just a node in Subscript, usually Constant or something.


def evaluate_rule(rule_expression: str, context: dict) -> bool:
    """
    Evaluate a security rule expression safely.
    
    Args:
        rule_expression (str): Python-like expression (e.g. "auth.uid == resource.owner_id")
        context (dict): Dictionary containing 'auth', 'resource', 'request'
        
    Returns:
        bool: True if allowed, False otherwise.
    """
    if not rule_expression or not rule_expression.strip():
        return True # Empty rule = allow by default? Or deny?
        # Firebase defaults to deny if no rule matches, but here we might want default allow for backward compatibility
        # if the rule is empty string.
        # Let's assume empty string means "no rule", so True.

    try:
        tree = ast.parse(rule_expression, mode='eval')
        evaluator = SafeEvaluator(context)
        return bool(evaluator.visit(tree))
    except Exception as e:
        logger.warning(f"Rule evaluation error: {e} | Rule: {rule_expression}")
        return False
