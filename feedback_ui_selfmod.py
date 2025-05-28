# Interactive Feedback MCP UI
# Developed by Fábio Ferreira (https://x.com/fabiomlferreira)
# Inspired by/related to dotcursorrules.com (https://dotcursorrules.com/)
import os
import sys
import json
import psutil
import argparse
import subprocess
import threading
import hashlib
from typing import Optional, TypedDict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTextEdit, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSettings
from PySide6.QtGui import QTextCursor, QIcon, QKeyEvent, QFont, QFontDatabase, QPalette, QColor

class FeedbackResult(TypedDict):
    command_logs: str
    interactive_feedback: str

class FeedbackConfig(TypedDict):
    run_command: str
    execute_automatically: bool

def set_dark_title_bar(widget: QWidget, dark_title_bar: bool) -> None:
    # Ensure we're on Windows
    if sys.platform != "win32":
        return

    from ctypes import windll, c_uint32, byref

    # Get Windows build number
    build_number = sys.getwindowsversion().build
    if build_number < 17763:  # Windows 10 1809 minimum
        return

    # Check if the widget's property already matches the setting
    dark_prop = widget.property("DarkTitleBar")
    if dark_prop is not None and dark_prop == dark_title_bar:
        return

    # Set the property (True if dark_title_bar != 0, False otherwise)
    widget.setProperty("DarkTitleBar", dark_title_bar)

    # Load dwmapi.dll and call DwmSetWindowAttribute
    dwmapi = windll.dwmapi
    hwnd = widget.winId()  # Get the window handle
    attribute = 20 if build_number >= 18985 else 19  # Use newer attribute for newer builds
    c_dark_title_bar = c_uint32(dark_title_bar)  # Convert to C-compatible uint32
    dwmapi.DwmSetWindowAttribute(hwnd, attribute, byref(c_dark_title_bar), 4)

    # HACK: Create a 1x1 pixel frameless window to force redraw
    temp_widget = QWidget(None, Qt.FramelessWindowHint)
    temp_widget.resize(1, 1)
    temp_widget.move(widget.pos())
    temp_widget.show()
    temp_widget.deleteLater()  # Safe deletion in Qt event loop

def get_apple_design_palette(app: QApplication):
    """Create Apple-inspired design palette with enhanced color system"""
    palette = app.palette()
    
    # Apple-inspired colors
    # Background colors
    palette.setColor(QPalette.Window, QColor(28, 28, 30))  # Apple dark background
    palette.setColor(QPalette.Base, QColor(44, 44, 46))    # Card background
    palette.setColor(QPalette.AlternateBase, QColor(58, 58, 60))  # Alternate background
    
    # Text colors
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))  # Primary text
    palette.setColor(QPalette.Text, QColor(255, 255, 255))        # Primary text
    palette.setColor(QPalette.PlaceholderText, QColor(142, 142, 147))  # Secondary text
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(142, 142, 147))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(142, 142, 147))
    
    # Button colors
    palette.setColor(QPalette.Button, QColor(44, 44, 46))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(142, 142, 147))
    
    # Highlight colors (Apple Blue)
    palette.setColor(QPalette.Highlight, QColor(0, 122, 255))     # Apple Blue
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    
    # Other colors
    palette.setColor(QPalette.Link, QColor(0, 122, 255))          # Apple Blue
    palette.setColor(QPalette.BrightText, QColor(255, 55, 48))    # Apple Red
    palette.setColor(QPalette.ToolTipBase, QColor(44, 44, 46))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    
    # Border and shadow colors
    palette.setColor(QPalette.Dark, QColor(84, 84, 88))
    palette.setColor(QPalette.Shadow, QColor(0, 0, 0))
    
    return palette

