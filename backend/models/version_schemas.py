from pydantic import BaseModel


class VersionOut(BaseModel):
    version: str
    commit: str
