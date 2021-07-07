import json
from os.path import dirname, join as join_path
from typing import Union

from trakt.tv import TVShow

from plex_trakt_sync.factory import Factory

TESTS_DIR = dirname(__file__)
MOCK_DATA_DIR = join_path(TESTS_DIR, "mock_data")
factory = Factory()

# Patch config to use separate config for tests
config = factory.config()
config.config_file = join_path(TESTS_DIR, "config.json")
config.env_file = join_path(TESTS_DIR, ".env")


def load_mock(name: str):
    filename = join_path(MOCK_DATA_DIR, name)
    with open(filename, encoding='utf-8') as f:
        return json.load(f)


def make(cls=None, **kwargs) -> Union[TVShow]:
    cls = cls if cls is not None else "object"
    # https://stackoverflow.com/a/2827726/2314626
    return type(cls, (object,), kwargs)
