"""Interactive Python version of the Ten Minute Physics Euler fluid demo.

Requires NumPy and Pillow (Tkinter is included with most Python installations):
    python -m pip install numpy Pillow
    python SimpleFluid.py

The simulation uses a staggered MAC grid: horizontal and vertical velocity
components live on cell faces, while pressure and smoke live at cell centres.
"""

# Copyright 2022 Matthias Müller - Ten Minute Physics,
# https://github.com/matthias-research/pages/blob/master/tenMinutePhysics/17-fluidSim.html

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageTk
except ImportError as exc:
    raise SystemExit(
        "SimpleFluid requires NumPy and Pillow. Install them with: "
        "python -m pip install numpy Pillow"
    ) from exc


U_FIELD = 0
V_FIELD = 1
S_FIELD = 2


class Fluid:
    """Incompressible smoke simulation on a staggered two-dimensional grid."""

    def __init__(self, density: float, num_x: int, num_y: int, cell_size: float):
        # Two ghost-cell layers make boundary sampling and face velocities easy.
        self.num_x = num_x + 2
        self.num_y = num_y + 2
        self.num_cells = self.num_x * self.num_y
        self.density = float(density)
        self.h = float(cell_size)

        shape = (self.num_x, self.num_y)
        self.u = np.zeros(shape, dtype=np.float32)
        self.v = np.zeros(shape, dtype=np.float32)
        self.new_u = np.zeros(shape, dtype=np.float32)
        self.new_v = np.zeros(shape, dtype=np.float32)
        self.p = np.zeros(shape, dtype=np.float32)
        self.s = np.zeros(shape, dtype=np.float32)  # 1 for fluid, 0 for solid
        self.m = np.ones(shape, dtype=np.float32)    # smoke density / dye
        self.new_m = np.ones(shape, dtype=np.float32)
        self.over_relaxation = 1.9

    def integrate(self, dt: float, gravity: float) -> None:
        """Apply gravity to vertical faces surrounded by fluid."""
        open_face = (self.s[1:, 1:-1] != 0.0) & (self.s[1:, :-2] != 0.0)
        vertical_velocity = self.v[1:, 1:-1]
        vertical_velocity[open_face] += gravity * dt

    def solve_incompressibility(self, num_iters: int, dt: float) -> None:
        """Project velocity toward zero divergence with relaxed iterations."""
        self.p.fill(0.0)
        cp = self.density * self.h / dt

        # Red/black Gauss–Seidel keeps each half-sweep independent: cells in one
        # colour do not share faces. This retains the reference solver's
        # sequential relaxation behaviour while vectorizing the grid work.
        checkerboard = (
            np.arange(1, self.num_x - 1)[:, None]
            + np.arange(1, self.num_y - 1)[None, :]
        ) & 1
        for _ in range(num_iters):
            for colour in (0, 1):
                sx0 = self.s[:-2, 1:-1]
                sx1 = self.s[2:, 1:-1]
                sy0 = self.s[1:-1, :-2]
                sy1 = self.s[1:-1, 2:]
                neighbours = sx0 + sx1 + sy0 + sy1
                divergence = (
                    self.u[2:, 1:-1] - self.u[1:-1, 1:-1]
                    + self.v[1:-1, 2:] - self.v[1:-1, 1:-1]
                )

                correction = np.zeros_like(divergence)
                np.divide(
                    -divergence * self.over_relaxation,
                    neighbours,
                    out=correction,
                    where=(
                        (neighbours > 0.0)
                        & (self.s[1:-1, 1:-1] != 0.0)
                        & (checkerboard == colour)
                    ),
                )

                self.p[1:-1, 1:-1] += cp * correction
                self.u[1:-1, 1:-1] -= sx0 * correction
                self.u[2:, 1:-1] += sx1 * correction
                self.v[1:-1, 1:-1] -= sy0 * correction
                self.v[1:-1, 2:] += sy1 * correction

    def extrapolate(self) -> None:
        """Copy neighbouring velocities into the outer ghost cells."""
        self.u[:, 0] = self.u[:, 1]
        self.u[:, -1] = self.u[:, -2]
        self.v[0, :] = self.v[1, :]
        self.v[-1, :] = self.v[-2, :]

    def sample_field(self, x, y, field: int):
        """Bilinearly sample a staggered field at world-space coordinates."""
        h = self.h
        x = np.clip(np.asarray(x), h, self.num_x * h)
        y = np.clip(np.asarray(y), h, self.num_y * h)

        if field == U_FIELD:
            values, dx, dy = self.u, 0.0, 0.5 * h
        elif field == V_FIELD:
            values, dx, dy = self.v, 0.5 * h, 0.0
        elif field == S_FIELD:
            values, dx, dy = self.m, 0.5 * h, 0.5 * h
        else:
            raise ValueError(f"Unknown fluid field: {field}")

        gx = (x - dx) / h
        gy = (y - dy) / h
        x0 = np.clip(np.floor(gx).astype(np.intp), 0, self.num_x - 1)
        y0 = np.clip(np.floor(gy).astype(np.intp), 0, self.num_y - 1)
        tx = gx - x0
        ty = gy - y0
        x1 = np.minimum(x0 + 1, self.num_x - 1)
        y1 = np.minimum(y0 + 1, self.num_y - 1)

        return (
            (1.0 - tx) * (1.0 - ty) * values[x0, y0]
            + tx * (1.0 - ty) * values[x1, y0]
            + tx * ty * values[x1, y1]
            + (1.0 - tx) * ty * values[x0, y1]
        )

    def avg_u(self, i: int, j: int) -> float:
        return float(
            (self.u[i, j - 1] + self.u[i, j]
             + self.u[i + 1, j - 1] + self.u[i + 1, j]) * 0.25
        )

    def avg_v(self, i: int, j: int) -> float:
        return float(
            (self.v[i - 1, j] + self.v[i, j]
             + self.v[i - 1, j + 1] + self.v[i, j + 1]) * 0.25
        )

    def advect_velocity(self, dt: float) -> None:
        """Move face velocities through the grid using semi-Lagrangian advection."""
        self.new_u[:] = self.u
        self.new_v[:] = self.v
        h = self.h

        # Horizontal (u) faces: x=i*h, y=(j+1/2)*h.
        valid_u = (self.s[1:, 1:-1] != 0.0) & (self.s[:-1, 1:-1] != 0.0)
        u = self.u[1:, 1:-1]
        v = (
            self.v[:-1, 1:-1] + self.v[1:, 1:-1]
            + self.v[:-1, 2:] + self.v[1:, 2:]
        ) * 0.25
        x = np.arange(1, self.num_x, dtype=np.float32)[:, None] * h - dt * u
        y = (np.arange(1, self.num_y - 1, dtype=np.float32)[None, :] + 0.5) * h - dt * v
        sampled_u = self.sample_field(x, y, U_FIELD)
        self.new_u[1:, 1:-1][valid_u] = sampled_u[valid_u]

        # Vertical (v) faces: x=(i+1/2)*h, y=j*h.
        valid_v = (self.s[1:-1, 1:] != 0.0) & (self.s[1:-1, :-1] != 0.0)
        u = (
            self.u[1:-1, :-1] + self.u[1:-1, 1:]
            + self.u[2:, :-1] + self.u[2:, 1:]
        ) * 0.25
        v = self.v[1:-1, 1:]
        x = (np.arange(1, self.num_x - 1, dtype=np.float32)[:, None] + 0.5) * h - dt * u
        y = np.arange(1, self.num_y, dtype=np.float32)[None, :] * h - dt * v
        sampled_v = self.sample_field(x, y, V_FIELD)
        self.new_v[1:-1, 1:][valid_v] = sampled_v[valid_v]

        self.u, self.new_u = self.new_u, self.u
        self.v, self.new_v = self.new_v, self.v

    def advect_smoke(self, dt: float) -> None:
        """Move smoke density through the grid with bilinear sampling."""
        self.new_m[:] = self.m
        h = self.h
        valid = self.s[1:-1, 1:-1] != 0.0
        u = (self.u[1:-1, 1:-1] + self.u[2:, 1:-1]) * 0.5
        v = (self.v[1:-1, 1:-1] + self.v[1:-1, 2:]) * 0.5
        x = (np.arange(1, self.num_x - 1, dtype=np.float32)[:, None] + 0.5) * h - dt * u
        y = (np.arange(1, self.num_y - 1, dtype=np.float32)[None, :] + 0.5) * h - dt * v
        sampled = self.sample_field(x, y, S_FIELD)
        self.new_m[1:-1, 1:-1][valid] = sampled[valid]
        self.m, self.new_m = self.new_m, self.m

    def simulate(self, dt: float, gravity: float, num_iters: int) -> None:
        self.integrate(dt, gravity)
        self.solve_incompressibility(num_iters, dt)
        self.extrapolate()
        self.advect_velocity(dt)
        self.advect_smoke(dt)


