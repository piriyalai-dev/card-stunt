from typing import List

from pydantic import BaseModel


class QueueItemOut(BaseModel):
    stunt_id: int
    position: int
    code: str
    title: str
    side: str
    status: str


class QueueReorderRequest(BaseModel):
    order: List[int]  # รายการ stunt id เรียงตามลำดับใหม่ (แทนทั้งคิว)


class QueueInsertRequest(BaseModel):
    stunt_id: int
    position: int
