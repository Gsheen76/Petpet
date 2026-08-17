import home_pet

from petpet.home import pet


def test_root_home_pet_is_a_compatibility_facade():
    assert home_pet.HomePetController is pet.HomePetController
    assert home_pet.clamp_to_walkable is pet.clamp_to_walkable
    assert home_pet.direction_for_delta is pet.direction_for_delta
    assert home_pet.route_footprints is pet.route_footprints

