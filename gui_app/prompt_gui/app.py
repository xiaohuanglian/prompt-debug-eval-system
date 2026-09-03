"""Main application window - Prompt 自动化调试与评测系统 GUI."""

import sys
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QMessageBox, QApplication, QSplitter,
    QLabel, QPushButton, QLineEdit, QTextEdit, QPlainTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ._project_paths import PROJECT_ROOT  # noqa: F401 (ensures sys.path is set)

from .panels import (
    STYLE, StepNavWidget, WelcomePanel,
    ModelPanel, RequirementPanel, PromptPanel,
    EvalDataPanel, EvalScriptPanel, EvalRunPanel,
    ResultsPanel, OptimizePanel, DeployPanel,
)


class MainWindow(QMainWindow):
    """Main window with step navigation and stacked panels."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prompt 自动化调试与评测系统 - Virtual Coach")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # Shared context data passed between steps
        self.context = {}

        self._setup_ui()
        self._connect_navigation()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setStyleSheet("background: #1976D2; padding: 8px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 4, 12, 4)
        top_label = QLabel("Prompt 自动化调试与评测系统")
        top_label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        top_layout.addWidget(top_label)
        top_layout.addStretch()
        self.step_indicator = QLabel("准备开始")
        self.step_indicator.setStyleSheet("color: white; font-size: 13px;")
        top_layout.addWidget(self.step_indicator)
        main_layout.addWidget(top_bar)

        # Content area: sidebar + stacked panels
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar navigation
        self.nav = StepNavWidget()
        self.nav.setFont(QFont("Microsoft YaHei", 11))
        content_layout.addWidget(self.nav)

        # Separator
        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #ddd;")
        content_layout.addWidget(sep)

        # Stacked widget for panels
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        main_layout.addWidget(content, 1)

        # Status bar
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet(
            "background: #f5f5f5; padding: 4px 12px; border-top: 1px solid #ddd;"
            " color: #666; font-size: 12px;"
        )
        main_layout.addWidget(self.status_bar)

        # Create panels
        self.panels = []
        self._create_panels()

        # Show welcome
        self.stack.setCurrentIndex(0)

    def _create_panels(self):
        """Create all step panels and add to stack."""
        # Index 0: Welcome
        welcome = WelcomePanel()
        self.stack.addWidget(welcome)
        self.panels.append(welcome)

        # Index 1: Model selection
        self.model_panel = ModelPanel()
        self.stack.addWidget(self.model_panel)
        self.panels.append(self.model_panel)

        # Index 2: Requirements
        self.req_panel = RequirementPanel()
        self.stack.addWidget(self.req_panel)
        self.panels.append(self.req_panel)

        # Index 3: Prompt
        self.prompt_panel = PromptPanel()
        self.stack.addWidget(self.prompt_panel)
        self.panels.append(self.prompt_panel)

        # Index 4: Eval data
        self.eval_data_panel = EvalDataPanel()
        self.stack.addWidget(self.eval_data_panel)
        self.panels.append(self.eval_data_panel)

        # Index 5: Eval script
        self.eval_script_panel = EvalScriptPanel()
        self.stack.addWidget(self.eval_script_panel)
        self.panels.append(self.eval_script_panel)

        # Index 6: Run eval
        self.eval_run_panel = EvalRunPanel()
        self.stack.addWidget(self.eval_run_panel)
        self.panels.append(self.eval_run_panel)

        # Index 7: Results
        self.results_panel = ResultsPanel()
        self.stack.addWidget(self.results_panel)
        self.panels.append(self.results_panel)

        # Index 8: Optimize
        self.optimize_panel = OptimizePanel()
        self.stack.addWidget(self.optimize_panel)
        self.panels.append(self.optimize_panel)

        # Index 9: Deploy
        self.deploy_panel = DeployPanel()
        self.stack.addWidget(self.deploy_panel)
        self.panels.append(self.deploy_panel)

        self._make_non_button_text_copyable()

    def _make_non_button_text_copyable(self):
        """Make non-button UI text selectable/copyable across the window."""
        for label in self.findChildren(QLabel):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        for widget_type in (QLineEdit, QTextEdit, QPlainTextEdit):
            for editor in self.findChildren(widget_type):
                editor.setContextMenuPolicy(Qt.DefaultContextMenu)

    def _connect_navigation(self):
        self.nav.currentRowChanged.connect(self._on_nav_changed)

    def _on_nav_changed(self, index):
        """Handle navigation click - 0-indexed, but stack index 0 is Welcome."""
        self.stack.setCurrentIndex(index + 1)  # +1 for Welcome panel
        step_names = [
            "欢迎", "模型选择", "需求输入", "生成 Prompt",
            "评测数据", "评测脚本", "运行评测", "结果分析", "迭代优化", "上线部署"
        ]
        label = step_names[index + 1] if index + 1 < len(step_names) else ""
        self.step_indicator.setText(f"当前步骤: {label}")
        self.status_bar.setText(f"步骤 {index + 1}/9: {label}")

    def on_step_complete(self, step_index: int, data: dict):
        """
        Called when a step is completed.
        step_index: 0=model, 1=requirement, 2=prompt, 3=eval_data,
                    4=eval_script, 5=eval_run, 6=results, 7=optimize
        """
        self.context.update(data)

        if step_index == 0:
            # Model selected -> go to requirement
            self.req_panel.set_helper_llm(self.context.get("helper_llm"))
            self.req_panel.model_panel = self.model_panel
            self.go_to_step(2)

        elif step_index == 1:
            # Requirement entered -> go to prompt
            self.prompt_panel.set_context(self.context)
            self.go_to_step(3)

        elif step_index == 2:
            # Prompt confirmed -> go to eval data
            self.eval_data_panel.set_context(self.context)
            self.go_to_step(4)

        elif step_index == 3:
            # Eval data confirmed -> go to eval script
            self.eval_script_panel.set_context(self.context)
            self.go_to_step(5)

        elif step_index == 4:
            # Eval script confirmed -> go to run eval
            self.eval_run_panel.set_context(self.context)
            self.go_to_step(6)

        elif step_index == 5:
            # Eval done -> go to results
            self.results_panel.set_context(self.context)
            self.go_to_step(7)

        elif step_index == 6:
            # Results analyzed -> go to optimize
            self.optimize_panel.set_context(self.context)
            self.go_to_step(8)

        elif step_index == 7:
            # Optimize -> go to deploy
            self.deploy_panel.set_context(self.context)
            self.go_to_step(9)

    def go_to_step(self, step: int, extra_context: dict = None):
        """
        Navigate to a specific step by index.
        step: 0=welcome, 1=model, 2=requirement, 3=prompt,
              4=eval_data, 5=eval_script, 6=eval_run, 7=results,
              8=optimize, 9=deploy
        """
        if extra_context:
            self.context.update(extra_context)

        if step == 0:
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(-1)
            self.nav.blockSignals(False)
            self.stack.setCurrentIndex(0)
            self.step_indicator.setText("准备开始")
        else:
            # step 1-9 maps to nav row 0-8 and stack index 1-9
            nav_idx = step - 1
            self.nav.blockSignals(True)
            self.nav.setCurrentRow(nav_idx)
            self.nav.blockSignals(False)
            self.stack.setCurrentIndex(step)
            self.step_indicator.setText(f"当前步骤: {self.nav.steps[nav_idx]}")
            self.status_bar.setText(f"步骤 {step}/9: {self.nav.steps[nav_idx]}")

        # Refresh panels that are often reached by direct jumps or sidebar clicks.
        if step == 6 and extra_context:
            self.eval_run_panel.set_context(self.context)
        elif step == 7:
            self.results_panel.set_context(self.context)
        elif step == 8:
            self.optimize_panel.set_context(self.context)
        elif step == 9:
            self.deploy_panel.set_context(self.context)


def run_app():
    """Launch the GUI application."""
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    # Auto-refresh models on startup
    QApplication.processEvents()
    window.model_panel.refresh_models()

    sys.exit(app.exec_())
