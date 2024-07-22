import uuid
import logging
import os
import sys
import tomllib
from typing import Any, Dict, Optional, List, Callable

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


class Workout:
    id: str
    exercises: List[workouts.Exercise]
    _actions: Dict[str, Callable[[], None]]

    def __init__(self, exercises: List[workouts.ExerciseTemplate]):
        self.id = str(uuid.uuid4())
        self.exercises = [workouts.Exercise(ex) for ex in exercises]
        self._actions = {}

    def generate_workout_markup(self) -> InlineKeyboardMarkup:
        keyboard = []
        for exercise in self.exercises:
            keyboard.append(
                [InlineKeyboardButton(exercise.template.name, callback_data=self._register_action(lambda: None))]
            )
            row = []
            for i, s in enumerate(exercise.sets):
                checkbox = "✅ " if s.completed else ""
                label = f"{checkbox}{s.reps} ({s.weight}kg)"
                row.append(InlineKeyboardButton(label, callback_data=self._register_action_toggle_set_completed(s)))
            keyboard.append(row)
            keyboard.append(
                [
                    InlineKeyboardButton("⬆️ reps", callback_data=self._register_action_change_reps(exercise, True)),
                    InlineKeyboardButton("⬇️ reps", callback_data=self._register_action_change_reps(exercise, False)),
                    InlineKeyboardButton("⬆️ weight", callback_data=self._register_action_change_weight(exercise, True)),
                    InlineKeyboardButton(
                        "⬇️ weight", callback_data=self._register_action_change_weight(exercise, False)
                    ),
                ]
            )
        return InlineKeyboardMarkup(keyboard)

    def run_action(self, action_id: str):
        action = self._actions.get(action_id, None)
        if action is None:
            raise ValueError(f"Unknown action ID: {action_id}")
        action()

    def _register_action_toggle_set_completed(self, s: workouts.WorkoutSet) -> str:
        def callback():
            s.completed = not s.completed

        return self._register_action(callback)

    def _register_action_change_reps(self, exercise: workouts.Exercise, increase: bool) -> str:
        def callback():
            delta = 1 if increase else -1
            for s in exercise.sets:
                if not s.completed:
                    s.reps = max(0, s.reps + delta)

        return self._register_action(callback)

    def _register_action_change_weight(self, exercise: workouts.Exercise, increase: bool) -> str:
        def callback():
            delta = exercise.template.weight_delta if increase else -exercise.template.weight_delta
            for s in exercise.sets:
                if not s.completed:
                    s.weight = round(s.weight + delta, 2)

        return self._register_action(callback)

    def _register_action(self, callback: Callable[[], None]) -> str:
        action_id = str(uuid.uuid4())
        assert action_id not in self._actions
        self._actions[action_id] = callback
        return action_id


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
    action_id = query.data
    assert isinstance(action_id, str)

    # NOTE: CallbackQueries need to be answered, even if no notification to the
    # user is needed Some clients may have trouble otherwise. See
    # https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    try:
        active_workout.run_action(action_id)
    except ValueError:
        logging.warn(f"Action ID not present in actions list: {action_id}")
        assert update.message
        await update.message.reply_text("The desired action can't be processed. Please refresh the UI!")
        return
    await query.edit_message_reply_markup(active_workout.generate_workout_markup())


if __name__ == "__main__":
    config = load_config()
    app = ApplicationBuilder().token(config["bot_auth_token"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling(poll_interval=0.5)
