import ast
import math
from typing import Any, Callable

from exercise_generation.services.exceptions import ExerciseValidationError

GRAPH_AXIS_WORDS = (
    "graph",
    "cobweb",
    "stair",
    "بياني",
    "التمثيل البياني",
    "السلم",
    "منحنى",
)


def axis_requires_graph(axis) -> bool:
    source = f"{getattr(axis, 'tag', '')} {getattr(axis, 'title', '')}".lower()
    return any(word in source for word in GRAPH_AXIS_WORDS)


_ALLOWED_FUNCS = {
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "abs": abs,
}
_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e}


def _compile_expression(expression: str) -> Callable[[float], float]:
    expression = str(expression or "").strip().replace("^", "**")
    if not expression:
        raise ExerciseValidationError("expression_python غير موجودة.")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExerciseValidationError("صيغة الدالة غير صالحة.") from exc

    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
    )

    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise ExerciseValidationError("graph_spec تحتوي عملية غير مسموحة.")
        if isinstance(node, ast.Name):
            if node.id not in {"x", *_ALLOWED_FUNCS, *_ALLOWED_CONSTS}:
                raise ExerciseValidationError(f"الرمز {node.id} غير مسموح في الرسم.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ExerciseValidationError("دالة غير مسموحة في الرسم.")

    code = compile(tree, "<graph>", "eval")

    def evaluate(x: float) -> float:
        value = eval(
            code,
            {"__builtins__": {}},
            {"x": x, **_ALLOWED_FUNCS, **_ALLOWED_CONSTS},
        )
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("non finite")
        return value

    return evaluate


def _number(source: dict[str, Any], key: str, default: float) -> float:
    try:
        value = float(source.get(key, default))
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def build_graph_data(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ExerciseValidationError("التمرين البياني يحتاج graph_spec.")

    graph_type = str(spec.get("graph_type") or "cobweb").lower()
    if graph_type not in {"function", "cobweb"}:
        raise ExerciseValidationError("graph_type يجب أن يكون function أو cobweb.")

    evaluate = _compile_expression(spec.get("expression_python"))
    x_min = _number(spec, "x_min", 0)
    x_max = _number(spec, "x_max", 5)
    y_min = _number(spec, "y_min", 0)
    y_max = _number(spec, "y_max", 5)
    step = max(0.03, min(_number(spec, "step", 0.08), 0.5))
    if x_min >= x_max:
        x_min, x_max = 0, 5
    if y_min >= y_max:
        y_min, y_max = 0, 5

    points = []
    x = x_min
    while x <= x_max + step / 2 and len(points) < 400:
        try:
            y = evaluate(x)
            if y_min - 2 <= y <= y_max + 2:
                points.append({"x": round(x, 6), "y": round(y, 6)})
        except (ValueError, ZeroDivisionError, OverflowError):
            pass
        x += step

    if len(points) < 2:
        raise ExerciseValidationError("تعذر حساب نقاط كافية للرسم.")

    functions = [
        {
            "id": "f",
            "label": str(spec.get("expression_label") or "f(x)"),
            "expression": str(spec.get("expression_label") or "f(x)"),
            "points": points,
        }
    ]
    sequence_values = []
    cobweb_segments = []
    construction_steps = [
        {
            "order": 1,
            "title": "رسم المنحنى",
            "description": "نرسم منحنى الدالة داخل المجال المحدد.",
        }
    ]

    if graph_type == "cobweb":
        functions.append(
            {
                "id": "identity",
                "label": "y=x",
                "expression": "y=x",
                "points": [
                    {"x": round(x_min, 6), "y": round(x_min, 6)},
                    {"x": round(x_max, 6), "y": round(x_max, 6)},
                ],
            }
        )

        u = _number(spec, "initial_value", 1)
        iterations = max(3, min(int(_number(spec, "iterations", 6)), 12))
        sequence_values.append({"n": 0, "value": round(u, 8)})
        current = {"x": round(u, 8), "y": 0.0}

        for n in range(iterations):
            next_u = evaluate(u)
            vertical = {"x": round(u, 8), "y": round(next_u, 8)}
            horizontal = {"x": round(next_u, 8), "y": round(next_u, 8)}
            cobweb_segments.append(
                {
                    "order": 2 * n + 1,
                    "segment_type": "vertical",
                    "from": current,
                    "to": vertical,
                }
            )
            cobweb_segments.append(
                {
                    "order": 2 * n + 2,
                    "segment_type": "horizontal",
                    "from": vertical,
                    "to": horizontal,
                }
            )
            u = next_u
            sequence_values.append({"n": n + 1, "value": round(u, 8)})
            current = horizontal

        construction_steps.extend(
            [
                {
                    "order": 2,
                    "title": "رسم المستقيم",
                    "description": "نرسم المستقيم ذي المعادلة \\(y=x\\).",
                },
                {
                    "order": 3,
                    "title": "إنشاء السلم",
                    "description": "ننتقل عموديًا إلى المنحنى ثم أفقيًا إلى المستقيم ونكرر.",
                },
            ]
        )

    return {
        "graph_type": graph_type,
        "title": str(spec.get("title") or "التمثيل البياني"),
        "x_label": "x",
        "y_label": "y",
        "x_domain": {"min": x_min, "max": x_max, "step": step},
        "y_domain": {"min": y_min, "max": y_max},
        "functions": functions,
        "sequence_values": sequence_values,
        "construction_steps": construction_steps,
        "cobweb_segments": cobweb_segments,
    }


def ensure_graph_payload(exercise: dict[str, Any], *, axis) -> dict[str, Any]:
    result = dict(exercise)
    must_graph = axis_requires_graph(axis)

    # لا نسمح للنموذج أو للمراجع بإضافة رسم خارج المحور البياني.
    result["requires_graph"] = must_graph
    if must_graph:
        result["graph_data"] = build_graph_data(result.get("graph_spec"))
    else:
        result["graph_spec"] = {}
        result["graph_data"] = {}

    return result
