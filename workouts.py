import dataclasses
from typing import List


@dataclasses.dataclass
class ExerciseTemplate:
    name: str
    weight: float
    weight_delta: float
    sets: int
    reps: int


_default_exercise_templates = [
    ExerciseTemplate(
        name="Bench Press",
        weight=30.0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Squat",
        weight=40.0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
]


@dataclasses.dataclass
class WorkoutSet:
    weight: float
    reps: int
    completed: bool


@dataclasses.dataclass
class Exercise:
    name: str
    short_name: str
    weight_delta: float
    sets: List[WorkoutSet]


@dataclasses.dataclass
class Workout:
    exercises: List[Exercise]
