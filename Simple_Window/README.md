# Simple Window

A small resizable raylib window. Click anywhere in the window to add a white dot. The dots stay visible because the program redraws all saved positions every frame.

## Build and run from the VS Code terminal

Starting at the repository root, run:

```powershell
Set-Location .\Simple_Window
cmake --preset windows-msvc
cmake --build --preset windows-debug
.\build\Debug\Simple_Window.exe
```

The commands have three stages: configure prepares the build and installs raylib; build compiles and links the executable; the last command runs it. The executable and generated files go under `Simple_Window\build`. The first configure can take longer because vcpkg builds raylib and its dependencies.

To use the CMake Tools buttons in VS Code, open `Simple_Window` itself as the folder, then select the `windows-msvc` configure preset. The build preset is `windows-debug`.

