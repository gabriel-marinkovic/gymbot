import logging
import os
import sys
import tomllib
from typing import Any, Dict, Optional

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


def _generate_workout_markup(workout) -> InlineKeyboardMarkup:
    keyboard = []
    for exercise, sets in workout:
        keyboard.append([InlineKeyboardButton(exercise.name, callback_data="bla")])
        row = []
        for i, s in enumerate(sets):
            rep_label = f"{s.reps} ({exercise.weight}kg)"
            row.append(InlineKeyboardButton(rep_label, callback_data=f"rep{i}"))
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


active_workout: Optional[workouts.WorkoutT] = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_workout

    if not update.message:
        logging.warn("Got update without 'message':", update)
        return

    message = "Starting a new workout!\n"
    if active_workout:
        message += "<code>WARNING: Overwriting previous workout!</code>\n"

    active_workout = workouts.make_workout()

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=_generate_workout_markup(active_workout))


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query
    # NOTE: CallbackQueries need to be answered, even if no notification to the
    # user is needed Some clients may have trouble otherwise. See
    # https://core.telegram.org/bots/api#callbackquery
    await query.answer()
    await query.edit_message_text(text=f"Selected option: {query.data}")


if __name__ == "__main__":
    config = load_config()
    app = ApplicationBuilder().token(config["bot_auth_token"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling(poll_interval=0.5)
