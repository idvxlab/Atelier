WINDOW_WIDTH = 720
WINDOW_HEIGHT = 760
FPS = 60

BOARD_WIDTH = 10
BOARD_HEIGHT = 20
CELL_SIZE = 30
BOARD_X = 60
BOARD_Y = 80

SIDE_PANEL_X = BOARD_X + BOARD_WIDTH * CELL_SIZE + 40
SIDE_PANEL_Y = BOARD_Y

TITLE = "PyGame Tetris"
HIGH_SCORE_FILE = "high_score.json"

BG_COLOR = (18, 16, 34)
PANEL_COLOR = (33, 31, 58)
GRID_COLOR = (53, 50, 82)
BORDER_COLOR = (120, 227, 253)
TEXT_COLOR = (238, 241, 255)
MUTED_TEXT_COLOR = (170, 177, 214)
ACCENT_COLOR = (255, 206, 84)
OVERLAY_COLOR = (8, 8, 16)

COLORS = {
    "I": (80, 227, 230),
    "O": (255, 214, 90),
    "T": (181, 126, 255),
    "S": (91, 214, 126),
    "Z": (255, 110, 140),
    "J": (94, 151, 255),
    "L": (255, 167, 66),
}

SCORES = {
    1: 100,
    2: 300,
    3: 500,
    4: 800,
}

LINES_PER_LEVEL = 10
INITIAL_FALL_MS = 700
MIN_FALL_MS = 100
FALL_STEP_MS = 55
LOCK_DELAY_MS = 400
SOFT_DROP_BONUS = 1
HARD_DROP_BONUS = 2

KEY_HELP = [
    "← → : 移动",
    "↑ / X : 旋转",
    "Z : 反向旋转",
    "↓ : 加速下落",
    "空格 : 瞬降",
    "P : 暂停",
    "R : 重新开始",
    "Enter : 开始/继续",
]
