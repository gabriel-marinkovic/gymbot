import json
import uuid
import logging
import os
import sys
import tomllib
from typing import Any, Dict, Optional, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

import workouts


logging.basicConfig(
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def load_config() -> Dict[str, Any]:
    try:
        path = os.environ["CONFIG"]
    except KeyError:
        print("'CONFIG' environment contain the path to the config file", file=sys.stderr)
        exit(-1)
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        print(f"Failed to parse config from '{path}': {e}", file=sys.stderr)
        exit(-1)


_workout = [
    {
        "name": "Bench Press",
        "sets": 3,
        "reps": 12,
        "weight": 40.0,
        "weight_delta": 2.5,
    },
    {
        "name": "Bench Press",
        "sets": 3,
        "reps": 12,
        "weight": 40.0,
        "weight_delta": 2.5,
    },
]


class InvalidWorkerIDError(ValueError):
    pass


class InvalidSetIDError(ValueError):
    pass


class UnknownKindError(ValueError):
    pass


class Workout:
    id: str
    exercises: List[workouts.Exercise]

    def __init__(self, exercises: List[workouts.ExerciseTemplate]):
        self.id = str(uuid.uuid4())
        self.exercises = [workouts.Exercise(ex) for ex in exercises]

    def generate_workout_markup(self) -> InlineKeyboardMarkup:
        keyboard = []
        for exercise in self.exercises:
            keyboard.append([InlineKeyboardButton(exercise.template.name, callback_data="bla")])
            row = []
            for i, s in enumerate(exercise.sets):
                checkbox = "✅ " if s.completed else ""
                label = f"{checkbox}{s.reps} ({exercise.template.weight}kg)"
                row.append(InlineKeyboardButton(label, callback_data=self._make_toggle_set_message(s)))
            keyboard.append(row)
            keyboard.append(
                [
                    InlineKeyboardButton("⬆️ reps", callback_data="reps_up"),
                    InlineKeyboardButton("⬇️ reps", callback_data="reps_down"),
                    InlineKeyboardButton("⬆️ weight", callback_data="weight_up"),
                    InlineKeyboardButton("⬇️ weight", callback_data="weight_down"),
                ]
            )
        return InlineKeyboardMarkup(keyboard)

    def handle_message(self, message: Dict[str, Any]):
        workout_id = message["workout_id"]
        if workout_id != self.id:
            raise InvalidWorkerIDError(workout_id)
        kind = message["kind"]
        if kind == Workout._MESSAGE_TOGGLE_SET:
            set_id = message["set_id"]
            toggled = False
            for exercise in self.exercises:
                for s in exercise.sets:
                    if s.id == set_id:
                        s.completed = not s.completed
                        toggled = True
            if not toggled:
                raise InvalidSetIDError(set_id)
        else:
            raise UnknownKindError(kind)

    _MESSAGE_TOGGLE_SET = "toggle_set"

    def _make_toggle_set_message(self, s: workouts.WorkoutSet) -> str:
        return self._make_message(Workout._MESSAGE_TOGGLE_SET, set_id=s.id)

    def _make_message(self, kind: str, **kwargs) -> str:
        x = json.dumps({"workout_id": self.id, "kind": kind, **kwargs})
        print(x)
        return x


active_workout: Optional[Workout] = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_workout

    if not update.message:
        logging.warn("Got update without 'message':", update)
        return

    message = "Starting a new workout!\n"
    if active_workout:
        message += "<code>WARNING: Overwriting previous workout!</code>\n"

    active_workout = Workout(workouts.make_workout_template())

    await update.message.reply_text(
        message, parse_mode=ParseMode.HTML, reply_markup=active_workout.generate_workout_markup()
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global active_workout
    assert active_workout

    query = update.callback_query
    assert query and query.data
    print(query.data)
    assert isinstance(query.data, str)
    try:
        message: Dict[str, Any] = json.loads(query.data)
    except ValueError as ex:
        logging.error(f"Failed to decode callback_query: {ex}")
    try:
        active_workout.handle_message(message)
    except ValueError as ex:
        logging.error(f"Failed to handle message: {ex}")

    # NOTE: CallbackQueries need to be answered, even if no notification to the
    # user is needed Some clients may have trouble otherwise. See
    # https://core.telegram.org/bots/api#callbackquery
    await query.answer()
    await query.edit_message_text("", reply_markup=active_workout.generate_workout_markup())


if __name__ == "__main__":
    config = load_config()
    app = ApplicationBuilder().token(config["bot_auth_token"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling(poll_interval=0.5)
