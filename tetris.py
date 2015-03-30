import time
import curses
import random
import threading


class Brick(object):
    """
    Piece of tetris blocks
    Args:
        x, y (int): position at the game board
    """
    char = 'X'

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def move(self, dx, dy):
        """
        Moves the brick on dx, dy steps
        Args:
            dx, dy (int): steps to move
        """
        self.x += dx
        self.y += dy

    def can_move(self, game, dx, dy):
        """
        Args:
            game (object): game instance
            dx, dy (int): steps to move
        Returns:
            True if can do move, and False otherwise
        """
        x = self.x + dx
        y = self.y + dy
        if x in range(game.border_size, game.width + 1) \
                and y in range(game.height + 1) \
                and (x, y) not in game.building:
            return True
        return False

    def get_rotation_coords(self, direction, center):
        x = self.x - center.x
        y = self.y - center.y
        dx = - direction * y - x
        dy = direction * x - y
        return dx, dy


class Block(object):
    """
    Block is basic class that can move and rotate blocks on the game board
    Args:
        center_x, center_x (int): coordinates of center of the figure
    Hint:
        Block.init_coordinates is required should be implemented
    """
    center_brick_index = 1

    def __init__(self, center_x, center_y):
        self.bricks = []
        for position in self.init_coordinates(center_x, center_y):
            self.bricks.append(Brick(*position))
        self.center = self.bricks[self.center_brick_index]

    @classmethod
    def init_coordinates(self, center_x, center_y):
        """
        Define figure in here. See child classes below.
        """
        raise NotImplementedError

    def can_move(self, game, dx, dy):
        """
        Args:
            game (object): game instance
            dx, dy (int): move step
        Returns:
            True if it can, and False otherwise
        """
        for brick in self.bricks:
            if not brick.can_move(game, dx, dy):
                return False
        return True

    def move(self, dx, dy):
        """
        Move block on dx, dy step
        """
        for brick in self.bricks:
            brick.move(dx, dy)

    def can_rotate(self, game, direction):
        """
        Args:
            game (object): game instance
            direction (int): -1:left 1:right
        Returns:
            True if it can, and False otherwise
        """
        for brick in self.bricks:
            dx, dy = brick.get_rotation_coords(direction, self.center)
            if not brick.can_move(game, dx, dy):
                return False
        return True

    def rotate(self, direction):
        """
        Rotate block around it's central coordinates
        """
        for brick in self.bricks:
            brick.move(*brick.get_rotation_coords(direction, self.center))


