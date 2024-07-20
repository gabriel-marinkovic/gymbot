import logging
import os
import sys
import tomllib
from typing import Any, Dict

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, MessageHandler

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        logging.warn("Got update without 'effective_chat':", update)
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, talk to me!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        logging.warn("Got update without 'effective_chat':", update)
        return
    if update.message and update.message.text:
        text = update.message.text
    else:
        logging.warn("Expected the update object to have 'message.text':", update)
        text = "<DEFAULT TEXT>"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


if __name__ == "__main__":
    config = load_config()
    app = ApplicationBuilder().token(config["bot_auth_token"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), echo))
    app.run_polling(poll_interval=0.5)
