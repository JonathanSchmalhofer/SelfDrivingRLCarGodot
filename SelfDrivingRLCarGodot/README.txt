  ________           .___      __    __________          __  .__                   
 /  _____/  ____   __| _/_____/  |_  \______   \___.__._/  |_|  |__   ____   ____  
/   \  ___ /  _ \ / __ |/  _ \   __\  |     ___<   |  |\   __\  |  \ /  _ \ /    \ 
\    \_\  (  <_> ) /_/ (  <_> )  |    |    |    \___  | |  | |   Y  (  <_> )   |  \
 \______  /\____/\____ |\____/|__|    |____|    / ____| |__| |___|  /\____/|___|  /
        \/            \/                        \/                \/            \/ 
                                                                     v0.40.0 (2020-06-01)


Introduction
------------

This is a beta version of the Python module for Godot.

You are likely to encounter bugs and catastrophic crashes, if so please
report them to https://github.com/touilleMan/godot-python/issues.


Working features
----------------

Every Godot core features are expected to work fine:
- builtins (e.g. Vector2)
- Objects classes (e.g. Node)
- signals
- variable export
- rpc synchronisation

On top of that, mixing GDscript and Python code inside a project should work fine.


Using Pip
---------

On windows, pip must be installed first with `ensurepip`:
```
$ <pythonscript_dir>/windows-64/python.exe -m ensurepip  # Only need to do that once
$ <pythonscript_dir>/windows-64/python.exe -m pip install whatever
```

On linux/macOS, pip should be already present:
```
$ <pythonscript_dir>/x11-64/bin/python3 -m pip install whatever
```

Note you must use `python -m pip` to invoke pip (using the command `pip`
directly will likely fail in a cryptic manner)


Not so well features
--------------------

Exporting the project hasn't been tested at all (however exporting for linux should be pretty simple and may work out of the box...).


Have fun ;-)

  - touilleMan
