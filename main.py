import enum
import logging
import os
import sys
import tomllib
from typing import Any, Dict, List, Literal, Tuple, Union, cast

import dataclass_wizard
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, MessageHandler, filters

import db
import workouts

logging.basicConfig(
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# `dataclass_wizard` global configuration.
class GlobalJSONMeta(dataclass_wizard.JSONWizard.Meta):
    debug_enabled = True
    key_transform_with_load = "SNAKE"
    key_transform_with_dump = "SNAKE"


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


def render_workout(workout: workouts.Workout) -> InlineKeyboardMarkup:
    keyboard = []
    for exercise in workout.exercises:
        keyboard.append([InlineKeyboardButton(exercise.template.name, callback_data=(MessageKind.EMPTY,))])
        row = []
        for i, s in enumerate(exercise.sets):
            checkbox = "✅ " if s.completed else ""
            label = f"{checkbox}{s.reps} ({s.weight}kg)"
            row.append(InlineKeyboardButton(label, callback_data=(MessageKind.SET_TOGGLE_COMPLETE, workout, s)))
        keyboard.append(row)
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⬆️ reps", callback_data=(MessageKind.EXERCISE_CHANGE_REPS, workout, exercise, True)
                ),
                InlineKeyboardButton(
                    "⬇️ reps",
                    callback_data=(MessageKind.EXERCISE_CHANGE_REPS, workout, exercise, False),
                ),
                InlineKeyboardButton(
                    "⬆️ weight",
                    callback_data=(MessageKind.EXERCISE_CHANGE_WEIGHT, workout, exercise, True),
                ),
                InlineKeyboardButton(
                    "⬇️ weight",
                    callback_data=(MessageKind.EXERCISE_CHANGE_WEIGHT, workout, exercise, False),
                ),
            ]
        )
    return InlineKeyboardMarkup(keyboard)


def get_workouts(user: telegram.User, context: ContextTypes.DEFAULT_TYPE) -> List[workouts.Workout]:
    assert context.user_data is not None
    if "active_workout" not in context.user_data:
        raw = db.load_json(db_connection, str(user.id))
        if not raw:
            raw = []
        context.user_data["active_workout"] = dataclass_wizard.fromlist(workouts.Workout, raw)
    return context.user_data["active_workout"]


def persist_workouts(user: telegram.User, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    workouts = get_workouts(user, context)
    context.user_data["active_workout"] = workouts
    raw = [dataclass_wizard.asdict(x) for x in workouts]
    db.store_json(db_connection, user.id, user.full_name, raw)


class MessageKind(enum.Enum):
    EMPTY = "empty"
    WORKOUT_START = "workout_start"
    WORKOUT_RENDER = "workout_render"
    SET_TOGGLE_COMPLETE = "set_toggle_complete"
    EXERCISE_CHANGE_REPS = "exercise_change_reps"
    EXERCISE_CHANGE_WEIGHT = "exercise_change_weight"


message_types = Union[
    Tuple[Literal[MessageKind.WORKOUT_START]],
    Tuple[Literal[MessageKind.WORKOUT_RENDER], workouts.Workout],
    Tuple[Literal[MessageKind.SET_TOGGLE_COMPLETE], workouts.Workout, workouts.WorkoutSet],
    Tuple[Literal[MessageKind.EXERCISE_CHANGE_REPS], workouts.Workout, workouts.Exercise, bool],
    Tuple[Literal[MessageKind.EXERCISE_CHANGE_WEIGHT], workouts.Workout, workouts.Exercise, bool],
]


async def handle_message(data: message_types, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat
    assert update.effective_user

    if data[0] == MessageKind.WORKOUT_START:
        existing_workouts = get_workouts(update.effective_user, context)
        workout = workouts.Workout.from_template(workouts.make_workout_template())
        existing_workouts.append(workout)
        persist_workouts(update.effective_user, context)
        await update.effective_chat.send_message("Starting a new workout!", reply_markup=render_workout(workout))
    elif data[0] == MessageKind.WORKOUT_RENDER:
        (workout,) = data[1:]
        await update.effective_chat.send_message("Resuming workout!", reply_markup=render_workout(workout))
    elif data[0] == MessageKind.SET_TOGGLE_COMPLETE:
        workout, s = data[1:]
        assert update.callback_query
        workout.toggle_set_completed(s)
        persist_workouts(update.effective_user, context)
        await update.callback_query.edit_message_reply_markup(render_workout(workout))
    elif data[0] == MessageKind.EXERCISE_CHANGE_REPS:
        workout, exercise, increase = data[1:]
        assert update.callback_query
        workout.change_reps(exercise, increase)
        persist_workouts(update.effective_user, context)
        await update.callback_query.edit_message_reply_markup(render_workout(workout))
    elif data[0] == MessageKind.EXERCISE_CHANGE_WEIGHT:
        assert update.callback_query
        workout, exercise, increase = data[1:]
        workout.change_weight(exercise, increase)
        persist_workouts(update.effective_user, context)
        await update.callback_query.edit_message_reply_markup(render_workout(workout))


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
    assert update.effective_message
    assert update.effective_user

    UNKNOWN_COMMAND_MESSAGE = "Unknown command! Type <code>help</code> for a list of available commands."

    text = update.effective_message.text if update.effective_message.text else ""
    command = text.strip().lower().split()
    if not command:
        await update.effective_message.reply_text(UNKNOWN_COMMAND_MESSAGE)
        return

    name, _ = command[0], command[1:]
    if name == "start" or name == "workout":
        existing_workouts = get_workouts(update.effective_user, context)
        if not existing_workouts:
            await handle_message((MessageKind.WORKOUT_START,), update, context)
        else:
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Resume", callback_data=(MessageKind.WORKOUT_RENDER, existing_workouts[-1])
                        ),
                        InlineKeyboardButton("Start New", callback_data=(MessageKind.WORKOUT_START,)),
                    ]
                ],
            )
            await update.effective_message.reply_text(
                "There is already a workout in progress. Do you want to resume it?", reply_markup=kb
            )

    elif name == "help":
        message = "List of commands:"
        message += "\n<code>start</code>, <code>workout</code>"
        message += "\n    Start a new workout."
        message += "\n<code>help</code>"
        message += "\n    Show this message."
        await update.effective_message.reply_text(message, parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text(UNKNOWN_COMMAND_MESSAGE)


if __name__ == "__main__":
    config = load_config()

    if "db_path" not in config:
        logging.error("Missing property 'db_path' in CONFIG.")
        exit(1)
    db_connection = db.open_sqlite_connection(config["db_path"])

    app = ApplicationBuilder().token(config["bot_auth_token"]).arbitrary_callback_data(True).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