class FluidApp:
    """Tkinter controls, scene setup, drawing, and mouse interaction."""

    SIM_HEIGHT = 1.1
    CANVAS_WIDTH = 1000
    CANVAS_HEIGHT = 650

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Eulerian Fluid — Ten Minute Physics")
        self.root.minsize(760, 500)

        self.scene_nr = 1
        self.gravity = 0.0
        self.dt = 1.0 / 60.0
        self.num_iters = 40
        self.over_relaxation = 1.9
        self.frame_nr = 0
        self.paused = False
        self.show_streamlines = False
        self.show_velocities = False
        self.show_pressure = False
        self.show_smoke = True
        self.show_obstacle = False
        self.obstacle_x = 0.0
        self.obstacle_y = 0.0
        self.obstacle_radius = 0.15
        self.dragging = False

        self.fluid: Fluid | None = None
        self.base_s: np.ndarray | None = None

        self._build_controls()
        self.setup_scene(1)
        self._tick()

    def _build_controls(self) -> None:
        controls = ttk.Frame(self.root, padding=(6, 6, 6, 3))
        controls.pack(side=tk.TOP, fill=tk.X)

        scene_controls = ttk.Frame(controls)
        scene_controls.pack(side=tk.LEFT)
        for label, scene_nr in (
            ("Wind Tunnel", 1), ("Hires Tunnel", 3),
            ("Tank", 0), ("Paint", 2),
        ):
            ttk.Button(
                scene_controls, text=label,
                command=lambda number=scene_nr: self.setup_scene(number),
            ).pack(side=tk.LEFT, padx=2)

        display_controls = ttk.Frame(controls)
        display_controls.pack(side=tk.LEFT, padx=(10, 0))
        self.stream_var = tk.BooleanVar(value=False)
        self.velocity_var = tk.BooleanVar(value=False)
        self.pressure_var = tk.BooleanVar(value=False)
        self.smoke_var = tk.BooleanVar(value=True)
        self.overrelax_var = tk.BooleanVar(value=True)
        checks = (
            ("Streamlines", self.stream_var, "show_streamlines"),
            ("Velocities", self.velocity_var, "show_velocities"),
            ("Pressure", self.pressure_var, "show_pressure"),
            ("Smoke", self.smoke_var, "show_smoke"),
            ("Overrelax", self.overrelax_var, "overrelax"),
        )
        for label, variable, attribute in checks:
            ttk.Checkbutton(
                display_controls, text=label, variable=variable,
                command=lambda name=attribute: self._toggle(name),
            ).pack(side=tk.LEFT, padx=2)

        ttk.Button(controls, text="Step", command=self.step_once).pack(
            side=tk.RIGHT, padx=(4, 2)
        )
        self.pause_button = ttk.Button(
            controls, text="Pause", command=self.toggle_pause
        )
        self.pause_button.pack(side=tk.RIGHT, padx=2)

        self.canvas = tk.Canvas(
            self.root, width=self.CANVAS_WIDTH, height=self.CANVAS_HEIGHT,
            background="white", highlightthickness=0,
        )
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.image_item = self.canvas.create_image(0, 0, anchor=tk.NW)
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)
        self.root.bind("p", lambda _event: self.toggle_pause())
        self.root.bind("m", lambda _event: self.step_once())

    def _toggle(self, name: str) -> None:
        if name == "overrelax":
            self.over_relaxation = 1.9 if self.overrelax_var.get() else 1.0
            if self.fluid is not None:
                self.fluid.over_relaxation = self.over_relaxation
        else:
            setattr(self, name, {
                "show_streamlines": self.stream_var.get(),
                "show_velocities": self.velocity_var.get(),
                "show_pressure": self.pressure_var.get(),
                "show_smoke": self.smoke_var.get(),
            }[name])

    def setup_scene(self, scene_nr: int) -> None:
        """Create one of the reference demo's tank, tunnel, or paint scenes."""
        self.scene_nr = scene_nr
        self.obstacle_radius = 0.15
        self.over_relaxation = 1.9
        self.dt = 1.0 / 60.0
        self.num_iters = 40

        resolution = 100
        if scene_nr == 0:
            resolution = 50
        elif scene_nr == 3:
            resolution = 200

        canvas_h = max(self.canvas.winfo_height(), self.CANVAS_HEIGHT)
        canvas_w = max(self.canvas.winfo_width(), self.CANVAS_WIDTH)
        scale = canvas_h / self.SIM_HEIGHT
        domain_width = canvas_w / scale / self.SIM_HEIGHT
        h = 1.0 / resolution
        num_x = max(4, int(domain_width / h))
        num_y = resolution
        fluid = Fluid(1000.0, num_x, num_y, h)
        self.fluid = fluid
        fluid.over_relaxation = self.over_relaxation

        # Start with fluid cells; scenes add solid walls below.
        fluid.s.fill(1.0)
        if scene_nr == 0:  # Tank: solid left, right, and bottom walls.
            fluid.s[0, :] = 0.0
            fluid.s[-1, :] = 0.0
            fluid.s[:, 0] = 0.0
            self.gravity = -9.81
            self.show_pressure = True
            self.show_smoke = False
            self.show_streamlines = False
            self.show_velocities = False
            self.show_obstacle = False
        elif scene_nr in (1, 3):  # Wind tunnel and higher resolution variant.
            fluid.s[0, :] = 0.0
            fluid.s[:, 0] = 0.0
            fluid.s[:, -1] = 0.0
            fluid.u[1, :] = 2.0
            pipe_height = int(0.1 * fluid.num_y)
            low = int(0.5 * fluid.num_y - 0.5 * pipe_height)
            high = int(0.5 * fluid.num_y + 0.5 * pipe_height)
            fluid.m[0, low:high] = 0.0
            self.gravity = 0.0
            self.show_pressure = scene_nr == 3
            self.show_smoke = True
            self.show_streamlines = False
            self.show_velocities = False
            self.show_obstacle = True
            if scene_nr == 3:
                self.dt = 1.0 / 120.0
                self.num_iters = 100
        elif scene_nr == 2:  # Paint: drag the circular obstacle to stir dye.
            fluid.s[0, :] = 0.0
            fluid.s[-1, :] = 0.0
            fluid.s[:, 0] = 0.0
            fluid.s[:, -1] = 0.0
            self.gravity = 0.0
            self.over_relaxation = 1.0
            self.obstacle_radius = 0.1
            self.show_pressure = False
            self.show_smoke = True
            self.show_streamlines = False
            self.show_velocities = False
            self.show_obstacle = False
            fluid.over_relaxation = self.over_relaxation
        else:
            raise ValueError("Scene must be 0 (Tank), 1 (Wind Tunnel), 2 (Paint), or 3 (Hires Tunnel)")

        self.base_s = fluid.s.copy()
        if scene_nr in (1, 3):
            self.set_obstacle(0.4, 0.5, reset=True)

        self.frame_nr = 0
        self.paused = False
        self.pause_button.configure(text="Pause")
        self.stream_var.set(self.show_streamlines)
        self.velocity_var.set(self.show_velocities)
        self.pressure_var.set(self.show_pressure)
        self.smoke_var.set(self.show_smoke)
        self.overrelax_var.set(self.over_relaxation > 1.0)

    def set_obstacle(self, x: float, y: float, reset: bool = False) -> None:
        """Move the circular solid and transfer its motion to nearby fluid."""
        if self.fluid is None or self.base_s is None:
            return
        if reset:
            vx = vy = 0.0
        else:
            vx = (x - self.obstacle_x) / self.dt
            vy = (y - self.obstacle_y) / self.dt
        self.obstacle_x, self.obstacle_y = x, y

        fluid = self.fluid
        fluid.s[:] = self.base_s
        cell_x = (np.arange(fluid.num_x, dtype=np.float32) + 0.5) * fluid.h
        cell_y = (np.arange(fluid.num_y, dtype=np.float32) + 0.5) * fluid.h
        dx = cell_x[:, None] - x
        dy = cell_y[None, :] - y
        inside = (dx * dx + dy * dy < self.obstacle_radius ** 2) & (self.base_s != 0.0)
        fluid.s[inside] = 0.0

        if self.scene_nr == 2:
            fluid.m[inside] = 0.5 + 0.5 * np.sin(0.1 * self.frame_nr)
        else:
            fluid.m[inside] = 1.0
        ix, iy = np.nonzero(inside)
        fluid.u[ix, iy] = vx
        fluid.u[ix + 1, iy] = vx
        fluid.v[ix, iy] = vy
        fluid.v[ix, iy + 1] = vy
        self.show_obstacle = True

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_button.configure(text="Resume" if self.paused else "Pause")

    def step_once(self) -> None:
        if self.fluid is not None:
            self.fluid.simulate(self.dt, self.gravity, self.num_iters)
            self.frame_nr += 1
            self._draw_frame()

    def _mouse_world_position(self, event) -> tuple[float, float]:
        height = max(self.canvas.winfo_height(), 1)
        scale = height / self.SIM_HEIGHT
        return event.x / scale, (height - event.y) / scale

    def _mouse_down(self, event) -> None:
        self.dragging = True
        x, y = self._mouse_world_position(event)
        self.set_obstacle(x, y, reset=True)

    def _mouse_drag(self, event) -> None:
        if self.dragging:
            x, y = self._mouse_world_position(event)
            self.set_obstacle(x, y)

    def _mouse_up(self, _event) -> None:
        self.dragging = False

    @staticmethod
    def _scientific_colors(values: np.ndarray, minimum: float, maximum: float) -> np.ndarray:
        if maximum - minimum < 1.0e-12:
            normalized = np.full(values.shape, 0.5, dtype=np.float32)
        else:
            normalized = np.clip((values - minimum) / (maximum - minimum), 0.0, 0.9999)
        segment = np.minimum((normalized * 4.0).astype(np.intp), 3)
        amount = normalized * 4.0 - segment
        red = np.zeros_like(normalized)
        green = np.zeros_like(normalized)
        blue = np.zeros_like(normalized)

        masks = segment == 0
        green[masks], blue[masks] = amount[masks], 1.0
        masks = segment == 1
        green[masks], blue[masks] = 1.0, 1.0 - amount[masks]
        masks = segment == 2
        red[masks], green[masks] = amount[masks], 1.0
        masks = segment == 3
        red[masks], green[masks] = 1.0, 1.0 - amount[masks]
        return np.stack((red, green, blue), axis=-1) * 255.0

    def _cell_colors(self, fluid: Fluid) -> np.ndarray:
        if self.show_pressure:
            minimum = float(np.min(fluid.p))
            maximum = float(np.max(fluid.p))
            colors = self._scientific_colors(fluid.p, minimum, maximum)
            if self.show_smoke:
                colors = np.maximum(colors - fluid.m[..., None] * 255.0, 0.0)
        elif self.show_smoke:
            if self.scene_nr == 2:
                colors = self._scientific_colors(fluid.m, 0.0, 1.0)
            else:
                colors = np.repeat((fluid.m * 255.0)[..., None], 3, axis=2)
        else:
            gray = np.where(fluid.s == 0.0, 0.0, 255.0)
            colors = np.repeat(gray[..., None], 3, axis=2)
        return np.clip(colors, 0, 255).astype(np.uint8)

    def _draw_frame(self) -> None:
        fluid = self.fluid
        if fluid is None:
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        scale = height / self.SIM_HEIGHT
        sim_width = max(1, int(round(fluid.num_x * fluid.h * scale)))
        sim_height = max(1, int(round(fluid.num_y * fluid.h * scale)))

        # Grid arrays use x first and y upward; image pixels use y downward.
        cells = self._cell_colors(fluid).transpose(1, 0, 2)[::-1, :, :]
        field_image = Image.fromarray(cells, mode="RGB")
        field_image = field_image.resize((sim_width, sim_height), Image.Resampling.NEAREST)
        frame = Image.new("RGB", (width, height), (255, 255, 255))
        y_offset = height - sim_height
        frame.paste(field_image, (0, y_offset))
        draw = ImageDraw.Draw(frame)

        if self.show_obstacle:
            center = (self.obstacle_x * scale, height - self.obstacle_y * scale)
            radius = (self.obstacle_radius + fluid.h) * scale
            fill = (0, 0, 0) if self.show_pressure else (221, 221, 221)
            box = (center[0] - radius, center[1] - radius,
                   center[0] + radius, center[1] + radius)
            draw.ellipse(box, fill=fill, outline=(0, 0, 0), width=2)

        if self.show_velocities:
            vector_scale = 0.02 * scale
            stride = max(1, max(fluid.num_x, fluid.num_y) // 150)
            for i in range(0, fluid.num_x, stride):
                for j in range(0, fluid.num_y, stride):
                    x0 = i * fluid.h * scale
                    x1 = (i * fluid.h + float(fluid.u[i, j]) * 0.02) * scale
                    y = height - (j + 0.5) * fluid.h * scale
                    draw.line((x0, y, x1, y), fill=(0, 0, 0))

                    x = (i + 0.5) * fluid.h * scale
                    y0 = height - j * fluid.h * scale
                    y1 = height - (j * fluid.h + float(fluid.v[i, j]) * 0.02) * scale
                    draw.line((x, y0, x, y1), fill=(0, 0, 0))

        if self.show_streamlines:
            step = max(1, max(fluid.num_x, fluid.num_y) // 40)
            for i in range(1, fluid.num_x - 1, step):
                for j in range(1, fluid.num_y - 1, step):
                    x = (i + 0.5) * fluid.h
                    y = (j + 0.5) * fluid.h
                    points = [(x * scale, height - y * scale)]
                    for _ in range(15):
                        u = float(fluid.sample_field(x, y, U_FIELD))
                        v = float(fluid.sample_field(x, y, V_FIELD))
                        x += u * 0.01
                        y += v * 0.01
                        if x < 0.0 or x > fluid.num_x * fluid.h:
                            break
                        points.append((x * scale, height - y * scale))
                    if len(points) > 1:
                        draw.line(points, fill=(0, 0, 0), width=1)

        if self.show_pressure:
            draw.text(
                (10, 10),
                f"Pressure: {float(np.min(fluid.p)):.0f} – {float(np.max(fluid.p)):.0f} N/m",
                fill=(0, 0, 0),
            )

        self.photo = ImageTk.PhotoImage(frame)
        self.canvas.itemconfigure(self.image_item, image=self.photo)

    def _tick(self) -> None:
        if not self.paused and self.fluid is not None:
            self.fluid.simulate(self.dt, self.gravity, self.num_iters)
            self.frame_nr += 1
        self._draw_frame()
        self.root.after(16, self._tick)


def main() -> None:
    root = tk.Tk()
    FluidApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
