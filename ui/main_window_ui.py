from __future__ import annotations

import base64
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtCore import QByteArray, QBuffer
from PyQt6.QtGui import QAction, QImage
from PyQt6.QtSql import QSqlDatabase, QSqlQuery, QSqlQueryModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from services.charts import build_bar_chart
from services.csv_importer import import_csv
from services.database import (
    find_standard_columns,
    get_table_columns,
    open_database,
)
from services.reports import export_html_to_pdf, render_table_to_html


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DGT Driving Exams")
        self.resize(1200, 720)

        self.db: QSqlDatabase = open_database()
        self.model = QSqlQueryModel(self)
        self.current_columns: List[str] = []
        self.current_headers: List[str] = []
        self.standard_columns = find_standard_columns(get_table_columns(self.db, "exams"))

        self._build_menu()
        self._build_ui()
        self._refresh_completers()
        self._apply_filters()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        import_action = QAction("Import CSV", self)
        import_action.triggered.connect(self._import_csv)
        file_menu.addAction(import_action)

    def _build_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(self._build_filters())
        layout.addWidget(self._build_results())

        self.setCentralWidget(container)

    def _build_filters(self) -> QWidget:
        group = QGroupBox("Filters")
        layout = QVBoxLayout(group)

        form = QFormLayout()

        self.from_month = QComboBox()
        self.to_month = QComboBox()
        months = ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
        self.from_month.addItems(months)
        self.to_month.addItems(months)

        self.from_year = QSpinBox()
        self.from_year.setRange(0, 2100)
        self.from_year.setSpecialValueText("")
        self.from_year.setValue(0)

        self.to_year = QSpinBox()
        self.to_year.setRange(0, 2100)
        self.to_year.setSpecialValueText("")
        self.to_year.setValue(0)

        self.province_input = QLineEdit()
        self.exam_center_input = QLineEdit()
        self.driving_school_input = QLineEdit()
        self.permit_input = QLineEdit()

        self.exam_type_input = QComboBox()
        self.exam_type_input.addItem("")

        form.addRow("From month", self.from_month)
        form.addRow("From year", self.from_year)
        form.addRow("To month", self.to_month)
        form.addRow("To year", self.to_year)
        form.addRow("Province", self.province_input)
        form.addRow("Exam center", self.exam_center_input)
        form.addRow("Exam type", self.exam_type_input)
        form.addRow("Driving school", self.driving_school_input)
        form.addRow("Permit", self.permit_input)

        layout.addLayout(form)

        self.group_by = QComboBox()
        self.group_by.addItems(
            [
                "None",
                "Year",
                "Month and Year",
                "Province",
                "Exam center",
                "Driving school",
            ]
        )

        self.limit_input = QSpinBox()
        self.limit_input.setRange(0, 50000)
        self.limit_input.setSpecialValueText("No limit")
        self.limit_input.setValue(0)

        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Group by"))
        group_layout.addWidget(self.group_by)
        group_layout.addWidget(QLabel("Limit"))
        group_layout.addWidget(self.limit_input)
        group_layout.addStretch(1)

        layout.addLayout(group_layout)

        self.columns_box = self._build_columns_box()
        layout.addWidget(self.columns_box)

        actions_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply filters")
        self.apply_button.clicked.connect(self._apply_filters)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self.apply_button)
        layout.addLayout(actions_layout)

        return group

    def _build_columns_box(self) -> QWidget:
        group = QGroupBox("Columns")
        layout = QHBoxLayout(group)
        self.column_checks: List[QCheckBox] = []

        for label, key in [
            ("Year", "year"),
            ("Month", "month"),
            ("Province", "province"),
            ("Exam center", "exam_center"),
            ("Exam type", "exam_type"),
            ("Driving school", "driving_school"),
            ("Permit", "permit"),
            ("Num aptos", "num_aptos"),
            ("Num no aptos", "num_no_aptos"),
        ]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.setProperty("column_key", key)
            self.column_checks.append(checkbox)
            layout.addWidget(checkbox)

        layout.addStretch(1)
        return group

    def _build_results(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        self.tabs = QTabWidget()

        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_changed)

        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_view = None

        self.tabs.addTab(self.table_view, "Table")
        self.tabs.addTab(self.chart_container, "Chart")

        layout.addWidget(self.tabs)

        export_layout = QHBoxLayout()
        export_layout.addStretch(1)
        self.export_button = QToolButton()
        self.export_button.setText("Export PDF")
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        export_menu = QMenu(self.export_button)
        export_menu.addAction("Table", self._export_table_pdf)
        export_menu.addAction("Chart", self._export_chart_pdf)
        export_menu.addAction("Table + Chart", self._export_both_pdf)
        self.export_button.setMenu(export_menu)
        self.export_button.clicked.connect(self._export_both_pdf)
        export_layout.addWidget(self.export_button)
        layout.addLayout(export_layout)

        return container

    def _import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV or TXT file",
            "",
            "CSV or Text Files (*.csv *.txt);;All Files (*)",
        )
        if not path:
            return
        inserted, periods = import_csv(self.db, path)
        if inserted == 0 and periods:
            QMessageBox.information(
                self,
                "CSV import",
                "Data for that month/year already exists. Import skipped.",
            )
        else:
            QMessageBox.information(self, "CSV import", f"Imported {inserted} rows.")
        self.standard_columns = find_standard_columns(get_table_columns(self.db, "exams"))
        self._refresh_completers()
        self._apply_filters()

    def _refresh_completers(self) -> None:
        province_values = self._distinct_values(self.standard_columns.get("province"))
        exam_center_values = self._distinct_values(self.standard_columns.get("exam_center"))
        driving_school_values = self._distinct_values(self.standard_columns.get("driving_school"))
        exam_type_values = self._distinct_values(self.standard_columns.get("exam_type"))
        permit_values = self._distinct_values(self.standard_columns.get("permit"))

        self._set_completer(self.province_input, province_values)
        self._set_completer(self.exam_center_input, exam_center_values)
        self._set_completer(self.driving_school_input, driving_school_values)
        self._set_completer(self.permit_input, permit_values)

        self.exam_type_input.clear()
        self.exam_type_input.addItem("")
        self.exam_type_input.addItems(exam_type_values)

        self.province_input.editingFinished.connect(self._refresh_exam_center_completer)
        self.exam_center_input.editingFinished.connect(self._refresh_driving_school_completer)
        self._refresh_year_month_ranges()

    def _refresh_exam_center_completer(self) -> None:
        province = self.province_input.text().strip()
        values = self._distinct_values(
            self.standard_columns.get("exam_center"),
            filters=[(self.standard_columns.get("province"), province)] if province else [],
        )
        self._set_completer(self.exam_center_input, values)

    def _refresh_driving_school_completer(self) -> None:
        province = self.province_input.text().strip()
        exam_center = self.exam_center_input.text().strip()
        filters = []
        if province:
            filters.append((self.standard_columns.get("province"), province))
        if exam_center:
            filters.append((self.standard_columns.get("exam_center"), exam_center))
        values = self._distinct_values(self.standard_columns.get("driving_school"), filters=filters)
        self._set_completer(self.driving_school_input, values)

    def _set_completer(self, line_edit: QLineEdit, values: List[str]) -> None:
        completer = QCompleter(values)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        line_edit.setCompleter(completer)

    def _distinct_values(self, column: Optional[str], filters: Optional[List[Tuple[Optional[str], str]]] = None) -> List[str]:
        if not column:
            return []
        filters = filters or []
        clauses = []
        for col, value in filters:
            if col and value:
                clauses.append(f'TRIM("{col}") = ?')
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = QSqlQuery(self.db)
        query.prepare(f'SELECT DISTINCT TRIM("{column}") FROM exams {where_sql} ORDER BY TRIM("{column}")')
        for col, value in filters:
            if col and value:
                query.addBindValue(value.strip())
        query.exec()
        values = []
        while query.next():
            val = query.value(0)
            if val is not None and str(val).strip():
                values.append(str(val))
        return values

    def _build_query(self, order_by: Optional[str] = None, order_dir: str = "ASC") -> Tuple[str, List]:
        select_columns = self._selected_columns()
        group = self.group_by.currentText()

        if group != "None":
            group_columns = self._group_columns(group)
            metrics = []
            aptos_col = self.standard_columns.get("num_aptos")
            no_aptos_col = self.standard_columns.get("num_no_aptos")
            if aptos_col:
                metrics.append(f'SUM(CAST("{aptos_col}" AS INTEGER)) as num_aptos')
            if no_aptos_col:
                metrics.append(f'SUM(CAST("{no_aptos_col}" AS INTEGER)) as num_no_aptos')
            if aptos_col and no_aptos_col:
                metrics.append(
                    f'(SUM(CAST("{aptos_col}" AS INTEGER)) + SUM(CAST("{no_aptos_col}" AS INTEGER))) as total_exams'
                )
            else:
                metrics.append("COUNT(*) as total_exams")
            select_sql = ", ".join([f'"{c}"' for c in group_columns] + metrics)
        else:
            select_sql = ", ".join([f'"{c}"' for c in select_columns]) if select_columns else "*"

        where_clauses = []
        params = []

        month_col = self.standard_columns.get("month")
        year_col = self.standard_columns.get("year")

        from_month = self.from_month.currentText()
        to_month = self.to_month.currentText()
        from_year = self.from_year.value() if self.from_year.value() != 0 else None
        to_year = self.to_year.value() if self.to_year.value() != 0 else None

        if month_col and year_col and from_year and from_month:
            where_clauses.append(
                f'(CAST("{year_col}" AS INTEGER) > ? OR (CAST("{year_col}" AS INTEGER) = ? AND CAST("{month_col}" AS INTEGER) >= ?))'
            )
            params.extend([from_year, from_year, from_month])
        if month_col and year_col and to_year and to_month:
            where_clauses.append(
                f'(CAST("{year_col}" AS INTEGER) < ? OR (CAST("{year_col}" AS INTEGER) = ? AND CAST("{month_col}" AS INTEGER) <= ?))'
            )
            params.extend([to_year, to_year, to_month])

        filters = [
            (self.standard_columns.get("province"), self.province_input.text().strip()),
            (self.standard_columns.get("exam_center"), self.exam_center_input.text().strip()),
            (self.standard_columns.get("exam_type"), self.exam_type_input.currentText().strip()),
            (self.standard_columns.get("driving_school"), self.driving_school_input.text().strip()),
            (self.standard_columns.get("permit"), self.permit_input.text().strip()),
        ]
        for col, value in filters:
            if col and value:
                where_clauses.append(f'TRIM("{col}") = ?')
                params.append(value.strip())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        group_sql = ""
        if group != "None":
            group_columns = self._group_columns(group)
            group_sql = " GROUP BY " + ", ".join([f'"{c}"' for c in group_columns])

        order_sql = f' ORDER BY "{order_by}" {order_dir}' if order_by else ""

        limit = self.limit_input.value()
        limit_sql = f" LIMIT {limit}" if limit > 0 else ""

        query = f"SELECT {select_sql} FROM exams {where_sql}{group_sql}{order_sql}{limit_sql}"
        return query, params

    def _selected_columns(self) -> List[str]:
        selected = []
        for checkbox in self.column_checks:
            if checkbox.isChecked():
                key = checkbox.property("column_key")
                column = self.standard_columns.get(key)
                if column:
                    selected.append(column)
        if not selected:
            selected = [col for col in self.standard_columns.values() if col]
        if not selected:
            selected = get_table_columns(self.db, "exams")
        return selected

    def _group_columns(self, group_label: str) -> List[str]:
        if group_label == "Year":
            return [c for c in [self.standard_columns.get("year")] if c]
        if group_label == "Month and Year":
            return [c for c in [self.standard_columns.get("year"), self.standard_columns.get("month")] if c]
        if group_label == "Province":
            return [c for c in [self.standard_columns.get("province")] if c]
        if group_label == "Exam center":
            return [c for c in [self.standard_columns.get("exam_center")] if c]
        if group_label == "Driving school":
            return [c for c in [self.standard_columns.get("driving_school")] if c]
        return []

    def _apply_filters(self) -> None:
        query_sql, params = self._build_query()
        query = QSqlQuery(self.db)
        query.prepare(query_sql)
        for param in params:
            query.addBindValue(param)
        query.exec()
        self.model.setQuery(query)

        self.current_columns = []
        self.current_headers = []
        for i in range(self.model.record().count()):
            header = self.model.headerData(i, Qt.Orientation.Horizontal)
            self.current_headers.append(str(header))
            self.current_columns.append(self.model.record().fieldName(i))
        self._apply_header_labels()

        self._render_chart()

    def _render_chart(self) -> None:
        for i in reversed(range(self.chart_layout.count())):
            widget = self.chart_layout.takeAt(i).widget()
            if widget:
                widget.setParent(None)

        if self.group_by.currentText() == "None":
            self.chart_layout.addWidget(QLabel("Group data to see the chart."))
            self.chart_view = None
            return

        data = []
        row_count = self.model.rowCount()
        if row_count == 0:
            self.chart_layout.addWidget(QLabel("No data to display."))
            self.chart_view = None
            return

        label_cols = self.model.record().count() - 1
        for row in range(row_count):
            labels = []
            for col in range(label_cols):
                labels.append(str(self.model.data(self.model.index(row, col))))
            label = " / ".join(labels)
            value = self.model.data(self.model.index(row, label_cols))
            data.append((label, float(value or 0)))

        chart = build_bar_chart(data, "Exam totals")
        self.chart_view = chart
        self.chart_layout.addWidget(chart)

    def _on_sort_changed(self, logical_index: int, order: Qt.SortOrder) -> None:
        if not self.current_columns:
            return
        if logical_index >= len(self.current_columns):
            return
        order_by = self.current_columns[logical_index]
        order_dir = "ASC" if order == Qt.SortOrder.AscendingOrder else "DESC"
        query_sql, params = self._build_query(order_by=order_by, order_dir=order_dir)
        query = QSqlQuery(self.db)
        query.prepare(query_sql)
        for param in params:
            query.addBindValue(param)
        query.exec()
        self.model.setQuery(query)

    def _export_table_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        headers, rows = self._collect_table_data()
        html = render_table_to_html(headers, rows, "Driving exams report")
        export_html_to_pdf(html, path)

    def _export_chart_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        if not self.chart_view:
            QMessageBox.warning(self, "Export chart", "No chart to export.")
            return
        png_base64 = self._chart_as_base64()
        html = render_table_to_html([], [], "Chart", chart_base64=png_base64)
        export_html_to_pdf(html, path)

    def _export_both_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        headers, rows = self._collect_table_data()
        chart_base64 = self._chart_as_base64()
        html = render_table_to_html(headers, rows, "Driving exams report", chart_base64=chart_base64)
        export_html_to_pdf(html, path)

    def _collect_table_data(self) -> Tuple[List[str], List[List[str]]]:
        while self.model.canFetchMore():
            self.model.fetchMore()
            QApplication.processEvents()
        column_count = self.model.columnCount()
        row_count = self.model.rowCount()
        headers = [self.model.headerData(i, Qt.Orientation.Horizontal) for i in range(column_count)]
        rows = []
        print(f"Exporting {row_count} rows and {column_count} columns...")
        for row in range(row_count):
            values = []
            for col in range(column_count):
                values.append(str(self.model.data(self.model.index(row, col))))
            rows.append(values)
            if (row + 1) % 1000 == 0 or row + 1 == row_count:
                print(f"Collected {row + 1}/{row_count} rows for export...")
                QApplication.processEvents()
        return [str(h) for h in headers], rows

    def _apply_header_labels(self) -> None:
        mapping = {
            self.standard_columns.get("year"): "Year",
            self.standard_columns.get("month"): "Month",
            self.standard_columns.get("province"): "Province",
            self.standard_columns.get("exam_center"): "Exam center",
            self.standard_columns.get("exam_type"): "Exam type",
            self.standard_columns.get("driving_school"): "Driving school",
            self.standard_columns.get("permit"): "Permit",
            self.standard_columns.get("num_aptos"): "Num aptos",
            self.standard_columns.get("num_no_aptos"): "Num no aptos",
            "total_exams": "Total exams",
        }
        for col_index in range(self.model.columnCount()):
            field = self.model.record().fieldName(col_index)
            label = mapping.get(field)
            if label:
                self.model.setHeaderData(col_index, Qt.Orientation.Horizontal, label)

    def _refresh_year_month_ranges(self) -> None:
        year_col = self.standard_columns.get("year")
        month_col = self.standard_columns.get("month")
        if not year_col:
            return
        query = QSqlQuery(self.db)
        query.exec(f'SELECT MIN(CAST("{year_col}" AS INTEGER)), MAX(CAST("{year_col}" AS INTEGER)) FROM exams')
        if not query.next():
            return
        min_year = query.value(0)
        max_year = query.value(1)
        if min_year is None or max_year is None:
            return
        self.from_year.setRange(int(min_year), int(max_year))
        self.to_year.setRange(int(min_year), int(max_year))
        self.from_year.setValue(int(min_year))
        self.to_year.setValue(int(max_year))

        if not month_col:
            return
        query = QSqlQuery(self.db)
        query.exec(f'SELECT DISTINCT CAST("{month_col}" AS INTEGER) FROM exams ORDER BY CAST("{month_col}" AS INTEGER)')
        months = [""]
        while query.next():
            value = query.value(0)
            if value is None:
                continue
            month = int(value)
            if 1 <= month <= 12:
                months.append(str(month))
        if len(months) > 1:
            self.from_month.clear()
            self.to_month.clear()
            self.from_month.addItems(months)
            self.to_month.addItems(months)
            self.from_month.setCurrentText(months[1])
            self.to_month.setCurrentText(months[-1])

    def _chart_as_base64(self) -> Optional[str]:
        if not self.chart_view:
            return None
        pixmap = self.chart_view.grab()
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        buffer = QByteArray()
        qbuffer = QBuffer(buffer)
        qbuffer.open(QBuffer.OpenModeFlag.WriteOnly)
        image.save(qbuffer, "PNG")
        return base64.b64encode(bytes(buffer)).decode("ascii")
