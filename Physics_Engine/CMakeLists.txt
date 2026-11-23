cmake_minimum_required(VERSION 3.28)
project(Physics_Engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(SFML 3 CONFIG REQUIRED COMPONENTS Graphics)
find_package(Threads REQUIRED)

add_library(physics_simulation STATIC BasicCollision.cpp Benchmark.cpp)
target_link_libraries(physics_simulation PRIVATE Threads::Threads)

function(add_collision_demo name mode title)
    add_executable(${name} Window.cpp)
    target_compile_definitions(${name} PRIVATE PHYSICS_MODE=${mode} PHYSICS_TITLE="${title}")
    target_link_libraries(${name} PRIVATE physics_simulation SFML::Graphics)
endfunction()

add_collision_demo(Physics_Naive Naive "Physics - Naive")
add_collision_demo(Physics_Grid Grid "Physics - Spatial Grid")
add_collision_demo(Physics_Halo Halo "Physics - Threaded Halo Grid")
