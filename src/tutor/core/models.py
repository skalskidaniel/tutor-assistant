from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .utils import slugify


class Student(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: str = Field(min_length=1)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def folder_slug(self) -> str:
        return slugify(f"{self.first_name}-{self.last_name}")
