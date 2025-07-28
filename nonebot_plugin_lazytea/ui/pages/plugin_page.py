import os
import ujson
from typing import Any, List, Dict, Optional
from PySide6.QtGui import (QColor, QPixmap,
                           QFontDatabase)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                               QSizePolicy, QMenu, QGraphicsDropShadowEffect, QScrollArea,
                               QGridLayout, QStackedWidget)
import webbrowser
import re
from .base_page import PageBase
from .utils.version_check import VersionUtils
from .utils.subpages.config_page import ConfigEditor
from .utils.Qcomponents.MessageBox import MessageBoxBuilder, MessageBoxConfig, ButtonConfig
from .utils.Qcomponents.networkmanager import ReleaseNetworkManager
from .utils.ui_types.plugins import PluginInfo
from .background.start import name_module
from .utils.client import talker, ResponsePayload
from .utils.tealog import logger


def format_plugin_name(name: str) -> str:
    """格式化插件名称，去除nonebot_plugin_前缀"""
    return name.replace("nonebot_plugin_", "", 1)


class PluginCard(QFrame):
    """插件卡片"""
    success_signal = Signal(ResponsePayload)
    update_signal = Signal(ResponsePayload)

    def __init__(self, plugin_data: PluginInfo, parent=None):
        super().__init__(parent)
        self.plugin_data = plugin_data
        self.latest_version = None
        self.icon_pixmap = None
        self.success_signal.connect(self._show_plugin_subpage)
        self.update_signal.connect(self._handle_update)
        self._load_icon()
        self._init_style()
        self._init_ui()
        self._init_context_menu()

    def _on_config_clicked(self):
        """获取插件配置"""
        instead_widget = self._get_plugin_widget()
        if instead_widget:
            parent = self.parent()
            grandparent = None
            while parent is not None:
                if isinstance(parent, PluginPage):
                    grandparent = parent
                    break
                parent = parent.parent()

            plugin_name = self.plugin_data["name"]

            if grandparent is not None:
                grandparent.show_subpage(instead_widget, f"{plugin_name}页面")
            else:
                logger.warning(f"加载插件 {plugin_name} 时配置页面未找到父控件")

        else:
            talker.send_request("get_plugin_config",
                                success_signal=self.success_signal, name=self.plugin_data.get("name"))

    def _show_plugin_subpage(self, response: ResponsePayload):
        schema: Dict[str, Any] = response.data.get("schema")  # type: ignore
        data: Dict[str, Any] = ujson.loads(
            response.data.get("data", ""))  # type: ignore
        editor = ConfigEditor(schema, data, self.plugin_data.get("module"))

        parent = self.parent()
        grandparent = None
        while parent is not None:
            if isinstance(parent, PluginPage):
                grandparent = parent
                break
            parent = parent.parent()

        plugin_name = self.plugin_data.get("meta").get(
            "name") or self.plugin_data.get("name")
        if grandparent is not None:
            grandparent.show_subpage(editor, f"{plugin_name} 插件配置")
        else:
            logger.warning(f"加载插件 {plugin_name} 时配置页面未找到父控件")

    def _load_icon(self):
        """加载插件图标"""
        icon_path = self.plugin_data["meta"].get("icon_abspath")
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # 缩放到40x40并保持比例
                self.icon_pixmap = pixmap.scaled(
                    QSize(40, 40),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

    def _init_style(self):
        self.setMinimumSize(320, 180)
        self.setMaximumWidth(400)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Preferred)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

        # 使用渐变色
        self.theme_color = QColor("#6C5CE7")  # 紫色主题
        self.hover_color = QColor("#A29BFE")  # 悬停颜色
        self.setStyleSheet(f"""
            PluginCard {{
                background: white;
                border-radius: 12px;
                border: none;
                padding: 0;
                margin: 0;
            }}
            QLabel {{
                margin: 0;
                padding: 0;
            }}
        """)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        self.setLayout(main_layout)

        # 顶部栏（图标+名称）
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(12)

        # 插件图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)

        display_name = format_plugin_name(
            self.plugin_data["meta"]["name"] or self.plugin_data["name"])

        if self.icon_pixmap:
            self.icon_label.setPixmap(self.icon_pixmap)
        else:
            self.icon_label.setStyleSheet(f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.theme_color.name()}, stop:1 #A29BFE);
                border-radius: 10px;
                color: white;
                font: bold 18px;
                qproperty-alignment: 'AlignCenter';
            """)
            # 显示插件名称首字母
            self.icon_label.setText(
                display_name[0].upper() if display_name else "P")

        top_bar_layout.addWidget(self.icon_label)

        # 插件名称和版本
        name_widget = QWidget()
        name_layout = QVBoxLayout(name_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(2)

        name_label = QLabel(display_name)
        name_label.setStyleSheet("""
            font: bold 16px 'Segoe UI';
            color: #2D3436;
        """)
        name_label.setWordWrap(True)
        name_layout.addWidget(name_label)

        # 版本显示
        version = self.plugin_data["meta"].get("version", "未知版本")
        if version != "未知版本":
            version = f"v{version}" if not version.startswith("v") else version

        self.version_label = QLabel(version)
        self.version_label.setStyleSheet("""
            font: 11px 'Segoe UI';
            color: #636E72;
        """)
        name_layout.addWidget(self.version_label)

        top_bar_layout.addWidget(name_widget, 1)

        main_layout.addWidget(top_bar)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(
            f"border: 1px solid {self.theme_color.name()}; opacity: 0.2; margin: 4px 0;")
        main_layout.addWidget(separator)

        # 作者信息
        author = self.plugin_data["meta"].get("author", "未知作者")
        if author != "未知作者":
            author_label = QLabel(f"作者: {author}")
            author_label.setStyleSheet("""
                font: 13px 'Segoe UI';
                color: #636E72;
                padding: 4px 0;
            """)
            main_layout.addWidget(author_label)

        # 插件描述
        desc_label = QLabel(self.plugin_data["meta"]["description"] or "暂无描述")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            font: 13px 'Segoe UI';
            color: #636E72;
            padding: 4px 0;
            margin-bottom: 8px;
        """)
        main_layout.addWidget(desc_label)

        # 底部信息栏
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        bottom_layout.addStretch()

        main_layout.addWidget(bottom_bar)

    def set_update_available(self, latest_version: str):
        """设置更新可用状态"""
        logger.debug(f"{self.plugin_data.get('name')} 最新版本为 {latest_version}")
        self.latest_version = latest_version
        current_version = self.plugin_data["meta"].get("version", "")

        if current_version and latest_version:
            self.version_label.setText(
                f'<a href="https://github.com/{self._get_github_repo()}/releases" style="color: #FF4757; text-decoration: none;">'
                f'v{current_version}</a> (最新: v{latest_version})'
            )
            self.version_label.setOpenExternalLinks(True)

    def _get_github_repo(self) -> str:
        """从主页URL提取GitHub仓库信息"""
        homepage = self.plugin_data["meta"].get("homepage", "")
        if not homepage:
            return ""

        match = re.search(r"github\.com/([^/]+)/([^/]+)", homepage)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        return ""

    def _init_context_menu(self):
        """初始化右键菜单"""
        self.context_menu = None

    def _get_plugin_widget(self) -> Optional[QWidget]:
        probable_module = name_module.get(self.plugin_data["name"])
        instead_widget = None

        if probable_module:
            widget_class = getattr(probable_module, "ShowMyPlugin", None)
            if widget_class is not None and issubclass(widget_class, QWidget):
                instead_widget = widget_class(parent=self)

        return instead_widget

    def _has_plugin_widget(self):
        probable_module = name_module.get(self.plugin_data["name"])

        if probable_module:
            widget_class = getattr(probable_module, "ShowMyPlugin", None)
            if widget_class is not None and issubclass(widget_class, QWidget):
                return True
        else:
            return False

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #EEE;
                border-radius: 8px;
                padding: 8px 0;
                min-width: 140px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #333;
                font: 14px;
            }
            QMenu::item:selected {
                background: #F0F4F8;
                border-radius: 4px;
            }
            QMenu::separator {
                height: 1px;
                background: #EEE;
                margin: 4px 0;
            }
        """)

        # 添加菜单项
        actions = []

        instead_widget = self._has_plugin_widget()

        # 仅在插件有配置或提供页面时添加配置菜单项
        if self.plugin_data["meta"]["config_exist"] or instead_widget:
            config_action = menu.addAction("⚙️ 插件配置")
            actions.append((config_action, self._on_config_clicked))
            menu.addSeparator()

        # 仅在插件有主页时添加主页菜单项
        if self.plugin_data["meta"]["homepage"]:
            homepage_action = menu.addAction("🌐 插件主页")
            actions.append((homepage_action, lambda: self._on_homepage_clicked(
                self.plugin_data["meta"]["homepage"])))  # type: ignore

        # 如果有新版本，添加更新菜单项
        if self.latest_version:
            update_action = menu.addAction("🔄 更新插件")
            actions.append((update_action, self._on_update_clicked))

        # 如果没有菜单项则不显示
        if not menu.actions():
            return

        # 执行菜单并处理结果
        action = menu.exec_(self.mapToGlobal(pos))
        for act, callback in actions:
            if action == act:
                callback()

    def _on_update_clicked(self):
        """处理更新插件点击事件"""
        plugin_name = self.plugin_data['name']
        formatted_name = format_plugin_name(plugin_name)
        version = self.latest_version

        if version is None:
            return

        title = "更新插件"
        message = f"将更新插件 {formatted_name} 到 v{version.removeprefix('v')}，请确认执行操作.\n更新完成后将弹窗提醒.\n请不要切换页面"

        reply = MessageBoxBuilder().set_title(title).set_content(
            message).set_icon_type(MessageBoxConfig.IconType.NoIcon).add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.OK,
                    text="确定"
                )
        ).add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.Cancel,
                    text="取消",
                    animation_color=QColor("#FFB4B4")
                )
        ).build_and_fetch_result()

        if reply != MessageBoxConfig.ButtonType.OK:
            return

        talker.send_request(
            "update_plugin", plugin_name=self.plugin_data["meta"].get("pip_name") or self.plugin_data["name"], success_signal=self.update_signal, error_signal=self.update_signal, timeout=600)

    def _handle_update(self, data: ResponsePayload):
        if data.error:
            returncode = 1
        else:
            returncode = 0
        plugin_name = self.plugin_data['name']
        formatted_name = format_plugin_name(plugin_name)
        version = self.latest_version
        if version is None:
            return  # 安抚类型检查

        if returncode == 0:

            MessageBoxBuilder().hide_icon().set_title("更新成功").set_content(
                f"插件 {formatted_name} 已成功更新到 v{version.removeprefix('v')}\n重启NoneBot以应用更新"
            ).add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.OK,
                    text="真是方便啊"
                )
            ).build_and_fetch_result()
        else:
            error_message = data.error or "未知错误"
            MessageBoxBuilder().hide_icon().set_title("更新失败惹").set_content(
                f"插件 {formatted_name} 更新失败:\n{error_message}"
            ).add_button(
                ButtonConfig(
                    btn_type=MessageBoxConfig.ButtonType.OK,
                    text="可恶"
                )
            ).build_and_fetch_result()

    def _on_homepage_clicked(self, homepage: str):
        """处理插件主页点击事件  直接在浏览器中打开"""
        logger.debug(f"开始处理主页点击事件，主页地址：{homepage}")
        webbrowser.open(homepage, new=2)

    def cleanup(self):
        try:
            self.success_signal.disconnect()
            self.update_signal.disconnect()
        except RuntimeError:
            pass


class PluginPage(PageBase):
    """插件管理页面"""
    success_signal = Signal(ResponsePayload)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_cards: List[PluginCard] = []
        self.main_widget = QWidget()
        self.stack = QStackedWidget(self)
        self.network_manager = ReleaseNetworkManager()
        self.network_manager.request_finished.connect(
            self._handle_network_response)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.main_widget)
        self.theme_color = QColor("#6C5CE7")
        self.success_signal.connect(self._load_plugins)
        self._init_ui()
        self._load_fonts()

    def get_plugins(self) -> None:
        """获取插件列表并调用生成"""
        talker.send_request("get_plugins", success_signal=self.success_signal)

    def _handle_network_response(self, request_type: str, data: dict, plugin_name: str):
        """处理网络请求响应"""
        if request_type == "github_release":
            if data["success"]:
                # 更新对应插件卡片的版本信息
                for card in self.plugin_cards:
                    if card.plugin_data.get("name") == plugin_name:
                        current_version = card.plugin_data["meta"].get(
                            "version", "")
                        if VersionUtils.compare_versions(
                            current_version,
                            data["version"]
                        ) < 0:
                            card.set_update_available(data["version"])
                        else:
                            logger.debug(
                                f"{plugin_name} 已经是最新版本 {card.plugin_data.get('meta').get('version')}")

    def _load_fonts(self):
        """加载自定义字体"""
        QFontDatabase.addApplicationFont(":/fonts/SegoeUI.ttf")
        QFontDatabase.addApplicationFont(":/fonts/SegoeUI-Bold.ttf")

    def _init_ui(self):
        self.setStyleSheet("""
            background: #F5F7FA;
            padding: 0;
            margin: 0;
        """)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(25)

        # 将主布局添加到主widget
        self.main_widget.setLayout(main_layout)

        # 标题栏
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("插件管理")
        title.setStyleSheet("""
            color: #279BFA; 
            font: bold 22px 'Segoe UI';
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.plugin_count = QLabel("加载中...")
        self.plugin_count.setStyleSheet("""
            color: #636E72;
            font: 15px 'Segoe UI';
        """)
        title_layout.addWidget(self.plugin_count)

        main_layout.addWidget(title_widget)

        # 卡片网格区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #E0E0E0;
                width: 10px;
                border-radius: 5px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self.content = QWidget()
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        # 使用网格布局
        self.card_layout = QGridLayout()
        self.card_layout.setHorizontalSpacing(25)
        self.card_layout.setVerticalSpacing(25)
        self.card_layout.setContentsMargins(5, 5, 5, 5)

        # 添加一个内部容器用于更好的间距控制
        inner_container = QWidget()
        inner_container.setLayout(QVBoxLayout())
        if layout := inner_container.layout():
            if isinstance(layout, QVBoxLayout):
                layout.addLayout(self.card_layout)
                layout.addStretch()

        scroll.setWidget(inner_container)
        main_layout.addWidget(scroll, 1)

        # 设置主布局
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.stack)

    def _check_plugin_updates(self, plugin_data: PluginInfo):
        """检查插件更新"""
        homepage = plugin_data["meta"].get("homepage", "")
        if not homepage or "github.com" not in homepage:
            return

        match = re.search(r"github\.com/([^/]+)/([^/]+)", homepage)
        if match:
            owner, repo = match.groups()
            self.network_manager.get_github_release(
                owner, repo, plugin_data.get("name"))

    def _load_plugins(self, plugins_: ResponsePayload):
        """加载插件数据并创建卡片"""
        try:
            if e := plugins_.error:
                raise Exception(e)

            plugins: Dict[str, PluginInfo] = plugins_.data  # type: ignore
            self._clear_plugins()
            if not plugins:
                return

            # 创建卡片
            row, col = 0, 0
            max_cols = 2  # 每行最多2个卡片

            for plugin_name, plugin_data in plugins.items():
                card = PluginCard(plugin_data, self)
                self.plugin_cards.append(card)
                self.card_layout.addWidget(card, row, col)

                # 检查更新
                if plugin_data.get("meta").get("version"):
                    self._check_plugin_updates(plugin_data)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            self.plugin_count.setText(f"已加载 {len(plugins)} 个插件")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.plugin_count.setText("加载失败")

    def _clear_plugins(self):
        """清除已加载的插件卡片"""
        for card in self.plugin_cards:
            card.cleanup()
            self.card_layout.removeWidget(card)
            card.deleteLater()
        self.plugin_cards.clear()

    def cleanup(self):
        """清理所有资源"""
        self._clear_plugins()
        # 清理堆栈中的子页面
        while self.stack.count() > 1:
            widget = self.stack.widget(1)
            self.stack.removeWidget(widget)
            widget.deleteLater()

    def on_enter(self):
        """页面进入时加载插件"""
        self.get_plugins()

    def on_leave(self):
        """页面离开时清除插件卡片"""
        self.cleanup()
