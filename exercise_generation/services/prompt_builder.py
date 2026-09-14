"""Compatibilité avec les anciens imports.

Le prompt canonique est dans ``services.prompts`` afin d'éviter deux
implémentations divergentes.
"""

from exercise_generation.services.prompts import (  # noqa: F401
    ExercisePromptBuilder,
    build_bac_like_exercise_prompt,
)

__all__ = ["ExercisePromptBuilder", "build_bac_like_exercise_prompt"]
