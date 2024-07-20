import os
import tomllib


def load_config():
    try:
        path = os.environ["CONFIG"]
    except KeyError:
        print("'CONFIG' environment contain the path to the config file")
    with open(path, "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            print(f"Failed to parse config from '{path}': {e}")


if __name__ == "__main__":
    print("Bot token:", load_config()["bot_auth_token"])