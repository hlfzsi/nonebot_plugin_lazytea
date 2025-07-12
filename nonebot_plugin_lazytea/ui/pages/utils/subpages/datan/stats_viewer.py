import colorsys
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Optional, Set, List

from PySide6.QtCore import Qt, QTimer, Slot, QPointF, QDateTime, QMargins, QObject, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QSplitter, QFrame
)
from PySide6.QtGui import QColor, QFont, QPalette, QPen, QBrush, QPainter, QWheelEvent
from PySide6.QtCharts import QChart, QChartView, QSplineSeries, QDateTimeAxis, QValueAxis

from ...Qcomponents.MessageBox import MessageBoxBuilder, MessageBoxConfig, ButtonConfig
from ...conn import get_database, AsyncQuerySignal
from ...tealog import logger


class PluginStatsViewer(QWidget):
    """
    - 鼠标滚轮: 在图表上滚动可缩放时间轴 (X轴)。
    - 鼠标左键拖动: 选择一个矩形区域可放大该区域。
    - 鼠标右键：未实现 不认为有必要
    """

    COLOR_BACKGROUND = QColor("#F8F9FA")
    COLOR_BORDER = QColor("#DEE2E6")
    COLOR_TEXT_PRIMARY = QColor("#212529")
    COLOR_TEXT_SECONDARY = QColor("#6C757D")
    COLOR_ACCENT = QColor("#0D6EFD")
    COLOR_ACCENT_LIGHT = QColor("#E9F2FF")

    def __init__(self, bot: str, platform: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        if not bot or not platform:
            raise ValueError("bot 和 platform 不能为空")

        self.bot = bot
        self.platform = platform
        self.table_name = "plugin_call_record"

        self.current_data: Dict[str, Dict[int, int]] = {}
        self.visible_plugins: Set[str] = set()
        self.plugin_series: Dict[str, QSplineSeries] = {}  # 存储QChart的Series对象
        self.plugin_colors: Dict[str, QColor] = {}
        self._is_loading = False
        self._is_closed = False
        self._is_first_load = True

        self.query_signal = AsyncQuerySignal()

        self.chart: QChart
        self.chart_view: QChartView
        self.axis_x: QDateTimeAxis
        self.axis_y: QValueAxis

        self.plugin_list_widget: QListWidget
        self.status_label: QLabel
        self.hover_label: QLabel

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)

        self._apply_stylesheet()
        self._init_ui()
        self._connect_signals()

        # 设置初始视图范围为最近24小时。自动触发第一次数据加载。
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        if hasattr(self, 'axis_x'):
            self.axis_x.setRange(
                QDateTime.fromSecsSinceEpoch(int(start_time.timestamp())),
                QDateTime.fromSecsSinceEpoch(int(end_time.timestamp()))
            )

    def _apply_stylesheet(self):
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, self.COLOR_BACKGROUND)
        self.setPalette(pal)

        qss = f"""
            /* 全局字体和颜色 */
            QWidget {{
                color: {self.COLOR_TEXT_PRIMARY.name()};
                font-family: "Segoe UI", "Microsoft YaHei", "Roboto", sans-serif;
            }}

            /* QChartView 边框 */
            QChartView {{
                border: 1px solid {self.COLOR_BORDER.name()};
                border-radius: 12px;
            }}

            /* 分割条样式 */
            QSplitter::handle {{
                background-color: {self.COLOR_BACKGROUND.name()};
            }}
            QSplitter::handle:vertical {{ height: 8px; }}
            QSplitter::handle:horizontal {{ width: 8px; }}
            QSplitter::handle:hover {{
                background-color: {self.COLOR_BORDER.name()};
            }}

            /* 控件容器样式 */
            QFrame#ControlsContainer {{
                background-color: {self.COLOR_BACKGROUND.name()};
                border: 1px solid {self.COLOR_BORDER.name()};
                border-radius: 12px; 
            }}

            /* 插件列表样式 */
            QListWidget {{
                background-color: transparent;
                border: none;
                padding: 5px;
                spacing: 5px; 
            }}
            QListWidget::item {{
                padding: 10px 8px;
                border-radius: 6px;
                background-color: transparent;
            }}
            QListWidget::item:hover {{
                background-color: {self.COLOR_ACCENT_LIGHT.name()};
            }}
            QListWidget::item:selected {{
                background-color: {self.COLOR_ACCENT_LIGHT.name()};
                color: {self.COLOR_ACCENT.name()};
                font-weight: bold;
            }}
            
            /* 列表项复选框样式 */
            QListWidget::indicator {{
                width: 16px; height: 16px; margin-right: 5px;
            }}
            QListWidget::indicator:unchecked {{
                image: url(none);
                border: 1.5px solid {self.COLOR_BORDER.darker(120).name()};
                border-radius: 4px;
                background-color: transparent;
            }}
            QListWidget::indicator:unchecked:hover {{
                border-color: {self.COLOR_ACCENT.name()};
            }}
            QListWidget::indicator:checked {{
                image: url(none);
                border: 1.5px solid {self.COLOR_ACCENT.name()};
                border-radius: 4px;
                background-color: {self.COLOR_ACCENT.name()};
            }}

            QScrollBar:vertical {{
                border: none;
                background: {self.COLOR_BACKGROUND.name()};
                width: 10px; margin: 15px 0 15px 0; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.COLOR_BORDER.name()};
                min-height: 20px; border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {self.COLOR_BORDER.darker(120).name()};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """
        self.setStyleSheet(qss)

    def _init_ui(self):
        """初始化用户界面布局和组件。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)

        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(10)

        self._setup_chart_view()

        self.status_label = QLabel("正在初始化，请稍候...", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(10)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet(
            f"color: {self.COLOR_TEXT_SECONDARY.name()}; padding: 5px;")

        chart_layout.addWidget(self.chart_view, 1)
        chart_layout.addWidget(self.status_label)

        controls_container = QFrame()
        controls_container.setObjectName("ControlsContainer")
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(15, 15, 15, 15)
        controls_layout.setSpacing(10)

        list_label = QLabel("选择插件以在图表中显示/隐藏", self)
        list_label_font = QFont()
        list_label_font.setPointSize(12)
        list_label_font.setBold(True)
        list_label.setFont(list_label_font)

        self.plugin_list_widget = QListWidget(self)

        controls_layout.addWidget(list_label)
        controls_layout.addWidget(self.plugin_list_widget)

        splitter.addWidget(chart_container)
        splitter.addWidget(controls_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 250])

        main_layout.addWidget(splitter)

    def _setup_chart_view(self):
        """配置QChartView和QChart，使其与主题风格融合。"""
        self.chart = QChart()
        self.chart.setBackgroundBrush(QBrush(self.COLOR_BACKGROUND))

        self.chart.setMargins(QMargins(0, 0, 0, 0))
        self.chart.layout().setContentsMargins(0, 0, 0, 0)
        self.chart.legend().hide()

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setObjectName("ChartView")

        # 配置X轴 (时间)
        self.axis_x = QDateTimeAxis()
        self.axis_x.setFormat("MM-dd HH:mm")
        self.axis_x.setTitleText("时间")
        self.axis_x.setLabelsColor(self.COLOR_TEXT_SECONDARY)
        self.axis_x.setTitleBrush(QBrush(self.COLOR_TEXT_SECONDARY))
        self.axis_x.setGridLinePen(
            QPen(self.COLOR_BORDER, 0.5, Qt.PenStyle.DashLine))
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)

        # 配置Y轴 (调用次数)
        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("调用次数")
        self.axis_y.setLabelsColor(self.COLOR_TEXT_SECONDARY)
        self.axis_y.setTitleBrush(QBrush(self.COLOR_TEXT_SECONDARY))
        self.axis_y.setGridLinePen(
            QPen(self.COLOR_BORDER, 0.5, Qt.PenStyle.SolidLine))
        self.axis_y.setLabelFormat("%d")
        self.axis_y.setTickCount(7)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)

        # 允许左键拖动区域缩放
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart_view.setRubberBand(
            QChartView.RubberBand.HorizontalRubberBand)

        # 创建悬浮提示标签
        self.hover_label = QLabel(self.chart_view)
        self.hover_label.setAutoFillBackground(True)
        hover_palette = self.hover_label.palette()
        hover_bg = self.COLOR_BACKGROUND.lighter(105)
        hover_bg.setAlpha(230)
        hover_palette.setColor(QPalette.ColorRole.Window, hover_bg)
        self.hover_label.setPalette(hover_palette)
        self.hover_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.hover_label.setStyleSheet(f"""
            QLabel {{
                color: {self.COLOR_TEXT_PRIMARY.name()};
                border: 1.5px solid {self.COLOR_BORDER.name()};
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }}
        """)
        self.hover_label.hide()
        self.hover_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _connect_signals(self):
        if hasattr(self, 'axis_x'):
            self.axis_x.rangeChanged.connect(self._on_range_changed_debounced)

        self._debounce_timer.timeout.connect(
            self._fetch_data_for_current_range)
        self.query_signal.finished.connect(self._on_data_received)
        self.plugin_list_widget.itemChanged.connect(
            self._on_plugin_selection_changed)

        self.chart_view.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        事件过滤器，用于在QChartView上实现滚轮缩放。
        """
        if watched is not self.chart_view:
            return super().eventFilter(watched, event)

        # 滚轮缩放事件
        if event.type() == QEvent.Type.Wheel:
            self.handle_wheel_event(event)  # type: ignore
            return True

        return super().eventFilter(watched, event)

    def handle_wheel_event(self, event: QWheelEvent):
        """处理图表视图上的滚轮事件以缩放X轴。"""
        if not hasattr(self, 'axis_x'):
            return

        zoom_factor = 1.25
        if event.angleDelta().y() < 0:
            zoom_factor = 1 / zoom_factor

        cursor_pos = event.position()
        first_series = next(iter(self.plugin_series.values()), None)
        center_value_ms = self.chart.mapToValue(cursor_pos, first_series).x()

        if center_value_ms == 0:
            center_value_ms = (self.axis_x.min().toMSecsSinceEpoch(
            ) + self.axis_x.max().toMSecsSinceEpoch()) / 2

        current_min_ms = self.axis_x.min().toMSecsSinceEpoch()
        current_max_ms = self.axis_x.max().toMSecsSinceEpoch()

        new_min_ms = center_value_ms - \
            (center_value_ms - current_min_ms) / zoom_factor
        new_max_ms = center_value_ms + \
            (current_max_ms - center_value_ms) / zoom_factor

        if new_max_ms - new_min_ms < 60 * 1000:
            return
        if new_max_ms - new_min_ms > 10 * 365 * 24 * 3600 * 1000:
            return

        self.axis_x.setRange(
            QDateTime.fromMSecsSinceEpoch(int(new_min_ms)),
            QDateTime.fromMSecsSinceEpoch(int(new_max_ms))
        )

    @Slot(QPointF, bool)
    def _on_series_hovered(self, point: QPointF, state: bool):
        """当鼠标悬停在数据点上时调用，显示悬浮提示。"""
        series = self.sender()
        if not state or not isinstance(series, QSplineSeries):
            self.hover_label.hide()
            return

        plugin_name = series.name()
        color = self.plugin_colors.get(plugin_name, self.COLOR_ACCENT)
        dt_object = QDateTime.fromMSecsSinceEpoch(int(point.x()))

        html_text = f"""
        <div style='font-family: "Segoe UI", "Microsoft YaHei";'>
            <span style='font-weight: bold; color: {color.name()};'>{plugin_name}</span><br>
            <span style='color: {self.COLOR_TEXT_SECONDARY.name()};'>时间: {dt_object.toString("yyyy-MM-dd HH:mm:ss")}</span><br>
            <span style='color: {self.COLOR_TEXT_SECONDARY.name()};'>调用: <b>{int(point.y())}</b> 次</span>
        </div>
        """
        self.hover_label.setText(html_text)
        self.hover_label.adjustSize()

        chart_pos = self.chart.mapToPosition(point, series)
        x = chart_pos.x() - self.hover_label.width() / 2
        y = chart_pos.y() - self.hover_label.height() - 15

        if x < 0:
            x = 5
        if y < 0:
            y = 5
        if x + self.hover_label.width() > self.chart_view.width():
            x = self.chart_view.width() - self.hover_label.width() - 5

        self.hover_label.move(int(x), int(y))
        self.hover_label.show()

    @Slot()
    def _on_range_changed_debounced(self):
        if self._is_loading:
            return
        self._debounce_timer.start()

    @Slot()
    def _fetch_data_for_current_range(self):
        """根据当前图表的X轴范围和预设规则，从数据库获取聚合后的数据。"""
        if self._is_loading:
            logger.debug("正在加载数据，忽略此次刷新请求。")
            return

        min_dt = self.axis_x.min()
        max_dt = self.axis_x.max()
        min_x = min_dt.toSecsSinceEpoch()
        max_x = max_dt.toSecsSinceEpoch()

        time_span_days = (max_x - min_x) / 86400.0

        time_bucket_expression = ""
        granularity_text = ""
        if time_span_days > 30:
            time_bucket_expression = "strftime('%s', strftime('%Y-%m-%d 00:00:00', timestamp, 'unixepoch'))"
            granularity_text = "天"
        elif time_span_days > 7:
            time_bucket_expression = "strftime('%s', strftime('%Y-%m-%d %H:00:00', timestamp, 'unixepoch'))"
            granularity_text = "小时"
        elif time_span_days > 1:
            time_bucket_expression = "CAST(timestamp / 1800 AS INTEGER) * 1800"
            granularity_text = "30分钟"
        elif time_span_days > (1.0 / 24.0):
            time_bucket_expression = "CAST(timestamp / 900 AS INTEGER) * 900"
            granularity_text = "15分钟"
        else:
            time_bucket_expression = "CAST(timestamp / 60 AS INTEGER) * 60"
            granularity_text = "分钟"

        sql = f"""
            SELECT
                CAST({time_bucket_expression} AS INTEGER) as time_bucket,
                plugin_name,
                COUNT(*) as call_count
            FROM {self.table_name}
            WHERE
                bot = ? AND
                platform = ? AND
                timestamp BETWEEN ? AND ?
            GROUP BY time_bucket, plugin_name
            ORDER BY time_bucket;
        """
        params = (self.bot, self.platform, int(min_x), int(max_x))

        self._is_loading = True
        self.status_label.setText(f"正在加载数据... (聚合粒度: {granularity_text})")

        try:
            db = get_database()
            db.execute_async(
                sql, params, callback_signal=self.query_signal, for_write=False)
        except Exception as e:
            self._is_loading = False
            error_msg = f"数据库连接或查询执行失败: {e}"
            logger.error(error_msg)
            self.status_label.setText(f"错误: {error_msg}")
            self._show_error_dialog("数据库错误", error_msg)

    @Slot(object, object)
    def _on_data_received(self, result: Optional[List], error: Optional[Exception]):
        """处理从数据库异步返回的数据。"""
        if self._is_closed:
            logger.debug(f"统计窗口已关闭 ({self.bot}@{self.platform})，忽略返回的数据。")
            return

        try:
            if error:
                error_msg = f"数据加载失败: {error}"
                logger.error(error_msg)
                self.status_label.setText(error_msg)
                self._show_error_dialog("查询错误", f"从数据库获取数据时出错：\n{error}")
                return

            new_data = defaultdict(dict)
            all_plugins_in_range = set()
            if result:
                for ts, plugin_name, count in result:
                    new_data[plugin_name][ts] = count
                    all_plugins_in_range.add(plugin_name)
                self.status_label.setText(
                    f"数据加载完成，共发现 {len(all_plugins_in_range)} 个插件。")
            else:
                self.status_label.setText("当前时间范围内无数据。")

            self.current_data = new_data
            self._update_plugin_list(all_plugins_in_range)
            self._update_plot()

            if self._is_first_load and result:
                all_timestamps = [
                    float(ts) for p_data in new_data.values() for ts in p_data.keys()]
                if all_timestamps:
                    min_ts, max_ts = min(all_timestamps), max(all_timestamps)
                    if min_ts == max_ts:
                        min_ts -= 3600
                        max_ts += 3600

                    current_min_ts = self.axis_x.min().toSecsSinceEpoch()
                    current_max_ts = self.axis_x.max().toSecsSinceEpoch()

                    if not (current_min_ts < min_ts < current_max_ts):
                        padding = (max_ts - min_ts) * 0.1
                        self.axis_x.setRange(
                            QDateTime.fromSecsSinceEpoch(
                                int(min_ts - padding)),
                            QDateTime.fromSecsSinceEpoch(int(max_ts + padding))
                        )
            self._is_first_load = False
        finally:
            self._is_loading = False

    def _update_plugin_list(self, plugins_in_range: Set[str]):
        """根据获取到的数据更新下方的插件选择列表。"""
        self.plugin_list_widget.blockSignals(True)
        existing_items_text = {self.plugin_list_widget.item(
            i).text() for i in range(self.plugin_list_widget.count())}

        for plugin_name in sorted(list(plugins_in_range)):
            if plugin_name not in self.plugin_colors:
                self.plugin_colors[plugin_name] = self._get_distinct_color(
                    len(self.plugin_colors))

            if plugin_name not in existing_items_text:
                item = QListWidgetItem(plugin_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item_font = item.font()
                item_font.setPointSize(10)
                item.setFont(item_font)
                item.setForeground(self.plugin_colors[plugin_name].darker(120))

                if self._is_first_load:
                    item.setCheckState(Qt.CheckState.Checked)
                    self.visible_plugins.add(plugin_name)
                else:
                    is_visible = plugin_name in self.visible_plugins
                    item.setCheckState(
                        Qt.CheckState.Checked if is_visible else Qt.CheckState.Unchecked)
                self.plugin_list_widget.addItem(item)

        plugins_to_remove = existing_items_text - plugins_in_range
        if plugins_to_remove:
            for i in range(self.plugin_list_widget.count() - 1, -1, -1):
                item = self.plugin_list_widget.item(i)
                if item.text() in plugins_to_remove:
                    self.plugin_list_widget.takeItem(i)
                    self.visible_plugins.discard(item.text())
        self.plugin_list_widget.blockSignals(False)

    @Slot(QListWidgetItem)
    def _on_plugin_selection_changed(self, item: QListWidgetItem):
        """当插件列表中的复选框状态改变时调用，更新可见插件集合并重绘图表。"""
        plugin_name = item.text()
        if item.checkState() == Qt.CheckState.Checked:
            self.visible_plugins.add(plugin_name)
        else:
            self.visible_plugins.discard(plugin_name)
        self._update_plot()

    def _update_plot(self):
        plugins_to_show = self.visible_plugins.intersection(
            self.current_data.keys())
        current_plotted_plugins = set(self.plugin_series.keys())
        max_y = 0

        plugins_to_remove = current_plotted_plugins - plugins_to_show
        for plugin_name in plugins_to_remove:
            if plugin_name in self.plugin_series:
                series = self.plugin_series.pop(plugin_name)
                self.chart.removeSeries(series)
                series.deleteLater()

        for plugin_name in sorted(list(plugins_to_show)):
            data_points = self.current_data.get(plugin_name, {})
            if not data_points:
                continue

            timestamps = sorted(data_points.keys())
            points_data = [(float(ts), data_points[ts]) for ts in timestamps]
            if points_data:
                max_y = max(max_y, max(p[1] for p in points_data))

            series = self.plugin_series.get(plugin_name)
            if series:
                series.clear()
            else:
                series = QSplineSeries()
                series.setName(plugin_name)
                series.setPen(QPen(self.plugin_colors[plugin_name], 2.5))
                series.setPointsVisible(True)
                series.setMarkerSize(8)
                series.hovered.connect(self._on_series_hovered)
                self.plugin_series[plugin_name] = series
                self.chart.addSeries(series)
                series.attachAxis(self.axis_x)
                series.attachAxis(self.axis_y)

            for ts, count in points_data:
                series.append(ts * 1000, count)

        y_range_top = max_y * 1.15 if max_y > 0 else 10
        self.axis_y.setRange(0, y_range_top)

    def _get_distinct_color(self, index: int) -> QColor:
        hue = (index * 0.61803398875) % 1.0
        saturation = 0.95
        value = 0.75
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        return QColor.fromRgbF(r, g, b)

    def _show_error_dialog(self, title: str, text: str):
        MessageBoxBuilder().set_title(title).set_content(text).set_icon_type(
            MessageBoxConfig.IconType.Critical
        ).add_button(
            ButtonConfig(btn_type=MessageBoxConfig.ButtonType.OK,
                         text="确定", role='danger')
        ).build_and_fetch_result()

    def closeEvent(self, event):
        self._is_closed = True
        self._debounce_timer.stop()
        try:
            self.query_signal.finished.disconnect(self._on_data_received)
        except (TypeError, RuntimeError):
            pass
        if hasattr(self, 'chart'):
            self.chart.removeAllSeries()
        super().closeEvent(event)
