VISUAL_KIND_ENUM = [
    "function_graph",
    "variation_table",
    "sign_table",
    "geometry",
    "diagram",
    "data_table",
]

VISUAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "placement": {"type": "string", "enum": ["question", "solution"]},
        "after_step": {"type": "integer", "minimum": 0, "maximum": 20},
        "kind": {"type": "string", "enum": VISUAL_KIND_ENUM},
        "title": {"type": "string"},
        "caption": {"type": "string"},
        "x_min": {"type": "number"},
        "x_max": {"type": "number"},
        "y_min": {"type": "number"},
        "y_max": {"type": "number"},
        "x_label": {"type": "string"},
        "y_label": {"type": "string"},
        "series": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "points": {
                        "type": "array",
                        "maxItems": 90,
                        "items": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 2,
                            "items": {"type": "number"},
                        },
                    },
                },
                "required": ["label", "points"],
            },
        },
        "columns": {
            "type": "array",
            "maxItems": 14,
            "items": {"type": "string"},
        },
        "rows": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "cells": {
                        "type": "array",
                        "maxItems": 14,
                        "items": {"type": "string"},
                    },
                },
                "required": ["label", "cells"],
            },
        },
        # Compact safe drawing DSL interpreted by the React frontend.
        # Supported commands are validated server-side:
        # line, arrow, point, circle, rect, polyline, polygon, text.
        # Diagram coordinates use a 0..100 logical viewBox.
        "commands": {
            "type": "array",
            "maxItems": 80,
            "items": {"type": "string"},
        },
    },
    "required": [
        "id",
        "placement",
        "after_step",
        "kind",
        "title",
        "caption",
        "x_min",
        "x_max",
        "y_min",
        "y_max",
        "x_label",
        "y_label",
        "series",
        "columns",
        "rows",
        "commands",
    ],
}


QUESTION_JSON_SCHEMA = {
    "name": "adaptive_math_question_with_visuals",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "statement_blocks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string", "enum": ["text", "math"]},
                        "value": {"type": "string"},
                    },
                    "required": ["type", "value"],
                },
            },
            "answer_type": {
                "type": "string",
                "enum": ["numeric", "expression", "equation", "proof", "multi_step"],
            },
            "correct_answer_latex": {"type": "string"},
            "solution_steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {"type": "string"},
            },
            "visuals": {
                "type": "array",
                "maxItems": 6,
                "items": VISUAL_SCHEMA,
            },
            "grading_rubric": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "max_score": {"type": "number"},
                    "required_elements": {
                        "type": "array",
                        "maxItems": 10,
                        "items": {"type": "string"},
                    },
                },
                "required": ["max_score", "required_elements"],
            },
            "teacher_hint": {"type": "string"},
        },
        "required": [
            "statement_blocks",
            "answer_type",
            "correct_answer_latex",
            "solution_steps",
            "visuals",
            "grading_rubric",
            "teacher_hint",
        ],
    },
}


GRADING_JSON_SCHEMA = {
    "name": "adaptive_teacher_grading",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["correct", "partially_correct", "incorrect"],
            },
            "score": {"type": "number", "minimum": 0, "maximum": 1},
            "teacher_message": {"type": "string"},
            "what_was_correct": {
                "type": "array",
                "items": {"type": "string"},
            },
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "step_number": {"type": "integer", "minimum": 1},
                        "issue": {"type": "string"},
                        "why": {"type": "string"},
                        "corrected_latex": {"type": "string"},
                    },
                    "required": ["step_number", "issue", "why", "corrected_latex"],
                },
            },
            "next_hint": {"type": "string"},
            "correct_solution_steps": {
                "type": "array",
                "items": {"type": "string"},
            },
            "mastered_skill_idea_codes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "weak_skill_idea_codes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "detected_misconception_codes": {
                "type": "array",
                "items": {"type": "string"},
            },
            "should_retry": {"type": "boolean"},
        },
        "required": [
            "verdict",
            "score",
            "teacher_message",
            "what_was_correct",
            "errors",
            "next_hint",
            "correct_solution_steps",
            "mastered_skill_idea_codes",
            "weak_skill_idea_codes",
            "detected_misconception_codes",
            "should_retry",
        ],
    },
}
