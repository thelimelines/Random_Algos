"""Create a perspective projection matrix for the software renderer."""

import math

import numpy as np


class Projection:
    """Build a camera-space to clip-space perspective matrix.

    The matrix follows the engine's row-vector convention, so transform a
    homogeneous camera-space point with ``point @ projection_matrix``. The
    resulting coordinates still need perspective division before drawing.
    """

    def __init__(self, render):
        """Create the projection matrix from the renderer's camera settings."""
        camera = render.camera
        near = camera.near_plane
        far = camera.far_plane

        right = math.tan(camera.h_fov / 2)
        left = -right
        top = math.tan(camera.v_fov / 2)
        bottom = -top

        m00 = 2 / (right - left)
        m11 = 2 / (top - bottom)
        m22 = (far + near) / (far - near)
        m32 = -2 * near * far / (far - near)

        self.projection_matrix = np.array(
            [
                [m00, 0, 0, 0],
                [0, m11, 0, 0],
                [0, 0, m22, 1],
                [0, 0, m32, 0],
            ],
            dtype=float,
        )

        HW, HH = render.H_WIDTH, render.H_HEIGHT
        self.to_screen_matrix = np.array([
                [HW, 0, 0, 0],
                [0, -HH, 0, 0],
                [0, 0, 1, 0],
                [HW, HH, 0, 1],
            ])