import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication

import progression
import progression_ui

from petpet.progression import ui


@pytest.fixture
def shop_window():
    app = QApplication.instance() or QApplication([])
    pet = SimpleNamespace(
        state=progression.ensure_progression({
            "player": {"pet_coins": 760},
            "pets": {"lunch_meat": {"pet_name": "午餐肉"}},
            "owned_pet_ids": ["lunch_meat"],
            "active_pet_id": "lunch_meat",
        }),
        say=Mock(),
        update=Mock(),
        set_active_pet=Mock(return_value={"ok": True}),
    )
    window = ui.ShopWindow(pet, Mock())
    yield window
    window.close()
    app.processEvents()


def test_root_progression_ui_is_a_compatibility_facade():
    assert progression_ui.CozyProgressWindow is ui.CozyProgressWindow
    assert progression_ui.RecordsWindow is ui.RecordsWindow
    assert progression_ui.AchievementsWindow is ui.AchievementsWindow
    assert progression_ui.ShopWindow is ui.ShopWindow


def test_shop_pages_include_pets_before_outfits(shop_window):
    shop_window.refresh()

    assert shop_window.page_ids() == (
        "pets", "outfits", "home", "upgrades"
    )


def test_shop_defaults_to_pets_and_keeps_owned_pet_price_and_description(
        shop_window):
    assert shop_window.page == "pets"
    shop_window.refresh()
    card = shop_window.findChild(ui.QFrame, "petCard_lunch_meat")
    price = shop_window.findChild(ui.QLabel, "petPrice_lunch_meat")
    description = shop_window.findChild(
        ui.QLabel, "petDescription_lunch_meat"
    )

    assert card is not None
    assert price.text() == "免费赠送"
    assert price.property("priceTagRole") == "gift"
    assert description.text() == "元气满满的陪伴小狗，喜欢在桌面上撒娇。"
    assert description.wordWrap() is False


def test_shop_sorts_free_items_first_and_preserves_furniture_information(
        shop_window):
    shop_window._set_page("home")
    grid = shop_window.findChild(ui.QGridLayout, "homeDecorationGrid")
    free_card = grid.itemAtPosition(0, 0).widget()
    paid_card = grid.itemAtPosition(0, 1).widget()

    assert free_card.objectName() == "homeDecorationCard_home_status_card"
    assert paid_card.objectName() == "homeDecorationCard_home_rug"
    preview = shop_window.findChild(
        ui.QLabel, "homePreview_home_status_card"
    )
    assert preview.size().width() == 170
    assert preview.size().height() == 112
    labels = " ".join(
        label.text() for label in free_card.findChildren(ui.QLabel)
    )
    assert all(text in labels for text in ("成长", "免费赠送", "家居"))
    assert free_card.height() == paid_card.height() == 310


def test_upgrade_card_shows_the_current_effect(shop_window):
    shop_window.pet.state["upgrades"]["petting"] = 2
    shop_window._set_page("upgrades")
    effect = shop_window.findChild(ui.QLabel, "upgradeEffect_petting")

    assert effect.text() == progression.upgrade_description(
        shop_window.pet.state, "petting"
    )
    assert "当前加成" not in effect.text()


def test_pets_page_shows_preview_nickname_status_and_one_action(shop_window):
    shop_window.pet.state["pets"]["ice_cream"] = {
        "pet_name": "甜筒",
    }

    shop_window.refresh()

    card = shop_window.findChild(ui.QFrame, "petCard_ice_cream")
    assert card is not None
    assert shop_window.findChild(
        ui.QLabel, "petPreview_ice_cream"
    ).pixmap().isNull() is False
    assert "甜筒" in " ".join(
        label.text() for label in card.findChildren(ui.QLabel)
    )
    assert "760 Pet币" in " ".join(
        label.text() for label in card.findChildren(ui.QLabel)
    )
    assert len(card.findChildren(ui.QPushButton)) == 1


def test_shop_shows_pet_name_with_default_name_when_nicknamed(shop_window):
    shop_window.pet.state["pets"]["lunch_meat"]["pet_name"] = "小肉"
    shop_window.refresh()
    QApplication.processEvents()
    title = shop_window.findChild(ui.QLabel, "petName_lunch_meat")
    assert title is not None
    assert title.text() == "小肉（午餐肉）"


def test_pet_cards_are_framed_and_discount_badge_has_its_own_action_column(shop_window):
    shop_window.refresh()
    QApplication.processEvents()
    lunch_card = shop_window.findChild(ui.QFrame, "petCard_lunch_meat")
    ice_card = shop_window.findChild(ui.QFrame, "petCard_ice_cream")
    assert lunch_card.property("shopCard") is True
    assert ice_card.property("shopCard") is True

    actions = shop_window.findChild(ui.QFrame, "petActions_ice_cream")
    badge = shop_window.findChild(ui.QLabel, "discountBadge_ice_cream")
    discounted = shop_window.findChild(ui.QLabel, "discountPrice_ice_cream")
    assert actions is not None
    assert badge.parent() is actions
    assert badge.property("discountBubble") is True
    assert badge.fontMetrics().height() < discounted.fontMetrics().height()
    assert actions.layout().indexOf(badge) == 0


