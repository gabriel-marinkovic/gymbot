import uuid
import logging
import os
import sys
import tomllib
from typing import Any, Dict, Optional, List, Callable

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


class ActionStore:
    def __init__(self, limit: int = 10000):
        self._actions: Dict[str, Callable[[], Any]] = {}
        self._limit = limit

    def register(self, action: Callable[[], Any]) -> str:
        if len(self._actions) > self._limit:
            to_remove = self._limit // 10
            for key in list(self._actions.keys())[:to_remove]:
                del self._actions[key]
        action_id = str(uuid.uuid4())
        self._actions[action_id] = action
        return action_id

    def register_empty(self) -> str:
        return self.register(lambda: None)

    def run_action(self, action_id: str) -> Any:
        try:
            action = self._actions[action_id]
        except KeyError:
            raise ValueError()
        return action()


class Workout:
    id: str
    exercises: List[workouts.Exercise]

    def __init__(self, exercises: List[workouts.ExerciseTemplate]):
        self.id = str(uuid.uuid4())
        self.exercises = [workouts.Exercise(ex) for ex in exercises]

    def generate_workout_markup(self, actions: ActionStore) -> InlineKeyboardMarkup:
        keyboard = []
        for exercise in self.exercises:
            keyboard.append([InlineKeyboardButton(exercise.template.name, callback_data=actions.register_empty())])
            row = []
            for i, s in enumerate(exercise.sets):
                checkbox = "✅ " if s.completed else ""
                label = f"{checkbox}{s.reps} ({s.weight}kg)"
                row.append(
                    InlineKeyboardButton(
                        label, callback_data=self._register_call(actions, self._toggle_set_completed, s)
                    )
                )
            keyboard.append(row)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "⬆️ reps",
                        callback_data=self._register_call(actions, self._change_reps, exercise, True),
                    ),
                    InlineKeyboardButton(
                        "⬇️ reps",
                        callback_data=self._register_call(actions, self._change_reps, exercise, False),
                    ),
                    InlineKeyboardButton(
                        "⬆️ weight",
                        callback_data=self._register_call(actions, self._change_weight, exercise, True),
                    ),
                    InlineKeyboardButton(
                        "⬇️ weight",
                        callback_data=self._register_call(actions, self._change_weight, exercise, False),
                    ),
                ]
            )
        return InlineKeyboardMarkup(keyboard)

    def _toggle_set_completed(self, s: workouts.WorkoutSet) -> "Workout":
        s.completed = not s.completed
        return self

    def _change_reps(self, exercise: workouts.Exercise, increase: bool) -> "Workout":
        delta = 1 if increase else -1
        for s in exercise.sets:
            if not s.completed:
                s.reps = max(0, s.reps + delta)
        return self

    def _change_weight(self, exercise: workouts.Exercise, increase: bool) -> "Workout":
        delta = exercise.template.weight_delta if increase else -exercise.template.weight_delta
        for s in exercise.sets:
            if not s.completed:
                s.weight = round(s.weight + delta, 2)
        return self

    def _register_call(self, action_store: ActionStore, method: Callable, *args: Any) -> str:
        return action_store.register(lambda: method(*args))


def get_action_store(context: ContextTypes.DEFAULT_TYPE) -> ActionStore:
    assert context.user_data is not None
    if "action_store" not in context.user_data:
        context.user_data["action_store"] = ActionStore()
    return context.user_data["action_store"]


def get_workout(context: ContextTypes.DEFAULT_TYPE) -> Optional[Workout]:
    assert context.user_data is not None
    if "active_workout" not in context.user_data:
        context.user_data["active_workout"] = None
    return context.user_data["active_workout"]


def set_workout(context: ContextTypes.DEFAULT_TYPE, workout: Optional[Workout]):
    assert context.user_data is not None
    context.user_data["active_workout"] = workout


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    actions = get_action_store(context)

    query = update.callback_query
    assert query
    # NOTE: CallbackQueries need to be answered, even if no notification to the
    # user is needed Some clients may have trouble otherwise. See
    # https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    assert query.data
    action_id = query.data
    assert isinstance(action_id, str)
    try:
        workout = actions.run_action(action_id)
        assert isinstance(workout, Workout)
    except ValueError:
        logging.warn(f"Action ID not present in actions list: {action_id}")
        assert update.effective_chat
        await update.effective_chat.send_message("The desired action can't be processed. Please refresh the UI!")
        return
    await query.edit_message_reply_markup(workout.generate_workout_markup(actions))



async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.message

    UNKNOWN_COMMAND_MESSAGE = "Unknown command! Type <code>help</code> for a list of available commands."

    text = update.message.text if update.message.text else ""
    command = text.strip().lower().split()
    if not command:
        await update.message.reply_text(UNKNOWN_COMMAND_MESSAGE)
        return

    name, args = command[0], command[1:]
    if name == "start" or name == "workout":
        message = "Starting a new workout!\n"
        if get_workout(context):
            message += "<code>WARNING: Overwriting previous workout!</code>\n"
        workout = Workout(workouts.make_workout_template())
        set_workout(context, workout)
        await update.message.reply_text(
            message, parse_mode=ParseMode.HTML, reply_markup=workout.generate_workout_markup(get_action_store(context))
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
    app = ApplicationBuilder().token(config["bot_auth_token"]).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()
