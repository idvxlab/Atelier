from config import BOARD_HEIGHT, BOARD_WIDTH


class Board:
    def __init__(self):
        self.width = BOARD_WIDTH
        self.height = BOARD_HEIGHT
        self.grid = [[None for _ in range(self.width)] for _ in range(self.height)]

    def reset(self):
        self.grid = [[None for _ in range(self.width)] for _ in range(self.height)]

    def valid(self, piece, dx=0, dy=0, matrix=None):
        matrix = matrix or piece.matrix
        for row_idx, row in enumerate(matrix):
            for col_idx, value in enumerate(row):
                if not value:
                    continue
                x = piece.x + col_idx + dx
                y = piece.y + row_idx + dy
                if x < 0 or x >= self.width or y >= self.height:
                    return False
                if y >= 0 and self.grid[y][x] is not None:
                    return False
        return True

    def lock_piece(self, piece):
        for row_idx, row in enumerate(piece.matrix):
            for col_idx, value in enumerate(row):
                if not value:
                    continue
                x = piece.x + col_idx
                y = piece.y + row_idx
                if y >= 0:
                    self.grid[y][x] = piece.kind

    def clear_lines(self):
        remaining = [row for row in self.grid if any(cell is None for cell in row)]
        lines_cleared = self.height - len(remaining)
        while len(remaining) < self.height:
            remaining.insert(0, [None for _ in range(self.width)])
        self.grid = remaining
        return lines_cleared
