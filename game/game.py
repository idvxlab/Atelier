from pathlib import Path

import pygame

from board import Board
from config import (
    ACCENT_COLOR,
    BG_COLOR,
    BOARD_HEIGHT,
    BOARD_WIDTH,
    BOARD_X,
    BOARD_Y,
    BORDER_COLOR,
    CELL_SIZE,
    COLORS,
    FALL_STEP_MS,
    FPS,
    GRID_COLOR,
    HIGH_SCORE_FILE,
    INITIAL_FALL_MS,
    KEY_HELP,
    LINES_PER_LEVEL,
    LOCK_DELAY_MS,
    MIN_FALL_MS,
    MUTED_TEXT_COLOR,
    OVERLAY_COLOR,
    PANEL_COLOR,
    SCORES,
    SIDE_PANEL_X,
    SIDE_PANEL_Y,
    SOFT_DROP_BONUS,
    HARD_DROP_BONUS,
    TEXT_COLOR,
    TITLE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from storage import load_high_score, save_high_score
from tetromino import BagGenerator, rotate_matrix_clockwise, rotate_matrix_counter_clockwise


PREFERRED_FONT_CANDIDATES = [
    "microsoftyahei",
    "microsoft yahei",
    "simhei",
    "simsun",
    "nsimsun",
    "pingfangsc",
    "hiraginosansgb",
    "notosanscjksc",
    "notosanssc",
    "wenquanyizenheifont",
    "arialunicode",
]


def choose_ui_font():
    for font_name in PREFERRED_FONT_CANDIDATES:
        matched = pygame.font.match_font(font_name)
        if matched:
            return font_name
    return pygame.font.get_default_font()


class TetrisGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.ui_font_name = choose_ui_font()
        self.font_small = pygame.font.SysFont(self.ui_font_name, 20)
        self.font_medium = pygame.font.SysFont(self.ui_font_name, 28, bold=True)
        self.font_large = pygame.font.SysFont(self.ui_font_name, 42, bold=True)

        self.board = Board()
        self.bag = BagGenerator()
        self.high_score_path = Path(__file__).resolve().parent / HIGH_SCORE_FILE
        self.high_score = load_high_score(self.high_score_path)

        self.state = "start"
        self.score = 0
        self.lines = 0
        self.level = 1
        self.fall_timer = 0
        self.lock_timer = 0
        self.current_piece = None
        self.next_piece = None
        self.reset_game()

    def reset_game(self):
        self.board.reset()
        self.bag = BagGenerator()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.fall_timer = 0
        self.lock_timer = 0
        self.current_piece = self.bag.create_piece(BOARD_WIDTH)
        self.next_piece = self.bag.create_piece(BOARD_WIDTH)
        self.state = "start"

    def spawn_piece(self):
        self.current_piece = self.next_piece
        self.current_piece.x = (BOARD_WIDTH - self.current_piece.width) // 2
        self.current_piece.y = 0
        self.next_piece = self.bag.create_piece(BOARD_WIDTH)
        if not self.board.valid(self.current_piece):
            self.state = "game_over"
            if self.score > self.high_score:
                self.high_score = self.score
                save_high_score(self.high_score_path, self.high_score)

    def get_fall_delay(self):
        return max(MIN_FALL_MS, INITIAL_FALL_MS - (self.level - 1) * FALL_STEP_MS)

    def move(self, dx):
        if self.state == "playing" and self.board.valid(self.current_piece, dx=dx):
            self.current_piece.x += dx

    def soft_drop(self):
        if self.state != "playing":
            return
        if self.board.valid(self.current_piece, dy=1):
            self.current_piece.y += 1
            self.score += SOFT_DROP_BONUS
        else:
            self.lock_piece()

    def hard_drop(self):
        if self.state != "playing":
            return
        dropped = 0
        while self.board.valid(self.current_piece, dy=1):
            self.current_piece.y += 1
            dropped += 1
        self.score += dropped * HARD_DROP_BONUS
        self.lock_piece()

    def rotate_piece(self, clockwise=True):
        if self.state != "playing":
            return
        rotated = (
            rotate_matrix_clockwise(self.current_piece.matrix)
            if clockwise
            else rotate_matrix_counter_clockwise(self.current_piece.matrix)
        )
        for offset in (0, -1, 1, -2, 2):
            if self.board.valid(self.current_piece, dx=offset, matrix=rotated):
                self.current_piece.matrix = rotated
                self.current_piece.x += offset
                return

    def lock_piece(self):
        self.board.lock_piece(self.current_piece)
        lines_cleared = self.board.clear_lines()
        if lines_cleared:
            self.lines += lines_cleared
            self.score += SCORES.get(lines_cleared, 0) * self.level
            self.level = self.lines // LINES_PER_LEVEL + 1
        if self.score > self.high_score:
            self.high_score = self.score
            save_high_score(self.high_score_path, self.high_score)
        self.spawn_piece()
        self.lock_timer = 0

    def update(self, dt):
        if self.state != "playing":
            return
        self.fall_timer += dt
        if self.fall_timer >= self.get_fall_delay():
            self.fall_timer = 0
            if self.board.valid(self.current_piece, dy=1):
                self.current_piece.y += 1
                self.lock_timer = 0
            else:
                self.lock_timer += dt
                if self.lock_timer >= LOCK_DELAY_MS:
                    self.lock_piece()

    def handle_keydown(self, key):
        if key == pygame.K_RETURN:
            if self.state in {"start", "paused"}:
                self.state = "playing"
            elif self.state == "game_over":
                self.reset_game()
                self.state = "playing"
            return

        if key == pygame.K_p:
            if self.state == "playing":
                self.state = "paused"
            elif self.state == "paused":
                self.state = "playing"
            return

        if key == pygame.K_r:
            self.reset_game()
            self.state = "playing"
            return

        if self.state != "playing":
            return

        if key == pygame.K_LEFT:
            self.move(-1)
        elif key == pygame.K_RIGHT:
            self.move(1)
        elif key == pygame.K_DOWN:
            self.soft_drop()
        elif key in (pygame.K_UP, pygame.K_x):
            self.rotate_piece(True)
        elif key == pygame.K_z:
            self.rotate_piece(False)
        elif key == pygame.K_SPACE:
            self.hard_drop()

    def draw_cell(self, x, y, color, shrink=0):
        rect = pygame.Rect(x + shrink, y + shrink, CELL_SIZE - shrink * 2, CELL_SIZE - shrink * 2)
        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        inner = rect.inflate(-8, -8)
        if inner.width > 0 and inner.height > 0:
            glow = tuple(min(255, channel + 35) for channel in color)
            pygame.draw.rect(self.screen, glow, inner, border_radius=3)

    def draw_board(self):
        board_rect = pygame.Rect(
            BOARD_X - 6,
            BOARD_Y - 6,
            BOARD_WIDTH * CELL_SIZE + 12,
            BOARD_HEIGHT * CELL_SIZE + 12,
        )
        pygame.draw.rect(self.screen, PANEL_COLOR, board_rect, border_radius=8)
        pygame.draw.rect(self.screen, BORDER_COLOR, board_rect, width=3, border_radius=8)

        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                x = BOARD_X + col * CELL_SIZE
                y = BOARD_Y + row * CELL_SIZE
                cell_rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, BG_COLOR, cell_rect)
                pygame.draw.rect(self.screen, GRID_COLOR, cell_rect, width=1)
                kind = self.board.grid[row][col]
                if kind:
                    self.draw_cell(x, y, COLORS[kind])

        if self.current_piece and self.state != "game_over":
            ghost_y = self.current_piece.y
            while self.board.valid(self.current_piece, dy=(ghost_y - self.current_piece.y) + 1):
                ghost_y += 1
            for row_idx, row in enumerate(self.current_piece.matrix):
                for col_idx, value in enumerate(row):
                    if not value:
                        continue
                    gx = BOARD_X + (self.current_piece.x + col_idx) * CELL_SIZE
                    gy = BOARD_Y + (ghost_y + row_idx) * CELL_SIZE
                    ghost_rect = pygame.Rect(gx + 6, gy + 6, CELL_SIZE - 12, CELL_SIZE - 12)
                    pygame.draw.rect(self.screen, MUTED_TEXT_COLOR, ghost_rect, width=2, border_radius=3)

            for row_idx, row in enumerate(self.current_piece.matrix):
                for col_idx, value in enumerate(row):
                    if not value:
                        continue
                    px = BOARD_X + (self.current_piece.x + col_idx) * CELL_SIZE
                    py = BOARD_Y + (self.current_piece.y + row_idx) * CELL_SIZE
                    if py >= BOARD_Y:
                        self.draw_cell(px, py, COLORS[self.current_piece.kind])

    def draw_panel(self):
        panel_rect = pygame.Rect(SIDE_PANEL_X, SIDE_PANEL_Y, 240, 600)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, ACCENT_COLOR, panel_rect, width=3, border_radius=10)

        title = self.font_large.render("TETRIS", True, TEXT_COLOR)
        self.screen.blit(title, (SIDE_PANEL_X + 36, SIDE_PANEL_Y + 24))

        info = [
            ("分数", self.score),
            ("最高分", self.high_score),
            ("等级", self.level),
            ("消行", self.lines),
        ]
        y = SIDE_PANEL_Y + 110
        for label, value in info:
            label_surface = self.font_small.render(label, True, MUTED_TEXT_COLOR)
            value_surface = self.font_medium.render(str(value), True, TEXT_COLOR)
            self.screen.blit(label_surface, (SIDE_PANEL_X + 22, y))
            self.screen.blit(value_surface, (SIDE_PANEL_X + 22, y + 24))
            y += 78

        next_label = self.font_small.render("NEXT", True, ACCENT_COLOR)
        self.screen.blit(next_label, (SIDE_PANEL_X + 22, SIDE_PANEL_Y + 420))
        preview_rect = pygame.Rect(SIDE_PANEL_X + 20, SIDE_PANEL_Y + 450, 160, 100)
        pygame.draw.rect(self.screen, BG_COLOR, preview_rect, border_radius=8)
        pygame.draw.rect(self.screen, BORDER_COLOR, preview_rect, width=2, border_radius=8)
        self.draw_next_piece(preview_rect)

        hint_y = SIDE_PANEL_Y + 565
        for hint in KEY_HELP:
            hint_surface = self.font_small.render(hint, True, MUTED_TEXT_COLOR)
            self.screen.blit(hint_surface, (SIDE_PANEL_X + 22, hint_y))
            hint_y += 24

    def draw_next_piece(self, rect):
        if not self.next_piece:
            return
        matrix = self.next_piece.matrix
        offset_x = rect.x + (rect.width - len(matrix[0]) * CELL_SIZE) // 2
        offset_y = rect.y + (rect.height - len(matrix) * CELL_SIZE) // 2
        for row_idx, row in enumerate(matrix):
            for col_idx, value in enumerate(row):
                if value:
                    x = offset_x + col_idx * CELL_SIZE
                    y = offset_y + row_idx * CELL_SIZE
                    self.draw_cell(x, y, COLORS[self.next_piece.kind], shrink=3)

    def draw_overlay(self, title, subtitle_lines):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*OVERLAY_COLOR, 190))
        self.screen.blit(overlay, (0, 0))

        title_surface = self.font_large.render(title, True, ACCENT_COLOR)
        title_rect = title_surface.get_rect(center=(WINDOW_WIDTH // 2, 220))
        self.screen.blit(title_surface, title_rect)

        y = 290
        for line in subtitle_lines:
            surface = self.font_medium.render(line, True, TEXT_COLOR)
            rect = surface.get_rect(center=(WINDOW_WIDTH // 2, y))
            self.screen.blit(surface, rect)
            y += 44

    def draw(self):
        self.screen.fill(BG_COLOR)
        self.draw_board()
        self.draw_panel()

        if self.state == "start":
            self.draw_overlay("PRESS ENTER", ["开始游戏", "P 暂停 / R 重开"])
        elif self.state == "paused":
            self.draw_overlay("PAUSED", ["按 Enter 或 P 继续", "R 可重新开始"])
        elif self.state == "game_over":
            self.draw_overlay("GAME OVER", [f"本局得分 {self.score}", "按 Enter 或 R 再来一局"])

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event.key)

            self.update(dt)
            self.draw()

        pygame.quit()
