from setuptools import find_packages
from setuptools import setup

setup(
    name="rainbow-iqn-apex-godot-car",
    install_requires=["atari-py", "redlock-py", "plotly", "opencv-python", "gym>=0.17.2"],
    packages=find_packages(),
)
