import asyncio
import os
import subprocess
import sys
from typing import Optional
from PyQt5.QtGui import (QColor, QPainter, QBrush, QPainterPath,
                         QFontDatabase, QIcon)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                             QSizePolicy, QMenu, QGraphicsDropShadowEffect, QScrollArea,
                             QMessageBox, QPushButton, QGridLayout,
                             QToolButton, QStackedWidget, QLineEdit, QTextBrowser,
                             QDialog, QProgressDialog, QApplication)
from nonebot import logger
import qasync
import httpx
import base64
import webbrowser
import re
import markdown2
from .base_page import PageBase
from .utils.version_check import VersionUtils
from .utils.client import talker


async def get_plugins():
    """获取插件列表"""
    result = await talker.send_request("get_plugins")
    if result.error:
        raise Exception(result.error)
    else:
        return result.data.get("result", {})


async def get_plugin_config(name: str):
    """获取插件配置"""
    result = await talker.send_request("get_plugin_config", {"name": name})
    if result.error:
        raise Exception(result.error)
    else:
        return result.data.get("result", {})


def format_plugin_name(name: str) -> str:
    """格式化插件名称，去除nonebot_plugin_前缀"""
    return name.replace("nonebot_plugin_", "", 1)


async def get_latest_release(owner: str, repo: str) -> str:
    """获取GitHub仓库最新release版本"""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github.v3+json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("tag_name", "")
    except Exception as e:
        logger.warning(f"获取最新release失败: {str(e)}")
        return ""


