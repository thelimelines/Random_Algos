"""Transformable 3D meshes and STL loading for the software renderer."""

import struct
from pathlib import Path

import numpy as np
import pygame as pg

from matricies import (
    rotate_x as rotation_matrix_x,
    rotate_y as rotation_matrix_y,
    rotate_z as rotation_matrix_z,
    scale as scale_matrix,
    translate as translation_matrix,
)


# Each row represents one clip-space half-space: x/y/z must be between -w and w.
_CLIP_PLANES = np.array(
    [
        [1, 0, 0, 1],   # left:   x + w >= 0
        [-1, 0, 0, 1],  # right:  w - x >= 0
        [0, 1, 0, 1],   # bottom: y + w >= 0
        [0, -1, 0, 1],  # top:    w - y >= 0
        [0, 0, 1, 1],   # near:   z + w >= 0
        [0, 0, -1, 1],  # far:    w - z >= 0
    ],
    dtype=float,
)


def _read_stl_triangles(path):
    """Read an ASCII or binary STL file as an array of triangle vertices."""
    data = Path(path).read_bytes()

    # Binary STL has an 80-byte header, a 4-byte triangle count, then 50 bytes
    # per triangle. Checking the exact size also handles headers starting "solid".
    if len(data) >= 84:
        triangle_count = struct.unpack_from("<I", data, 80)[0]
        expected_size = 84 + triangle_count * 50
        if len(data) == expected_size:
            triangles = np.empty((triangle_count, 3, 3), dtype=float)
            for index, record in enumerate(struct.iter_unpack("<12fH", data[84:])):
                # The first three floats are the stored normal; the next nine
                # are the three vertex coordinates. Normals are not needed here.
                triangles[index] = np.asarray(record[3:12]).reshape(3, 3)
            return triangles

    # ASCII STL lists each facet as three lines beginning with "vertex".
    text = data.decode("ascii", errors="ignore")
    vertices = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[0].lower() == "vertex":
            try:
                vertices.append([float(value) for value in fields[1:4]])
            except ValueError as error:
                raise ValueError(f"Invalid vertex coordinates in STL file: {path}") from error

    if not vertices or len(vertices) % 3:
        raise ValueError(f"Could not read complete triangles from STL file: {path}")

    return np.asarray(vertices, dtype=float).reshape(-1, 3, 3)


