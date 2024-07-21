import dataclasses
from typing import List, Dict, Tuple


@dataclasses.dataclass
class WorkoutSet:
    weight: float
    reps: int
    completed: bool


@dataclasses.dataclass
class Exercise:
    name: str
    long_cycle_progression: bool
    weight: float
    weight_delta: float
    sets: int
    reps: int


    def generate_sets(self) -> List[WorkoutSet]:
        return [
            WorkoutSet(weight=self.weight, reps=self.reps, completed=False)
            for i in range(self.sets)
        ]


_default_exercise_templates: List[Exercise] = [
    Exercise(
        name="Squat",
        long_cycle_progression=True,
        weight=40.0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Bench Press",
        long_cycle_progression=True,
        weight=30.0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Barbell Row",
        long_cycle_progression=True,
        weight=30.0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Lying Tricep Extension",
        long_cycle_progression=True,
        weight=0,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Leg Curl",
        long_cycle_progression=True,
        weight=0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Dumbbell Curl",
        long_cycle_progression=True,
        weight=6,
        weight_delta=1,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Weighted Sit Up",
        long_cycle_progression=False,
        weight=25,
        weight_delta=5,
        sets=3,
        reps=20,
    ),
    Exercise(
        name="Deadlift",
        long_cycle_progression=True,
        weight=40.0,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Overhead Press",
        long_cycle_progression=True,
        weight=20,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Pull Ups",
        long_cycle_progression=False,
        weight=0,
        weight_delta=0,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Lat Pulls",
        long_cycle_progression=False,
        weight=25,
        weight_delta=7,
        sets=3,
        reps=20,
    ),
    Exercise(
        name="Dips",
        long_cycle_progression=False,
        weight=0,
        weight_delta=0,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Seated Calf Raise",
        long_cycle_progression=True,
        weight=20,
        weight_delta=5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Power Barbell Shrug",
        long_cycle_progression=True,
        weight=50,
        weight_delta=2.5,
        sets=3,
        reps=12,
    ),
    Exercise(
        name="Plank",
        long_cycle_progression=False,
        weight=0,
        weight_delta=0,
        sets=3,
        reps=60,
    ),
]


_name_to_template: Dict[str, Exercise] = {
    x.name: x
    for x in _default_exercise_templates
}


def make_workout() -> List[Tuple[Exercise, List[WorkoutSet]]]:
    names = [
        "Squat",
        "Bench Press",
        "Barbell Row",
        "Lying Tricep Extension",
        "Leg Curl",
        "Dumbbell Curl",
        "Weighted Sit Up",
    ]
    exercises = []
    for name in names:
        exercise = _name_to_template[name]
        exercises.append((exercise, exercise.generate_sets()))
    return exercises

