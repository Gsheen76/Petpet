"""礼物系统：商店购买（消耗品库存）→ 宠物面板送出（按宠物加好感）。

目录与数值在 progression.core.GIFT_DEFINITIONS；库存是玩家共享字段
gift_inventory（state.PLAYER_FIELDS），送礼目标可以是当前宠物（走门面
add_affection）或非当前宠物（直接落到该宠物 profile）。
"""

import unittest

from PyQt5.QtCore import Qt

import progression


def fresh_state(**overrides):
    state = {
        "born": 0.0,
        "level": 1,
        "xp": 0,
        "hunger": 80,
        "mood": 70,
        "energy": 90,
    }
    state.update(overrides)
    return progression.ensure_progression(state)


class GiftCatalogTests(unittest.TestCase):
    def test_nine_gifts_three_per_tier(self):
        definitions = progression.GIFT_DEFINITIONS
        self.assertEqual(len(definitions), 9)
        by_tier = {1: [], 2: [], 3: []}
        for gift_id, definition in definitions.items():
            tier = definition.get("tier")
            self.assertIn(tier, (1, 2, 3))
            by_tier[tier].append(gift_id)
        self.assertEqual([len(by_tier[t]) for t in (1, 2, 3)], [3, 3, 3])

    def test_tier_prices_and_affection_are_consistent(self):
        expected = {1: (80, 10), 2: (200, 30), 3: (480, 80)}
        for gift_id, definition in progression.GIFT_DEFINITIONS.items():
            tier = definition["tier"]
            self.assertEqual(
                (definition["price"], definition["affection"]),
                expected[tier],
                f"{gift_id} 档位数值应与档位表一致",
            )
            self.assertTrue(str(definition["name"]).strip())
            self.assertTrue(str(definition["summary"]).strip())

    def test_no_dog_specific_naming(self):
        """礼物名目保持宠物中性（未来会有小猫等）：不出现骨头/毛线球/小鱼干。"""
        joined = "".join(
            definition["name"] + definition["summary"]
            for definition in progression.GIFT_DEFINITIONS.values()
        )
        for word in ("骨头", "毛线", "鱼干", "狗狗", "汪"):
            self.assertNotIn(word, joined)


class GiftPreferenceTests(unittest.TestCase):
    def test_registry_declares_one_preference_per_tier_per_pet(self):
        for pet_id in ("lunch_meat", "ice_cream"):
            preferences = progression.preferred_gift_ids(pet_id)
            self.assertEqual(len(preferences), 3, pet_id)
            tiers = [
                progression.GIFT_DEFINITIONS[g]["tier"] for g in preferences
            ]
            self.assertEqual(sorted(tiers), [1, 2, 3], pet_id)

    def test_preference_multiplier_rounds_clean(self):
        base, final, preferred = progression.gift_affection_for(
            "lunch_meat", "sweet_cookie",
        )
        self.assertEqual((base, final, preferred), (10, 15, True))
        base, final, preferred = progression.gift_affection_for(
            "ice_cream", "sweet_cookie",
        )
        self.assertEqual((base, final, preferred), (10, 10, False))
        base, final, _ = progression.gift_affection_for(
            "ice_cream", "warm_blanket",
        )
        self.assertEqual((base, final), (80, 120))

    def test_unknown_pet_gets_no_bonus(self):
        base, final, preferred = progression.gift_affection_for(
            "ghost_pet", "love_box",
        )
        self.assertEqual((base, final, preferred), (80, 80, False))


class GiftInventoryTests(unittest.TestCase):
    def test_empty_by_default(self):
        state = fresh_state()
        self.assertEqual(progression.gift_inventory(state), {})
        self.assertEqual(progression.gift_count(state, "sweet_cookie"), 0)

    def test_junk_inventory_is_normalized(self):
        state = fresh_state(gift_inventory={
            "sweet_cookie": 2,
            "unknown_gift": 5,
            "meat_can": -3,
            "love_box": "oops",
        })
        self.assertEqual(
            progression.gift_inventory(state), {"sweet_cookie": 2}
        )

    def test_legacy_bone_cookies_migrate_to_tier_peer(self):
        """旧目录的骨头饼干折算为同档甜心曲奇（中性化改版不吞库存）。"""
        state = fresh_state(gift_inventory={
            "bone_cookie": 2, "sweet_cookie": 1,
        })
        self.assertEqual(
            progression.gift_inventory(state), {"sweet_cookie": 3},
        )
        state = fresh_state(gift_inventory={"bone_cookie": 1})
        self.assertEqual(
            progression.gift_inventory(state), {"sweet_cookie": 1},
        )