class Object3D:
    """Store a cube's vertices and faces, and apply 3D transforms to it.

    Vertices use homogeneous coordinates ``(x, y, z, 1)`` so they can be
    multiplied by the 4x4 matrices in :mod:`matricies`. Transformations update
    the current vertex positions in place.
    """

    def __init__(self, render, stl_path=None, fit_size=1.0):
        """Create a unit cube or load a mesh from an STL file.

        When ``stl_path`` is supplied, the mesh is centered and its longest
        dimension is scaled to ``fit_size`` world units. Set ``fit_size`` to
        ``None`` to keep the STL's original coordinates and size.
        """
        self.render = render
        self.show_vertices = stl_path is None

        if stl_path is None:
            self.vertices = np.array(
                [
                    [0, 0, 0, 1],
                    [0, 1, 0, 1],
                    [1, 1, 0, 1],
                    [1, 0, 0, 1],
                    [0, 0, 1, 1],
                    [0, 1, 1, 1],
                    [1, 1, 1, 1],
                    [1, 0, 1, 1],
                ],
                dtype=float,
            )
            self.faces = np.array(
                [
                    [0, 1, 2, 3],
                    [4, 5, 6, 7],
                    [0, 4, 5, 1],
                    [2, 3, 7, 6],
                    [1, 2, 6, 5],
                    [0, 3, 7, 4],
                ],
                dtype=int,
            )
        else:
            self.load_stl(stl_path, fit_size=fit_size)

    def load_stl(self, path, fit_size=1.0):
        """Replace the current mesh with triangles loaded from an STL file.

        ``fit_size`` sets the desired longest dimension after centering. Pass
        ``None`` to preserve the file's original scale and position.
        """
        triangles = _read_stl_triangles(path)
        if triangles.size == 0:
            raise ValueError(f"STL file contains no triangles: {path}")

        positions = triangles.reshape(-1, 3)

        if not np.isfinite(positions).all():
            raise ValueError(f"STL file contains non-finite coordinates: {path}")

        if fit_size is not None:
            if not np.isfinite(fit_size) or fit_size <= 0:
                raise ValueError("fit_size must be a positive number or None")

            minimum = positions.min(axis=0)
            maximum = positions.max(axis=0)
            center = (minimum + maximum) / 2
            largest_dimension = np.max(maximum - minimum)
            positions = positions - center
            if largest_dimension > 0:
                positions *= fit_size / largest_dimension

        # Merge repeated triangle corners so the renderer doesn't draw the
        # same point many times for a dense mesh.
        unique_positions, face_indices = np.unique(
            positions, axis=0, return_inverse=True
        )
        self.vertices = np.column_stack(
            (unique_positions, np.ones(len(unique_positions)))
        )
        self.faces = face_indices.reshape(-1, 3)
        self.show_vertices = False

    def draw(self):
        """Draw the cube's faces and vertices to the renderer's screen."""
        self.screen_projection()

    def screen_projection(self):
        """Clip faces to the view volume, project them, and draw the result."""
        world_to_clip = (
            self.render.camera.camera_matrix()
            @ self.render.projection.projection_matrix
        )
        clip_vertices = self.vertices @ world_to_clip

        for face in self.faces:
            # Clipping can add vertices where a face crosses the view boundary.
            clipped_polygon = self._clip_polygon(clip_vertices[face])
            if len(clipped_polygon) < 3:
                continue

            clipped_polygon = np.asarray(clipped_polygon)
            ndc = clipped_polygon[:, :3] / clipped_polygon[:, 3, None]
            ndc_homogeneous = np.column_stack((ndc, np.ones(len(ndc))))
            screen_polygon = ndc_homogeneous @ self.render.projection.to_screen_matrix
            screen_polygon = np.rint(screen_polygon[:, :2]).astype(int)
            pg.draw.polygon(self.render.screen, pg.Color("orange"), screen_polygon, 3)

        if self.show_vertices:
            # Draw original vertices only when they lie inside all six planes.
            for vertex in clip_vertices:
                if np.all(_CLIP_PLANES @ vertex >= 0):
                    ndc = vertex[:3] / vertex[3]
                    ndc_homogeneous = np.append(ndc, 1.0)
                    screen_vertex = ndc_homogeneous @ self.render.projection.to_screen_matrix
                    screen_vertex = np.rint(screen_vertex[:2]).astype(int)
                    pg.draw.circle(self.render.screen, pg.Color("white"), screen_vertex, 5)

    @staticmethod
    def _clip_polygon(vertices):
        """Clip a polygon against all six homogeneous view-volume planes.

        An edge crossing a plane is cut at the point where it intersects that
        plane. This keeps the visible part of a face instead of dropping the
        entire face when one of its vertices is outside the view.
        """
        plane_distances = vertices @ _CLIP_PLANES.T
        if np.all(plane_distances >= 0):
            # Most faces are wholly inside; avoid the per-plane clipping loop.
            return [vertex.copy() for vertex in vertices]
        if np.any(np.all(plane_distances < 0, axis=0)):
            # All vertices are outside at least one shared plane, so no part
            # of this polygon can be visible.
            return []

        polygon = [vertex.copy() for vertex in vertices]

        for plane in _CLIP_PLANES:
            if not polygon:
                break

            clipped = []
            previous = polygon[-1]
            previous_distance = np.dot(plane, previous)

            for current in polygon:
                current_distance = np.dot(plane, current)
                previous_inside = previous_distance >= 0
                current_inside = current_distance >= 0

                if previous_inside != current_inside:
                    # The signed distances vary linearly along this edge.
                    amount = previous_distance / (previous_distance - current_distance)
                    intersection = previous + amount * (current - previous)
                    clipped.append(intersection)

                if current_inside:
                    clipped.append(current)

                previous = current
                previous_distance = current_distance

            polygon = clipped

        return polygon

    def translate(self, pos):
        """Move the cube by ``(x, y, z)`` and store its updated vertices."""
        self.vertices = self.vertices @ translation_matrix(pos)

    def scale(self, scale_to):
        """Scale the cube uniformly on all three axes by ``scale_to``."""
        self.vertices = self.vertices @ scale_matrix(scale_to)

    def rotate_x(self, angle):
        """Rotate the cube around the x-axis by ``angle`` radians."""
        self.vertices = self.vertices @ rotation_matrix_x(angle)

    def rotate_y(self, angle):
        """Rotate the cube around the y-axis by ``angle`` radians."""
        self.vertices = self.vertices @ rotation_matrix_y(angle)

    def rotate_z(self, angle):
        """Rotate the cube around the z-axis by ``angle`` radians."""
        self.vertices = self.vertices @ rotation_matrix_z(angle)
