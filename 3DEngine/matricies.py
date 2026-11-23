"""Create 4x4 transformation matrices for points in 3D space.

These matrices use the row-vector convention: multiply a point on the left
(`point @ matrix`). Translation therefore appears in the matrix's last row.
Rotation angles are measured in radians.
"""

import math

import numpy as np


def translate(pos):
    """Return a matrix that moves points by ``(x, y, z)``.

    ``pos`` must contain the translation along the x, y, and z axes, in that
    order. For example, ``translate((2, 0, 0))`` moves a point two units along
    the x-axis.
    """
    tx, ty, tz = pos
    return np.array(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [tx, ty, tz, 1],
        ]
    )


def rotate_x(angle):
    """Return a matrix that rotates points around the x-axis by ``angle``."""
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        [
            [1, 0, 0, 0],
            [0, cosine, sine, 0],
            [0, -sine, cosine, 0],
            [0, 0, 0, 1],
        ]
    )


def rotate_y(angle):
    """Return a matrix that rotates points around the y-axis by ``angle``."""
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        [
            [cosine, 0, -sine, 0],
            [0, 1, 0, 0],
            [sine, 0, cosine, 0],
            [0, 0, 0, 1],
        ]
    )


def rotate_z(angle):
    """Return a matrix that rotates points around the z-axis by ``angle``."""
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return np.array(
        [
            [cosine, sine, 0, 0],
            [-sine, cosine, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
    )


def scale(n):
    """Return a matrix that scales all three spatial axes by ``n``."""
    return np.array(
        [
            [n, 0, 0, 0],
            [0, n, 0, 0],
            [0, 0, n, 0],
            [0, 0, 0, 1],
        ]
    )
