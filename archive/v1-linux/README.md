# Archive: Dictator v1 (Linux-only)

This directory contains the original v1 implementation of Dictator which was Linux-only
and used xdotool, PulseAudio, and systemd directly.

It has been superseded by the v2 rewrite in the root `dictator/` package which:
- Supports both Windows and Linux
- Uses proper design patterns (State, Strategy, Factory, Observer, Command, etc.)
- Includes a Windows installer (PyInstaller + Inno Setup)
- Has comprehensive fault tolerance and safety guarantees

Kept for reference only. Do not use these files for new development.
