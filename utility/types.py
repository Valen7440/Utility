
from typing import TYPE_CHECKING, TypedDict, Union

if TYPE_CHECKING:
    from datetime import datetime

    from discord import User, Member, Guild

class PrisonData(TypedDict):
    id: int
    guild: "Guild"
    user: Union["User", "Member"]
    moderator: Union["User", "Member"]
    reason: str
    since: "datetime"
