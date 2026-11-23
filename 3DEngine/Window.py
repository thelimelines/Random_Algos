# Source tutorial: https://youtu.be/M_Hx0g5vFko

import math

import pygame as pg

from camera import Camera
from object_3d import Object3D
from projection import Projection


# Set this to an STL file path to load a model instead of the demo cube.
STL_PATH = r"C:\Users\brodi\Downloads\zonda.stl"


class SoftwareRenderer:
    # A class keeps the window's settings and the methods that use them together.
    # Each instance has its own state, accessed inside methods through `self`.
    def __init__(self):
        pg.init()
        # RES is the full window resolution; H_WIDTH and H_HEIGHT are its center coordinates.
        self.RES = self.WIDTH, self.HEIGHT = 1600, 900
        self.H_WIDTH, self.H_HEIGHT = self.WIDTH // 2, self.HEIGHT // 2
        self.FPS = 240
        self.screen = pg.display.set_mode(self.RES)
        self.clock = pg.time.Clock()
        self.create_object()

    def create_object(self):
        self.camera = Camera(self, [0.5, 1, -4])
        self.projection = Projection(self)
        self.object = Object3D(self, stl_path=STL_PATH)
        if STL_PATH is None:
            self.object.translate([0.2, 0.4, 0.2])
            self.object.rotate_y(math.pi / 6)
        else:
            # STL meshes are centered around their origin when loaded.
            self.object.rotate_y(math.pi / 6)
            self.object.translate([0.5, 1.0, 0.5])

    def draw(self):
        self.screen.fill(pg.Color("black"))
        self.object.draw()

    def run(self):
        while True:
            self.camera.control()
            self.draw()
            for event in pg.event.get():
                if event.type == pg.QUIT or (event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE):
                    exit()
            pg.display.set_caption(str(self.clock.get_fps()))
            pg.display.flip()
            self.clock.tick(self.FPS)

# Python sets __name__ to "__main__" when this file is run directly. This guard
# lets other files import SoftwareRenderer without starting the window loop.
if __name__ == "__main__":
    app = SoftwareRenderer()
    app.run()
