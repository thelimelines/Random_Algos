# Ball collision demos

Each executable opens a 1080 × 1080 SFML window. Balls spawn near (36, 108), with a rightward launch velocity and gravity. Each window spawns up to 3,000 balls. Press **R** to restart the same stream or **Esc** to close the window.

| Executable | Collision search |
| --- | --- |
| `Physics_Naive.exe` | Checks every unique pair of balls. |
| `Physics_Grid.exe` | Checks balls in the same or adjacent cells of a 20 px uniform grid. |
| `Physics_Halo.exe` | Assigns 9 × 9 cell tiles to persistent workers. Each tile can read one cell beyond its edges, including the corners. |

The shared solver uses position Verlet with gravity. Balls launch at 300–620 px/s to the right, with no drag during free flight. The solver predicts the centers for the substep, then projects overlapping pairs apart. Those corrected positions feed into the next substep. A limit on speed added by contact keeps an overlapping spawn from turning a large correction into an extreme launch speed.

The grid variants sort nearby pairs by ball index to match the naive loop. A single thread runs up to 16 solver sweeps in alternating directions. It refreshes the search when corrections can move a ball into an unlisted contact. Wall constraints keep the balls inside the window throughout the solve. The solver was inspired by [johnBuffer's Verlet solver](https://github.com/johnBuffer/VerletSFML-Multithread/tree/main/src/physics).

Physics advances at 60 ticks per second, with eight 1/480 second substeps per tick. The emitter uses a fixed seed and launches a ball every two ticks, even if another ball is in its path. The collision solver separates overlapping balls.

The window title reports average frame time and FPS about four times a second. The emitter pauses below 30 FPS and resumes at 32 FPS, skipping the releases missed during the pause. Balls already in the scene keep moving.

## Build and run

From the repository root, using CMake 3.28+, Visual Studio 2019 C++ Build Tools and `VCPKG_ROOT` pointing to your vcpkg checkout:

```powershell
Set-Location .\Physics_Engine
cmake --preset windows-msvc
cmake --build --preset windows-release
.\build\Release\Physics_Naive.exe
.\build\Release\Physics_Grid.exe
.\build\Release\Physics_Halo.exe
```

The current demos show **(Verlet)** in their window titles. Close a running demo and launch it again after rebuilding to load the new executable.

To reuse the existing x64 SFML install from the sibling `SFML_Window` project, configure with the same preset and pass `-DVCPKG_MANIFEST_INSTALL=OFF "-DVCPKG_INSTALLED_DIR:PATH=$PWD/../SFML_Window/build/vcpkg_installed"`.

## Compare results

```powershell
.\build\Release\Physics_Halo.exe --benchmark
```

The headless benchmark checks all three modes against a boundary scenario, verifies that a prebuilt stack settles, then times the grid and halo modes separately over 105 seconds of simulation. It compares sorted collision candidates and the exact float bits of each ball's current and previous positions after each substep. An independent check measures the deepest overlap at the end of every 60 Hz tick, which is the state used for drawing. A mismatch or an overlap greater than 1 px at a displayed tick fails this benchmark. Comparisons, overlap measurements and rendering are excluded from the timings.