class PluginCard(QFrame):
    """美化后的插件卡片，带有图标和更好的视觉效果"""

    def __init__(self, plugin_data: dict, parent=None):
        super().__init__(parent)
        self.plugin_data = plugin_data
        self.latest_version = None
        self._init_style()
        self._init_ui()
        self._init_context_menu()

    def _init_style(self):
        self.setMinimumSize(320, 180)
        self.setMaximumWidth(400)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

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
        self.setContextMenuPolicy(Qt.CustomContextMenu)
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

        # 插件图标（模拟）
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {self.theme_color.name()}, stop:1 #A29BFE);
            border-radius: 10px;
            color: white;
            font: bold 18px;
            qproperty-alignment: 'AlignCenter';
        """)
        # 显示插件名称首字母
        display_name = format_plugin_name(
            self.plugin_data["meta"]["name"] or self.plugin_data["name"])
        icon_label.setText(display_name[0].upper() if display_name else "P")
        top_bar_layout.addWidget(icon_label)

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

        # 优化版本显示
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
        separator.setFrameShape(QFrame.HLine)
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

        # 仅在插件有配置时添加配置菜单项
        if self.plugin_data["meta"]["config_exist"]:
            config_action = menu.addAction("⚙️ 插件配置")
            actions.append((config_action, self._on_config_clicked))
            menu.addSeparator()

        # 仅在插件有主页时添加主页菜单项
        if self.plugin_data["meta"]["homepage"]:
            homepage_action = menu.addAction("🌐 插件主页")
            actions.append((homepage_action, lambda: self._on_homepage_clicked(
                self.plugin_data["meta"]["homepage"])))

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
        index_url = os.getenv("PIP_INDEX_URL")

        title = "更新插件"
        message = f"将更新插件 {formatted_name} 到 v{version}，请稍等..."

        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok
        )

        if reply != QMessageBox.Ok:
            return

        pip_cmd = [
            sys.executable, "-m", "pip", "install",
            "--upgrade", f"{plugin_name}=={version}",
            "-i", index_url
        ]

        progress = QProgressDialog("正在更新插件，请稍候...", "", 0, 0, self)
        progress.setCancelButton(None)  # 禁止取消
        progress.setWindowTitle("更新中")
        progress.setModal(True)
        progress.show()
        QApplication.processEvents()

        try:
            result = subprocess.run(
                pip_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            progress.close()

            if result.returncode == 0:
                QMessageBox.information(
                    self,
                    "更新成功",
                    f"插件 {formatted_name} 已成功更新到 v{version}"
                )
            else:
                error_message = result.stderr.strip() or result.stdout.strip() or "未知错误"
                QMessageBox.critical(
                    self,
                    "更新失败",
                    f"更新插件时发生错误：\n{error_message}"
                )
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self,
                "异常",
                f"执行更新过程中出现异常：\n{str(e)}"
            )

    def _on_config_clicked(self):
        """处理插件配置点击事件"""
        parent = self.parent()
        QMessageBox.information(
            self, "施工中...", "红豆泥私密马赛! 插件配置页面正在施工中...")
        return
        while parent and not hasattr(parent, "show_subpage"):
            parent = parent.parent()

        if parent and hasattr(parent, "show_subpage"):
            config_page = PluginConfigPage(self.plugin_data, parent)
            parent.show_subpage(config_page)
        else:
            QMessageBox.information(
                self, "插件配置", f"将显示 {self.plugin_data['name']} 的配置页面")

    def _on_homepage_clicked(self, homepage: str):
        """处理插件主页点击事件"""
        logger.debug(f"开始处理主页点击事件，主页地址：{homepage}")

        if not homepage:
            QMessageBox.information(self, "无主页", "该插件没有设置主页")
            return

        try:
            if "github.com" in homepage:
                logger.debug(f"开始解析GitHub主页: {homepage}")
                match = re.search(r"github\.com/([^/]+)/([^/]+)", homepage)
                if match:
                    owner, repo = match.groups()
                    logger.debug(f"解析到GitHub仓库：{owner}/{repo}")
                    self._fetch_github_readme(owner, repo)
                else:
                    logger.warning(f"GitHub地址格式不标准: {homepage}")
                    webbrowser.open(homepage)
            else:
                logger.debug(f"打开普通主页: {homepage}")
                webbrowser.open(homepage)
        except Exception as e:
            logger.error(f"处理主页时发生异常: {str(e)}")
            QMessageBox.warning(self, "错误", f"无法处理主页地址: {str(e)}")

    async def _fetch_github_readme_async(self, owner: str, repo: str):
        """异步获取GitHub README"""
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        # 增加超时设置
        timeout = httpx.Timeout(10.0, connect=15.0)  # 连接超时15秒，读取超时10秒

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')

                # 移除图片支持，替换为提示信息
                content = re.sub(
                    r'\!\[(.*?)\]\(.*?\)',
                    lambda m: f'*[图片: {m.group(1) if m.group(1) else "本应有图片"}]',
                    content
                )

                return content

        except httpx.TimeoutException:
            logger.warning(f"获取GitHub README超时: {url}")
            # raise Exception("请求GitHub API超时，请检查网络连接")
        except httpx.HTTPStatusError as e:
            logger.warning(f"GitHub API返回错误状态码: {e.response.status_code}")
            raise Exception(f"GitHub API返回错误: {e.response.status_code}")
        except Exception as e:
            logger.error(f"获取GitHub README时发生错误: {str(e)}")
            raise Exception(f"获取README失败: {str(e)}")

    def _fetch_github_readme(self, owner: str, repo: str):
        """获取GitHub README并显示"""
        async def fetch_and_show():
            # 查找可以显示子页面的父组件
            parent = self.parent()
            while parent and not hasattr(parent, "show_subpage"):
                parent = parent.parent()

            loading_dialog = None
            try:
                # 显示加载中状态
                loading_dialog = QMessageBox(self)
                loading_dialog.setWindowTitle("加载中")
                loading_dialog.setText("正在从GitHub获取README内容...")
                loading_dialog.show()

                readme_content = await asyncio.wait_for(
                    self._fetch_github_readme_async(owner, repo),
                    timeout=20.0  # 总超时20秒
                )

                if loading_dialog:
                    loading_dialog.close()
                    loading_dialog = None

                self._show_readme_content(readme_content, f"{owner}/{repo}")

            except asyncio.TimeoutError:
                if loading_dialog:
                    loading_dialog.close()
                QMessageBox.warning(
                    self, "超时",
                    "获取README内容超时，将直接打开GitHub页面"
                )
                webbrowser.open(f"https://github.com/{owner}/{repo}")
            except Exception as e:
                if loading_dialog:
                    loading_dialog.close()
                QMessageBox.warning(
                    self, "错误",
                    f"无法获取README: {str(e)}\n将直接打开GitHub页面"
                )
                webbrowser.open(f"https://github.com/{owner}/{repo}")

        asyncio.create_task(fetch_and_show())

    def _show_readme_content(self, content: str, title: str):
        """在原窗口显示Markdown内容"""
        parent = self.parent()
        while parent and not hasattr(parent, "show_subpage"):
            parent = parent.parent()

        if parent and hasattr(parent, "show_subpage"):
            readme_page = ReadmePage(content, title, parent)
            parent.show_subpage(readme_page)
        else:
            # 如果没有找到可以显示子页面的父组件，则在新窗口显示
            dialog = QDialog()
            dialog.setWindowTitle(f"{title} - README")
            dialog.setMinimumSize(800, 600)
            layout = QVBoxLayout(dialog)

            text_browser = QTextBrowser()
            text_browser.setReadOnly(True)
            text_browser.setOpenLinks(False)  # 禁用链接点击

            html_content = markdown2.markdown(content, extras=[
                "break-on-newline",
                "fenced-code-blocks",
                "tables",
                "code-friendly",
                "strike",
                "footnotes",
                "cuddled-lists",
                "task_list",
                "highlightjs-lang",
            ])

            style = """
            <style>
                body { font-family: 'Segoe UI', sans-serif; line-height: 1.6; }
                pre { background: #f5f5f5; padding: 10px; border-radius: 4px; }
                code { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; }
                th { background-color: #f2f2f2; }
                a { color: #6C5CE7; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
            """

            text_browser.setHtml(f"{style}{html_content}")
            layout.addWidget(text_browser)

            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)

            dialog.exec_()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制圆角背景
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        painter.fillPath(path, QBrush(QColor("white")))

        # 绘制顶部装饰条
        decor_path = QPainterPath()
        decor_path.addRoundedRect(QRectF(0, 0, self.width(), 4), 2, 2)
        painter.fillPath(decor_path, QBrush(self.theme_color))


class ReadmePage(QWidget):
    """README页面，用于在原窗口显示"""

    def __init__(self, content: str, title: str, parent=None):
        super().__init__(parent)
        self.content = content
        self.title = title
        self.theme_color = QColor("#6C5CE7")
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            background: white;
            border-radius: 12px;
            padding: 0;
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setStyleSheet("""
            background: white;
            padding: 12px 20px;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid #E0E0E0;
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        back_btn = QPushButton("← 返回")
        back_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding: 2px 6px;
                border-radius: 4px;
                font: 14px 'Segoe UI';
                color: #6C5CE7;
                text-align: left;
            }
            QPushButton:hover {
                background: #F0F0F0;
            }
        """)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self._on_back_clicked)
        title_layout.addWidget(back_btn)

        # 标题标签
        title_label = QLabel(f"{self.title} - README")
        title_label.setStyleSheet("""
            color: #2D3436;
            font: bold 16px;
            margin-left: 10px;
        """)
        title_layout.addWidget(title_label, 1)

        close_btn = QPushButton("×")
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding: 2px 6px;
                border-radius: 4px;
                font: bold 16px;
                color: #6C5CE7;
            }
            QPushButton:hover {
                background: #F0F0F0;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self._on_back_clicked)
        title_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        # 内容区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: white;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
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

        content_widget = QWidget()
        content_widget.setStyleSheet("""
            background: white;
            padding: 15px;
        """)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)

        text_browser = QTextBrowser()
        text_browser.setReadOnly(True)
        text_browser.setOpenLinks(False)
        text_browser.setStyleSheet("""
            QTextBrowser {
                border: none;
                font: 13px 'Segoe UI';
            }
        """)

        html_content = markdown2.markdown(self.content, extras=[
            "break-on-newline",
            "fenced-code-blocks",
            "tables",
            "code-friendly",
            "strike",
            "footnotes",
            "cuddled-lists",
            "task_list",
            "highlightjs-lang",
        ])

        style = """
        <style>
            body {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
                line-height: 1.6;
                color: #2D3436;
                padding: 5px;
            }
            pre {
                background-color: #F5F7FA;
                border-radius: 6px;
                padding: 12px;
                overflow: auto;
                border-left: 4px solid #6C5CE7;
            }
            code {
                background-color: #F5F7FA;
                border-radius: 4px;
                padding: 0.2em 0.4em;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 0.9em;
            }
            a {
                color: #6C5CE7;
                text-decoration: none;
                font-weight: 500;
            }
            a:hover {
                text-decoration: underline;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 16px 0;
            }
            table th {
                background-color: #6C5CE7;
                color: white;
                font-weight: 500;
                padding: 10px 12px;
                text-align: left;
            }
            table td {
                padding: 8px 12px;
                border-bottom: 1px solid #E0E0E0;
            }
            table tr:nth-child(even) {
                background-color: #F9F9F9;
            }
            h1, h2, h3 {
                color: #2D3436;
                margin-top: 24px;
                margin-bottom: 16px;
            }
            h1 {
                border-bottom: 1px solid #E0E0E0;
                padding-bottom: 8px;
            }
            blockquote {
                border-left: 4px solid #A29BFE;
                background-color: #F5F7FA;
                padding: 8px 16px;
                margin: 16px 0;
                color: #636E72;
            }
            .image-placeholder {
                color: #636E72;
                font-style: italic;
                background-color: #F5F7FA;
                padding: 8px;
                border-radius: 4px;
                border: 1px dashed #BDBDBD;
            }
        </style>
        """

        html_content = f"{style}{html_content}"
        text_browser.setHtml(html_content)
        content_layout.addWidget(text_browser)

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, 1)

        self.setLayout(layout)

    def _on_back_clicked(self):
        """统一处理返回逻辑"""
        parent = self.parent()
        while parent and not hasattr(parent, "show_subpage"):
            parent = parent.parent()

        if parent and hasattr(parent, "show_subpage"):
            parent.stack.removeWidget(self)
            parent.show_subpage(None)
            self.deleteLater()


class PluginConfigPage(QWidget):
    """改进后的插件配置页面"""

    def __init__(self, plugin_data: dict, parent=None):
        super().__init__(parent)
        self.plugin_data = plugin_data
        self.theme_color = QColor("#6C5CE7")
        self.hover_color = QColor("#A29BFE")
        self.config_data = None
        self._init_ui()
        self.load_config()

    def _init_ui(self):
        self.setStyleSheet("""
            background: white;
            border-radius: 12px;
            padding: 0;
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题栏
        title_bar = QWidget()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(
            f"{format_plugin_name(self.plugin_data['name'])} 配置")
        title_label.setStyleSheet(f"""
            font: bold 18px 'Segoe UI';
            color: {self.theme_color.name()};
        """)
        title_layout.addWidget(title_label)

        close_btn = QToolButton()
        close_btn.setIcon(QIcon.fromTheme("window-close"))
        close_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                padding: 2px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background: #E0E0E0;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(lambda: self.parent().show_subpage(None))
        title_layout.addWidget(close_btn, 0, Qt.AlignRight)

        layout.addWidget(title_bar)

        # 表单区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        form_widget = QWidget()
        self.form_layout = QVBoxLayout(form_widget)
        self.form_layout.setContentsMargins(0, 10, 0, 0)
        self.form_layout.setSpacing(15)

        # 添加加载中的提示
        self.loading_label = QLabel("正在加载配置...")
        self.loading_label.setStyleSheet(
            "font: 14px 'Segoe UI'; color: #636E72;")
        self.form_layout.addWidget(self.loading_label, 0, Qt.AlignCenter)

        scroll.setWidget(form_widget)
        layout.addWidget(scroll, 1)

        self.setLayout(layout)

    async def _load_config_async(self):
        """异步加载配置"""
        try:
            return await get_plugin_config(self.plugin_data["name"])
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            return None

    def load_config(self):
        """加载配置数据"""
        async def _load():
            self.config_data = await self._load_config_async()
            if self.config_data:
                self._populate_config()
            else:
                self.loading_label.setText("无法加载插件配置")

        asyncio.create_task(_load())

    def _populate_config(self):
        """填充配置内容"""
        # 清除旧内容
        self.loading_label.hide()

        # 创建配置项
        if not self.config_data.get("configs"):
            info_label = QLabel("该插件没有可配置选项")
            info_label.setStyleSheet("font: 14px 'Segoe UI'; color: #636E72;")
            self.form_layout.addWidget(info_label, 0, Qt.AlignCenter)
            return

        for config_item in self.config_data["configs"]:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(15)

            label = QLabel(config_item["name"])
            label.setStyleSheet("""
                font: 14px 'Segoe UI';
                min-width: 120px;
            """)

            value_input = QLineEdit(str(config_item["value"]))
            value_input.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 8px;
                    min-width: 200px;
                }
            """)
            value_input.setProperty("config_key", config_item["key"])

            row_layout.addWidget(label)
            row_layout.addWidget(value_input, 1)
            self.form_layout.addWidget(row)

        # 添加保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme_color.name()};
                color: white;
                padding: 10px 24px;
                border-radius: 6px;
                font: 14px 'Segoe UI';
                margin-top: 20px;
            }}
            QPushButton:hover {{
                background: {self.hover_color.name()};
            }}
        """)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_config)
        self.form_layout.addWidget(save_btn, 0, Qt.AlignRight)

    def save_config(self):
        """保存配置逻辑"""
        # 收集所有配置项
        config_values = {}
        for i in range(self.form_layout.count()):
            widget = self.form_layout.itemAt(i).widget()
            if isinstance(widget, QWidget) and hasattr(widget, "layout"):
                for j in range(widget.layout().count()):
                    input_widget = widget.layout().itemAt(j).widget()
                    if isinstance(input_widget, QLineEdit):
                        config_key = input_widget.property("config_key")
                        if config_key:
                            config_values[config_key] = input_widget.text()

        # 实现具体保存逻辑
        QMessageBox.information(self, "保存成功", "配置已保存（模拟）")


