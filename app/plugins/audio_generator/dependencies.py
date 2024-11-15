# app/plugins/image_generator/dependencies.py

from fastapi import Depends
from app.lib.dependencies import get_function_handler
from app.lib.function_handler import FunctionHandler
from app.plugins.audio_generator.functions import AudioGeneratorFunctions


async def get_audio_generator_functions(
    function_handler: FunctionHandler = Depends(get_function_handler),
) -> AudioGeneratorFunctions:
    return AudioGeneratorFunctions(function_handler)
