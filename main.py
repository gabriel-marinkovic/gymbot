import logging
import os
import sys
import tomllib
from typing import Any, Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, MessageHandler, CallbackQueryHandler

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


def _generate_workout_markup() -> InlineKeyboardMarkup:
    keyboard = []
    for (exercise, sets) in workouts.make_workout():
        keyboard.append([InlineKeyboardButton(exercise.name, callback_data="bla")])
        row = []
        for i, s in enumerate(sets):
            rep_label = f"{s.reps} ({exercise.weight}kg)"
            row.append(InlineKeyboardButton(rep_label, callback_data=f"rep{i}"))
        keyboard.append(row)
        keyboard.append([
            InlineKeyboardButton("⬆️ reps", callback_data="reps_up"),
            InlineKeyboardButton("⬇️ reps", callback_data="reps_down"),
            InlineKeyboardButton("⬆️ weight", callback_data="weight_up"),
            InlineKeyboardButton("⬇️ weight", callback_data="weight_down"),
        ])
    from pprint import pprint
    pprint(keyboard)
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        logging.warn("Got update without 'message':", update)
        return

    await update.message.reply_text("Starting a new workout!", reply_markup=_generate_workout_markup())


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
