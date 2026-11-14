"""What a new journey starts with: data/game.json."""
from game.data.defs import game_info
from game.state.store import Save


def new_save() -> Save:
    info = game_info()
    save = Save()
    save.map = info.start_map
    save.money = info.money
    save.heal_map = info.heal_map
    save.heal_at = info.heal_at
    return save
