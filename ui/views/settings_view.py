"""Settings view module with Keyring integration, cache cleaner, hardware status, and diagnostics (Phase 12)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.config_store import ConfigStore
from core.diagnostics import DiagnosticsManager
from core.event_bus import get_event_bus
from core.hardware import HardwareProbe


class SettingsView(QWidget):
    """Application settings, API credentials in Windows Credential Locker, cache maintenance, and diagnostics."""

    def __init__(
        self,
        config_store: ConfigStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_store = config_store or ConfigStore.instance()
        self._build_ui()
        self._calculate_cache_size()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for clean layout
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(18)

        # 1. Header
        title = QLabel("Settings & Preferences")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        subtitle = QLabel("Manage secure AI credentials, output directories, cache maintenance, and system diagnostics.")
        subtitle.setStyleSheet("color: #9ca3af; font-size: 12px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # 2. AI Credentials Card (Windows Credential Locker)
        cred_card = self._create_card("AI Provider Credentials (Windows Credential Locker)")
        cc_layout = QVBoxLayout(cred_card)
        cc_layout.setSpacing(12)

        c_info = QLabel("API keys are encrypted in Windows Credential Locker and never stored in plaintext.")
        c_info.setStyleSheet("color: #64748b; font-size: 11px;")
        cc_layout.addWidget(c_info)

        # Gemini
        self._gemini_input = self._add_key_input(cc_layout, "Gemini API Key:", "gemini_api_key", "AIzaSy...")
        # DeepSeek
        self._deepseek_input = self._add_key_input(cc_layout, "DeepSeek API Key:", "deepseek_api_key", "sk-...")
        # Qwen
        self._qwen_input = self._add_key_input(cc_layout, "Qwen / DashScope Key:", "qwen_api_key", "sk-...")
        # Hugging Face
        self._hf_input = self._add_key_input(cc_layout, "Hugging Face Token:", "hf_token", "hf_...")

        save_cred_btn = QPushButton("💾 Save Credentials Securely")
        save_cred_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 700;
                padding: 7px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        save_cred_btn.setFixedWidth(220)
        save_cred_btn.clicked.connect(self._save_credentials)
        cc_layout.addWidget(save_cred_btn)

        layout.addWidget(cred_card)

        # 3. Storage & Output Paths Card
        paths_card = self._create_card("Output & Working Directories")
        pc_layout = QVBoxLayout(paths_card)
        pc_layout.setSpacing(12)

        # Download directory
        row_dl = QHBoxLayout()
        row_dl.addWidget(QLabel("Downloads Directory:"), 0)
        self.dl_path_lbl = QLabel(str(self._get_downloads_dir()))
        self.dl_path_lbl.setStyleSheet("color: #94a3b8; font-family: Consolas; font-size: 11px;")
        row_dl.addWidget(self.dl_path_lbl, 1)

        change_dl_btn = QPushButton("📁 Browse...")
        change_dl_btn.setToolTip("Select downloads directory")
        change_dl_btn.clicked.connect(self._change_downloads_dir)
        row_dl.addWidget(change_dl_btn)
        pc_layout.addLayout(row_dl)

        layout.addWidget(paths_card)

        # 4. Cache & Maintenance Card
        cache_card = self._create_card("Disk Cache & Temporary Files")
        cac_layout = QVBoxLayout(cache_card)
        cac_layout.setSpacing(10)

        row_c = QHBoxLayout()
        self.cache_size_lbl = QLabel("Calculating cache size...")
        self.cache_size_lbl.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: 600;")
        row_c.addWidget(self.cache_size_lbl)

        row_c.addStretch()

        clean_cache_btn = QPushButton("🧹 Clear All Caches")
        clean_cache_btn.setToolTip("Permanently clear cached frames, stems, and temporary files")
        clean_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        clean_cache_btn.clicked.connect(self._clear_all_caches)
        row_c.addWidget(clean_cache_btn)
        cac_layout.addLayout(row_c)

        layout.addWidget(cache_card)

        # 5. Diagnostics & System Health Card
        diag_card = self._create_card("System Health & Crash Diagnostics")
        dc_layout = QVBoxLayout(diag_card)
        dc_layout.setSpacing(12)

        # Hardware info overview
        probe = HardwareProbe()
        metrics = probe.probe()
        hw_text = f"CPU: {metrics.get('cpu_percent', 0)}% • RAM: {metrics.get('ram_used_gb', 0)} / {metrics.get('ram_total_gb', 0)} GB"
        if metrics.get("gpu_name"):
            hw_text += f" • GPU: {metrics['gpu_name']} ({metrics.get('gpu_mem_total_mb', 0)} MB)"
        hw_lbl = QLabel(hw_text)
        hw_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        dc_layout.addWidget(hw_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        test_btn = QPushButton("🔍 Run System Self-Test")
        test_btn.setToolTip("Verify hardware acceleration, FFmpeg, and model dependencies")
        test_btn.clicked.connect(self._run_self_test)
        btn_row.addWidget(test_btn)

        crash_btn = QPushButton("📦 Export Diagnostics Zip")
        crash_btn.setToolTip("Export diagnostic report and recent log files for debugging")
        crash_btn.clicked.connect(self._export_diagnostics_zip)
        btn_row.addWidget(crash_btn)

        btn_row.addStretch()
        dc_layout.addLayout(btn_row)

        layout.addWidget(diag_card)
        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(10)

        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #818cf8;")
        c_layout.addWidget(lbl)
        return card

    def _add_key_input(self, layout: QVBoxLayout, label: str, config_key: str, placeholder: str) -> QLineEdit:
        row = QHBoxLayout()
        row.setSpacing(10)
        lbl = QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        row.addWidget(lbl)

        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(placeholder)
        val = self.config_store.get(config_key, secret=True)
        if val:
            edit.setText(str(val))
        row.addWidget(edit, 1)

        # Toggle visibility button
        show_btn = QPushButton("👁️")
        show_btn.setFixedSize(28, 24)
        show_btn.setToolTip("Show / Hide Secret Key")
        show_btn.setStyleSheet("padding: 0px; font-size: 11px;")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda checked, e=edit: e.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        )
        row.addWidget(show_btn)

        layout.addLayout(row)
        return edit

    def _save_credentials(self) -> None:
        g = self._gemini_input.text().strip() or None
        d = self._deepseek_input.text().strip() or None
        q = self._qwen_input.text().strip() or None
        h = self._hf_input.text().strip() or None

        self.config_store.set("gemini_api_key", g, secret=True)
        self.config_store.set("deepseek_api_key", d, secret=True)
        self.config_store.set("qwen_api_key", q, secret=True)
        self.config_store.set("hf_token", h, secret=True)

        QMessageBox.information(
            self,
            "Credentials Saved",
            "API keys have been stored securely in Windows Credential Locker.",
        )
        get_event_bus().toast.emit("success", "Credentials saved securely to Windows Credential Locker.")

    def _get_downloads_dir(self) -> Path:
        custom = self.config_store.get("downloads_dir")
        if custom and Path(str(custom)).exists():
            return Path(str(custom))
        default_dir = Path.home() / "AppData" / "Local" / "MediaForgeAI" / "downloads"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    def _change_downloads_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Downloads Directory", str(self._get_downloads_dir()))
        if folder:
            p = Path(folder)
            self.config_store.set("downloads_dir", str(p))
            self.dl_path_lbl.setText(str(p))

    def _calculate_cache_size(self) -> None:
        cache_roots = [
            Path.home() / "AppData" / "Local" / "MediaForgeAI" / "tts_cache",
            Path.home() / "AppData" / "Local" / "MediaForgeAI" / "cache",
            Path.home() / "AppData" / "Local" / "MediaForgeAI" / "batch_exports",
        ]
        total_bytes = 0
        for root in cache_roots:
            if root.exists():
                for f in root.rglob("*"):
                    if f.is_file():
                        total_bytes += f.stat().st_size

        mb = total_bytes / (1024 * 1024)
        self.cache_size_lbl.setText(f"Total Temporary Cache: {mb:.1f} MB")

    def _clear_all_caches(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear Caches",
            "Are you sure you want to clean all temporary audio stems, waveforms, and TTS caches?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cache_roots = [
                Path.home() / "AppData" / "Local" / "MediaForgeAI" / "tts_cache",
                Path.home() / "AppData" / "Local" / "MediaForgeAI" / "cache",
            ]
            for root in cache_roots:
                if root.exists():
                    shutil.rmtree(root, ignore_errors=True)
                    root.mkdir(parents=True, exist_ok=True)

            self._calculate_cache_size()
            QMessageBox.information(self, "Cache Cleared", "Temporary cache files have been deleted.")

    def _run_self_test(self) -> None:
        checks = DiagnosticsManager.run_self_test()
        lines = []
        all_ok = True
        for c in checks:
            tag = "✅" if c.status == "ok" else ("⚠️" if c.status == "warning" else "❌")
            lines.append(f"{tag} {c.name}: {c.details}")
            if c.status == "error":
                all_ok = False

        msg = "\n\n".join(lines)
        title = "System Diagnostics: All Passed" if all_ok else "System Diagnostics"
        QMessageBox.information(self, title, msg)

    def _export_diagnostics_zip(self) -> None:
        zip_path = DiagnosticsManager.create_crash_report()
        reply = QMessageBox.information(
            self,
            "Diagnostics Exported",
            f"Redacted diagnostics bundle created at:\n\n{zip_path}\n\nWould you like to open the folder?",
            QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok,
        )
        if reply == QMessageBox.StandardButton.Open:
            os.startfile(zip_path.parent)