def get_apple_styles():
    """Return comprehensive Apple-inspired stylesheet"""
    return """
    /* Main Window Styling */
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                   stop:0 #1C1C1E, stop:1 #2C2C2E);
        color: #FFFFFF;
    }
    
    /* Group Box Styling - Card Style */
    QGroupBox {
        background: rgba(44, 44, 46, 0.95);
        border: 1px solid rgba(84, 84, 88, 0.6);
        border-radius: 16px;
        margin: 16px 8px;
        padding: 20px 16px 16px 16px;
        font-weight: 600;
        font-size: 15px;
        color: #FFFFFF;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 16px;
        top: -8px;
        background: rgba(44, 44, 46, 0.95);
        padding: 4px 12px;
        border-radius: 8px;
        color: #FFFFFF;
    }
    
    /* Button Styling */
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                   stop:0 #007AFF, stop:1 #0051D5);
        border: none;
        border-radius: 12px;
        color: #FFFFFF;
        font-weight: 600;
        font-size: 14px;
        padding: 12px 24px;
        min-height: 20px;
    }
    
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                   stop:0 #0084FF, stop:1 #0056E0);
        transform: translateY(-1px);
    }
    
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                   stop:0 #0066CC, stop:1 #0044BB);
        transform: translateY(0px);
    }
    
    QPushButton:disabled {
        background: rgba(84, 84, 88, 0.4);
        color: rgba(255, 255, 255, 0.3);
    }
    
    /* Secondary Button Style */
    QPushButton#secondaryButton {
        background: rgba(142, 142, 147, 0.2);
        border: 1px solid rgba(84, 84, 88, 0.6);
        color: #FFFFFF;
    }
    
    QPushButton#secondaryButton:hover {
        background: rgba(142, 142, 147, 0.3);
        border-color: rgba(84, 84, 88, 0.8);
    }
    
    /* Success Button Style */
    QPushButton#successButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                   stop:0 #34C759, stop:1 #2DB346);
    }
    
    QPushButton#successButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                   stop:0 #3BCC5F, stop:1 #32BA4C);
    }
    
    /* Toggle Button Style */
    QPushButton#toggleButton {
        background: rgba(58, 58, 60, 0.8);
        border: 1px solid rgba(84, 84, 88, 0.6);
        border-radius: 10px;
        color: #FFFFFF;
        font-weight: 500;
        font-size: 14px;
        padding: 10px 20px;
        min-width: 200px;
        text-align: center;
    }
    
    QPushButton#toggleButton:hover {
        background: rgba(68, 68, 70, 0.9);
        border-color: rgba(84, 84, 88, 0.8);
        color: #FFFFFF;
    }
    
    QPushButton#toggleButton:pressed {
        background: rgba(48, 48, 50, 0.9);
        border-color: rgba(84, 84, 88, 1.0);
    }
    
    /* Line Edit Styling */
    QLineEdit {
        background: rgba(58, 58, 60, 0.8);
        border: 2px solid rgba(84, 84, 88, 0.6);
        border-radius: 10px;
        padding: 12px 16px;
        font-size: 14px;
        color: #FFFFFF;
        selection-background-color: #007AFF;
    }
    
    QLineEdit:focus {
        border-color: #007AFF;
        background: rgba(58, 58, 60, 0.9);
    }
    
    QLineEdit:hover {
        border-color: rgba(84, 84, 88, 0.8);
        background: rgba(58, 58, 60, 0.9);
    }
    
    /* Text Edit Styling */
    QTextEdit {
        background: rgba(58, 58, 60, 0.8);
        border: 2px solid rgba(84, 84, 88, 0.6);
        border-radius: 12px;
        padding: 16px;
        font-size: 14px;
        color: #FFFFFF;
        selection-background-color: #007AFF;
        line-height: 1.4;
    }
    
    QTextEdit:focus {
        border-color: #007AFF;
        background: rgba(58, 58, 60, 0.9);
    }
    
    /* Console/Terminal Text Edit */
    QTextEdit#consoleText {
        background: rgba(28, 28, 30, 0.95);
        border: 1px solid rgba(84, 84, 88, 0.4);
        border-radius: 8px;
        padding: 12px;
        font-family: 'SF Mono', 'Monaco', 'Consolas', 'Courier New', monospace;
        font-size: 12px;
        color: #00FF00;
        selection-background-color: rgba(0, 122, 255, 0.3);
    }
    
    /* Checkbox Styling */
    QCheckBox {
        color: #FFFFFF;
        font-size: 14px;
        spacing: 8px;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 2px solid rgba(84, 84, 88, 0.6);
        background: rgba(58, 58, 60, 0.8);
    }
    
    QCheckBox::indicator:hover {
        border-color: #007AFF;
        background: rgba(58, 58, 60, 0.9);
    }
    
    QCheckBox::indicator:checked {
        background: #007AFF;
        border-color: #007AFF;
        image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMC42IDEuNEw0LjI1IDcuNzVMMSA0LjUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMS41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
    }
    
    /* Label Styling */
    QLabel {
        color: #FFFFFF;
        font-size: 14px;
        line-height: 1.4;
    }
    
    QLabel#sectionTitle {
        font-size: 17px;
        font-weight: 600;
        color: #FFFFFF;
        margin-bottom: 8px;
    }
    
    QLabel#secondaryLabel {
        color: #8E8E93;
        font-size: 13px;
    }
    
    QLabel#contactLabel {
        color: #8E8E93;
        font-size: 11px;
        padding: 16px;
    }
    
    QLabel#contactLabel a {
        color: #007AFF;
        text-decoration: none;
    }
    
    QLabel#contactLabel a:hover {
        color: #0084FF;
        text-decoration: underline;
    }
    
    /* Scrollbar Styling */
    QScrollBar:vertical {
        background: rgba(44, 44, 46, 0.3);
        width: 12px;
        border-radius: 6px;
        margin: 0;
    }
    
    QScrollBar::handle:vertical {
        background: rgba(142, 142, 147, 0.5);
        border-radius: 6px;
        min-height: 20px;
        margin: 2px;
    }
    
    QScrollBar::handle:vertical:hover {
        background: rgba(142, 142, 147, 0.7);
    }
    
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: none;
    }
    
    /* Horizontal Scrollbar */
    QScrollBar:horizontal {
        background: rgba(44, 44, 46, 0.3);
        height: 12px;
        border-radius: 6px;
        margin: 0;
    }
    
    QScrollBar::handle:horizontal {
        background: rgba(142, 142, 147, 0.5);
        border-radius: 6px;
        min-width: 20px;
        margin: 2px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background: rgba(142, 142, 147, 0.7);
    }
    
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    /* Animation-like transitions would be handled in code with QPropertyAnimation */
    """

