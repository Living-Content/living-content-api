# app/plugins/image_generator/dependencies.py

from fastapi import Depends
from app.lib.dependencies import get_function_handler
from app.lib.function_handler import FunctionHandler
from app.plugins.image_generator.functions import ImageGeneratorFunctions


async def get_image_generator_functions(
    function_handler: FunctionHandler = Depends(get_function_handler),
) -> ImageGeneratorFunctions:
    return ImageGeneratorFunctions(function_handler)
