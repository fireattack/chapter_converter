try:
    from gooey import Gooey
except ImportError:
    print("Please install `gooey` manually to use the GUI:")
    print("`pip install attrdict3`, then `pip install gooey` (in two transactions)")
    exit(1)

from .chapter_converter import main

def gui():
    Gooey(main, program_name="chapter_converter")()  # type: ignore