class PluginPage(PageBase):
    """插件管理页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_cards = []
        self.main_widget = QWidget()
        self.stack = QStackedWidget(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self.main_widget)
        self.theme_color = QColor("#6C5CE7")
        self._init_ui()
        self._load_fonts()

    def show_subpage(self, widget: QWidget):
        """显示子页面"""
        if widget is None:
            # 返回主页面
            self.stack.setCurrentWidget(self.main_widget)
        else:
            # 显示子页面
            if widget not in [self.stack.widget(i) for i in range(self.stack.count())]:
                self.stack.addWidget(widget)
            self.stack.setCurrentWidget(widget)

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

        title = QLabel("插件管理中心")
        title.setStyleSheet("""
            color: #2D3436; 
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
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        # 使用网格布局
        self.card_layout = QGridLayout()
        self.card_layout.setHorizontalSpacing(25)
        self.card_layout.setVerticalSpacing(25)
        self.card_layout.setContentsMargins(5, 5, 5, 5)

        # 添加一个内部容器用于更好的间距控制
        inner_container = QWidget()
        inner_container.setLayout(QVBoxLayout())
        inner_container.layout().addLayout(self.card_layout)
        inner_container.layout().addStretch()

        scroll.setWidget(inner_container)
        main_layout.addWidget(scroll, 1)

        # 设置主布局
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.stack)

    async def _check_plugin_updates(self, plugin_data: dict) -> Optional[str]:
        """检查插件是否有更新"""
        current_version = plugin_data["meta"].get("version")
        if not current_version:
            return None

        homepage = plugin_data["meta"].get("homepage", "")
        if not homepage or "github.com" not in homepage:
            return None

        # 从主页提取GitHub仓库信息
        match = re.search(r"github\.com/([^/]+)/([^/]+)", homepage)
        if not match:
            return None

        owner, repo = match.groups()
        latest_version = await get_latest_release(owner, repo)
        if not latest_version:
            return None

        # 比较版本
        current_version = current_version.lstrip('v')
        latest_version = latest_version.lstrip('v')

        if VersionUtils.compare_versions(current_version, latest_version) < 0:
            return latest_version

        return None

    async def _load_plugins(self):
        """加载插件数据并创建卡片"""
        try:
            plugins = await get_plugins()
            self._clear_plugins()

            # 创建卡片
            row, col = 0, 0
            max_cols = 2  # 每行最多2个卡片

            for plugin_name, plugin_data in plugins.items():
                card = PluginCard(plugin_data, self)
                self.plugin_cards.append(card)
                self.card_layout.addWidget(card, row, col)

                # 检查更新
                latest_version = await self._check_plugin_updates(plugin_data)
                if latest_version:
                    card.set_update_available(latest_version)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            self.plugin_count.setText(f"已加载 {len(plugins)} 个插件")

        except Exception as e:
            QMessageBox.warning(self, "加载失败", f"无法加载插件列表: {str(e)}")
            self.plugin_count.setText("加载失败")

    def _clear_plugins(self):
        """清除已加载的插件卡片"""
        for card in self.plugin_cards:
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

    async def on_enter(self):
        """页面进入时加载插件"""
        await self._load_plugins()

    @qasync.asyncSlot()
    async def on_leave(self):
        """页面离开时清除插件卡片"""
        self.cleanup()
