from gooey import Gooey

from .__main__ import main

def gui():
    Gooey(main, program_name="chapter_converter")()  # type: ignore

