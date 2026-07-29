import math

import pytest

from rig2d import Affine2D, RigDefinition, RigPose, Slot, local_matrix


def simple_rig():
    return RigDefinition.from_dict({
        "canvas": {"width": 400, "height": 500},
        "bones": [
            {"name": "root", "x": 100, "y": 200},
            {"name": "neck", "parent": "root", "x": 20, "y": -40},
        ],
        "slots": [
            {
                "name": "collar",
                "bone": "neck",
                "asset": "collar.png",
                "x": 5,
                "y": 4,
                "order": 20,
            }
        ],
        "animations": {
            "nod": {
                "fps": 10,
                "loop": True,
                "frames": 10,
                "tracks": {
                    "neck": [
                        {"frame": 0, "rotation": 0},
                        {"frame": 5, "rotation": 20},
                        {"frame": 10, "rotation": 0},
                    ]
                },
            }
        },
    })


def test_affine_composition_maps_child_coordinates():
    parent = local_matrix(100, 200, rotation=90)
    child = local_matrix(10, 0)
    point = (parent @ child).map(0, 0)
    assert point.x() == pytest.approx(100)
    assert point.y() == pytest.approx(210)


def test_pose_inherits_parent_and_interpolates_animation():
    rig = simple_rig()
    pose = RigPose(rig, "nod", 2.5)
    transform = pose.world_transform("neck")
    assert transform.tx == pytest.approx(120)
    assert transform.ty == pytest.approx(160)
    assert math.degrees(math.atan2(transform.b, transform.a)) == pytest.approx(10)


def test_looping_pose_wraps_frame_number():
    rig = simple_rig()
    assert RigPose(rig, "nod", 12.5).frame == pytest.approx(2.5)


def test_slot_uses_named_bone_attachment():
    rig = simple_rig()
    pose = RigPose(rig)
    transform = pose.slot_transform(rig.slots[0])
    assert transform.map(0, 0).x() == pytest.approx(125)
    assert transform.map(0, 0).y() == pytest.approx(164)


def test_invalid_parent_and_cycles_are_rejected():
    with pytest.raises(ValueError, match="missing parent"):
        RigDefinition.from_dict({
            "bones": [{"name": "head", "parent": "missing"}],
        })
    with pytest.raises(ValueError, match="cycle"):
        RigDefinition.from_dict({
            "bones": [
                {"name": "a", "parent": "b"},
                {"name": "b", "parent": "a"},
            ],
        })


def test_decoration_slot_can_be_built_without_mutating_manifest():
    rig = simple_rig()
    attachment = Slot.from_dict({
        "name": "red_collar",
        "bone": "neck",
        "asset": "decorations/red_collar.png",
        "order": 21,
        "pivot_x": 0.5,
        "pivot_y": 0.3,
    })
    assert attachment.bone == "neck"
    assert attachment.attachment is None
    assert len(rig.slots) == 1
