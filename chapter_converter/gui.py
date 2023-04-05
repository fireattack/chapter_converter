from gooey import Gooey

from .chapter_converter import main

def gui():
    Gooey(main, program_name="chapter_converter")()  # type: ignore

