SelfDrivingRLCarGodot
=======

License: MIT

A Godot Project for a Self Driving Car Game using Reinforcement Learning

Introduction
------------
tbd

Requirements/Installation
------------
Tested with

- Ubuntu 20.04
- conda 4.9.2
- Godot 3.3.2

Get the newest sources from Github:
```bash
$ git clone https://github.com/JonathanSchmalhofer/SelfDrivingRLCarGodot
```

To install all dependencies with Anaconda run
```bash
$ cd SelfDrivingRLCarGodot\python\conda
$ conda env create -f environment.yml`
```

To verify the environment was created successfully run
```bash
$ conda env list
```
One of the rows should list an environment named `godot-sl-car`.

To activate the conda environment run
```bash
$ conda activate godot-sl-car
$ echo $CONDA_DEFAULT_ENV # this should output godot-sl-car
```
