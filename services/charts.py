from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtCharts import QBarSeries, QBarSet, QChart, QChartView, QValueAxis, QBarCategoryAxis
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter


def build_bar_chart(data: List[Tuple[str, float]], title: str) -> QChartView:
    chart = QChart()
    chart.setTitle(title)

    series = QBarSeries()
    bar_set = QBarSet("Total")
    categories = []
    for label, value in data:
        categories.append(label)
        bar_set.append(float(value))
    series.append(bar_set)
    chart.addSeries(series)

    axis_x = QBarCategoryAxis()
    axis_x.append(categories)
    axis_x.setLabelsAngle(-35)
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)

    axis_y = QValueAxis()
    axis_y.setLabelFormat("%d")
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)

    chart.legend().setVisible(False)

    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    return view