def test_pet_discount_price_row_matches_compact_reference_style(shop_window):
    shop_window.refresh()
    QApplication.processEvents()
    original = shop_window.findChild(ui.QLabel, "originalPrice_ice_cream")
    discounted = shop_window.findChild(ui.QLabel, "discountPrice_ice_cream")
    badge = shop_window.findChild(ui.QLabel, "discountBadge_ice_cream")
    assert original.text() == "原价：1000 Pet币"
    assert discounted.text() == "现价：760 Pet币"
    assert badge.text() == "-24%"
    assert original.property("priceTagRole") == "normal"
    assert discounted.property("priceTagRole") == "sale"
    assert badge.property("priceTagRole") == "discount"
    assert original.font().strikeOut() is True


def test_price_tags_reserve_a_text_safe_height(shop_window):
    for role in ("normal", "sale", "discount", "gift"):
        label = shop_window._price_tag("售价：760 Pet币", role, role)
        assert label.minimumHeight() >= 34
        assert label.contentsMargins().left() >= 12
        assert label.contentsMargins().right() >= 12
        assert label.sizeHint().height() >= label.fontMetrics().height() + 10


def test_outfit_and_home_pages_show_original_prices_without_discount_badges(shop_window):
    shop_window._set_page("outfits")
    QApplication.processEvents()
    labels = shop_window.findChildren(ui.QLabel)
    assert not any(label.objectName().startswith("discountBadge_") for label in labels)
    outfit_button = next(
        button for button in shop_window.findChildren(ui.QPushButton)
        if button.text() == "680 Pet币 · 购买"
    )
    assert outfit_button.isEnabled() is True

    shop_window._set_page("home")
    QApplication.processEvents()
    labels = shop_window.findChildren(ui.QLabel)
    assert not any(label.objectName().startswith("discountBadge_") for label in labels)
    home_button = next(
        button for button in shop_window.findChildren(ui.QPushButton)
        if button.text() == "120 Pet币 · 购买"
    )
    assert home_button.isEnabled() is True


def test_outfit_pet_selector_is_framed_and_switches_checked_state(shop_window):
    shop_window._set_page("outfits")
    QApplication.processEvents()
    selector = shop_window.findChild(ui.QFrame, "outfitPetSelector")
    lunch_button = shop_window.findChild(ui.QPushButton, "outfitPet_lunch_meat")
    ice_button = shop_window.findChild(ui.QPushButton, "outfitPet_ice_cream")
    assert selector is not None
    assert selector.property("outfitPetSelector") is True
    assert lunch_button.isChecked() is True
    assert ice_button.isChecked() is False

    ice_button.click()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    lunch_button = shop_window.findChild(ui.QPushButton, "outfitPet_lunch_meat")
    ice_button = shop_window.findChild(ui.QPushButton, "outfitPet_ice_cream")
    assert lunch_button.isChecked() is False
    assert ice_button.isChecked() is True
    ice_button.click()
    assert ice_button.isChecked() is True


def test_ice_cream_outfit_page_uses_framed_preparation_card(shop_window):
    shop_window._set_page("outfits")
    shop_window.findChild(ui.QPushButton, "outfitPet_ice_cream").click()
    QApplication.processEvents()
    empty = shop_window.findChild(ui.QFrame, "outfitEmptyCard")
    assert empty is not None
    texts = [label.text() for label in empty.findChildren(ui.QLabel)]
    assert "🌷 冰淇淋套装正在准备" in texts
    assert "后续会继续补充新的完整套装，已购买的套装可以随时切换。" in texts


def test_pet_card_purchase_and_successful_switch_save_exactly_once(shop_window):
    save_count = 0

    def save_state(state):
        nonlocal save_count
        save_count += 1
        assert state["owned_pet_ids"] == ["lunch_meat", "ice_cream"]
        assert state["player"]["pet_coins"] == 0

    def switch_and_save(pet_id):
        shop_window.pet.state["active_pet_id"] = pet_id
        save_state(shop_window.pet.state)
        return {"ok": True, "pet_id": pet_id, "message": "已切换宠物。"}

    shop_window.save_callback = save_state
    shop_window.pet.set_active_pet = switch_and_save
    shop_window.refresh()
    card = shop_window.findChild(ui.QFrame, "petCard_ice_cream")
    card.findChild(ui.QPushButton).click()

    assert shop_window.pet.state["owned_pet_ids"] == [
        "lunch_meat", "ice_cream"
    ]
    assert shop_window.pet.state["active_pet_id"] == "ice_cream"
    assert save_count == 1


def test_pet_purchase_keeps_ownership_when_switch_is_rejected(shop_window):
    shop_window.pet.set_active_pet.return_value = {
        "ok": False,
        "message": "切换服务未就绪。",
    }
    shop_window.refresh()
    card = shop_window.findChild(ui.QFrame, "petCard_ice_cream")
    card.findChild(ui.QPushButton).click()

    assert shop_window.pet.state["owned_pet_ids"] == [
        "lunch_meat", "ice_cream"
    ]
    assert shop_window.pet.state["player"]["pet_coins"] == 0
    shop_window.pet.set_active_pet.assert_called_once_with("ice_cream")
    shop_window.save_callback.assert_called_once_with(shop_window.pet.state)
    assert "购买成功" in shop_window.status_label.text()
    assert "切换失败" in shop_window.status_label.text()


def test_pet_card_switches_through_callbacks(shop_window):
    shop_window.pet.state["owned_pet_ids"].append("ice_cream")
    shop_window.refresh()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QApplication.processEvents()
    card = shop_window.findChild(ui.QFrame, "petCard_ice_cream")
    card.findChild(ui.QPushButton).click()

    shop_window.pet.set_active_pet.assert_called_once_with("ice_cream")
    shop_window.save_callback.assert_not_called()
