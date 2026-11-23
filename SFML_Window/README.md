# SFML Window

A minimal SFML 3 window built with CMake and vcpkg.

## Build and run from the repository root

```powershell
Set-Location .\SFML_Window
cmake --preset windows-msvc
cmake --build --preset windows-debug
.\build\Debug\SFML_Window.exe
```

The first configure installs SFML and its dependencies into `SFML_Window\build\vcpkg_installed`. It requires CMake, Visual Studio 2019 or newer C++ build tools, and `VCPKG_ROOT` pointing to your vcpkg checkout. The preset uses the x64 MSVC triplet.
