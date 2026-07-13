import random
from dataclasses import dataclass

SHAPES = {
    "I": [[1, 1, 1, 1]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1]],
    "S": [[0, 1, 1], [1, 1, 0]],
    "Z": [[1, 1, 0], [0, 1, 1]],
    "J": [[1, 0, 0], [1, 1, 1]],
    "L": [[0, 0, 1], [1, 1, 1]],
}


def rotate_matrix_clockwise(matrix):
    return [list(row) for row in zip(*matrix[::-1])]


def rotate_matrix_counter_clockwise(matrix):
    return [list(row) for row in zip(*matrix)][::-1]


@dataclass
class Tetromino:
    kind: str
    matrix: list
    x: int = 0
    y: int = 0

    @property
    def width(self):
        return len(self.matrix[0])

    @property
    def height(self):
        return len(self.matrix)


class BagGenerator:
    def __init__(self):
        self._bag = []

    def next_kind(self):
        if not self._bag:
            self._bag = list(SHAPES.keys())
            random.shuffle(self._bag)
        return self._bag.pop()

    def create_piece(self, board_width):
        kind = self.next_kind()
        matrix = [row[:] for row in SHAPES[kind]]
        piece = Tetromino(kind, matrix)
        piece.x = (board_width - piece.width) // 2
        piece.y = 0
        return piece
