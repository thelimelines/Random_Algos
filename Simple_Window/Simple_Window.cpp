#include <raylib.h> // Window creation, mouse input, and drawing functions.

#include <vector>   // std::vector stores the positions of all added dots.

int main()
{
    // Tell raylib to let the user resize the window. Set this before InitWindow.
    SetConfigFlags(FLAG_WINDOW_RESIZABLE);

    // Create an 800x600 window with a title.
    InitWindow(800, 600, "Simple Window");

    // Limit the drawing loop to 240 frames per second.
    SetTargetFPS(240);

    // Each Vector2 contains the x and y pixel coordinates of one dot.
    std::vector<Vector2> dots;

    // Keep running until the user closes the window or presses Escape.
    while (!WindowShouldClose())
    {
        // This is true for one frame when the left mouse button is clicked.
        if (IsMouseButtonPressed(MOUSE_BUTTON_LEFT))
        {
            // Save the click location so the dot can be redrawn in later frames.
            dots.push_back(GetMousePosition());
        }

        // Begin a new frame and erase the previous frame to a black background.
        BeginDrawing();
        ClearBackground(BLACK);

        // Redraw every saved dot; otherwise clearing the frame would erase them.
        for (const Vector2 dot : dots)
        {
            // DrawCircleV takes a position, radius, and color.
            DrawCircleV(dot, 10.0F, WHITE);
        }

        // Finish and display this frame.
        EndDrawing();
    }

    // Release the window and graphics resources before exiting.
    CloseWindow();
    return 0;
}