class PurchaseGiftTests(unittest.TestCase):
    def test_purchase_deducts_shared_coins_and_stocks_inventory(self):
        state = fresh_state(
            player={"pet_coins": 900},
            owned_pet_ids=["lunch_meat"],
            pets={"lunch_meat": {"pet_name": "午餐肉"}},
        )
        result = progression.purchase_gift(state, "sweet_cookie")
        self.assertTrue(result["ok"])
        self.assertEqual(result["price"], 80)
        self.assertEqual(result["count"], 1)
        self.assertEqual(state["player"]["pet_coins"], 820)
        self.assertEqual(state["pet_coins"], 820)
        self.assertEqual(progression.gift_count(state, "sweet_cookie"), 1)
        self.assertEqual(state["records"]["coins_spent"], 80)
        self.assertEqual(state["records"]["gifts_bought"], 1)

        again = progression.purchase_gift(state, "sweet_cookie")
        self.assertTrue(again["ok"])
        self.assertEqual(again["count"], 2)

    def test_purchase_rejects_insufficient_coins(self):
        state = fresh_state(pet_coins=50)
        result = progression.purchase_gift(state, "love_box")
        self.assertFalse(result["ok"])
        self.assertEqual(result["price"], 480)
        self.assertIn("430", result["message"])
        self.assertEqual(progression.gift_count(state, "love_box"), 0)
        self.assertEqual(state["pet_coins"], 50)

    def test_purchase_rejects_unknown_gift(self):
        state = fresh_state(pet_coins=9999)
        result = progression.purchase_gift(state, "golden_bone")
        self.assertFalse(result["ok"])
        self.assertEqual(state["pet_coins"], 9999)


class GiveGiftTests(unittest.TestCase):
    def _stocked(self, **overrides):
        state = fresh_state(pet_coins=9999, **overrides)
        for _ in range(2):
            progression.purchase_gift(state, "sweet_cookie")
        return state

    def test_give_to_active_pet_adds_affection(self):
        state = self._stocked()
        result = progression.give_gift(state, "lunch_meat", "sweet_cookie")
        self.assertTrue(result["ok"])
        # 午餐肉偏好甜心曲奇：+10 → ×1.5 = +15。
        self.assertTrue(result["preferred"])
        self.assertEqual(result["affection"]["gained"], 15)
        self.assertEqual(state["affection_points"], 15)
        self.assertEqual(progression.gift_count(state, "sweet_cookie"), 1)
        self.assertEqual(state["records"]["gifts_given"], 1)
        self.assertEqual(state["records"]["affection_earned"], 15)

    def test_give_non_preferred_gift_gets_base_affection(self):
        state = fresh_state(pet_coins=9999)
        progression.purchase_gift(state, "cheese_cubes")
        result = progression.give_gift(state, "lunch_meat", "cheese_cubes")
        self.assertTrue(result["ok"])
        self.assertFalse(result["preferred"])
        self.assertEqual(result["affection"]["gained"], 10)
        self.assertEqual(state["affection_points"], 10)

    def test_give_levels_up_affection(self):
        state = self._stocked()
        state["affection_points"] = progression.affection_to_next(1) - 1
        result = progression.give_gift(state, None, "sweet_cookie")
        self.assertTrue(result["ok"])
        self.assertTrue(result["affection"]["leveled"])
        self.assertEqual(state["affection_level"], 2)
        self.assertEqual(state["records"]["affection_level_ups"], 1)
        self.assertIn("Lv.2", result["message"])

    def test_give_to_inactive_pet_updates_profile_only(self):
        state = self._stocked(
            active_pet_id="ice_cream",
            owned_pet_ids=["lunch_meat", "ice_cream"],
            pets={
                "lunch_meat": {
                    "pet_name": "午餐肉",
                    "affection_level": 3,
                    "affection_points": 5,
                },
                "ice_cream": {"pet_name": "冰淇淋"},
            },
        )
        result = progression.give_gift(state, "lunch_meat", "sweet_cookie")
        self.assertTrue(result["ok"])
        profile = state["pets"]["lunch_meat"]
        # 偏好加成同样作用于非当前宠物（5 + 15 = 20）。
        self.assertEqual(profile["affection_points"], 20)
        # 门面（当前宠物冰淇淋）好感不动。
        self.assertEqual(state["affection_points"], 0)
        self.assertEqual(state["records"]["affection_earned"], 15)
        self.assertEqual(progression.gift_count(state, "sweet_cookie"), 1)

    def test_give_requires_stock(self):
        state = fresh_state(pet_coins=0)
        result = progression.give_gift(state, "lunch_meat", "love_box")
        self.assertFalse(result["ok"])
        self.assertEqual(state["affection_points"], 0)

    def test_give_rejects_unknown_gift_and_pet(self):
        state = self._stocked()
        self.assertFalse(progression.give_gift(state, "lunch_meat", "x")["ok"])
        missing = fresh_state(
            active_pet_id="lunch_meat",
            pets={"lunch_meat": {"pet_name": "午餐肉"}},
        )
        missing["gift_inventory"] = {"sweet_cookie": 1}
        self.assertFalse(
            progression.give_gift(missing, "ghost_pet", "sweet_cookie")["ok"]
        )


