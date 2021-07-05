from setuptools import find_packages
from setuptools import setup

setup(
    name="rainbow-iqn-apex-godot-car",
    install_requires=["atari-py", "redlock-py>=1.0.8", "plotly>=5.1.0", "opencv-python>=4.5.2.54", "gym>=0.17.2"],
    packages=find_packages(),
)
