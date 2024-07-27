import enum
import uuid
import logging
import os
import sys
import tomllib
from typing import Any, Dict, Optional, List, cast, Union, Literal, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CallbackQueryHandler, filters

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

    def __init__(self, exercises: List[workouts.ExerciseTemplate]):
        self.id = str(uuid.uuid4())
        self.exercises = [workouts.Exercise(ex) for ex in exercises]

    def generate_workout_markup(self) -> InlineKeyboardMarkup:
        keyboard = []
        for exercise in self.exercises:
            keyboard.append([InlineKeyboardButton(exercise.template.name, callback_data=(MessageKind.EMPTY,))])
            row = []
            for i, s in enumerate(exercise.sets):
                checkbox = "✅ " if s.completed else ""
                label = f"{checkbox}{s.reps} ({s.weight}kg)"
                row.append(InlineKeyboardButton(label, callback_data=(MessageKind.SET_TOGGLE_COMPLETE, self, s)))
            keyboard.append(row)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⬆️ reps", callback_data=(MessageKind.EXERCISE_CHANGE_REPS, self, exercise, True)
                    ),
                    InlineKeyboardButton(
                        "⬇️ reps",
                        callback_data=(MessageKind.EXERCISE_CHANGE_REPS, self, exercise, False),
                    ),
                    InlineKeyboardButton(
                        "⬆️ weight",
                        callback_data=(MessageKind.EXERCISE_CHANGE_WEIGHT, self, exercise, True),
                    ),
                    InlineKeyboardButton(
                        "⬇️ weight",
                        callback_data=(MessageKind.EXERCISE_CHANGE_WEIGHT, self, exercise, False),
                    ),
                ]
            )
        return InlineKeyboardMarkup(keyboard)

    def _toggle_set_completed(self, s: workouts.WorkoutSet):
        s.completed = not s.completed

    def _change_reps(self, exercise: workouts.Exercise, increase: bool):
        delta = 1 if increase else -1
        for s in exercise.sets:
            if not s.completed:
                s.reps = max(0, s.reps + delta)

    def _change_weight(self, exercise: workouts.Exercise, increase: bool):
        delta = exercise.template.weight_delta if increase else -exercise.template.weight_delta
        for s in exercise.sets:
            if not s.completed:
                s.weight = round(s.weight + delta, 2)


def get_workout(context: ContextTypes.DEFAULT_TYPE) -> Optional[Workout]:
    assert context.user_data is not None
    if "active_workout" not in context.user_data:
        context.user_data["active_workout"] = None
    return context.user_data["active_workout"]


def set_workout(context: ContextTypes.DEFAULT_TYPE, workout: Optional[Workout]):
    assert context.user_data is not None
    context.user_data["active_workout"] = workout


class MessageKind(enum.Enum):
    EMPTY = "empty"
    WORKOUT_START = "workout_start"
    WORKOUT_RENDER = "workout_render"
    SET_TOGGLE_COMPLETE = "set_toggle_complete"
    EXERCISE_CHANGE_REPS = "exercise_change_reps"
    EXERCISE_CHANGE_WEIGHT = "exercise_change_weight"


message_types = Union[
    Tuple[Literal[MessageKind.WORKOUT_START]],
    Tuple[Literal[MessageKind.WORKOUT_RENDER], Workout],
    Tuple[Literal[MessageKind.SET_TOGGLE_COMPLETE], Workout, workouts.WorkoutSet],
    Tuple[Literal[MessageKind.EXERCISE_CHANGE_REPS], Workout, workouts.Exercise, bool],
    Tuple[Literal[MessageKind.EXERCISE_CHANGE_WEIGHT], Workout, workouts.Exercise, bool],
]


async def handle_message(data: message_types, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat

    if data[0] == MessageKind.WORKOUT_START:
        workout = Workout(workouts.make_workout_template())
        set_workout(context, workout)
        await update.effective_chat.send_message(
            "Starting a new workout!", reply_markup=workout.generate_workout_markup()
        )
    elif data[0] == MessageKind.WORKOUT_RENDER:
        (workout,) = data[1:]
        await update.effective_chat.send_message("Resuming workout!", reply_markup=workout.generate_workout_markup())
    elif data[0] == MessageKind.SET_TOGGLE_COMPLETE:
        workout, s = data[1:]
        assert update.callback_query
        workout._toggle_set_completed(s)
        await update.callback_query.edit_message_reply_markup(workout.generate_workout_markup())
    elif data[0] == MessageKind.EXERCISE_CHANGE_REPS:
        workout, exercise, increase = data[1:]
        assert update.callback_query
        workout._change_reps(exercise, increase)
        await update.callback_query.edit_message_reply_markup(workout.generate_workout_markup())
    elif data[0] == MessageKind.EXERCISE_CHANGE_WEIGHT:
        assert update.callback_query
        workout, exercise, increase = data[1:]
        workout._change_weight(exercise, increase)
        await update.callback_query.edit_message_reply_markup(workout.generate_workout_markup())


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.callback_query
    # NOTE: CallbackQueries need to be answered, even if no notification to the
    # user is needed Some clients may have trouble otherwise. See
    # https://core.telegram.org/bots/api#callbackquery
    await update.callback_query.answer()
    data = update.callback_query.data
    try:
        assert isinstance(data, tuple)
        assert len(data) > 0
        assert data[0] in MessageKind
    except AssertionError:
        logging.error(f'Unknown message: "{data}"')
        # TODO: General error handler.
        assert update.effective_chat
        await update.effective_chat.send_message(f"Fatal bot error, unknown message! {data}")
        return
    await handle_message(cast(message_types, data), update, context)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.message

    UNKNOWN_COMMAND_MESSAGE = "Unknown command! Type <code>help</code> for a list of available commands."

    text = update.message.text if update.message.text else ""
    command = text.strip().lower().split()
    if not command:
        await update.message.reply_text(UNKNOWN_COMMAND_MESSAGE)
        return

    name, _ = command[0], command[1:]
    if name == "start" or name == "workout":
        existing_workout = get_workout(context)
        if not existing_workout:
            await handle_message((MessageKind.WORKOUT_START,), update, context)
        else:
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Resume", callback_data=(MessageKind.WORKOUT_RENDER, existing_workout)),
                        InlineKeyboardButton("Start New", callback_data=(MessageKind.WORKOUT_START,)),
                    ]
                ],
            )
            await update.message.reply_text(
                "There is already a workout in progress. Do you want to resume it?", reply_markup=kb
            )

    elif name == "help":
        message = "List of commands:"
        message += "\n<code>start</code>, <code>workout</code>"
        message += "\n    Start a new workout."
        message += "\n<code>help</code>"
        message += "\n    Show this message."
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(UNKNOWN_COMMAND_MESSAGE)


if __name__ == "__main__":
    config = load_config()
    app = ApplicationBuilder().token(config["bot_auth_token"]).arbitrary_callback_data(True).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
