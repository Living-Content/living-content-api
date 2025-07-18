# app/models/function.py


from pydantic import BaseModel, Field


class GetEnabledFunctionListRequest(BaseModel):
    """
    Represents a request to get a list of functions.

    Attributes:
        function_type (Optional[str]): Optional filter to get functions of a specific type.
    """

    function_type: str | None = Field(None, alias="functionType")