def kill_tree(process: subprocess.Popen):
    killed: list[psutil.Process] = []
    parent = psutil.Process(process.pid)
    for proc in parent.children(recursive=True):
        try:
            proc.kill()
            killed.append(proc)
        except psutil.Error:
            pass
    try:
        parent.kill()
    except psutil.Error:
        pass
    killed.append(parent)

    # Terminate any remaining processes
    for proc in killed:
        try:
            if proc.is_running():
                proc.terminate()
        except psutil.Error:
            pass

def get_user_environment() -> dict[str, str]:
    if sys.platform != "win32":
        return os.environ.copy()

    import ctypes
    from ctypes import wintypes

    # Load required DLLs
    advapi32 = ctypes.WinDLL("advapi32")
    userenv = ctypes.WinDLL("userenv")
    kernel32 = ctypes.WinDLL("kernel32")

    # Constants
    TOKEN_QUERY = 0x0008

    # Function prototypes
    OpenProcessToken = advapi32.OpenProcessToken
    OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    OpenProcessToken.restype = wintypes.BOOL

    CreateEnvironmentBlock = userenv.CreateEnvironmentBlock
    CreateEnvironmentBlock.argtypes = [ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.BOOL]
    CreateEnvironmentBlock.restype = wintypes.BOOL

    DestroyEnvironmentBlock = userenv.DestroyEnvironmentBlock
    DestroyEnvironmentBlock.argtypes = [wintypes.LPVOID]
    DestroyEnvironmentBlock.restype = wintypes.BOOL

    GetCurrentProcess = kernel32.GetCurrentProcess
    GetCurrentProcess.argtypes = []
    GetCurrentProcess.restype = wintypes.HANDLE

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    # Get process token
    token = wintypes.HANDLE()
    if not OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise RuntimeError("Failed to open process token")

    try:
        # Create environment block
        environment = ctypes.c_void_p()
        if not CreateEnvironmentBlock(ctypes.byref(environment), token, False):
            raise RuntimeError("Failed to create environment block")

        try:
            # Convert environment block to list of strings
            result = {}
            env_ptr = ctypes.cast(environment, ctypes.POINTER(ctypes.c_wchar))
            offset = 0

            while True:
                # Get string at current offset
                current_string = ""
                while env_ptr[offset] != "\0":
                    current_string += env_ptr[offset]
                    offset += 1

                # Skip null terminator
                offset += 1

                # Break if we hit double null terminator
                if not current_string:
                    break

                equal_index = current_string.index("=")
                if equal_index == -1:
                    continue

                key = current_string[:equal_index]
                value = current_string[equal_index + 1:]
                result[key] = value

            return result

        finally:
            DestroyEnvironmentBlock(environment)

    finally:
        CloseHandle(token)

class FeedbackTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            # Find the parent FeedbackUI instance and call submit
            parent = self.parent()
            while parent and not isinstance(parent, FeedbackUI):
                parent = parent.parent()
            if parent:
                parent._submit_feedback()
        else:
            super().keyPressEvent(event)

class LogSignals(QObject):
    append_log = Signal(str)

class FeedbackUI(QMainWindow):
    def __init__(self, project_directory: str, prompt: str):
        super().__init__()
        self.project_directory = project_directory
        self.prompt = prompt

        self.process: Optional[subprocess.Popen] = None
        self.log_buffer = []
        self.feedback_result = None
        self.log_signals = LogSignals()
        self.log_signals.append_log.connect(self._append_log)

        self.setWindowTitle("Interactive Feedback • MCP")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "images", "feedback.png")
        self.setWindowIcon(QIcon(icon_path))
        
        # Configure window properties for better Apple-like appearance
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)  # Ensure solid background
        
        self.settings = QSettings("InteractiveFeedbackMCP", "InteractiveFeedbackMCP")
        
        # Load general UI settings for the main window (geometry, state)
        self.settings.beginGroup("MainWindow_General")
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(800, 600)
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - 800) // 2
            y = (screen.height() - 600) // 2
            self.move(x, y)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
        self.settings.endGroup() # End "MainWindow_General" group
        
        # Load project-specific settings (command, auto-execute, command section visibility)
        self.project_group_name = get_project_settings_group(self.project_directory)
        self.settings.beginGroup(self.project_group_name)
        loaded_run_command = self.settings.value("run_command", "", type=str)
        loaded_execute_auto = self.settings.value("execute_automatically", False, type=bool)
        command_section_visible = self.settings.value("commandSectionVisible", False, type=bool)
        self.settings.endGroup() # End project-specific group
        
        self.config: FeedbackConfig = {
            "run_command": loaded_run_command,
            "execute_automatically": loaded_execute_auto
        }

        self._create_ui() # self.config is used here to set initial values

        # Set command section visibility AFTER _create_ui has created relevant widgets
        self.command_group.setVisible(command_section_visible)
        if command_section_visible:
            self.toggle_command_button.setText("Hide Command & Console")
        else:
            self.toggle_command_button.setText("Show Command & Console")

        set_dark_title_bar(self, True)

        if self.config.get("execute_automatically", False):
            self._run_command()

    def _format_windows_path(self, path: str) -> str:
        if sys.platform == "win32":
            # Convert forward slashes to backslashes
            path = path.replace("/", "\\")
            # Capitalize drive letter if path starts with x:\
            if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
                path = path[0].upper() + path[1:]
        return path

    def _create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Apply Apple styles to the application
        self.setStyleSheet(get_apple_styles())
        
        # Improved layout with proper spacing
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Toggle Command Section Button with Apple styling
        self.toggle_command_button = QPushButton("Show Command & Console")
        self.toggle_command_button.setObjectName("toggleButton")
        
        # Ensure button has enough width for both states of text
        self.toggle_command_button.setMinimumWidth(220)  # Enough for "Hide Command & Console"
        self.toggle_command_button.setMaximumWidth(300)  # Prevent excessive stretching
        self.toggle_command_button.setSizePolicy(
            self.toggle_command_button.sizePolicy().horizontalPolicy(),
            self.toggle_command_button.sizePolicy().verticalPolicy()
        )
        
        self.toggle_command_button.clicked.connect(self._toggle_command_section)
        layout.addWidget(self.toggle_command_button)

        # Command section with Apple card design
        self.command_group = QGroupBox("Command & Console")
        command_layout = QVBoxLayout(self.command_group)
        command_layout.setSpacing(16)
        command_layout.setContentsMargins(20, 24, 20, 20)

        # Working directory label with improved styling
        formatted_path = self._format_windows_path(self.project_directory)
        working_dir_label = QLabel(f"Working Directory")
        working_dir_label.setObjectName("sectionTitle")
        command_layout.addWidget(working_dir_label)
        
        # Path value label
        path_value_label = QLabel(formatted_path)
        path_value_label.setObjectName("secondaryLabel")
        path_value_label.setWordWrap(True)
        command_layout.addWidget(path_value_label)
        
        # Add spacing
        command_layout.addSpacing(8)

        # Command input section
        command_title = QLabel("Command")
        command_title.setObjectName("sectionTitle")
        command_layout.addWidget(command_title)
        
        # Command input row with improved layout
        command_input_layout = QHBoxLayout()
        command_input_layout.setSpacing(12)
        
        self.command_entry = QLineEdit()
        self.command_entry.setText(self.config["run_command"])
        self.command_entry.setPlaceholderText("Enter command to execute...")
        self.command_entry.returnPressed.connect(self._run_command)
        self.command_entry.textChanged.connect(self._update_config)
        
        self.run_button = QPushButton("Run")
        self.run_button.setFixedWidth(100)
        self.run_button.clicked.connect(self._run_command)

        command_input_layout.addWidget(self.command_entry)
        command_input_layout.addWidget(self.run_button)
        command_layout.addLayout(command_input_layout)

        # Auto-execute and save config row with improved spacing
        auto_layout = QHBoxLayout()
        auto_layout.setSpacing(16)
        
        self.auto_check = QCheckBox("Execute automatically on startup")
        self.auto_check.setChecked(self.config.get("execute_automatically", False))
        self.auto_check.stateChanged.connect(self._update_config)

        save_button = QPushButton("Save Configuration")
        save_button.setObjectName("secondaryButton")
        save_button.setFixedWidth(160)
        save_button.clicked.connect(self._save_config)

        auto_layout.addWidget(self.auto_check)
        auto_layout.addStretch()
        auto_layout.addWidget(save_button)
        command_layout.addLayout(auto_layout)
        
        # Add more spacing before console
        command_layout.addSpacing(16)

        # Console section with enhanced styling
        console_title = QLabel("Console Output")
        console_title.setObjectName("sectionTitle")
        command_layout.addWidget(console_title)

        # Log text area with terminal styling
        self.log_text = QTextEdit()
        self.log_text.setObjectName("consoleText")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(180)
        
        # Use system monospace font for better cross-platform compatibility
        font = QFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        font.setPointSize(11)
        self.log_text.setFont(font)
        command_layout.addWidget(self.log_text)

        # Clear button with improved positioning
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        
        self.clear_button = QPushButton("Clear Console")
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.setFixedWidth(120)
        self.clear_button.clicked.connect(self.clear_logs)
        
        button_layout.addStretch()
        button_layout.addWidget(self.clear_button)
        command_layout.addLayout(button_layout)

        # Initially hide command section
        self.command_group.setVisible(False) 
        layout.addWidget(self.command_group)

        # Feedback section with enhanced Apple card design
        self.feedback_group = QGroupBox("Interactive Feedback")
        feedback_layout = QVBoxLayout(self.feedback_group)
        feedback_layout.setSpacing(16)
        feedback_layout.setContentsMargins(20, 24, 20, 20)

        # Description label with better typography
        self.description_label = QLabel(self.prompt)
        self.description_label.setWordWrap(True)
        self.description_label.setObjectName("sectionTitle")
        feedback_layout.addWidget(self.description_label)

        # Feedback input instructions
        instructions_label = QLabel("Share your thoughts, suggestions, or feedback below:")
        instructions_label.setObjectName("secondaryLabel")
        feedback_layout.addWidget(instructions_label)

        # Enhanced feedback text area
        self.feedback_text = FeedbackTextEdit()
        self.feedback_text.setMinimumHeight(120)
        self.feedback_text.setPlaceholderText("Type your feedback here...\n\nPress Ctrl+Enter to submit quickly, or use the button below.")
        
        # Improve font for better readability
        feedback_font = self.feedback_text.font()
        feedback_font.setPointSize(13)
        feedback_font.setFamily("-apple-system, BlinkMacSystemFont, 'Segoe UI', 'SF Pro Text', system-ui, sans-serif")
        self.feedback_text.setFont(feedback_font)
        
        feedback_layout.addWidget(self.feedback_text)

        # Submit button with enhanced styling
        submit_button = QPushButton("Send Feedback")
        submit_button.setObjectName("successButton")
        submit_button.setFixedHeight(48)
        submit_button.clicked.connect(self._submit_feedback)
        feedback_layout.addWidget(submit_button)

        # Add the feedback section to main layout
        layout.addWidget(self.feedback_group)

        # Enhanced credits/contact label
        contact_label = QLabel('Designed with ❤️ • Contact <a href="https://x.com/fabiomlferreira">Fábio Ferreira</a> • Visit <a href="https://dotcursorrules.com/">dotcursorrules.com</a>')
        contact_label.setObjectName("contactLabel")
        contact_label.setOpenExternalLinks(True)
        contact_label.setAlignment(Qt.AlignCenter)
        contact_label.setContentsMargins(0, 8, 0, 8)
        layout.addWidget(contact_label)
        
        # Ensure proper minimum window size
        self.setMinimumSize(500, 400)
        
        # Set focus to feedback text by default
        self.feedback_text.setFocus()

    def _toggle_command_section(self):
        is_visible = self.command_group.isVisible()
        self.command_group.setVisible(not is_visible)
        if not is_visible:
            self.toggle_command_button.setText("Hide Command & Console")
        else:
            self.toggle_command_button.setText("Show Command & Console")
        
        # Immediately save the visibility state for this project
        self.settings.beginGroup(self.project_group_name)
        self.settings.setValue("commandSectionVisible", self.command_group.isVisible())
        self.settings.endGroup()

        # Improved window resizing logic to prevent button displacement
        QApplication.processEvents()  # Process pending events first
        
        # Force layout updates before calculating sizes
        self.centralWidget().layout().update()
        self.centralWidget().updateGeometry()
        
        # Get current and preferred sizes
        current_size = self.size()
        preferred_size = self.centralWidget().sizeHint()
        
        # Calculate safe new dimensions with better logic
        min_width = max(500, self.minimumWidth())  # Respect minimum window width
        new_width = max(current_size.width(), preferred_size.width(), min_width)
        
        if self.command_group.isVisible():
            # When showing command section, add height incrementally
            command_section_height = self.command_group.sizeHint().height()
            new_height = current_size.height() + command_section_height + 50  # Extra padding
        else:
            # When hiding command section, calculate optimal height
            new_height = max(400, preferred_size.height() + 50)
        
        # Apply resize gradually to prevent layout jumps
        self.resize(new_width, new_height)
        
        # Ensure layout is properly updated
        QApplication.processEvents()
        self.centralWidget().layout().activate()
        
        # Verify button is still properly positioned and sized
        self.toggle_command_button.updateGeometry()
        
        # Final window position check to prevent off-screen displacement
        screen_geometry = QApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        
        # Adjust position if window extends beyond screen boundaries
        new_x = window_geometry.x()
        new_y = window_geometry.y()
        
        if window_geometry.bottom() > screen_geometry.bottom():
            new_y = max(0, screen_geometry.bottom() - window_geometry.height())
        
        if window_geometry.right() > screen_geometry.right():
            new_x = max(0, screen_geometry.right() - window_geometry.width())
        
        if new_x != window_geometry.x() or new_y != window_geometry.y():
            self.move(new_x, new_y)

    def _update_config(self):
        self.config["run_command"] = self.command_entry.text()
        self.config["execute_automatically"] = self.auto_check.isChecked()

    def _append_log(self, text: str):
        self.log_buffer.append(text)
        self.log_text.append(text.rstrip())
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def _check_process_status(self):
        if self.process and self.process.poll() is not None:
            # Process has terminated
            exit_code = self.process.poll()
            self._append_log(f"\nProcess exited with code {exit_code}\n")
            self.run_button.setText("Run")
            self.run_button.setObjectName("")  # Reset to default style
            self.run_button.setStyleSheet("")  # Clear any custom styles
            self.process = None
            self.activateWindow()
            self.feedback_text.setFocus()

    def _run_command(self):
        if self.process:
            kill_tree(self.process)
            self.process = None
            self.run_button.setText("Run")
            self.run_button.setObjectName("")  # Reset to default style
            self.run_button.setStyleSheet("")  # Clear any custom styles
            return

        # Clear the log buffer but keep UI logs visible
        self.log_buffer = []

        command = self.command_entry.text()
        if not command:
            self._append_log("Please enter a command to run\n")
            return

        self._append_log(f"$ {command}\n")
        self.run_button.setText("Stop")
        # Apply a warning style to the stop button
        self.run_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #FF3B30, stop:1 #D70015);
                border: none;
                border-radius: 12px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 14px;
                padding: 12px 24px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #FF453A, stop:1 #DC1E1E);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #D70015, stop:1 #B20000);
            }
        """)

        try:
            self.process = subprocess.Popen(
                command,
                shell=True,
                cwd=self.project_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=get_user_environment(),
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="ignore",
                close_fds=True,
            )

            def read_output(pipe):
                for line in iter(pipe.readline, ""):
                    self.log_signals.append_log.emit(line)

            threading.Thread(
                target=read_output,
                args=(self.process.stdout,),
                daemon=True
            ).start()

            threading.Thread(
                target=read_output,
                args=(self.process.stderr,),
                daemon=True
            ).start()

            # Start process status checking
            self.status_timer = QTimer()
            self.status_timer.timeout.connect(self._check_process_status)
            self.status_timer.start(100)  # Check every 100ms

        except Exception as e:
            self._append_log(f"Error running command: {str(e)}\n")
            self.run_button.setText("Run")

    def _submit_feedback(self):
        self.feedback_result = FeedbackResult(
            logs="".join(self.log_buffer),
            interactive_feedback=self.feedback_text.toPlainText().strip(),
        )
        self.close()

    def clear_logs(self):
        self.log_buffer = []
        self.log_text.clear()

    def _save_config(self):
        # Save run_command and execute_automatically to QSettings under project group
        self.settings.beginGroup(self.project_group_name)
        self.settings.setValue("run_command", self.config["run_command"])
        self.settings.setValue("execute_automatically", self.config["execute_automatically"])
        self.settings.endGroup()
        self._append_log("Configuration saved for this project.\n")

    def closeEvent(self, event):
        # Save general UI settings for the main window (geometry, state)
        self.settings.beginGroup("MainWindow_General")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.endGroup()

        # Save project-specific command section visibility (this is now slightly redundant due to immediate save in toggle, but harmless)
        self.settings.beginGroup(self.project_group_name)
        self.settings.setValue("commandSectionVisible", self.command_group.isVisible())
        self.settings.endGroup()

        if self.process:
            kill_tree(self.process)
        super().closeEvent(event)

    def run(self) -> FeedbackResult:
        self.show()
        QApplication.instance().exec()

        if self.process:
            kill_tree(self.process)

        if not self.feedback_result:
            return FeedbackResult(logs="".join(self.log_buffer), interactive_feedback="")

        return self.feedback_result

def get_project_settings_group(project_dir: str) -> str:
    # Create a safe, unique group name from the project directory path
    # Using only the last component + hash of full path to keep it somewhat readable but unique
    basename = os.path.basename(os.path.normpath(project_dir))
    full_hash = hashlib.md5(project_dir.encode('utf-8')).hexdigest()[:8]
    return f"{basename}_{full_hash}"

def feedback_ui(project_directory: str, prompt: str, output_file: Optional[str] = None) -> Optional[FeedbackResult]:
    app = QApplication.instance() or QApplication()
    app.setPalette(get_apple_design_palette(app))
    app.setStyle("Fusion")
    
    # Apply the Apple stylesheet globally
    app.setStyleSheet(get_apple_styles())
    
    ui = FeedbackUI(project_directory, prompt)
    result = ui.run()

    if output_file and result:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        # Save the result to the output file
        with open(output_file, "w") as f:
            json.dump(result, f)
        return None

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the feedback UI")
    parser.add_argument("--project-directory", default=os.getcwd(), help="The project directory to run the command in")
    parser.add_argument("--prompt", default="I implemented the changes you requested.", help="The prompt to show to the user")
    parser.add_argument("--output-file", help="Path to save the feedback result as JSON")
    args = parser.parse_args()

    result = feedback_ui(args.project_directory, args.prompt, args.output_file)
    if result:
        print(f"\nLogs collected: \n{result['logs']}")
        print(f"\nFeedback received:\n{result['interactive_feedback']}")
    sys.exit(0)
