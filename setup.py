import os
import sys
from setuptools import setup, find_packages


def get_install_requirements():
    commons = [
        "flask==1.1.2", "flask_cors==3.0.10", "requests==2.25.1",
        "textblob==0.15.3", "numpy==1.20.2", "pandas==1.2.4",
        "matplotlib==3.4.1","praw==7.2.0", "geocoder==1.38.1"
    ]
    deps = commons
    if sys.platform == "darwin":
        deps += []
    elif sys.platform == "win32":
        deps += []
    elif sys.platform == "linux2":
        deps += []
    else:
        raise Exception("unsupported platform {}".format(sys.platform))

    return deps


with open(os.path.join(os.path.dirname(__file__), "version.py"), "r") as f:
    vf = f.read()

version = vf.split(" = ")[1][1:-2]

setup(
    name="forgery",
    version=version,
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={},
    install_requires=get_install_requirements()
)