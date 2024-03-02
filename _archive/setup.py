"""
MIT License

Copyright (c) 2020 PyKOB - MorseKOB in Python

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

from distutils.core import setup
from pathlib import Path

# Resource/Data folder
root_folder = Path(__file__).parent.resolve()
resource_folder = root_folder / "pykob/resources"
data_folder = root_folder / "pykob/data"
print("Root:", str(root_folder))
print("Data:", str(data_folder))
print("Recources:", str(resource_folder))

setup(name = "PyKOB",
      version = "1.2",
      description = "MorseKOB library package",
      author = "Les Kerr",
      author_email = "les@morsekob.org",
      url = "https://github.com/MorseKOB/PyKOB/",
      packages = ["pykob"],
      package_data = {"pykob": ["resources/*.wav", "data/*.txt"]}
     )
