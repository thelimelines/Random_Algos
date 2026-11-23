"""Camera settings and world-to-camera transformation matrices."""

import math

import numpy as np
import pygame as pg


class Camera:
    """Represent a camera and build its view matrix for row-vector points.

    The camera looks along its forward axis. Vertices are transformed with
    ``vertices @ camera_matrix()``; the camera's translation is applied before
    its orientation.
    """

    def __init__(self, render, position):
        """Set the camera position, basis directions, field of view, and clip planes.

        ``position`` is an ``(x, y, z)`` coordinate. The renderer supplies the
        viewport dimensions used to calculate the vertical field of view.
        """
        self.render = render
        self.position = np.array([*position, 1.0], dtype=float)

        # Direction vectors use w=0 so translations do not affect them.
        self.forward = np.array([0.0, 0.0, 1.0, 0.0])
        self.up = np.array([0.0, 1.0, 0.0, 0.0])
        self.right = np.array([1.0, 0.0, 0.0, 0.0])

        self.h_fov = math.pi / 3
        self.v_fov = self.h_fov * (render.HEIGHT / render.WIDTH)
        self.near_plane = 0.1
        self.far_plane = 100.0
        self.moving_speed = 0.02
        self.rotation_speed = 0.01

    def control(self):
        """Move with WASD and Q/E; turn with the arrow keys."""
        keys = pg.key.get_pressed()

        if keys[pg.K_a]:
            self.position -= self.right * self.moving_speed
        if keys[pg.K_d]:
            self.position += self.right * self.moving_speed
        if keys[pg.K_w]:
            self.position += self.forward * self.moving_speed
        if keys[pg.K_s]:
            self.position -= self.forward * self.moving_speed
        if keys[pg.K_q]:
            self.position += self.up * self.moving_speed
        if keys[pg.K_e]:
            self.position -= self.up * self.moving_speed

        if keys[pg.K_LEFT]:
            self.rotate_yaw(-self.rotation_speed)
        if keys[pg.K_RIGHT]:
            self.rotate_yaw(self.rotation_speed)
        if keys[pg.K_UP]:
            self.rotate_pitch(-self.rotation_speed)
        if keys[pg.K_DOWN]:
            self.rotate_pitch(self.rotation_speed)

    def rotate_yaw(self, angle):
        """Turn the camera left or right around the world up axis."""
        world_up = np.array([0.0, 1.0, 0.0])
        self.right = self._rotate_direction(self.right, world_up, angle)
        self.forward = self._rotate_direction(self.forward, world_up, angle)

    def rotate_pitch(self, angle):
        """Turn the camera up or down around its local right axis."""
        self.up = self._rotate_direction(self.up, self.right, angle)
        self.forward = self._rotate_direction(self.forward, self.right, angle)

    @staticmethod
    def _rotate_direction(direction, axis, angle):
        """Rotate a direction vector around an axis using Rodrigues' formula."""
        axis = axis[:3] / np.linalg.norm(axis[:3])
        vector = direction[:3]
        cosine = math.cos(angle)
        sine = math.sin(angle)
        rotated = (
            vector * cosine
            + np.cross(axis, vector) * sine
            + axis * np.dot(axis, vector) * (1 - cosine)
        )
        return np.array([*rotated, 0.0])

    def translate_matrix(self):
        """Return a matrix that moves world points relative to the camera."""
        x, y, z, _ = self.position
        return np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [-x, -y, -z, 1],
            ],
            dtype=float,
        )

    def rotate_matrix(self):
        """Return a matrix that expresses points in the camera's basis."""
        right_x, right_y, right_z = self.right[:3]
        up_x, up_y, up_z = self.up[:3]
        forward_x, forward_y, forward_z = self.forward[:3]

        return np.array(
            [
                [right_x, up_x, forward_x, 0],
                [right_y, up_y, forward_y, 0],
                [right_z, up_z, forward_z, 0],
                [0, 0, 0, 1],
            ],
            dtype=float,
        )

    def camera_matrix(self):
        """Return the combined world-to-camera matrix."""
        return self.translate_matrix() @ self.rotate_matrix()
