import json
import urllib.request
import urllib.error
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QWidget, QComboBox, QMessageBox, QTabWidget, QGridLayout,
    QScrollArea, QFrame, QLineEdit, QTextEdit, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QColor, QFont

def get_firebase_url():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    if key.strip() == 'FIREBASE_DB_URL':
                        return val.strip()
    return ""

FIREBASE_URL = get_firebase_url()

class FetchCloudWorker(QThread):
    data_fetched = Signal(dict)
    error = Signal(str)

    def run(self):
        if not FIREBASE_URL:
            self.error.emit("Firebase URL is missing. Check your .env file.")
            return
            
        try:
            req = urllib.request.Request(FIREBASE_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8', errors='ignore'))
                if not data:
                    data = {}
                self.data_fetched.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class UploadCloudWorker(QThread):
    upload_success = Signal()
    error = Signal(str)

    def __init__(self, data_payload):
        super().__init__()
        self.data_payload = data_payload

    def run(self):
        if not FIREBASE_URL:
            self.error.emit("Firebase URL is missing. Check your .env file.")
            return
            
        try:
            payload = json.dumps(self.data_payload).encode('utf-8')
            req = urllib.request.Request(
                FIREBASE_URL, 
                data=payload, 
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()
            self.upload_success.emit()
        except Exception as e:
            self.error.emit(str(e))


class MarketplaceItemCard(QFrame):
    """Parallel display card for Presets and Custom Effects inside the grid."""
    def __init__(self, item_key, item_data, on_click_callback, parent=None):
        super().__init__(parent)
        self.item_key = item_key
        self.item_data = item_data
        self.on_click_callback = on_click_callback
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(80)

        self.setStyleSheet("""
            MarketplaceItemCard {
                background-color: #151722;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
            }
            MarketplaceItemCard:hover {
                background-color: #1C1E2D;
                border: 1px solid rgba(0, 229, 255, 0.6);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = item_data.get("preset_name", "Untitled Creation")
        author = item_data.get("author", "Community Member")
        desc = item_data.get("description", "")
        if len(desc) > 36:
            desc = desc[:33] + "..."

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #FFFFFF; border: none; background: transparent;")
        
        lbl_author = QLabel(f"by {author}")
        lbl_author.setStyleSheet("font-size: 11px; color: #9AA0A6; border: none; background: transparent;")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_author)
        if desc:
            lbl_desc = QLabel(desc)
            lbl_desc.setStyleSheet("font-size: 11px; color: #707585; font-style: italic; border: none; background: transparent;")
            layout.addWidget(lbl_desc)
        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click_callback:
            self.on_click_callback(self.item_key, self.item_data)
        super().mousePressEvent(event)


class EffectDetailDialog(QDialog):
    """Full detail screen for marketplace items with live hardware previewing and studio editing."""
    def __init__(self, item_key, item_data, parent_app=None, marketplace_dialog=None):
        super().__init__(marketplace_dialog or parent_app)
        self.item_key = item_key
        self.item_data = item_data
        self.parent_app = parent_app
        self.marketplace_dialog = marketplace_dialog
        self.is_previewing = False

        title = item_data.get("preset_name", "Untitled")
        self.setWindowTitle(f"Effect Details - {title}")
        self.setMinimumSize(540, 380)
        self.setStyleSheet("""
            QDialog { background-color: #0F1118; color: #E2E2E2; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: #E2E2E2; }
            QPushButton { background: #1C1E2B; color: white; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background: rgba(0, 229, 255, 0.18); color: #00E5FF; border-color: #00E5FF; }
            QTextEdit { background-color: #151722; color: #D0D4E0; border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 12px; font-size: 13px; }
        """)

        # Save active mode to restore when dialog closes or preview stops
        self.previous_mode = None
        if self.parent_app and hasattr(self.parent_app, "mode_list") and self.parent_app.mode_list.currentItem():
            self.previous_mode = self.parent_app.mode_list.currentItem().text()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #00E5FF;")
        layout.addWidget(lbl_title)

        author = item_data.get("author", "Community Member")
        lbl_author = QLabel(f"Created by: {author}")
        lbl_author.setStyleSheet("font-size: 12px; color: #9AA0A6; font-weight: 600;")
        layout.addWidget(lbl_author)

        layout.addWidget(QLabel("Description & Overview:"))
        desc_box = QTextEdit()
        desc = item_data.get("description", "No description provided by author.")
        desc_box.setPlainText(desc)
        desc_box.setReadOnly(True)
        desc_box.setMaximumHeight(110)
        layout.addWidget(desc_box)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_preview = QPushButton("Preview Effect")
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.clicked.connect(self.toggle_preview)
        btn_row.addWidget(self.btn_preview)

        self.btn_download = QPushButton("Download & Save")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.setStyleSheet("QPushButton { background: rgba(0, 229, 255, 0.12); color: #00E5FF; border: 1px solid #00E5FF; } QPushButton:hover { background: #00E5FF; color: #0A0B0E; }")
        self.btn_download.clicked.connect(self.download_item)
        btn_row.addWidget(self.btn_download)

        if "custom_effect_data" in item_data:
            self.btn_edit = QPushButton("Edit in Effect Builder")
            self.btn_edit.setCursor(Qt.PointingHandCursor)
            self.btn_edit.clicked.connect(self.edit_in_studio)
            btn_row.addWidget(self.btn_edit)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def toggle_preview(self):
        if not self.is_previewing:
            self.is_previewing = True
            self.btn_preview.setText("Stop Preview")
            self.btn_preview.setStyleSheet("QPushButton { background: #FF5252; color: white; border: 1px solid #FF5252; }")
            self.apply_preview_hardware()
        else:
            self._stop_preview_mode()

    def apply_preview_hardware(self):
        if not self.parent_app:
            return
        is_custom = "custom_effect_data" in self.item_data
        if is_custom:
            c_data = self.item_data.get("custom_effect_data", {})
            if hasattr(self.parent_app, "kb") and self.parent_app.kb:
                try:
                    self.parent_app.kb.set_effect("static")
                except Exception:
                    pass
            if hasattr(self.parent_app, "effect_manager") and self.parent_app.effect_manager:
                self.parent_app.effect_manager.set_effect("Custom Sequence")
                self.parent_app.effect_manager.update_config("frames", c_data.get("frames", []))
                self.parent_app.effect_manager.update_config("speed", c_data.get("speed", 50))
                self.parent_app.effect_manager.update_config("brightness", c_data.get("brightness", 100))
        else:
            settings = self.item_data.get("settings", {})
            temp_key = "_Preview_Cloud_Preset_"
            self.parent_app.presets[temp_key] = settings
            self.parent_app.apply_preset_logic(temp_key)
            if temp_key in self.parent_app.presets:
                del self.parent_app.presets[temp_key]

    def _stop_preview_mode(self):
        if self.is_previewing:
            self.is_previewing = False
            self.btn_preview.setText("Preview Effect")
            self.btn_preview.setStyleSheet("")
            if self.parent_app and self.previous_mode:
                items = self.parent_app.mode_list.findItems(self.previous_mode, Qt.MatchExactly)
                if items:
                    self.parent_app.mode_list.setCurrentItem(items[0])
                    self.parent_app.apply_effect()

    def download_item(self):
        is_custom = "custom_effect_data" in self.item_data
        title = self.item_data.get("preset_name", "Downloaded Creation")

        if is_custom:
            c_data = self.item_data.get("custom_effect_data")
            if c_data and isinstance(c_data, dict):
                from core.custom_effects_io import save_custom_effect
                save_custom_effect(c_data)
                if self.parent_app and hasattr(self.parent_app, "reload_custom_effects"):
                    self.parent_app.reload_custom_effects()
                QMessageBox.information(self, "Success", f"Custom effect '{title}' has been downloaded to your local library!")
        else:
            if self.parent_app and hasattr(self.parent_app, "presets"):
                final_name = title
                counter = 1
                while final_name in self.parent_app.presets:
                    final_name = f"{title} ({counter})"
                    counter += 1

                self.parent_app.presets[final_name] = self.item_data.get("settings", {})
                self.parent_app.update_preset_combos()
                idx = self.parent_app.preset_combo.findText(final_name)
                if idx >= 0:
                    self.parent_app.preset_combo.setCurrentIndex(idx)
                    self.parent_app.apply_preset_from_ui(idx)
                if hasattr(self.parent_app, "save_settings"):
                    self.parent_app.save_settings()
                QMessageBox.information(self, "Success", f"Preset '{final_name}' successfully downloaded to your local presets library!")

    def edit_in_studio(self):
        # Ensure effect is downloaded before launching studio
        c_data = self.item_data.get("custom_effect_data")
        if not c_data or not isinstance(c_data, dict):
            return
        from core.custom_effects_io import save_custom_effect
        save_custom_effect(c_data)
        if self.parent_app and hasattr(self.parent_app, "reload_custom_effects"):
            self.parent_app.reload_custom_effects()

        effect_name = c_data.get("name", self.item_data.get("preset_name", "Untitled"))
        self._stop_preview_mode()
        self.close()
        if self.marketplace_dialog:
            self.marketplace_dialog.close()

        if self.parent_app:
            from custom_builder_gui import EffectStudioDialog
            studio = EffectStudioDialog(self.parent_app)
            idx = studio.effect_selector_combo.findText(effect_name)
            if idx >= 0:
                studio.effect_selector_combo.setCurrentIndex(idx)
                studio.on_load_effect_selected(idx)
            studio.exec()

    def closeEvent(self, event):
        self._stop_preview_mode()
        super().closeEvent(event)


class MarketplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Community Marketplace (Beta)")
        self.setMinimumSize(820, 600)
        self.setStyleSheet("""
            QDialog { background-color: #0E1017; color: white; font-family: 'Segoe UI', sans-serif; }
            QLabel { color: white; font-size: 13px; }
            QComboBox, QLineEdit, QTextEdit { background-color: #161822; color: white; border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 6px; padding: 6px 10px; font-size: 13px; }
            QComboBox::drop-down { border: none; }
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E2030, stop:1 #161824); color: white; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px; padding: 8px 16px; font-weight: 700; }
            QPushButton:hover { background: rgba(0, 229, 255, 0.15); color: #00E5FF; border-color: #00E5FF; }
            QTabWidget::pane { border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; background: #12141D; margin-top: -1px; }
            QTabBar::tab { background: #151722; color: #8F94A6; padding: 10px 28px; border: 1px solid rgba(255,255,255,0.08); border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: 700; font-size: 13px; margin-right: 2px; }
            QTabBar::tab:selected { background: #00E5FF; color: #0A0B0E; }
            QScrollArea { border: none; background: transparent; }
        """)

        master_layout = QVBoxLayout(self)
        master_layout.setContentsMargins(16, 16, 16, 16)
        master_layout.setSpacing(14)

        top_header = QHBoxLayout()
        title_lbl = QLabel("Community Marketplace (Beta)")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #00E5FF;")
        top_header.addWidget(title_lbl)
        top_header.addStretch()
        self.btn_refresh = QPushButton("Refresh Feed")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_cloud_data)
        top_header.addWidget(self.btn_refresh)
        master_layout.addLayout(top_header)

        self.main_tabs = QTabWidget()
        master_layout.addWidget(self.main_tabs)

        self.init_presets_tab()
        self.init_custom_effects_tab()
        self.init_upload_tab()

        self.cloud_data = {}
        self.refresh_cloud_data()

    def init_presets_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.presets_grid_layout = QGridLayout(container)
        self.presets_grid_layout.setSpacing(12)
        self.presets_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.main_tabs.addTab(tab, "Presets")

    def init_custom_effects_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.custom_grid_layout = QGridLayout(container)
        self.custom_grid_layout.setSpacing(12)
        self.custom_grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.main_tabs.addTab(tab, "Custom Effects")

    def init_upload_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("Share Your Creation With The Community")
        header.setStyleSheet("font-size: 16px; font-weight: 800; color: #00E5FF;")
        layout.addWidget(header)

        form_grid = QGridLayout()
        form_grid.setSpacing(14)

        form_grid.addWidget(QLabel("Creation Type:"), 0, 0)
        self.upload_type_combo = QComboBox()
        self.upload_type_combo.addItems(["Preset", "Custom Effect"])
        self.upload_type_combo.setFixedHeight(30)
        self.upload_type_combo.currentTextChanged.connect(self.on_upload_type_changed)
        form_grid.addWidget(self.upload_type_combo, 0, 1)

        form_grid.addWidget(QLabel("Select Item to Share:"), 1, 0)
        self.item_select_combo = QComboBox()
        self.item_select_combo.setFixedHeight(30)
        form_grid.addWidget(self.item_select_combo, 1, 1)

        form_grid.addWidget(QLabel("Author Name (max 20):"), 2, 0)
        author_row = QHBoxLayout()
        self.author_input = QLineEdit()
        self.author_input.setMaxLength(20)
        self.author_input.setFixedHeight(30)
        self.author_counter_lbl = QLabel("0/20")
        self.author_counter_lbl.setStyleSheet("color: #9AA0A6; font-size: 11px;")
        self.author_input.textChanged.connect(lambda t: self.author_counter_lbl.setText(f"{len(t)}/20"))
        author_row.addWidget(self.author_input, stretch=1)
        author_row.addWidget(self.author_counter_lbl)
        self.author_input.setPlaceholderText("Enter author name...")
        form_grid.addLayout(author_row, 2, 1)

        form_grid.addWidget(QLabel("Description (max 50):"), 3, 0, Qt.AlignTop)
        desc_box_layout = QVBoxLayout()
        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(80)
        self.desc_counter_lbl = QLabel("0/50")
        self.desc_counter_lbl.setStyleSheet("color: #9AA0A6; font-size: 11px; text-align: right;")
        self.desc_input.textChanged.connect(self.on_desc_changed)
        desc_box_layout.addWidget(self.desc_input)
        desc_box_layout.addWidget(self.desc_counter_lbl, alignment=Qt.AlignRight)
        form_grid.addLayout(desc_box_layout, 3, 1)

        layout.addLayout(form_grid)

        self.btn_upload = QPushButton("Upload To Marketplace")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.setFixedHeight(36)
        self.btn_upload.setStyleSheet("QPushButton { background: #00E5FF; color: #0A0B0E; font-weight: 800; border: none; font-size: 14px; } QPushButton:hover { background: #52EDFF; }")
        self.btn_upload.clicked.connect(self.upload_action)
        layout.addWidget(self.btn_upload)

        layout.addStretch()
        self.main_tabs.addTab(tab, "Upload Creation")

    def on_desc_changed(self):
        text = self.desc_input.toPlainText()
        if len(text) > 50:
            self.desc_input.blockSignals(True)
            self.desc_input.setPlainText(text[:50])
            cursor = self.desc_input.textCursor()
            cursor.movePosition(cursor.End)
            self.desc_input.setTextCursor(cursor)
            self.desc_input.blockSignals(False)
            text = text[:50]
        self.desc_counter_lbl.setText(f"{len(text)}/50")

    def on_upload_type_changed(self, text):
        self.item_select_combo.clear()
        if "Preset" in text:
            if self.parent() and hasattr(self.parent(), "presets"):
                for p_name in sorted(self.parent().presets.keys()):
                    self.item_select_combo.addItem(p_name)
        else:
            try:
                from core.custom_effects_io import list_custom_effects
                effects = list_custom_effects()
                for eff in effects:
                    e_name = eff.get("name", "Untitled")
                    self.item_select_combo.addItem(e_name, eff)
            except Exception as e:
                print(f"Error loading custom effects into upload combo: {e}")

    def refresh_cloud_data(self):
        self.on_upload_type_changed(self.upload_type_combo.currentText())
        self._clear_layout(self.presets_grid_layout)
        self._clear_layout(self.custom_grid_layout)

        self.presets_grid_layout.addWidget(QLabel("Loading community presets..."), 0, 0)
        self.custom_grid_layout.addWidget(QLabel("Loading community custom effects..."), 0, 0)
        self.btn_refresh.setEnabled(False)

        self.fetch_worker = FetchCloudWorker()
        self.fetch_worker.data_fetched.connect(self.on_fetch_success)
        self.fetch_worker.error.connect(self.on_fetch_error)
        self.fetch_worker.start()

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def on_fetch_success(self, data):
        self.btn_refresh.setEnabled(True)
        self.cloud_data = data or {}

        self._clear_layout(self.presets_grid_layout)
        self._clear_layout(self.custom_grid_layout)

        preset_idx = 0
        custom_idx = 0

        for key, item in self.cloud_data.items():
            is_custom = "custom_effect_data" in item
            if is_custom:
                card = MarketplaceItemCard(key, item, self.open_item_detail)
                row, col = divmod(custom_idx, 3)
                self.custom_grid_layout.addWidget(card, row, col)
                custom_idx += 1
            else:
                card = MarketplaceItemCard(key, item, self.open_item_detail)
                row, col = divmod(preset_idx, 3)
                self.presets_grid_layout.addWidget(card, row, col)
                preset_idx += 1

        if preset_idx == 0:
            self.presets_grid_layout.addWidget(QLabel("No presets found in the community feed."), 0, 0)
        if custom_idx == 0:
            self.custom_grid_layout.addWidget(QLabel("No custom effects found in the community feed."), 0, 0)

    def on_fetch_error(self, err_msg):
        self.btn_refresh.setEnabled(True)
        self._clear_layout(self.presets_grid_layout)
        self.presets_grid_layout.addWidget(QLabel(f"Error loading presets: {err_msg}"), 0, 0)
        self._clear_layout(self.custom_grid_layout)
        self.custom_grid_layout.addWidget(QLabel(f"Error loading custom effects: {err_msg}"), 0, 0)

    def open_item_detail(self, key, item_data):
        dlg = EffectDetailDialog(key, item_data, parent_app=self.parent(), marketplace_dialog=self)
        dlg.exec()

    def upload_action(self):
        type_str = self.upload_type_combo.currentText().strip()
        selected_item_name = self.item_select_combo.currentText().strip()
        author_name = self.author_input.text().strip() or "Community Member"
        description = self.desc_input.toPlainText().strip()

        if not selected_item_name:
            QMessageBox.warning(self, "No Selection", "Please select a local item from the dropdown to share.")
            return

        payload = {
            "preset_name": selected_item_name,
            "author": author_name,
            "description": description,
            "type": "custom_effect" if type_str == "Custom Effect" else "preset"
        }

        if type_str == "Preset":
            if not self.parent() or not hasattr(self.parent(), "presets") or selected_item_name not in self.parent().presets:
                QMessageBox.critical(self, "Error", "Selected preset data not found in local library.")
                return
            payload["settings"] = self.parent().presets[selected_item_name]
        else:
            eff_data = self.item_select_combo.currentData()
            if not eff_data:
                QMessageBox.critical(self, "Error", "Selected custom effect data could not be retrieved.")
                return
            payload["custom_effect_data"] = eff_data

        self.btn_upload.setEnabled(False)
        self.btn_upload.setText("Uploading...")
        self.upload_worker = UploadCloudWorker(payload)
        self.upload_worker.upload_success.connect(lambda: (
            self.btn_upload.setEnabled(True),
            self.btn_upload.setText("Upload To Marketplace"),
            self.desc_input.clear(),
            QMessageBox.information(self, "Uploaded", f"Creation '{selected_item_name}' successfully shared with the community!"),
            self.refresh_cloud_data(),
            self.main_tabs.setCurrentIndex(1 if type_str == "Custom Effect" else 0)
        ))
        self.upload_worker.error.connect(lambda err: (
            self.btn_upload.setEnabled(True),
            self.btn_upload.setText("Upload To Marketplace"),
            QMessageBox.critical(self, "Upload Error", f"Failed to upload creation:\n{err}")
        ))
        self.upload_worker.start()


# Compatibility alias for any legacy imports
CloudHubDialog = MarketplaceDialog
