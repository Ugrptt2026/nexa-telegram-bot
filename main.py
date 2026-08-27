"""Nexa uygulamasını başlatır."""

from nexa.bot import run_polling
from nexa.config import Settings


if __name__ == "__main__":
    run_polling(Settings.from_env())
