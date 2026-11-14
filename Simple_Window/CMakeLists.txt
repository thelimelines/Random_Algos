cmake_minimum_required(VERSION 4.4)

# Give the project a name and tell CMake that it contains C++ code
project(Simple_Window LANGUAGES CXX)

# Use the C++20 language standard, require compiler support for it,
# and disable compiler-specific C++ extensions.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Ask CMake to locate raylib. The vcpkg toolchain path in the preset
# makes vcpkg-installed packages visible to this find_package call.
find_package(raylib CONFIG REQUIRED)

# Compile Simple_Window.cpp and name the resulting executable Simple_Window.
add_executable(Simple_Window Simple_Window.cpp)

# Link raylib into this executable so its window, input, and drawing
# functions are available to the program.
target_link_libraries(Simple_Window PRIVATE raylib)
