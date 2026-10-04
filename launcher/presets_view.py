"""
presets_view.py
---------------
Provides the graphical interface for exploring the aircraft database, managing weapon loadouts,
and configuring custom presets for pylons and countermeasures.
"""

import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QLabel, QWidget, QScrollArea, QPushButton, QComboBox,
    QListWidgetItem, QGridLayout, QStackedWidget, QToolButton,
    QLineEdit, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QIntValidator


class PresetManagerDialog(QDialog):
    """
    Sub-dialog for managing existing user presets (loading, setting as main, or deleting).
    """
    def __init__(self, presets_dict, main_preset_name=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Presets")
        self.setFixedSize(320, 400)
        self.selected_preset = None
        self.action = None

        layout = QVBoxLayout(self)

        lbl = QLabel("Select a preset:")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        for p_name in presets_dict.keys():
            if p_name == "_main":
                continue
            display_text = f"⭐ {p_name}" if p_name == main_preset_name else p_name
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, p_name)
            self.list_widget.addItem(item)

        self.list_widget.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.list_widget)

        btn_layout = QGridLayout()
        self.btn_load = QPushButton("📂 Load")
        self.btn_main = QPushButton("⭐ Set Main")
        self.btn_delete = QPushButton("🗑 Delete")

        self.btn_delete.setStyleSheet("color: #d9534f; font-weight: bold;")

        btn_layout.addWidget(self.btn_load, 0, 0)
        btn_layout.addWidget(self.btn_main, 0, 1)
        btn_layout.addWidget(self.btn_delete, 1, 0, 1, 2)
        layout.addLayout(btn_layout)

        self.btn_load.clicked.connect(self._load)
        self.btn_main.clicked.connect(self._set_main)
        self.btn_delete.clicked.connect(self._delete)
        self.list_widget.itemDoubleClicked.connect(self._load)

    def _get_selected(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _load(self):
        name = self._get_selected()
        if name:
            self.selected_preset = name
            self.action = "load"
            self.accept()

    def _set_main(self):
        name = self._get_selected()
        if name:
            self.selected_preset = name
            self.action = "set_main"
            self.accept()

    def _delete(self):
        name = self._get_selected()
        if name:
            reply = QMessageBox.question(
                self, 'Delete Preset', f"Are you sure you want to delete '{name}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.selected_preset = name
                self.action = "delete"
                self.accept()


class PresetsWindow(QDialog):
    """
    Main dialog window for exploring available aircraft, filtering by nation/rank/BR,
    and modifying the payload configurations for each pylon.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aircraft Presets & Weapons Loadout")

        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        self.resize(850, 550)

        self.database = self._load_database()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_presets_path = os.path.join(base_dir, "data", "user_presets.json")
        self.favorites_path = os.path.join(base_dir, "data", "favorites.json")

        self.user_presets = self._load_user_presets()
        self.favorites = self._load_favorites()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self.page_countries = QWidget()
        self.page_loadout = QWidget()

        self._build_country_page()
        self._build_loadout_page()

        self.stacked_widget.addWidget(self.page_countries)
        self.stacked_widget.addWidget(self.page_loadout)

        self._populate_countries()
        self.stacked_widget.setCurrentIndex(0)

    def _load_database(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, "data", "aircraft_db.json")

        if not os.path.exists(db_path):
            print(f"[ERROR] [PRESETS] Database file missing at: {db_path}")
            return {}

        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] [PRESETS] Failed to parse database: {e}")
            return {}

    def _load_user_presets(self):
        if not os.path.exists(self.user_presets_path):
            return {}
        try:
            with open(self.user_presets_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_user_presets_to_disk(self):
        os.makedirs(os.path.dirname(self.user_presets_path), exist_ok=True)
        try:
            with open(self.user_presets_path, "w", encoding="utf-8") as f:
                json.dump(self.user_presets, f, indent=4)
        except Exception as e:
            print(f"[ERROR] [PRESETS] Failed to save user presets: {e}")

    def _load_favorites(self):
        if not os.path.exists(self.favorites_path):
            return []
        try:
            with open(self.favorites_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_favorites(self):
        os.makedirs(os.path.dirname(self.favorites_path), exist_ok=True)
        try:
            with open(self.favorites_path, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, indent=4)
        except Exception as e:
            print(f"[ERROR] [PRESETS] Failed to save favorites: {e}")

    def _get_flag_icon(self, country_name):
        if not country_name:
            return None

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_base_name = str(country_name).lower().replace(' ', '_')

        icon_path_png = os.path.join(base_dir, "assets", "flags", f"{icon_base_name}.png")
        icon_path_svg = os.path.join(base_dir, "assets", "flags", f"{icon_base_name}.svg")

        if os.path.exists(icon_path_png):
            return QIcon(icon_path_png)
        elif os.path.exists(icon_path_svg):
            return QIcon(icon_path_svg)

        return None

    def _build_country_page(self):
        layout = QVBoxLayout(self.page_countries)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("Select Nation")
        font = lbl.font()
        font.setPointSize(22)
        font.setBold(True)
        lbl.setFont(font)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(lbl)
        layout.addSpacing(15)

        search_layout = QHBoxLayout()
        self.main_search_bar = QLineEdit()
        self.main_search_bar.setPlaceholderText("Quick search all aircraft...")
        self.main_search_bar.setFixedSize(500, 45)

        self.main_search_bar.setStyleSheet("""
            QLineEdit { background-color: #FFFFFF; color: #000000; border: 2px solid #CCCCCC; border-radius: 22px; padding: 5px 20px; font-size: 15px; }
            QLineEdit:focus { border: 2px solid #5c9ddb; }
        """)
        self.main_search_bar.textChanged.connect(self._on_main_search)

        search_layout.addStretch()
        search_layout.addWidget(self.main_search_bar)
        search_layout.addStretch()

        layout.addLayout(search_layout)
        layout.addSpacing(30)

        self.main_country_grid = QGridLayout()
        self.main_country_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_country_grid.setSpacing(15)
        layout.addLayout(self.main_country_grid)

        layout.addSpacing(40)

        self.lbl_sub = QLabel("Sub-Nations")
        font_sub = self.lbl_sub.font()
        font_sub.setPointSize(14)
        font_sub.setBold(True)
        self.lbl_sub.setFont(font_sub)
        self.lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_sub)
        layout.addSpacing(15)

        self.sub_country_grid = QGridLayout()
        self.sub_country_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_country_grid.setSpacing(10)
        layout.addLayout(self.sub_country_grid)

        layout.addStretch(2)

    def _build_loadout_page(self):
        layout = QHBoxLayout(self.page_loadout)
        layout.setContentsMargins(10, 10, 10, 10)

        # Left Panel (Filters and List)
        left_panel = QWidget()
        left_panel.setFixedWidth(310)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.btn_back = QPushButton("← Back to Nations")
        self.btn_back.setMinimumHeight(35)
        self.btn_back.setStyleSheet("font-weight: bold;")
        self.btn_back.clicked.connect(self._go_back)
        left_layout.addWidget(self.btn_back)

        self.local_search = QLineEdit()
        self.local_search.setPlaceholderText("Search in list...")
        self.local_search.setFixedHeight(35)
        self.local_search.setStyleSheet(
            "border: 1px solid #aaa; border-radius: 4px; padding: 2px 8px; color: #000; background: #fff;")
        self.local_search.textChanged.connect(self._apply_filters)
        left_layout.addWidget(self.local_search)

        filters_widget = QWidget()
        filters_layout = QVBoxLayout(filters_widget)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(5)

        combo_style = "QComboBox { background: #fff; color: #000; border: 1px solid #aaa; border-radius: 4px; padding: 3px; }"

        self.combo_country = QComboBox()
        self.combo_country.setStyleSheet(combo_style)
        self.combo_country.currentIndexChanged.connect(self._apply_filters)
        filters_layout.addWidget(self.combo_country)

        rank_br_layout = QHBoxLayout()
        self.combo_rank = QComboBox()
        self.combo_rank.setStyleSheet(combo_style)
        self.combo_br = QComboBox()
        self.combo_br.setStyleSheet(combo_style)

        self.combo_rank.currentIndexChanged.connect(self._on_rank_changed)
        self.combo_br.currentIndexChanged.connect(self._on_br_changed)

        rank_br_layout.addWidget(self.combo_rank)
        rank_br_layout.addWidget(self.combo_br)
        filters_layout.addLayout(rank_br_layout)

        left_layout.addWidget(filters_widget)

        self.plane_list = QListWidget()
        self.plane_list.currentItemChanged.connect(self._on_plane_selected)
        self.plane_list.setIconSize(QSize(24, 16))
        left_layout.addWidget(self.plane_list)

        layout.addWidget(left_panel)

        # Right Panel (Loadout Configuration)
        right_panel = QWidget()
        self.right_layout = QVBoxLayout(right_panel)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        self.lbl_plane_name = QLabel("Select an aircraft")
        font = self.lbl_plane_name.font()
        font.setPointSize(16)
        font.setBold(True)
        self.lbl_plane_name.setFont(font)

        self.lbl_current_preset = QLabel("Current:")
        self.lbl_current_preset.setStyleSheet("color: #5c9ddb; font-weight: bold;")

        title_layout.addWidget(self.lbl_plane_name)
        title_layout.addWidget(self.lbl_current_preset)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        self.btn_favorite = QPushButton("☆ Favorite")
        self.btn_favorite.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.btn_favorite.clicked.connect(self._toggle_favorite)
        self.btn_favorite.hide()
        header_layout.addWidget(self.btn_favorite)

        self.btn_my_presets = QPushButton("📂 My Presets")
        self.btn_my_presets.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.btn_my_presets.clicked.connect(self._open_preset_manager)
        self.btn_my_presets.hide()
        header_layout.addWidget(self.btn_my_presets)

        self.btn_clear = QPushButton("🧹 Clear")
        self.btn_clear.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.btn_clear.clicked.connect(self._clear_current_loadout)
        self.btn_clear.hide()
        header_layout.addWidget(self.btn_clear)

        self.btn_save_preset = QPushButton("💾 Save Preset")
        self.btn_save_preset.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.btn_save_preset.clicked.connect(self._save_current_preset)
        self.btn_save_preset.hide()
        header_layout.addWidget(self.btn_save_preset)

        self.right_layout.addLayout(header_layout)
        self.right_layout.addSpacing(15)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        pylons_container = QWidget()

        self.pylons_layout = QHBoxLayout(pylons_container)
        self.pylons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(pylons_container)
        self.right_layout.addWidget(scroll_area)
        layout.addWidget(right_panel)

    def _create_flag_button(self, name, width, height, icon_width, icon_height):
        btn = QToolButton()
        btn.setText(name)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setFixedSize(width, height)

        btn.setStyleSheet("""
            QToolButton { background: transparent; color: #000000; border: 2px solid transparent; border-radius: 6px; }
            QToolButton:hover { background: rgba(0, 0, 0, 0.05); border: 2px solid #5c9ddb; }
            QToolButton:pressed { background: rgba(0, 0, 0, 0.1); border: 2px solid #3a7ebf; }
        """)

        font = btn.font()
        font.setPointSize(11 if width > 100 else 9)
        font.setBold(True)
        btn.setFont(font)

        icon = self._get_flag_icon(name)
        if icon:
            btn.setIcon(icon)
        else:
            transparent_pixmap = QPixmap(icon_width, icon_height)
            transparent_pixmap.fill(Qt.transparent)
            btn.setIcon(QIcon(transparent_pixmap))

        btn.setIconSize(QSize(icon_width, icon_height))
        return btn

    def _populate_countries(self):
        unique_main = set()
        unique_sub = set()
        unique_ranks = set()
        unique_brs = set()

        for data in self.database.values():
            country = data.get("country")
            sub_country = data.get("sub_country")
            rank = data.get("rank")
            br = data.get("br")

            if country:
                unique_main.add(str(country).strip())
            if sub_country:
                unique_sub.add(str(sub_country).strip())

            if rank is not None:
                try:
                    unique_ranks.add(int(rank))
                except ValueError:
                    pass
            if br is not None:
                try:
                    unique_brs.add(float(br))
                except ValueError:
                    pass

        wt_order = ["USA", "Germany", "USSR", "Great Britain", "Japan", "China", "Italy", "France", "Sweden", "Israel"]

        def sort_wt_logic(c_name):
            for i, wt_country in enumerate(wt_order):
                if c_name.upper() == wt_country.upper() or (c_name.upper() == "GB" and wt_country == "Great Britain"):
                    return i
            return 999

        sorted_main = sorted(list(unique_main), key=lambda x: (sort_wt_logic(x), x))
        sorted_sub = sorted(list(unique_sub))

        main_col_count = 5
        for i, country in enumerate(sorted_main):
            btn = self._create_flag_button(country, width=130, height=95, icon_width=110, icon_height=65)
            btn.clicked.connect(lambda checked, c=country: self._filter_planes_by_country(c))

            row = i // main_col_count
            col = i % main_col_count
            self.main_country_grid.addWidget(btn, row, col)

        if not sorted_sub:
            self.lbl_sub.hide()
        else:
            self.lbl_sub.show()
            sub_col_count = 6
            for i, sub_c in enumerate(sorted_sub):
                btn = self._create_flag_button(sub_c, width=100, height=75, icon_width=75, icon_height=45)
                btn.clicked.connect(lambda checked, sc=sub_c: self._filter_planes_by_country(sc))

                row = i // sub_col_count
                col = i % sub_col_count
                self.sub_country_grid.addWidget(btn, row, col)

        self.combo_country.blockSignals(True)
        self.combo_country.clear()
        self.combo_country.addItem("All Nations")
        all_countries = sorted(list(unique_main.union(unique_sub)), key=lambda x: (sort_wt_logic(x), x))
        self.combo_country.addItems(all_countries)
        self.combo_country.blockSignals(False)

        self.combo_rank.blockSignals(True)
        self.combo_rank.clear()
        self.combo_rank.addItem("Any Rank", -1)
        for r in sorted(list(unique_ranks)):
            self.combo_rank.addItem(f"Rank {r}", r)
        self.combo_rank.blockSignals(False)

        self.combo_br.blockSignals(True)
        self.combo_br.clear()
        self.combo_br.addItem("Any BR", -1.0)
        for b in sorted(list(unique_brs)):
            self.combo_br.addItem(f"{b:.1f}", b)
        self.combo_br.blockSignals(False)

    def _on_main_search(self, text):
        if not text.strip():
            return

        self.main_search_bar.blockSignals(True)
        self.main_search_bar.clear()
        self.main_search_bar.blockSignals(False)

        self.combo_country.blockSignals(True)
        self.combo_country.setCurrentIndex(0)
        self.combo_country.blockSignals(False)

        self.combo_rank.blockSignals(True)
        self.combo_rank.setCurrentIndex(0)
        self.combo_rank.blockSignals(False)

        self.combo_br.blockSignals(True)
        self.combo_br.setCurrentIndex(0)
        self.combo_br.blockSignals(False)

        self.local_search.setText(text)
        self.stacked_widget.setCurrentIndex(1)
        self.local_search.setFocus()

    def _on_rank_changed(self, index):
        if self.combo_rank.currentData() != -1:
            self.combo_br.blockSignals(True)
            self.combo_br.setCurrentIndex(0)
            self.combo_br.blockSignals(False)
        self._apply_filters()

    def _on_br_changed(self, index):
        if self.combo_br.currentData() != -1.0:
            self.combo_rank.blockSignals(True)
            self.combo_rank.setCurrentIndex(0)
            self.combo_rank.blockSignals(False)
        self._apply_filters()

    def _filter_planes_by_country(self, target_country):
        index = self.combo_country.findText(target_country)
        if index >= 0:
            self.combo_country.blockSignals(True)
            self.combo_country.setCurrentIndex(index)
            self.combo_country.blockSignals(False)

        self.local_search.blockSignals(True)
        self.local_search.clear()
        self.local_search.blockSignals(False)

        self.combo_rank.blockSignals(True)
        self.combo_rank.setCurrentIndex(0)
        self.combo_rank.blockSignals(False)

        self.combo_br.blockSignals(True)
        self.combo_br.setCurrentIndex(0)
        self.combo_br.blockSignals(False)

        self._apply_filters()
        self.stacked_widget.setCurrentIndex(1)

    def _apply_filters(self, *args):
        self.plane_list.clear()
        search_text = self.local_search.text().strip().lower()
        clean_search = search_text.replace("-", "").replace(" ", "")

        selected_country = self.combo_country.currentText()
        selected_rank = self.combo_rank.currentData()
        selected_br = self.combo_br.currentData()

        matches = []
        for tag, data in self.database.items():
            c = str(data.get("country", "")).strip()
            sc = str(data.get("sub_country", "")).strip()

            if selected_country != "All Nations":
                if c != selected_country and sc != selected_country:
                    continue

            if selected_rank != -1:
                if data.get("rank") != selected_rank:
                    continue

            if selected_br != -1.0:
                try:
                    plane_br = float(data.get("br", 0))
                    if abs(plane_br - selected_br) > 0.05:
                        continue
                except (ValueError, TypeError):
                    continue

            raw_name = data.get("name", tag)
            name_lower = raw_name.lower()
            clean_name = name_lower.replace("-", "").replace(" ", "")

            if clean_search:
                if clean_search not in clean_name and search_text not in tag.lower():
                    continue

                if name_lower.startswith(search_text) or clean_name.startswith(clean_search):
                    priority = 0
                elif f" {search_text}" in name_lower or f"-{search_text}" in name_lower:
                    priority = 1
                else:
                    priority = 2
            else:
                priority = 0

            if tag in self.favorites:
                priority -= 0.5

            country_for_icon = sc if sc else c
            matches.append((priority, raw_name, tag, country_for_icon))

        matches.sort(key=lambda x: (x[0], x[1]))

        for priority, raw_name, tag, country_for_icon in matches:
            display_name = f"⭐ {raw_name}" if tag in self.favorites else raw_name
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, tag)

            icon = self._get_flag_icon(country_for_icon)
            if icon:
                item.setIcon(icon)

            self.plane_list.addItem(item)

        self.lbl_plane_name.setText(f"Found: {len(matches)} aircraft")
        self._clear_pylons_layout()

        self.btn_my_presets.hide()
        self.btn_save_preset.hide()
        self.btn_favorite.hide()
        self.btn_clear.hide()

    def _go_back(self):
        self.stacked_widget.setCurrentIndex(0)

    def _clear_pylons_layout(self):
        def clear_recursive(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    clear_recursive(item.layout())
                    item.layout().deleteLater()

        clear_recursive(self.pylons_layout)

    def _toggle_favorite(self):
        if not getattr(self, 'current_plane', None):
            return

        if self.current_plane in self.favorites:
            self.favorites.remove(self.current_plane)
        else:
            self.favorites.append(self.current_plane)

        self._save_favorites()
        self._update_favorite_button()

        for i in range(self.plane_list.count()):
            item = self.plane_list.item(i)
            if item.data(Qt.UserRole) == self.current_plane:
                raw_name = self.database.get(self.current_plane, {}).get("name", self.current_plane)
                display_name = f"⭐ {raw_name}" if self.current_plane in self.favorites else raw_name
                item.setText(display_name)
                break

    def _update_favorite_button(self):
        if not getattr(self, 'current_plane', None):
            self.btn_favorite.hide()
            return

        self.btn_favorite.show()
        if self.current_plane in self.favorites:
            self.btn_favorite.setText("⭐ Unfavorite")
            self.btn_favorite.setStyleSheet(
                "font-weight: bold; padding: 5px 15px; color: #f0ad4e; border: 1px solid #f0ad4e;")
        else:
            self.btn_favorite.setText("☆ Favorite")
            self.btn_favorite.setStyleSheet("font-weight: bold; padding: 5px 15px;")

    def _update_preset_visibility(self):
        if self.current_plane in self.user_presets:
            has_presets = any(k != "_main" for k in self.user_presets[self.current_plane].keys())
            if has_presets:
                self.btn_my_presets.show()
                return
        self.btn_my_presets.hide()

    def _apply_preset_to_ui(self, preset_name):
        preset_data = self.user_presets[self.current_plane][preset_name]
        loadout = preset_data.get("pylons", {})

        for pylon_idx, combo in self.current_pylon_combos.items():
            combo.blockSignals(True)
            saved_weapon = loadout.get(pylon_idx, "< Empty >")

            if combo.isEnabled():
                idx = combo.findText(saved_weapon)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentIndex(0)
            combo.blockSignals(False)

        self.input_flares.blockSignals(True)
        self.input_flares.setText(str(preset_data.get("flares", 0)))
        self.input_flares.blockSignals(False)

        self.input_chaff.blockSignals(True)
        self.input_chaff.setText(str(preset_data.get("chaff", 0)))
        self.input_chaff.blockSignals(False)

        self.lbl_current_preset.setText(f"Current: {preset_name}")

    def _clear_current_loadout(self):
        """Clears all comboboxes and input fields without deleting the saved preset."""
        for pylon_idx, combo in self.current_pylon_combos.items():
            combo.blockSignals(True)
            if combo.isEnabled():
                idx = combo.findText("< Empty >")
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentIndex(0)
            combo.blockSignals(False)

        self.input_flares.blockSignals(True)
        self.input_flares.setText("0")
        self.input_flares.blockSignals(False)

        self.input_chaff.blockSignals(True)
        self.input_chaff.setText("0")
        self.input_chaff.blockSignals(False)

        self._on_loadout_manually_changed()

    def _on_loadout_manually_changed(self):
        if not self.lbl_current_preset.text().startswith("Current: < Custom Loadout >"):
            self.lbl_current_preset.setText("Current: < Custom Loadout >")

    def _open_preset_manager(self):
        presets_dict = self.user_presets.get(self.current_plane, {})
        if not presets_dict:
            return

        main_preset = presets_dict.get("_main")
        dialog = PresetManagerDialog(presets_dict, main_preset, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.selected_preset

            if dialog.action == "load":
                self._apply_preset_to_ui(selected)

            elif dialog.action == "set_main":
                self.user_presets[self.current_plane]["_main"] = selected
                self._save_user_presets_to_disk()
                QMessageBox.information(
                    self, "Main Preset",
                    f"'{selected}' is now the main preset and will load automatically."
                )

            elif dialog.action == "delete":
                del self.user_presets[self.current_plane][selected]
                if presets_dict.get("_main") == selected:
                    del self.user_presets[self.current_plane]["_main"]

                self._save_user_presets_to_disk()
                self._update_preset_visibility()

                if self.lbl_current_preset.text() == f"Current: {selected}":
                    self.lbl_current_preset.setText("Current: < Custom Loadout >")

    def _save_current_preset(self):
        loadout_dict = {}
        for pylon_idx, combo in self.current_pylon_combos.items():
            weapon_name = combo.currentText()
            if weapon_name not in ("< Empty >", "< N/A >"):
                loadout_dict[pylon_idx] = weapon_name

        preset_data = {
            "plane_tag": self.current_plane,
            "pylons": loadout_dict,
            "flares": int(self.input_flares.text() or "0"),
            "chaff": int(self.input_chaff.text() or "0")
        }

        text, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this loadout (e.g. 'Air-to-Air'):")
        if ok and text.strip():
            preset_name = text.strip()

            if self.current_plane in self.user_presets and preset_name in self.user_presets[self.current_plane]:
                QMessageBox.warning(
                    self, "Duplicate Name",
                    f"A preset named '{preset_name}' already exists for this aircraft!\n\n"
                    "Please choose a different name or delete the old one first."
                )
                return

            if self.current_plane not in self.user_presets:
                self.user_presets[self.current_plane] = {}

            self.user_presets[self.current_plane][preset_name] = preset_data

            if len([k for k in self.user_presets[self.current_plane].keys() if k != "_main"]) == 1:
                self.user_presets[self.current_plane]["_main"] = preset_name

            self._save_user_presets_to_disk()
            self._update_preset_visibility()
            self.lbl_current_preset.setText(f"Current: {preset_name}")
            QMessageBox.information(self, "Saved", f"Preset '{preset_name}' saved successfully!")

    def _on_plane_selected(self, current_item, previous_item=None):
        if not current_item:
            self.btn_my_presets.hide()
            self.btn_save_preset.hide()
            self.btn_favorite.hide()
            self.btn_clear.hide()
            return

        self.current_plane = current_item.data(Qt.UserRole)
        plane_data = self.database.get(self.current_plane)

        if not plane_data:
            return

        self.lbl_plane_name.setText(plane_data.get("name", self.current_plane))
        self.lbl_current_preset.setText("Current: < Custom Loadout >")
        self._clear_pylons_layout()

        self.btn_save_preset.show()
        self.btn_clear.show()
        self._update_preset_visibility()
        self._update_favorite_button()

        pylons = plane_data.get("pylons", {})
        self.current_pylon_combos = {}

        grid_layout = QGridLayout()
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        grid_layout.setHorizontalSpacing(40)
        grid_layout.setVerticalSpacing(4)

        for pylon_idx in range(1, 14):
            str_idx = str(pylon_idx)
            weapons = pylons.get(str_idx, [])

            lbl = QLabel(f"Station {pylon_idx}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = lbl.font()
            font.setPointSize(9)
            lbl.setFont(font)

            combo = QComboBox()
            combo.setFixedWidth(160)

            if weapons:
                combo.addItem("< Empty >")
                combo.addItems(weapons)
                combo.setEnabled(True)
            else:
                combo.addItem("< N/A >")
                combo.setEnabled(False)
                lbl.setStyleSheet("color: #999999;")

            self.current_pylon_combos[str_idx] = combo

            if pylon_idx <= 6:
                row_base = (pylon_idx - 1) * 3
                col = 0
            elif pylon_idx == 7:
                row_base = 6
                col = 1
            else:
                row_base = (pylon_idx - 8) * 3
                col = 2

            grid_layout.addWidget(lbl, row_base, col)
            grid_layout.addWidget(combo, row_base + 1, col)
            grid_layout.setRowMinimumHeight(row_base + 2, 12)

            combo.activated.connect(self._on_loadout_manually_changed)

        vertical_container = QVBoxLayout()
        vertical_container.setAlignment(Qt.AlignmentFlag.AlignTop)

        vertical_container.addLayout(grid_layout)
        vertical_container.addSpacing(30)

        counter_layout = QHBoxLayout()
        counter_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_flares = QLabel("Flares:")
        lbl_flares.setStyleSheet("font-weight: bold; font-size: 14px; color: #d9534f;")

        self.input_flares = QLineEdit()
        self.input_flares.setValidator(QIntValidator(0, 9999, self))
        self.input_flares.setText("0")
        self.input_flares.setFixedWidth(80)
        self.input_flares.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_flares.setStyleSheet(
            "font-size: 14px; padding: 4px; border: 1px solid #aaa; border-radius: 4px; background: #fff;")

        lbl_chaff = QLabel("Chaff:")
        lbl_chaff.setStyleSheet("font-weight: bold; font-size: 14px; color: #5c9ddb;")

        self.input_chaff = QLineEdit()
        self.input_chaff.setValidator(QIntValidator(0, 9999, self))
        self.input_chaff.setText("0")
        self.input_chaff.setFixedWidth(80)
        self.input_chaff.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_chaff.setStyleSheet(
            "font-size: 14px; padding: 4px; border: 1px solid #aaa; border-radius: 4px; background: #fff;")

        self.input_flares.textChanged.connect(lambda *args: self._on_loadout_manually_changed())
        self.input_chaff.textChanged.connect(lambda *args: self._on_loadout_manually_changed())

        counter_layout.addWidget(lbl_flares)
        counter_layout.addWidget(self.input_flares)
        counter_layout.addSpacing(40)
        counter_layout.addWidget(lbl_chaff)
        counter_layout.addWidget(self.input_chaff)

        vertical_container.addLayout(counter_layout)
        vertical_container.addStretch()

        self.pylons_layout.addLayout(vertical_container)

        plane_presets = self.user_presets.get(self.current_plane, {})
        main_preset_name = plane_presets.get("_main")
        if main_preset_name and main_preset_name in plane_presets:
            self._apply_preset_to_ui(main_preset_name)

    def jump_to_plane(self, plane_tag):
        self.combo_country.blockSignals(True)
        self.combo_country.setCurrentIndex(0)
        self.combo_country.blockSignals(False)

        self.combo_rank.blockSignals(True)
        self.combo_rank.setCurrentIndex(0)
        self.combo_rank.blockSignals(False)

        self.combo_br.blockSignals(True)
        self.combo_br.setCurrentIndex(0)
        self.combo_br.blockSignals(False)

        self.local_search.blockSignals(True)
        self.local_search.clear()
        self.local_search.blockSignals(False)

        self._apply_filters()

        self.stacked_widget.setCurrentIndex(1)

        for i in range(self.plane_list.count()):
            item = self.plane_list.item(i)
            if item.data(Qt.UserRole) == plane_tag:
                self.plane_list.setCurrentItem(item)
                self.plane_list.scrollToItem(item)
                break