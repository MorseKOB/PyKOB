"""
MIT License

Copyright (c) 2020-24 PyKOB - MorseKOB in Python

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
mkobenv.py

Persisted MKOB environment data.
"""
import json
from json import JSONDecodeError
import os.path
from typing import Any, Optional

from pykob import config, log, util


MKOB_ENV_FILENAME = "mkob.env"

KEY_CFG_FILEPATH = "cfgpath"

class EnvLoadError(Exception):
    pass

class MKOBEnv:
    def __init__(self) -> None:
        config.read_config()
        self._cfg_file_path: Optional[str] = None

        self._env_file_path: str = self._gen_env_path()
        self.load_env()
        return

    def _gen_env_path(self) -> str:
        path = os.path.join(config.user_config_dir, MKOB_ENV_FILENAME)
        return path


    @property
    def cfg_filepath(self) -> str:
        return self._cfg_file_path
    @cfg_filepath.setter
    def cfg_filepath(self, filepath) -> None:
        self._cfg_file_path = util.str_none_or_value(filepath)
        return

    def get_data(self) -> dict[str:Any]:
        data = dict()
        data[KEY_CFG_FILEPATH] = self._cfg_file_path
        return data

    def load_env(self) -> None:
        if os.path.exists(self._env_file_path):
            try:
                data: dict[str:Any]
                with open(self._env_file_path, 'r', encoding="utf-8") as fp:
                    data = json.load(fp)
                if data:
                    self._cfg_file_path = data.get(KEY_CFG_FILEPATH, None)
            except JSONDecodeError as jde:
                log.debug(jde)
                raise EnvLoadError(jde)
            except Exception as ex:
                log.debug(ex)
                raise EnvLoadError(ex)
            pass
        return

    def save_env(self) -> None:
        data = self.get_data()
        with open(self._env_file_path, 'w', encoding="utf-8") as fp:
            json.dump(data, fp)
            fp.write('\n')
        return
