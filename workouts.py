import dataclasses
from typing import List, Dict
import uuid


@dataclasses.dataclass
class ExerciseTemplate:
    name: str
    long_cycle_progression: bool
    weight: float
    weight_delta: float
    sets: int
    reps: int


@dataclasses.dataclass
class WorkoutSet:
    id: str
    weight: float
    reps: int
    completed: bool


@dataclasses.dataclass
class Exercise:
    id: str
    template: ExerciseTemplate
    sets: List[WorkoutSet]

    @classmethod
    def from_template(cls, template: ExerciseTemplate) -> "Exercise":
        return Exercise(
            id=str(uuid.uuid4()),
            template=template,
            sets=[
                WorkoutSet(id=str(uuid.uuid4()), weight=template.weight, reps=template.reps, completed=False)
                for i in range(template.sets)
            ],
        )


_default_exercise_templates: List[ExerciseTemplate] = [
    ExerciseTemplate(
        name="Squat",
        long_cycle_progression=True,
        weight=40.0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Bench Press",
        long_cycle_progression=True,
        weight=30.0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Barbell Row",
        long_cycle_progression=True,
        weight=30.0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Lying Tricep Extension",
        long_cycle_progression=True,
        weight=0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Leg Curl",
        long_cycle_progression=True,
        weight=0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Dumbbell Curl",
        long_cycle_progression=True,
        weight=6,
        weight_delta=1,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Weighted Sit Up",
        long_cycle_progression=False,
        weight=25,
        weight_delta=5,
        sets=3,
        reps=20,
    ),
    ExerciseTemplate(
        name="Deadlift",
        long_cycle_progression=True,
        weight=40.0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Overhead Press",
        long_cycle_progression=True,
        weight=20,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Pull Ups",
        long_cycle_progression=False,
        weight=0,
        weight_delta=0,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Lat Pulls",
        long_cycle_progression=False,
        weight=25,
        weight_delta=7,
        sets=3,
        reps=20,
    ),
    ExerciseTemplate(
        name="Dips",
        long_cycle_progression=False,
        weight=0,
        weight_delta=0,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Seated Calf Raise",
        long_cycle_progression=True,
        weight=20,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Power Barbell Shrug",
        long_cycle_progression=True,
        weight=50,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    ExerciseTemplate(
        name="Plank",
        long_cycle_progression=False,
        weight=0,
        weight_delta=0,
        sets=3,
        reps=60,
    ),
]


_name_to_template: Dict[str, ExerciseTemplate] = {x.name: x for x in _default_exercise_templates}


def make_workout_template() -> List[ExerciseTemplate]:
    names = [
        "Squat",
        "Bench Press",
        "Barbell Row",
        "Lying Tricep Extension",
        "Leg Curl",
        "Dumbbell Curl",
        "Weighted Sit Up",
    ]
    return [_name_to_template[name] for name in names]


@dataclasses.dataclass
class Workout:
    id: str
    exercises: List[Exercise]

    @classmethod
    def from_template(cls, template: List[ExerciseTemplate]) -> "Workout":
        return Workout(id=str(uuid.uuid4()), exercises=[Exercise.from_template(ex) for ex in template])

    def toggle_set_completed(self, s: WorkoutSet):
        s.completed = not s.completed

    def change_reps(self, exercise: Exercise, increase: bool):
        delta = 1 if increase else -1
        for s in exercise.sets:
            if not s.completed:
                s.reps = max(0, s.reps + delta)

    def change_weight(self, exercise: Exercise, increase: bool):
        delta = exercise.template.weight_delta if increase else -exercise.template.weight_delta
        for s in exercise.sets:
            if not s.completed:
                s.weight = round(s.weight + delta, 2)