class GiftInventoryPersistenceTests(unittest.TestCase):
    def test_player_field_projects_and_captures_through_facade(self):
        from petpet.app import state as app_state

        state = app_state.ensure_state_schema(
            {"pet_name": "Sheen"}, "Sheen", str,
        )
        # 玩家字段：门面与 player 双端可见，旧存档自动补默认值。
        self.assertEqual(state["player"]["gift_inventory"], {})
        state["gift_inventory"] = {"sweet_cookie": 2}
        app_state.prepare_state_for_save(state)
        self.assertEqual(state["player"]["gift_inventory"], {"sweet_cookie": 2})
        self.assertEqual(
            app_state.STATE_SCHEMA_VERSION, state["state_schema_version"]
        )

    def test_purchase_gift_persists_via_shared_player_field(self):
        from petpet.app import state as app_state

        state = app_state.ensure_state_schema(
            {"pet_name": "Sheen", "pet_coins": 500}, "Sheen", str,
        )
        self.assertTrue(progression.purchase_gift(state, "sweet_cookie")["ok"])
        app_state.prepare_state_for_save(state)
        self.assertEqual(
            state["player"]["gift_inventory"], {"sweet_cookie": 1}
        )


def _qt_app():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class ShopGiftPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _qt_app()

    def setUp(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from PyQt5.QtCore import QPoint, QRect

        self.pet = SimpleNamespace(
            state=progression.ensure_progression({
                "born": 1, "level": 3,
                "hunger": 80, "mood": 70, "energy": 90,
                "pet_coins": 600,
            }),
            current_screen_rect=Mock(return_value=QRect(0, 0, 1200, 900)),
            geometry=Mock(return_value=QRect(900, 600, 190, 220)),
            interface_window_position=Mock(return_value=QPoint(700, 180)),
            say=Mock(),
            update=Mock(),
            home_scene_window=None,
        )

    def test_gift_page_lists_catalog_and_purchases(self):
        from PyQt5.QtWidgets import QLabel, QPushButton
        from progression_ui import ShopWindow
        from unittest.mock import Mock

        saved = []
        shop = ShopWindow(self.pet, saved.append)
        self.addCleanup(shop.close)
        shop._set_page("gifts")

        texts = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        # 偏好轮：分栏（总共/三档）+ 两列网格，商店不显示最爱。
        for _key, label in ShopWindow.GIFT_FILTERS:
            button = shop.findChild(
                QPushButton, "giftFilter_all" if _key == "all"
                else f"giftFilter_{_key}",
            )
            self.assertIsNotNone(button, label)
        for definition in progression.GIFT_DEFINITIONS.values():
            self.assertIn(definition["name"], texts)
            self.assertIn(f"{definition['price']} Pet币", texts)
            self.assertIn(
                f"送出后好感 +{definition['affection']}", texts,
            )
        self.assertIn("持有 0", texts)

        button = shop.findChild(
            QPushButton, "buyGift_sweet_cookie",
        )
        self.assertIsNotNone(button)
        button.click()
        self.assertEqual(
            progression.gift_count(self.pet.state, "sweet_cookie"), 1,
        )
        self.assertEqual(len(saved), 1)
        refreshed = " ".join(
            label.text() for label in shop.findChildren(QLabel)
        )
        self.assertIn("持有 1", refreshed)

    def test_gift_filter_bar_switches_tier(self):
        from PyQt5.QtWidgets import QApplication, QFrame, QPushButton, QSizePolicy
        from progression_ui import ShopWindow
        from unittest.mock import Mock

        shop = ShopWindow(self.pet, Mock())
        self.addCleanup(shop.close)
        shop._set_page("gifts")
        # 等分铺满整行（2026-09-08 用户定稿）：布局不变量 = 无占位
        # stretch 项 + 四枚按钮全部水平 Expanding（像素等宽受离屏字体
        # 最小宽影响，视觉等宽由 Windows 截图验收兜底）。
        shop.show()
        QApplication.processEvents()
        bar = shop.findChild(QFrame, "giftFilterBar")
        self.assertEqual(bar.layout().count(), 4)
        for i in range(bar.layout().count()):
            self.assertIsNone(bar.layout().itemAt(i).spacerItem())
        for key in ("all", "t1", "t2", "t3"):
            button = shop.findChild(QPushButton, f"giftFilter_{key}")
            self.assertEqual(
                button.sizePolicy().horizontalPolicy(),
                QSizePolicy.Expanding,
            )

        def visible_card_names():
            # refresh() 重建页面走 deleteLater——先冲刷延迟删除再扫
            #（坑位：DeferredDelete 不落地时旧卡仍可被 findChild 命中）。
            from PyQt5.QtCore import QEvent
            from PyQt5.QtWidgets import QApplication

            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            names = set()
            for gift_id in progression.GIFT_DEFINITIONS:
                card = shop.findChild(QFrame, f"giftCard_{gift_id}")
                if card is not None and not card.isHidden():
                    names.add(gift_id)
            return names

        tier1 = {
            gid for gid, d in progression.GIFT_DEFINITIONS.items()
            if d["tier"] == 1
        }
        self.assertEqual(
            visible_card_names(), set(progression.GIFT_DEFINITIONS),
        )
        shop._set_gift_filter("t1")
        self.assertEqual(visible_card_names(), tier1)
        shop._set_gift_filter("all")
        self.assertEqual(
            visible_card_names(), set(progression.GIFT_DEFINITIONS),
        )

    def test_shop_hides_preferences(self):
        """偏好轮定稿：商店不显示最爱（偏好只在宠物面板送礼时体现）。"""
        from PyQt5.QtWidgets import QLabel
        from progression_ui import ShopWindow
        from unittest.mock import Mock

        self.pet.state["active_pet_id"] = "lunch_meat"
        shop = ShopWindow(self.pet, Mock())
        self.addCleanup(shop.close)
        shop._set_page("gifts")

        favorites = [
            label for label in shop.findChildren(QLabel)
            if label.objectName().startswith("giftFavorite_")
        ]
        self.assertEqual(favorites, [])
        effect = shop.findChild(QLabel, "giftEffect_sweet_cookie")
        self.assertEqual(effect.text(), "送出后好感 +10")

    def test_buy_button_disabled_without_coins(self):
        from PyQt5.QtWidgets import QPushButton
        from progression_ui import ShopWindow
        from unittest.mock import Mock

        self.pet.state["pet_coins"] = 10
        shop = ShopWindow(self.pet, Mock())
        self.addCleanup(shop.close)
        shop._set_page("gifts")
        button = shop.findChild(QPushButton, "buyGift_love_box")
        self.assertIsNotNone(button)
        self.assertFalse(button.isEnabled())


class ProfileGiftTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _qt_app()

    def _window(self, state=None):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from petpet.ui.pet_profile import PetProfileWindow
        from petpet.app import state as app_state

        if state is None:
            state = app_state.ensure_state_schema({}, "Sheen", str)
            progression.ensure_progression(state)
        pet = SimpleNamespace(
            state=state,
            set_active_pet=Mock(return_value={"ok": True}),
            set_pet_name=Mock(),
            update=Mock(),
            say=Mock(),
            home_scene_window=None,
            open_shop=Mock(),
        )
        window = PetProfileWindow(pet, save_state=Mock())
        self.addCleanup(window.close)
        return window, pet

    def test_third_tab_switches_to_gift_page(self):
        from PyQt5.QtTest import QTest

        window, _ = self._window()
        self.assertIn("礼物", window._tab_buttons)
        QTest.mouseClick(window._tab_buttons["礼物"], Qt.LeftButton)
        self.assertTrue(window._gift_page.isVisibleTo(window))
        self.assertFalse(window._intro_page.isVisibleTo(window))

    def test_gift_cards_are_compact_three_per_row_equal_width(self):
        """简略三列网格（2026-09-08）：一行三个、最爱与否等宽。"""
        from PyQt5.QtWidgets import QApplication, QGridLayout, QLabel

        state = progression.ensure_progression({"pet_coins": 9999})
        for gift_id in ("sweet_cookie", "cheese_cubes", "meat_can"):
            progression.purchase_gift(state, gift_id)
        window, _ = self._window(state)
        window._show_tab("礼物")

        # 三张卡（甜心曲奇=最爱、其余非最爱）都在同一网格里。
        grids = window._gift_page.findChildren(QGridLayout)
        self.assertTrue(grids, "礼物卡应在 QGridLayout 内")
        cards = [
            window._gift_widgets[gift_id]
            for gift_id in ("sweet_cookie", "cheese_cubes", "meat_can")
        ]
        window.show()
        QApplication.processEvents()
        widths = [card.width() for card in cards]
        # 三列等分允许 1px 布局取整差（175/174/175）。
        self.assertLessEqual(
            max(widths) - min(widths), 1,
            "最爱/非最爱卡片应等宽（三列等分）",
        )
        # 最爱卡与普通卡等高（♥ 字形回退变高的回归防线）。
        heights = [card.height() for card in cards]
        self.assertLessEqual(
            max(heights) - min(heights), 1,
            "最爱/非最爱卡片应等高",
        )
        # 简略卡：无描述行。
        self.assertIsNone(
            cards[0].findChild(QLabel, "giftSummary_sweet_cookie"),
        )

    def test_empty_inventory_shows_guidance(self):
        from PyQt5.QtWidgets import QLabel

        window, pet = self._window()
        window._show_tab("礼物")
        from PyQt5.QtWidgets import QWidget

        host = window._gift_page.findChild(
            QWidget, "giftEmptyHint").parentWidget()
        hint = host.findChild(QLabel, "giftEmptyHint")
        self.assertIsNotNone(hint)
        self.assertEqual(window._gift_widgets, {})
        # 直达按钮（2026-09-10）：点击调用 open_shop("gifts")。
        from PyQt5.QtWidgets import QPushButton

        go = window._gift_page.findChild(QPushButton, "giftGoShopButton")
        self.assertIsNotNone(go)
        go.click()
        pet.open_shop.assert_called_once_with("gifts")

    def test_stocked_gift_shows_card_and_gives_with_confirm(self):
        from PyQt5.QtWidgets import QLabel

        state = progression.ensure_progression({"pet_coins": 9999})
        progression.purchase_gift(state, "sweet_cookie")
        window, pet = self._window(state)
        window._show_tab("礼物")

        self.assertEqual(list(window._gift_widgets), ["sweet_cookie"])
        card = window._gift_widgets["sweet_cookie"]
        # 2026-09-08 定稿：「♥ 最爱」行删去，最爱仅由珊瑚色 ♥ 数值行表达。
        self.assertIsNone(
            card.findChild(QLabel, "giftFavorite_sweet_cookie"),
        )
        count = card.findChild(QLabel, "giftCount_sweet_cookie")
        # 2026-09-09：♥ 字符已去（幼圆缺字形回退变高，最爱卡比普通卡高）。
        self.assertNotIn("♥", count.text())
        self.assertIn("+15", count.text())
        self.assertIn("×1", count.text())

        window._confirm_send_gift = lambda _gid: True
        window._give_gift("sweet_cookie")
        self.assertEqual(
            progression.gift_count(state, "sweet_cookie"), 0,
        )
        self.assertEqual(state["affection_points"], 15)
        window._save_state.assert_called_once()
        pet.say.assert_called_once()
        hint = window._gift_page.findChild(QLabel, "giftEmptyHint")
        self.assertIsNotNone(hint, "送出后背包清空应回到引导文案")

    def test_declined_confirm_keeps_inventory(self):
        state = progression.ensure_progression({"pet_coins": 9999})
        progression.purchase_gift(state, "meat_can")
        window, _ = self._window(state)
        window._confirm_send_gift = lambda _gid: False
        window._give_gift("meat_can")
        self.assertEqual(
            progression.gift_count(state, "meat_can"), 1,
        )
        self.assertEqual(state["affection_points"], 0)
