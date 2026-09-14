import math
import re
from dataclasses import dataclass, field


ALLOWED_ANSWER_TYPES = {
    "numeric",
    "expression",
    "equation",
    "proof",
    "multi_step",
}

ALLOWED_VISUAL_KINDS = {
    "function_graph",
    "variation_table",
    "sign_table",
    "geometry",
    "diagram",
    "data_table",
}

COMMAND_HEADS = {
    "line": 4,
    "arrow": 4,
    "point": 2,
    "circle": 3,
    "rect": 4,
    "polyline": 2,
    "polygon": 3,
    "text": 2,
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def to_dict(self):
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class QuestionValidator:
    """Deterministic quality/scope/visual gate after Structured Output generation."""

    REQUIRED_FIELDS = {
        "statement_blocks",
        "answer_type",
        "correct_answer_latex",
        "solution_steps",
        "visuals",
        "grading_rubric",
        "teacher_hint",
    }

    def validate(self, payload, *, slot, source=None):
        errors = []
        warnings = []

        if not isinstance(payload, dict):
            return ValidationResult(False, ["Question payload must be an object."])

        missing = [key for key in self.REQUIRED_FIELDS if key not in payload]
        if missing:
            errors.append("Missing required fields: " + ", ".join(missing))

        blocks = payload.get("statement_blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append("statement_blocks must be a non-empty array.")
            rendered_statement = ""
        else:
            rendered_statement = " ".join(
                str(item.get("value", "")) for item in blocks if isinstance(item, dict)
            )
            for index, block in enumerate(blocks):
                if not isinstance(block, dict):
                    errors.append(f"statement_blocks[{index}] must be an object.")
                    continue
                if block.get("type") not in {"text", "math"}:
                    errors.append(f"Invalid block type at index {index}.")
                if not str(block.get("value", "")).strip():
                    errors.append(f"Empty statement block at index {index}.")

        if len(rendered_statement.strip()) < 10:
            errors.append("Question statement is too short.")
        if len(rendered_statement) > 5000:
            errors.append("Question statement is too long.")

        answer_type = payload.get("answer_type")
        if answer_type not in ALLOWED_ANSWER_TYPES:
            errors.append(f"Unsupported answer_type: {answer_type}")

        if not str(payload.get("correct_answer_latex", "")).strip():
            errors.append("correct_answer_latex cannot be empty.")

        solution_steps = payload.get("solution_steps")
        if not isinstance(solution_steps, list) or not solution_steps:
            errors.append("solution_steps must be a non-empty array.")
            solution_steps = []
        elif len(solution_steps) > 12:
            errors.append("solution_steps cannot exceed 12 items.")

        self._validate_visuals(payload.get("visuals"), len(solution_steps), errors, warnings)

        rubric = payload.get("grading_rubric")
        if not isinstance(rubric, dict):
            errors.append("grading_rubric must be an object.")
        else:
            try:
                max_score = float(rubric.get("max_score", 0))
                if max_score != 1.0:
                    errors.append("grading_rubric.max_score must be 1.0.")
            except (TypeError, ValueError):
                errors.append("grading_rubric.max_score must be numeric.")

        try:
            difficulty = int(payload.get("difficulty", slot.get("difficulty")))
            if not 1 <= difficulty <= 5:
                errors.append("Difficulty must be between 1 and 5.")
        except (TypeError, ValueError):
            errors.append("Difficulty must be an integer.")

        if payload.get("source_type") and payload["source_type"] != slot["source_type"]:
            errors.append("Generated source_type differs from blueprint.")

        for payload_key, slot_key, label in [
            ("bac_idea_code", "bac_idea_code", "BAC idea"),
            ("variant_code", "variant_code", "variant"),
            ("skill_code", "skill_code", "skill"),
        ]:
            expected = slot.get(slot_key) or ""
            actual = payload.get(payload_key) or ""
            if expected and actual != expected:
                errors.append(f"Generated {label} does not match blueprint.")

        expected_targets = set(slot.get("target_skill_idea_codes", []) or [])
        actual_targets = set(payload.get("target_skill_idea_codes", []) or [])
        if expected_targets and actual_targets != expected_targets:
            errors.append("Generated target skill idea codes must exactly match the blueprint.")

        forbidden = []
        if source is not None:
            guidance = getattr(source, "generation_guidance", {}) or {}
            forbidden = guidance.get("forbidden_concepts", []) or []

        lowered = rendered_statement.casefold()
        for concept in forbidden:
            text = str(concept).strip()
            if text and text.casefold() in lowered:
                errors.append(f"Question contains forbidden concept: {text}")

        if payload.get("requires_external_data"):
            errors.append("Question must be self-contained.")
        if payload.get("ambiguous") is True:
            errors.append("Generator marked the question as ambiguous.")

        return ValidationResult(not errors, errors, warnings)

    @staticmethod
    def _finite_number(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _validate_visuals(self, visuals, solution_step_count, errors, warnings):
        if visuals is None:
            errors.append("visuals is required (use [] when no drawing is needed).")
            return
        if not isinstance(visuals, list):
            errors.append("visuals must be an array.")
            return
        if len(visuals) > 6:
            errors.append("visuals cannot exceed 6 items.")
            return

        seen_ids = set()
        for index, visual in enumerate(visuals):
            prefix = f"visuals[{index}]"
            if not isinstance(visual, dict):
                errors.append(f"{prefix} must be an object.")
                continue

            visual_id = str(visual.get("id") or "").strip()
            if not visual_id:
                errors.append(f"{prefix}.id cannot be empty.")
            elif visual_id in seen_ids:
                errors.append(f"Duplicate visual id: {visual_id}")
            seen_ids.add(visual_id)

            placement = visual.get("placement")
            if placement not in {"question", "solution"}:
                errors.append(f"{prefix}.placement is invalid.")

            try:
                after_step = int(visual.get("after_step", 0))
            except (TypeError, ValueError):
                after_step = -1
            if after_step < 0 or after_step > 20:
                errors.append(f"{prefix}.after_step is invalid.")
            if placement == "solution" and after_step > solution_step_count:
                errors.append(f"{prefix}.after_step exceeds solution_steps length.")
            if placement == "question" and after_step != 0:
                warnings.append(f"{prefix}: question visual ignores after_step; use 0.")

            kind = visual.get("kind")
            if kind not in ALLOWED_VISUAL_KINDS:
                errors.append(f"{prefix}.kind is unsupported.")
                continue

            if kind == "function_graph":
                self._validate_function_graph(visual, prefix, errors)
            elif kind in {"variation_table", "sign_table", "data_table"}:
                self._validate_table_visual(visual, prefix, errors)
            elif kind in {"geometry", "diagram"}:
                self._validate_commands(visual.get("commands"), prefix, errors)

    def _validate_function_graph(self, visual, prefix, errors):
        bounds = []
        for key in ("x_min", "x_max", "y_min", "y_max"):
            number = self._finite_number(visual.get(key))
            if number is None:
                errors.append(f"{prefix}.{key} must be finite.")
                return
            bounds.append(number)
        x_min, x_max, y_min, y_max = bounds
        if not x_min < x_max:
            errors.append(f"{prefix}: x_min must be smaller than x_max.")
        if not y_min < y_max:
            errors.append(f"{prefix}: y_min must be smaller than y_max.")
        if max(abs(x_min), abs(x_max), abs(y_min), abs(y_max)) > 1e7:
            errors.append(f"{prefix}: graph bounds are unreasonably large.")

        series = visual.get("series")
        if not isinstance(series, list) or not series:
            errors.append(f"{prefix}.series must contain at least one curve.")
            return
        if len(series) > 4:
            errors.append(f"{prefix}.series cannot exceed 4 curves.")
        for s_index, serie in enumerate(series):
            points = serie.get("points") if isinstance(serie, dict) else None
            if not isinstance(points, list) or len(points) < 2:
                errors.append(f"{prefix}.series[{s_index}] needs at least 2 points.")
                continue
            if len(points) > 90:
                errors.append(f"{prefix}.series[{s_index}] has too many points.")
            previous_x = None
            for p_index, point in enumerate(points):
                if not isinstance(point, list) or len(point) != 2:
                    errors.append(f"{prefix}.series[{s_index}].points[{p_index}] is invalid.")
                    continue
                x = self._finite_number(point[0])
                y = self._finite_number(point[1])
                if x is None or y is None:
                    errors.append(f"{prefix}.series[{s_index}].points[{p_index}] must be finite.")
                    continue
                if previous_x is not None and x < previous_x:
                    errors.append(f"{prefix}.series[{s_index}] points must be ordered by x.")
                    break
                previous_x = x

    @staticmethod
    def _validate_table_visual(visual, prefix, errors):
        columns = visual.get("columns")
        rows = visual.get("rows")
        if not isinstance(columns, list) or len(columns) < 2:
            errors.append(f"{prefix}.columns needs at least 2 columns.")
            return
        if len(columns) > 14:
            errors.append(f"{prefix}.columns cannot exceed 14 items.")
        if not isinstance(rows, list) or not rows:
            errors.append(f"{prefix}.rows must be non-empty.")
            return
        for r_index, row in enumerate(rows):
            cells = row.get("cells") if isinstance(row, dict) else None
            if not isinstance(cells, list) or len(cells) != len(columns):
                errors.append(
                    f"{prefix}.rows[{r_index}].cells must match columns length ({len(columns)})."
                )

    def _validate_commands(self, commands, prefix, errors):
        if not isinstance(commands, list) or not commands:
            errors.append(f"{prefix}.commands must be non-empty for diagram/geometry.")
            return
        if len(commands) > 80:
            errors.append(f"{prefix}.commands cannot exceed 80 items.")
            return

        for c_index, raw in enumerate(commands):
            command = str(raw or "").strip()
            if not command or len(command) > 300:
                errors.append(f"{prefix}.commands[{c_index}] is empty or too long.")
                continue
            if any(marker in command.lower() for marker in ("<script", "javascript:", "http://", "https://")):
                errors.append(f"{prefix}.commands[{c_index}] contains forbidden content.")
                continue

            head = command.split(maxsplit=1)[0].lower()
            if head not in COMMAND_HEADS:
                errors.append(f"{prefix}.commands[{c_index}] uses unsupported command '{head}'.")
                continue

            if head in {"polyline", "polygon"}:
                coords = re.findall(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", command)
                required = 2 if head == "polyline" else 3
                if len(coords) < required:
                    errors.append(f"{prefix}.commands[{c_index}] has too few points.")
                    continue
                numbers = [float(value) for pair in coords for value in pair]
            elif head == "text":
                parts = command.split(maxsplit=3)
                if len(parts) < 4:
                    errors.append(f"{prefix}.commands[{c_index}] text command is incomplete.")
                    continue
                numbers = [self._finite_number(parts[1]), self._finite_number(parts[2])]
                if any(v is None for v in numbers):
                    errors.append(f"{prefix}.commands[{c_index}] text coordinates are invalid.")
                    continue
            else:
                count = COMMAND_HEADS[head]
                parts = command.split()
                if len(parts) < count + 1:
                    errors.append(f"{prefix}.commands[{c_index}] has too few numeric arguments.")
                    continue
                numbers = [self._finite_number(value) for value in parts[1 : count + 1]]
                if any(v is None for v in numbers):
                    errors.append(f"{prefix}.commands[{c_index}] has invalid numeric arguments.")
                    continue

            # Diagram coordinates live in a predictable logical canvas. Radius/width/height
            # may be up to 100 as well. A tiny margin is allowed for labels/arrows.
            if any(value < -5 or value > 105 for value in numbers):
                errors.append(f"{prefix}.commands[{c_index}] coordinates must stay near 0..100.")