class GameThread(threading.Thread):
    def __init__(self, target):
        super(GameThread, self).__init__(target=target)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class Game(object):
    """
    Attrs:
        blocks (list of Block instances): blocks that will appear in the game
        width (int): width for game board
        height (int): height for game board
        current_block (object): Block instance that currently is available
            for movements
        building (dict): here stored all bottom bricks coordinates
                         {(1, 19): brick_instance}
        border_size (int): game board border is taking place in axes,
            so it used for bricks movement calculations
        directions (dict): possible directions on key press
            {key: (x_step, y_step)}
        rotate_directions (dict): map of possible rotation directions
    """
    win = None
    current_block = None
    border_size = 1
    directions = {curses.KEY_LEFT: (-1, 0),
                  curses.KEY_RIGHT: (1, 0),
                  'down': (0, 1)}
    rotate_directions = {curses.KEY_UP: 1, curses.KEY_DOWN: -1}

    def __init__(self, blocks, speed=200, width=20, height=20):
        self.blocks = blocks
        self.speed = speed
        self.building = {}
        self.width = width
        self.height = height
        self.init_play_board()
        self.mainloop_thread = GameThread(target=self.mainloop)

    def init_play_board(self):
        # initialize
        curses.initscr()
        # hide cursor
        curses.curs_set(0)
        # create game board
        self.win = curses.newwin(self.height + 2, self.width + 2)
        self.win.keypad(1)
        self.win.nodelay(1)
        self.draw_border()
        self.create_block()
        self.draw_block()

    def draw_border(self):
        self.win.border(124, 124, 32, 34, 32, 32, 39, 39)

    def create_block(self):
        """
        Randomly get and initialize Block class and set it as current
        """
        self.current_block = self.blocks[
            random.randint(0, len(self.blocks) - 1)](self.width/2, 0)

    def update_building(self):
        """
        Collect bricks coordinates and remove completed line
        """
        # add game board bottom bricks coordinates
        for brick in self.current_block.bricks:
            self.building[(brick.x, brick.y)] = brick
        # remove completed rows if necessary
        for y in range(self.border_size, self.height + 1):
            if self.row_is_completed(y):
                self.remove_row(y)

    def remove_row(self, y):
        # move cursor to the line that should be removed
        self.win.move(y, self.border_size)
        self.win.deleteln()
        # move cursor to the top and add missed line
        self.win.move(self.border_size, self.border_size)
        self.win.insertln()
        # refresh border
        self.draw_border()
        # remove deleted bricks from building map
        for x in range(self.border_size, self.width + 1):
            del self.building[(x, y)]
            # now we have to recalculate bricks axes
            self.move_bricks_down(x, y)

    def move_bricks_down(self, from_x, from_y):
        """
        Visually bricks are moved down, but they may still have old axes
        need to update them
        """
        for y in reversed(range(self.border_size, from_y + 1)):
            if (from_x, y) in self.building:
                brick = self.building[from_x, y]
                del self.building[from_x, y]
                brick.move(*self.directions['down'])
                self.building[from_x, y + 1] = brick

    def row_is_completed(self, y):
        for x in range(self.border_size, self.width + 1):
            if (x, y) not in self.building:
                return False
        return True

    def draw_block(self):
        for brick in self.current_block.bricks:
            self.win.addch(brick.y, brick.x, brick.char)

    def redraw_block(self, action, *args):
        # clear block
        for brick in self.current_block.bricks:
            self.win.addch(brick.y, brick.x, 32)
        # move or rotate
        getattr(self.current_block, action)(*args)
        self.draw_block()

    def do_move(self, key):
        """
        key (int): char code of pressed key
        """
        if key in self.directions:
            dx, dy = self.directions[key]
            if self.current_block.can_move(self, dx, dy):
                self.redraw_block('move', dx, dy)
            elif key == 'down':
                # create new block if current block can't move and it's
                # directions is "down"
                self.update_building()
                self.create_block()
                # if now way to move current block it's a game over
                if not self.current_block.can_move(self, 0, 0):
                    self.exit()

        elif key in self.rotate_directions:
            direction = self.rotate_directions[key]
            if self.current_block.can_rotate(self, direction):
                self.redraw_block('rotate', direction)

    def mainloop(self):
        while not self.mainloop_thread.stopped():
            time.sleep(self.speed / 1000.0)
            self.do_move('down')

    def listen_key_loop(self):
        while not self.mainloop_thread.stopped():
            key = self.win.getch()
            # exit on esc pressed
            if key == 27:
                self.exit()
            self.do_move(key)

    def exit(self):
        self.mainloop_thread.stop()
        curses.endwin()

    def start(self):
        self.mainloop_thread.start()
        self.listen_key_loop()


class IBlock(Block):
    center_brick_index = 2

    @classmethod
    def init_coordinates(cls, center_x, center_y):
        return [[center_x - 2, center_y],
                [center_x - 1, center_y],
                [center_x, center_y],
                [center_x + 1, center_y]]


class LBlock(Block):
    @classmethod
    def init_coordinates(cls, center_x, center_y):
        return [[center_x - 1, center_y],
                [center_x, center_y],
                [center_x + 1, center_y],
                [center_x - 1, center_y + 1]]


class JBlock(Block):
    @classmethod
    def init_coordinates(cls, center_x, center_y):
        return [[center_x - 1, center_y],
                [center_x, center_y],
                [center_x + 1, center_y],
                [center_x + 1, center_y + 1]]


class ZBlock(Block):
    @classmethod
    def init_coordinates(cls, center_x, center_y):
        return [[center_x - 1, center_y],
                [center_x, center_y],
                [center_x, center_y + 1],
                [center_x + 1, center_y + 1]]


class OBlock(Block):
    center_brick_index = 0

    @classmethod
    def init_coordinates(cls, center_x, center_y):
        return [[center_x, center_y],
                [center_x - 1, center_y],
                [center_x, center_y + 1],
                [center_x - 1, center_y + 1]]

    def rotate(self, direction):
        return


if __name__ == '__main__':
    Game([IBlock, LBlock, JBlock, ZBlock, OBlock]).start()
