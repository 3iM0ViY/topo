import sys
import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib.cm import ScalarMappable
from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.collections import LineCollection
from PyQt6.QtWidgets import *
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
import itertools
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import OrderedDict

import maths # Допоміжний файл з математикою 
import math # пітонівська бібліотека
from scipy.interpolate import make_interp_spline

import utm
import mgrs

from pyproj import Geod
from shapely.geometry import Polygon, LineString, box
from shapely.ops import orient

# from pprint import pprint

# .py -> .exe         --noconsole
# pyinstaller --onefile --hidden-import maths --hidden-import mgrs --add-binary venv\Lib\site-packages\libmgrs.cp312-win_amd64.pyd:. --icon=icon.ico main.py

MAPS_FOLDER = "maps/"
TEMPLATES_FOLDER = "templates/"
SAVE_COLUMNS = 5
# Налаштування шаблонів за змовчуавнням
DEFAULT_TAB_SETTINGS = {
    "Частота (GHz)": (3, 0.03, 6, 0.01), 
    "Радіус (m)": (20000, 150, 300000, 50), 
    "Кут (°)": (100, 10, 360, 10), 
    "Крок (°)": (1, 1, 15, 1), 
    "Азимут (°)": (0, 0, 360, 1), 
    "Висота передавача (m)": (500, 0, 5000, 10), 
    "Висота приймача (m)": (300, 0, 5000, 10), 
    "Ймовірність (%)": (80, 1, 99, 1), 
    "Динамічний крок": (60, 50, 500, 10), 
    "Потужність передавача (W)": (50, 0, 300, 1), 
    "Коеф. підсилення антени (dBi)": (5, 0, 20, 0.1),
    "Втрати в дуплексному фільтрі": (1.5, 0.1, 20, 0.1),
    "Втрати в фідері передавального тракту (dB)": (4, 0, 20, 0.1),
    "Додаткові втрати в передавальному тракті": (2, 0, 20, 0.1),
    "Коеф. підсилення приймальної антени (dBi)": (2, 0, 20, 0.1),
    "Втрати в фідері приймального тракту (dB)": (0.5, 0, 20, 0.1),
    "Додаткові втрати в приймальному тракті": (1, 0, 20, 0.1),
    "Чутливість приймача (dbW)": (-110, -300, 100, 1),
}

def latlon_to_utm(lat, lon):
    """
    Конвертація картографічної проєкції в UTM

    :param lat, lon: Координати точки в формі широта, довгота.
   
    :return: Координати UTM, приклад:
        (array([395201.31038113, 45.59]), array([56.24, 54276.20]), 32, 'U')
    """
    return utm.from_latlon(lat, lon)

def latlon_to_mgrs(lat, lon):
    """
    Конвертація картографічної проєкції в MGRS

    :param lat, lon: Координати точки в формі широта, довгота.
   
    :return: Координати MGRS, приклад:
        36U UA 2424 9160
    """
    m = mgrs.MGRS()
    return m.toMGRS(lat, lon)

class Ui_MainWindow(object):
    """
    GUI програми та основний потік
    """
    def __init__(self):
        # Набір певних зміних, для подальшого доступу
        self.tabs = []
        self.map_area = None
        self.current_save_index = 0

    def setupUi(self, MainWindow):
        """
        Створення основних областей GUI та їх взаємозв'язок
        """
        MainWindow.setObjectName("Топографічна Карта")
        MainWindow.resize(1170,810)

        MainWindow.setWindowIcon(QtGui.QIcon("icon.ico"))

        self.statusbar = QStatusBar(parent=MainWindow)
        MainWindow.setStatusBar(self.statusbar)
        
        self.centralwidget = QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # основний шаблон
        self.main_layout = QVBoxLayout(self.centralwidget)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        # Горизонтальний роздільник для розділення лівої панелі та області мапи
        self.splitter = QSplitter(Qt.Orientation.Horizontal, parent=self.centralwidget)
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical, parent=self.centralwidget)
        
        # Ліва панель
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)

        self.map_selector_label = QLabel("Виберіть карту:", parent=self.left_panel)
        self.left_layout.addWidget(self.map_selector_label)

        self.map_selector = QComboBox(parent=self.left_panel)
        self.map_selector.setObjectName("map_selector")
        self.left_layout.addWidget(self.map_selector)

        # Можливість створенн власних налагтувань пристроїв
        self.add_tab_button = QPushButton(text="Зберегти як новий пресет", parent=self.left_panel)
        self.add_tab_button.clicked.connect(self.ask_tab_creation) # Створення нової вкладки
        self.left_layout.addWidget(self.add_tab_button)

        self.preset_name_label = QLabel("Введіть назву нового пресету:", parent=self.left_panel)
        self.left_layout.addWidget(self.preset_name_label)

        self.preset_name_input = QLineEdit(parent=self.left_panel)  # Кастомне ім'я
        self.left_layout.addWidget(self.preset_name_input) 

        self.confirm_button = QPushButton(text="Підтвердити", parent=self.left_panel)
        self.confirm_button.clicked.connect(self.create_custom_tab)  # Створення пресету
        self.left_layout.addWidget(self.confirm_button)

        self.preset_name_label.setVisible(False)
        self.preset_name_input.setVisible(False)
        self.confirm_button.setVisible(False)

        self.tabWidget = QTabWidget(parent=self.left_panel)
        self.tabWidget.setObjectName("tabWidget")

        # Вкладки
        self.tabManager = TabManager(self.tabWidget, self) # батько для наслідування області мапи
        # Шаблонні налаштування перших пари пресетів
        self.create_tabs_from_templates(TEMPLATES_FOLDER, self.tabManager)

        self.left_layout.addWidget(self.tabWidget)
        self.splitter.addWidget(self.left_panel)

        # Область мапи
        self.map_area = None

        # Низ
        self.bottom_panel = QWidget()
        self.bottom_layout = QHBoxLayout(self.bottom_panel)
        self.vertical_splitter.addWidget(self.bottom_panel)

        # Ініціалізація сітки
        self.gridLayout = QGridLayout()

        # Списки для збереження елементів
        self.groupBoxes = []
        self.closeButtons = []

        for i in range(SAVE_COLUMNS):  # автоматизація
            # Створення основного віджета групи
            groupWidget = QWidget()
            groupLayout = QVBoxLayout(groupWidget)
            
            # Додавання міток у групу
            for j in range(len(DEFAULT_TAB_SETTINGS) + 2):  # кількість виведених параметрів
                label = QLabel(f"Label {i+1}.{j+1}", parent=groupWidget)
                groupLayout.addWidget(label)

            # Створення області прокручування для групи
            scroll_area = QScrollArea(parent=self.centralwidget)
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(groupWidget)

            # Додавання області прокручування у `QGroupBox`
            groupBox = QGroupBox(f"Збереження {i+1}", parent=self.centralwidget)
            groupBoxLayout = QVBoxLayout(groupBox)
            groupBoxLayout.addWidget(scroll_area)

            # Створення кнопки закриття
            pushButton = QPushButton("❌", parent=self.centralwidget)
            pushButton.clicked.connect(lambda _, idx=i: self.delete_location_data(idx))

            # Додавання `QGroupBox` і кнопки в сітковий макет
            self.gridLayout.addWidget(groupBox, 0, i)
            self.gridLayout.addWidget(pushButton, 1, i)

            # Збереження посилань
            self.groupBoxes.append(groupBox)
            self.closeButtons.append(pushButton)

        # Додавання макету в основний макет
        self.bottom_layout.addLayout(self.gridLayout)
        self.main_layout.addWidget(self.splitter)
        self.main_layout.addWidget(self.vertical_splitter)
        # self.main_layout.addLayout(self.bottom_layout)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        # Динамічне підвантаження мап
        self.map_selector.currentTextChanged.connect(self.update_map_area)
        self.populate_map_selector()

    def retranslateUi(self, MainWindow): 
        # можна робити дк-факто* заміну тексту // *де-юре лишається старе значення
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "РЕЗташування"))

    def populate_map_selector(self):
        """
        Заповнення QComboBox файлами .asc з теки /maps/.
        """
        maps_folder = os.path.join(os.getcwd(), MAPS_FOLDER)
        if not os.path.exists(maps_folder):
            os.makedirs(maps_folder)

        asc_files = [f for f in os.listdir(maps_folder) if f.endswith(".asc")]
        if asc_files:
            self.map_selector.addItems(asc_files)
        else:
            self.map_selector.addItem("No maps found")

    def update_map_area(self, selected_map):
        """
        Надсилання вибраного файлу мапи до відповідного класу для опрацювання.
        """
        if selected_map and selected_map != "No maps found":
            maps_folder = os.path.join(os.getcwd(), "maps")
            map_path = os.path.join(maps_folder, selected_map)

            if os.path.exists(map_path):
                # Ініціалізація MapArea вибраним файлом
                if self.map_area:
                    self.splitter.widget(1).deleteLater()
                self.map_area = MapArea(self, file_path=map_path, tabWidget=self.tabWidget, tabManager=self.tabManager)
                self.splitter.addWidget(self.map_area)
                print(f"Мапу промальовано: {map_path}")
                self.statusbar.showMessage(f"Мапу промальовано: {map_path}")


    def create_tabs_from_templates(self, folder_path, tab_manager):
        """
        Створення вкладок у диспетчері вкладок на основі шаблонних файлів.

        :param folder_path: Шлях до папки, що містить файли шаблонів (з розширенням .txt).
        :param tab_manager: Об'єкт диспетчера вкладок, у який додаються нові вкладки.
        """
        for filename in os.listdir(folder_path):
            if filename.endswith(".txt"):
                file_path = os.path.join(folder_path, filename)
                name, full_name, settings = self.parse_template_file(file_path)
                if name and full_name and settings:
                    tab_manager.create_tab(name, full_name, settings)

    def parse_template_file(self, file_path):
        """
        Розбір файлу шаблону для отримання назви вкладки, повної назви та налаштувань.

        :param file_path: Шлях до файлу шаблону для аналізу.
        
        :return: Кортеж, що складається з:
            - name (str): Назва вкладки.
            - full_name (str): Повна назва вкладки.
            - settings (OrderedDict): Налаштування, де ключі — імена параметрів, а значення — кортежі з чотирьох чисел.
            Якщо розбір не вдається, повертається (None, None, None).
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                lines = file.readlines()

            if len(lines) < 2:
                raise ValueError(f"File {file_path} is missing required header lines.")

            # Отримання назви та повної назви
            name = lines[0].strip().split(":")[1].strip()
            full_name = lines[1].strip().split(":")[1].strip()

            # Отримання налаштувань
            settings = OrderedDict()
            for line in lines[2:]:
                if line.strip():
                    parts = line.strip().split(":")
                    if len(parts) != 2:
                        raise ValueError(f"Invalid parameter line in {file_path}: {line}")
                    
                    param_name = parts[0].strip()
                    values = list(map(float, parts[1].split(",")))
                    if len(values) != 4:
                        raise ValueError(f"Invalid parameter values in {file_path}: {line}")
                    
                    settings[param_name] = tuple(values)

            return name, full_name, settings
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None, None, None

    def ask_tab_creation(self):
        """
        Дозволяє створити нову вкладку за відображеними полями
        """
        self.preset_name_label.setVisible(True)
        self.preset_name_input.setVisible(True)
        self.confirm_button.setVisible(True)

    def create_custom_tab(self):
        """
        Створення нової вкладки з користувацьким пресетом.
        """
        preset_name = self.preset_name_input.text()  # Користувацьке ім'я
        if preset_name:
            current_tab_index = self.tabWidget.currentIndex()  # обрана вкладка
            current_tab_name = self.tabWidget.tabText(current_tab_index)  # її ім'я
            current_tab_settings = self.tabManager.get_tab_settings(current_tab_name)  # налаштування

            new_tab_settings = {}

            # Обрані налаштування об'єднуються з максимальними значеннями та кроком
            for key, value in current_tab_settings.get('sliders', {}).items():
                if key in DEFAULT_TAB_SETTINGS:
                    new_tab_settings[key] = (value, *DEFAULT_TAB_SETTINGS[key][1:])

            # Створення вкрадки
            self.tabManager.create_tab(preset_name, preset_name, new_tab_settings)

            # Збереження шаблону в .txt 
            preset_file_path = os.path.join("templates", f"{preset_name}.txt")
            try:
                with open(preset_file_path, "w", encoding="utf-8") as preset_file:
                    preset_file.write(f"Заголовок: {preset_name}\n")
                    preset_file.write(f"Назва шаблону: {preset_name}\n")

                    # Параметри та їх значення
                    for param_name, values in new_tab_settings.items():
                        values_str = ", ".join(map(str, values))
                        preset_file.write(f"{param_name}: {values_str}\n")

                print(f"Пресет '{preset_name}' успішно збережено в файл {preset_file_path}")
                self.statusbar.showMessage(f"Пресет '{preset_name}' успішно збережено в файл {preset_file_path}")
            except Exception as e:
                print(f"Помилка при збереженні пресету: {e}")
                self.statusbar.showMessage(f"Помилка при збереженні пресету: {e}")

        else:
            print("Будь ласка, введіть назву пресету.")
            self.statusbar.showMessage(f"Будь ласка, введіть назву пресету.")

        # Приховати інпути
        self.preset_name_label.setVisible(False)
        self.preset_name_input.setVisible(False)
        self.confirm_button.setVisible(False)

    def save_location_data(self, tab):
        """
        Збереження результатів точки для подальшого порівняння
        :param tab: Вкладка параметри котрої описують цю точку.
        """

        # Доступ до налаштувань у вкладці
        tab_settings = self.tabManager.get_tab_settings(tab)
        print(tab_settings)
        last_point = self.map_area.get_last_point()

        # Вивід збережень (залежить від нагенерованої кількості в автоматизації)
        labels_text = []

        t_point = [coord for coord in last_point.get_xydata()[0]] #координати обраної точки
        lon, lat = t_point[0], t_point[1] #self.map_area.get_coordinates(t_point[0], t_point[1], self.map_area.header, self.map_area.downsample_factor)
        labels_text.append(f"Розташування: {lon:.5f}, {lat:.5f}")

        # Інформація про обчиленну площу покриття
        coverage_area = self.map_area.coverage_area
        labels_text.append(f"Площа покриття: {coverage_area:.2f} km²")

        for key, value in tab_settings['sliders'].items():
            labels_text.append(f"{key}: {value}")
        # labels_text.append(f"Тип місцевості: {tab_settings['comboBox1']}")
        # labels_text.append(f"Зона: {tab_settings['comboBox2']}")
        # labels_text.append(f"Checkbox: {'Так' if tab_settings['checkBox'] else 'Ні'}")

        # Перевірка, чи дані вже існують у будь-якому groupBox
        for groupBox in self.groupBoxes:
            boxes_texts = []
            for label in groupBox.findChildren(QLabel):
                boxes_texts.append(label.text())

            if len(set(labels_text) & set(boxes_texts)) == len(labels_text):
                # print("Дані вже збережені в іншій групі!")
                self.statusbar.showMessage("Дані вже збережені в іншій групі!")
                return  # Вихід, якщо дані дублюються

        # Оновлення поточного groupBox про успішне збереження
        if self.current_save_index < len(self.groupBoxes):
            while self.check_labels_not_default(self.current_save_index):
                self.current_save_index += 1

            groupBox = self.groupBoxes[self.current_save_index]
            labels = groupBox.findChildren(QLabel)

            for i, label in enumerate(labels):
                if i < len(labels_text):
                    label.setText(labels_text[i])
                else:
                    label.setText("") # Очистка зайвого

            # print(f"Дані збережено в {groupBox.title()}!")
            self.statusbar.showMessage(f"Дані збережено в {groupBox.title()}!")

            self.map_area.collections[1][self.current_save_index] = self.map_area.last_collection # Збереження результатів обчислень пучка
            self.map_area.collections[0][self.current_save_index] = self.map_area.last_point # Збереженн графічної крапки
            self.map_area.last_collections_length += 1
            self.current_save_index += 1  # Для подальших збережень
        else:
            self.statusbar.showMessage("Усі групи збережень вже зайняті!")

    def delete_location_data(self, idx):
        """
        Видалення та очищення слоту збережень
        """
        if self.check_labels_not_default(idx):
            selected_groupBox = self.groupBoxes[idx]
            
            # Отримання `QScrollArea` з `QGroupBox`
            scroll_area = selected_groupBox.findChild(QScrollArea)
            if not scroll_area:
                self.statusbar.showMessage("Помилка: Не знайдено область прокрутки!")
                return
            
            # Отримання `QWidget` з мітками
            content_widget = scroll_area.widget()
            if not content_widget:
                self.statusbar.showMessage("Помилка: Не знайдено вміст області прокрутки!")
                return

            # Пошук всіх міток у внутрішньому віджеті
            labels = content_widget.findChildren(QLabel)
            for i, label in enumerate(labels):
                label.setText(f"Label {idx+1}.{i+1}")  # Скидання тексту міток до стандартного

            self.statusbar.showMessage(f"Дані видалено з {selected_groupBox.title()}!")
            self.current_save_index = idx


            # Видалення обраних збрежених було рендерів
            self.map_area.collections[1][self.current_save_index].remove()
            self.map_area.collections[1][self.current_save_index] = None
            if self.map_area.collections[0][self.current_save_index] != self.map_area.last_point:
                self.map_area.collections[0][self.current_save_index].remove()
            self.map_area.collections[0][self.current_save_index] = None
            self.map_area.last_collections_length -= 1

    def check_labels_not_default(self, groupBoxIndex):
        """
        Перевірка, чи всі мітки в `QGroupBox` мають стандартний текст.
        """
        default_pattern = f"Label {groupBoxIndex + 1}."
        selected_groupBox = self.groupBoxes[groupBoxIndex]

        # Отримання `QScrollArea` з `QGroupBox`
        scroll_area = selected_groupBox.findChild(QScrollArea)
        if not scroll_area:
            return False

        # Отримання `QWidget` з мітками
        content_widget = scroll_area.widget()
        if not content_widget:
            return False

        # Переміщення всіх міток у внутрішньому віджеті
        for child in content_widget.findChildren(QLabel):
            if not child.text().startswith(default_pattern):
                return True

        return False


class MapArea(QWidget):
    """
    Рендер топографії та обчислень пов'язаних із нею
    """
    def __init__(self, parent, file_path, tabWidget=None, tabManager=None):
        super().__init__()

        # Набір певних зміних, для подальшого доступу
        self.parent = parent
        self.tabWidget = tabWidget
        self.tabManager = tabManager
        self.coverage_area = 0 # Приблизна площа ділянок, де сигнал слабне
        self.collections = [[None] * SAVE_COLUMNS, [None] * SAVE_COLUMNS] # Список пучків обрахованих відрізків
        self.last_collections_length = 0
        self.last_collection = None

        # Читання мапи
        self.file_path = file_path
        self.data, self.header = self.load_asc(self.file_path)

        # Зменшення вибірки
        self.downsample_factor = 10 # Відрегулюйте для продуктивності
        self.data_downsampled = self.downsample_data(self.data, self.downsample_factor)

        # Matplotlib Figure
        self.figure, self.ax = plt.subplots()
        self.figure.patch.set_facecolor('#1e1e1e') # темна тема
        self.ax.set_facecolor('#1e1e1e')
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.canvas.mpl_connect('motion_notify_event', self.on_hover)

        # Plot
        self.plot_asc(self.data_downsampled, self.downsample_factor)

        # Макет
        layout = QVBoxLayout()

        self.pushButton_2 = QPushButton("Обчислити", self)
        self.pushButton_2.clicked.connect(lambda: self.do_signal(self.header, self.data)) # Змоделювати пристрій

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.pushButton_2)
        self.setLayout(layout)

        # Клік
        self.last_point = None # Для зберігання посилання на останню точку
        self.canvas.mpl_connect('button_press_event', self.onclick)

    def load_asc(self, file_path):
        """
        Завантаження .asc файлу у numpy-масив.

        :param file_path: Адреса до файлу (за змовчування всредині maps/).

        :return data: Мапа рельєфу.
        :return header: Інформація про заголовок файлу рельєфу.
        """
        header = {}
        with open(file_path, 'r') as file:
            for _ in range(6):
                line = file.readline()
                key, value = line.split()
                header[key] = float(value) if '.' in value else int(value)

            data = np.loadtxt(file, dtype=float)

        return data, header

    def downsample_data(self, data, factor):
        """
        Зменшення вибірки за заданим фактором
        """
        return data[::factor, ::factor]

    def on_hover(self, event):
        """
        Відображення широти, довготи, та MGRS координат при наведенні.

        :param event: Опис взаємодії користувача з графіком matplotlib.
        """
        if event.inaxes == self.ax and event.xdata is not None and event.ydata is not None:
            lon, lat = event.xdata, event.ydata # координати ділянки

            # Отримати індекси матриці з координат 
            x_index = int((lon - self.header['xllcorner']) / self.header['cellsize'])
            y_index = int((self.header['yllcorner'] - lat) / self.header['cellsize'])

            # Висота поверхні в точці наведення
            surface_height = self.data[y_index, x_index]

            # Висота передавача з налаштувань
            current_tab_index = self.tabWidget.currentIndex()
            current_tab_name = self.tabWidget.tabText(current_tab_index)
            transmitter_height_settings = self.tabManager.get_tab_settings(current_tab_name)["sliders"]["Висота передавача (m)"]
            transmitter_height = surface_height + transmitter_height_settings

            # Статус бар
            if self.parent.statusbar:
                mgrs = latlon_to_mgrs(lat, lon)  # Конвертація в MGRS
                self.parent.statusbar.showMessage(
                    f"Довгота: {lon:.5f}, Паралель: {lat:.5f} || MGRS: {mgrs} || "
                    f"Висота поверхні: {surface_height:.2f} м || "
                    f"Висота передавача: {transmitter_height:.2f} м"
                )

    def plot_asc(self, data, downsample_factor):
        """
        Відображення мапи з розрізненням рельєфу та моря.

        :param data: Дані про висоти карти.
        :param downsample_factor: Коефіцієнт дискретизації координат.
        """
        self.ax.clear()

        # Коригування роздільної здатності на основі коефіцієнта
        cellsize_adjusted = self.header['cellsize'] * downsample_factor
        extent = [
            self.header['xllcorner'], 
            self.header['xllcorner'] + cellsize_adjusted * data.shape[1], 
            self.header['yllcorner'], 
            self.header['yllcorner'] + cellsize_adjusted * data.shape[0],
        ]

        # Маскування морських ділянок (припускаємо, що рівень моря ≤ 0)
        sea_mask = data <= 0
        terrain_data = np.ma.masked_where(sea_mask, data)

        terrain_cmap = plt.cm.terrain
        terrain_colors = terrain_cmap(np.linspace(0.22, 1, 256))  # Remove blue (lower 25% of cmap)
        custom_cmap = LinearSegmentedColormap.from_list("custom_terrain", terrain_colors)

        terrain_norm = Normalize(vmin=max(data.min() *2, 1), vmax=data.max() / 2)

        # Рельєф місцевості
        terrain = self.ax.imshow(
            terrain_data, 
            cmap=custom_cmap,
            norm=terrain_norm,
            origin="upper", 
            extent=extent
        )

        # Побудова моря в білому кольорі
        sea = self.ax.imshow(
            np.where(sea_mask, 1, np.nan),  # Бінарне море
            cmap="plasma",  # Білий
            origin="upper", 
            extent=extent, 
            alpha=1
        )

        # Додавання colorbar-у для рельєфу
        cb = self.figure.colorbar(terrain, ax=self.ax, orientation='vertical', label='Elevation (m)')
        
        # Темна тема
        cb.ax.tick_params(labelcolor="white")
        cb.set_label(label='Висота (m)', color="white")
        self.ax.set_title("Карта", color="white")
        self.ax.tick_params(labelcolor='white')

        self.canvas.draw()

    def onclick(self, event):
        """
        Натискання колесиком по мапі ставить точку випромінювача

        :param event: Обробник взаємодії з графіком = натиск кнопки.
        """
        # event.button == 1 - ЛКМ, 2 - колесико, 3 - ПКМ
        if event.button == 2 and event.xdata is not None and event.ydata is not None:
            print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
              ('double' if event.dblclick else 'single', event.button,
               event.x, event.y, event.xdata, event.ydata))
            self.parent.statusbar.showMessage(f"Обрано точку для обчислень: xdata={event.xdata}, ydata={event.ydata}")

            # Видаляє попередню точку, якщо вона існує
            if self.last_point is not None and self.last_point not in self.collections[0]:
                self.last_point.remove()
                self.last_point = None

            # Динамічне отримання назви поточної вкладки
            current_tab_index = self.tabWidget.currentIndex()
            current_tab_name = self.tabWidget.tabText(current_tab_index)
            color = self.tabManager.get_color(current_tab_name)
            self.last_point = None
            self.last_point = self.ax.plot(event.xdata, event.ydata, 'o', color=color, markersize=5)[0] #точечна точка

            self.canvas.draw()

    def get_last_point(self):
        """
        Повертає останню вибрану точку на мапі
        """
        return self.last_point

    def do_signal(self, header, height_data):
        """
        Відгук на натискання кнопки, що встановлює порядок 
        обчислення сигналу та відображення результатів на мапі.

        :param header: Інформація про заголовок файлу рельєфу.
        :param height_data: Дані з рельєфом місцевості.
        """
        if self.last_point is not None:
            t_point = [coord for coord in self.last_point.get_xydata()[0]] #координати обраної точки
            lon_start, lat_start = t_point[0], t_point[1] # self.get_coordinates(t_point[0], t_point[1], header, self.downsample_factor)
            print(f"Ірл широта, довгота: {lat_start}, {lon_start}")

            print("Думаю, шурупаю...")
            self.parent.statusbar.showMessage(f"Відбувається обчислення...")
            
            # Розрахунок покриття
            coverage_results = self.calculate_coverage(lon_start, lat_start, height_data, header)
            
            print("Покриття знайдено, малюю...")
            self.parent.statusbar.showMessage(f"Покриття знайдено, відбувається рендер...")

            # Візуалізація покриття
            self.update_map_with_coverage(coverage_results, lon_start, lat_start)

            self.coverage_area = self.calculate_coverage_area(coverage_results, lon_start, lat_start)
            print(f"Площа покриття: {self.coverage_area} km²")
            self.parent.statusbar.showMessage(f"Площа покриття: {self.coverage_area} km²")
            
            ####### Original maths ####### 
            # Видалений сегмент коду, збережений у нотатках, що обчислював 
            # втрати сигналу між двома вказаними точками

    def update_map_with_coverage(self, coverage_results, lon_start, lat_start):
        """
        Візуалізація покриття сигналу у вигляді градієнтних ліній, що виходять з обраної точки.
        
        :param coverage_results (list of dict): Дані про присутність покриття для кожного азимута,
            отримані в результаті функції calculate_coverage.
        :param lon_start, lat_start: Координати центру пучка.
        """

        # pprint(coverage_results)

        # Очищує попередній пучок, якщо користувач його не зберіг
        if self.last_collection and self.last_collection not in self.collections[1]:
            self.last_collection.remove()
            self.canvas.draw()

        cmap = plt.cm.Reds  # Вибір колірної схеми
        cmap2 = plt.cm.Greens

        # Підготовка для пучка LineCollection
        segments = []  # Список відрізків ліній, координати: [(x1, y1), (x2, y2)]
        colors = []  # Відповідний колір для кожного відрізка лінії

        for coverage_result in coverage_results:
            lon1, lat1 = lon_start, lat_start
            i = 0
            while i < len(coverage_result[0]):
                lon2, lat2 = coverage_result[0][i], coverage_result[1][i]
                p_rec_real = coverage_result[2][i]
                coverage = coverage_result[3][i]

                if coverage != np.True_:
                    # Збереження відрізка
                    segments.append([(lon1, lat1), (lon2, lat2)])

                    # Нормалізація всіх значень втрат для узгодженого відображення кольору та прозорості
                    # normalized_loss = norm(losses_db[i])

                    # Визначення кольору для поточного сегмента
                    loss_color = abs(p_rec_real) / 100
                    color = cmap(loss_color)
                    # Динамічний ступінь прозорості
                    alpha = np.clip(0.1 + (abs(p_rec_real) / 100) * 0.3, 0.1, 0.4)  # Scale the alpha to [0.1, 0.4]
                    # alpha = 0.1 + alpha * (0.4)

                    colors.append((1, 0, 0, alpha))
                else:
                    segments.append([(lon1, lat1), (lon2, lat2)])

                    # Нормалізація всіх значень втрат для узгодженого відображення кольору та прозорості
                    # normalized_loss = norm(losses_db[i])

                    # Визначення кольору для поточного сегмента
                    loss_color = np.clip(0.25 + (abs(p_rec_real) / 100) * 0.3, 0.1, 0.4)
                    color = cmap2(loss_color)
                    # Динамічний ступінь прозорості
                    # alpha = np.clip(loss_color, 0, 1) 
                    alpha = 0.1

                    colors.append((0, 1, 1, loss_color))

                # Оновлення початкової точки для наступного відрізка
                lon1, lat1 = lon2, lat2
                i += 1

        # Пучор відрізків
        line_collection = LineCollection(segments, colors=colors, linewidths=1)
        collection = self.ax.add_collection(line_collection)
        self.last_collection = collection

        # Add a colorbar using a ScalarMappable object
        # sm = ScalarMappable(cmap=cmap, norm=norm)
        # sm.set_array([])  # Dummy array for ScalarMappable
        # cb = self.figure.colorbar(sm, ax=self.ax, orientation='vertical', label='Сила втрат (dB)')
        # cb.ax.tick_params(labelcolor="white")
        # cb.set_label(label='Сила втрат (dB)', color="white")

        # Промальовка
        self.canvas.draw()

    def calculate_coverage(self, lon_start, lat_start, height_data, header):
        """
        Розрахунок зони покриття передавача. Для математичних розрахунків використовуються 
        параметри, що обираються користувачем та підгружаються з інтерфейсу напряму.

        :param lon_start, lat_start: Розташування передавача.
        :param height_data: масив даних з рельєфом місцевості.
        :param header: Інформація про заголовок файлу рельєфу.

        :return: Дані про втрату сигналу та присутність покриття для кожного азимута.
            Приклад структури: 
                [
                    [lons], [lats], [losses_db], [coverages (bool)]},
                    [lons], [lats], [losses_db], [coverages (bool)]},
                    ...
                ]
        """
        # Динамічне отримання назви поточної вкладки
        current_tab_index = self.tabWidget.currentIndex()
        current_tab_name = self.tabWidget.tabText(current_tab_index)

        # Параметри
        settings = self.tabManager.get_tab_settings(current_tab_name)["sliders"]
        step_azimuth = int(settings["Крок (°)"])            # Крок обчислень в межах сегмента (у градусах)
        range_start = int(settings["Азимут (°)"])           # Початковий азимут сегмента (у градусах)
        range_end = range_start + int(settings["Кут (°)"])  # Автоматично визначений крайній кут сегмента
        
        # Змінна результатів
        azimuths = list(range(range_start, range_end, step_azimuth))
        coverage_grid = []

        ### Паралельний розрахунок для кожного азимута ###
        # Використання ThreadPoolExecutor або ProcessPoolExecutor для паралельного обчислення
        # with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        #     futures = {
        #         executor.submit(
        #             self.maths_for_line, lon_start, lat_start, height_data, header, azimuth, settings
        #         ) for azimuth in azimuths
        #     }
            
        #     for future in futures:
        #         result = future.result()
        #         if result:  # Пропуск None
        #             # print(result)
        #             coverage_grid.append(result)
        #             # coverage_grid.append({"azimuth": azimuth, "distances": distances, "losses_db": losses_output})

        # print(coverage_grid)

        ### Послідовний розрахунок для кожного азимута ###
        for azimuth in azimuths:
            result = self.maths_for_line(lon_start, lat_start, height_data, header, azimuth, settings)
            if result:  # Пропуск None
                coverage_grid.append(result)

        return coverage_grid

    def maths_for_line(self, lon_start, lat_start, height_data, header, azimuth, settings):
        """Математика втрат на відрізку"""

        # Параметри
        freq_mhz = settings["Частота (GHz)"]            # Частота в ГГц
        lambda_wave = 3e8 / (freq_mhz * 1e6)            # Довжина хвилі в метрах
        tx_height = settings["Висота передавача (m)"]   # Висота передавача (у метрах)
        rx_height = settings["Висота приймача (m)"]     # Висота приймача (у метрах)
        q_percent = settings["Ймовірність (%)"]         # Відсоток імовірності ціле число від 1 до 99
        wa = 4000                                       # Роздільна здатність у метрах/Підібрано, щоб sigma_L = 5,5 дБ
        max_distance_m = settings["Радіус (m)"]         # Радіус кола/сегмента (у метрах)
        step_azimuth = int(settings["Крок (°)"])        # Крок обчислень в межах сегмента (у градусах)
        range_start = int(settings["Азимут (°)"])       # Початковий азимут сегмента (у градусах)
        range_end = range_start + int(settings["Кут (°)"]) # Автоматично визначений крайній кут сегмента
        points_step = settings["Динамічний крок"]       # Число, що регулює кількість сегментів обчислень 
                                                        # (більше число <=> більша оптимізація <=> менша точність)
        P_trm = settings["Потужність передавача (W)"]                       # Потужність передавача (Вт)
        G_trm = settings["Коеф. підсилення антени (dBi)"]              # Посилення антени передавача (дБi)
        L_dp = settings["Втрати в дуплексному фільтрі"]                     # Втрати в дуплексному фільтри
        L_f_trm = settings["Втрати в фідері передавального тракту (dB)"]    # Втрати в фідері передавального тракту (дБ)
        L_dop_trm = settings["Додаткові втрати в передавальному тракті"]    # Додаткові втрати в передавальному тракті (дБ)
        G_rec = settings["Коеф. підсилення приймальної антени (dBi)"]  # Коефіцієнт підсилення приймальної антени (дБi)
        L_f_rec = settings["Втрати в фідері приймального тракту (dB)"]      # Втрати фідера приймача (дБ)
        L_dop_rec = settings["Додаткові втрати в приймальному тракті"]      # Втрати через доплер приймача (дБ)
        P_rec = settings["Чутливість приймача (dbW)"]                       # Порогове значення добиття (дБВт)

        # Кінець відрізка для кожного обчислювального азимута
        endpoint = self.coordinates_away_from_centre_with_radius_and_azimuth(lat_start, lon_start, max_distance_m, azimuth)
        
        lat_end = endpoint[0]
        lon_end = endpoint[1]

        # print(f"Кінцева широта, довгота: {lat_end}, {lon_end}")

        # Перевірка та коригування координат відповідно до меж карти
        cellsize_adjusted = header['cellsize'] * self.downsample_factor
        x_min = header['xllcorner']
        x_max = header['xllcorner'] + header['cellsize'] * self.data.shape[1]
        y_min = header['yllcorner']
        y_max = header['yllcorner'] + header['cellsize'] * self.data.shape[0]

        if not (x_min <= lon_end <= x_max and y_min <= lat_end <= y_max):
            # Коригування кінцевої точки на межі карти
            # print("We're out!")
            lon_end, lat_end = self.adjust_to_map_boundary(lat_start, lon_start, lon_end, lat_end, )
            print(f"Змінено! Кінцева широта, довгота: {lat_end}, {lon_end}")

        # Отримання висоти місцевості в початковій та кінцевій точках
        startpoint_height = maths.get_height_for_coordinates(lon_start, lat_start, height_data, header)
        endpoint_height = maths.get_height_for_coordinates(lon_end, lat_end, height_data, header)

        # Розрахунок реальної відстані між двома точками за допомогою формули Хаверсінуса
        d_total = maths.haversine_distance(lon_start, lat_start, lon_end, lat_end)

        # Кількість точок уздовж маршруту (дистанція буде автоматично змінюватися залежно від довжини маршруту)
        num_points = int(d_total/points_step)

        # Генерація точок за маршрутом
        distances = np.linspace(0, d_total, num_points)
        lons = np.linspace(lon_start, lon_end, num_points)
        lats = np.linspace(lat_start, lat_end, num_points)

        terrain_heights = np.array([
            maths.get_height_for_coordinates(lon, lat, height_data, header) for lon, lat in zip(lons, lats)
        ])

        # Згладжування профілю рельєфу
        spl = make_interp_spline(distances, terrain_heights, k=3)
        smooth_distances = np.linspace(distances.min(), distances.max(), num_points)
        smooth_terrain_heights = spl(smooth_distances)

        # Генерація точок для більш гладкого графіка
        smooth_graph_points = num_points * 10  # Збільшуємо кількість точок тільки для графіка
        smooth_graph_distances = np.linspace(distances.min(), distances.max(), smooth_graph_points)
        smooth_graph_terrain_heights = spl(smooth_graph_distances)

        # Обчислення лінії LOS з урахуванням висот антен
        smooth_los_heights = maths.calculate_los_with_antenna(
            smooth_graph_distances,
            smooth_graph_terrain_heights,
            startpoint_height + tx_height,
            endpoint_height + rx_height
        )

        # Розрахунок сумарних втрат
        total_losses_linear, total_losses_db = maths.calculate_total_losses(smooth_distances, 
            smooth_terrain_heights, smooth_los_heights, d_total, lambda_wave)

        # Виведення сумарних втрат
        # print(f"\nЗагальні втрати дифракції (лінійні): {total_losses_linear:.2f}")
        # print(f"Загальні втрати дифракції (дБ): {total_losses_db:.2f}")

        distance_km = d_total  # Відстань у км
        total_loss_lr = maths.longley_rice_fixed_with_propob_loc(freq_mhz, distance_km, q_percent, wa, lambda_wave)
        total_loss = total_loss_lr + total_losses_db
        # print(f"Final Total Loss (Longley-Rice, propob_loc, Difr): {total_loss:.2f} dB")

        # Виведення таблиці з результатами
        print("\nТочка    Відстань (м)    Висота рельєфу (м)  Висота LOS (м)  Радіус Френеля (м)      Втрати (м)      Втрати (дБ)")

        losses_output = []

        for i in range(0, len(smooth_distances), 2):  # Виводимо для всіх точок
            losses_at_i = \
            maths.calculate_integrated_losses(smooth_distances, smooth_terrain_heights, smooth_los_heights, d_total, lambda_wave)[i]
            losses_db_at_i = 10 * math.log10(losses_at_i) if losses_at_i > 1 else 0
            fresnel_r_at_i = maths.fresnel_radius(smooth_distances[i], d_total, lambda_wave)
            losses_output.append(losses_db_at_i)

            print(
                f"{i + 1:<10}{smooth_distances[i]:<20.2f}{smooth_terrain_heights[i]:<20.2f}{smooth_los_heights[i]:<20.2f}"
                f"{fresnel_r_at_i:<20.2f}{losses_at_i:<20.2f}{losses_db_at_i:<20.2f}"
            )

        # Можливість побудови графіка для останнього відрізка 
        # maths.plot_updated_smooth_terrain(
        #     smooth_distances,
        #     smooth_terrain_heights,
        #     smooth_los_heights,
        #     smooth_graph_distances,
        #     smooth_graph_terrain_heights,
        #     smooth_los_heights
        # )



        P_rec_real = (10 * np.log10(P_trm) + G_trm + G_rec - L_dp - L_f_trm - L_dop_trm -
                  L_f_rec - L_dop_rec - total_loss)
        coverage_map = P_rec_real >= P_rec
        # print(f"P_rec_real: {P_rec_real}, покриття: {coverage_map}")

        # Розрахунок рівня сигналу на кожній точці
        P_rec_real_points = []

        for i in range(1, num_points):
            # Відстань до поточної точки
            d_current = distances[i]
            
            # Загальні втрати на поточній точці
            losses_current = maths.calculate_integrated_losses(
                smooth_distances[:i+1], smooth_terrain_heights[:i+1], smooth_los_heights[:i+1], 
                d_total, lambda_wave
            )
            total_loss_lr = maths.longley_rice_fixed_with_propob_loc(freq_mhz, d_current, q_percent, wa, lambda_wave)
            total_loss_linear = sum(losses_current)
            total_loss_db = 10 * math.log10(total_loss_linear) if total_loss_linear > 1 else 0
            total_loss_at_i = total_loss_lr + total_loss_db
            
            # Розрахунок поточного рівня сигналу
            P_rec_real_current = (
                10 * np.log10(P_trm) + G_trm + G_rec 
                - L_dp - L_f_trm - L_dop_trm
                - L_f_rec - L_dop_rec 
                - total_loss_at_i
            )
            
            # Збереження рівня сигналу для поточної точки
            P_rec_real_points.append(P_rec_real_current)

        # Перевірка покриття на кожній точці
        coverage_map_points = [P >= P_rec for P in P_rec_real_points]

        # Виведення результатів
        ray = [lons[1::], lats[1::], P_rec_real_points, coverage_map_points]
        # for i, (lon, lat, P, coverage) in enumerate(zip(lons, lats, P_rec_real_points, coverage_map_points)):
        #     print(f"Точка {i + 1}: довгота {lon:.6f}, широта {lat:.6f}, P_rec_real = {P:.2f} дБм, покриття: {'Так' if coverage else 'Ні'}")

        # print(f"ray: {ray}")

        return ray 
        """{
                "azimuth": azimuth,
                "distances": distances,
                "losses_db": total_loss,
            }"""

    def adjust_to_map_boundary(self, lat_start, lon_start, lon_end, lat_end):
        """
        Коригування точки кінцевого маршруту на межі карти, враховуючи зчитані параметри.
        """
        # Розрахунок меж карти з урахуванням зменшення роздільної здатності
        cellsize_adjusted = self.header['cellsize'] * self.downsample_factor
        x_min = self.header['xllcorner']
        x_max = self.header['xllcorner'] + cellsize_adjusted * self.data_downsampled.shape[1]
        y_min = self.header['yllcorner']
        y_max = self.header['yllcorner'] + cellsize_adjusted * self.data_downsampled.shape[0]

        # Створення лінії між стартовою та кінцевою точками
        line = LineString([(lon_start, lat_start), (lon_end, lat_end)])

        # Визначення меж карти
        map_boundary = box(x_min, y_min, x_max, y_max)

        # Перевірка перетину
        if not line.intersects(map_boundary):
            return lon_start, lat_start  # Якщо немає перетину, повертаємо стартову точку

        intersection = line.intersection(map_boundary)

        if intersection.is_empty:
            return lon_start, lat_start

        # Обробка типів геометрій
        if intersection.geom_type == "Point":
            return intersection.x, intersection.y
        elif intersection.geom_type == "MultiPoint":
            last_point = list(intersection)[-1]
            return last_point.x, last_point.y
        elif intersection.geom_type == "LineString":
            last_point = list(intersection.coords)[-1]
            return last_point[0], last_point[1]
        elif intersection.geom_type == "GeometryCollection":
            points = [geom for geom in intersection.geoms if geom.geom_type == "Point"]
            if points:
                last_point = points[-1]
                return last_point.x, last_point.y

            lines = [geom for geom in intersection.geoms if geom.geom_type == "LineString"]
            if lines:
                last_point = list(lines[-1].coords)[-1]
                return last_point[0], last_point[1]

        raise ValueError(f"Unexpected geometry type for intersection: {intersection.geom_type}")

    def coordinates_away_from_centre_with_radius_and_azimuth(self, lat, lon, radius, azimuth, radians=False):
        """
        Пошук координат на певній відстані та під певним кутом від точки з заданими широтою та довготою.

        :param lat, lon: Координати початку обчислень.
        :param radius: Обрана відстань від точки початку.
        :param azimuth: Кутове значення відхилення в градусах або радіанах.
        :param radians (bool): Якщо True, azimuth інтерпретується в радіанах. Інакше - в градусах.
       
        :return: Пара (широта, довгота), що представляє обчислені координати.
        """
        R = 6378100  # Радіус Землі в метрах

        if not radians:
            azimuth = math.radians(azimuth)  # Перетворення азимуту у радіани, якщо він заданий у градусах

        lat_rad = math.radians(lat)  # Convert latitude to radians once
        lon_rad = math.radians(lon)  # Convert longitude to radians once

        # Apply the formulas for latitude and longitude difference
        dlat = math.asin(math.sin(lat_rad) * math.cos(radius / R) +
                         math.cos(lat_rad) * math.sin(radius / R) * math.cos(azimuth))

        dlon = lon_rad + math.atan2(
            math.sin(azimuth) * math.sin(radius / R) * math.cos(lat_rad),
            math.cos(radius / R) - math.sin(lat_rad) * math.sin(dlat)
        )

        # Конвертація назад у градуси
        point = [math.degrees(dlat), math.degrees(dlon)]

        return point

    def calculate_coverage_area(self, coverage_results, lon_start, lat_start):
        """
        Розрахунок приблизної площі покриття на криволінійній поверхні Землі за формулою площі Гаусса.

        :param coverage_results (list of dict): Дані про присутність покриття для кожного азимута,
            отримані в результаті функції calculate_coverage.
        :param lat, lon: Координати початку обчислень.

        :return: Загальна площа покриття в км^2.
        """
        vertices = []
        vertices.append([lat_start, lon_start])

        for result in coverage_results:
            i = 0
            for coverage in result[3]:
                if not coverage:
                    break
                i += 1

            if i == len(result[3]):
                i -= 1

            point = [result[1][i], result[0][i]]
            vertices.append(point)

        # Сортування вершин за годинниковою стрілкою
        center = vertices[0]

        def angle_from_north(point):
            dx = point[1] - center[1]
            dy = point[0] - center[0]
            angle = np.arctan2(dx, dy)  # Кут в радіанах
            return (2 * np.pi + angle) % (2 * np.pi)  # Нормалізація до [0, 2π]

        # Сортування вершин (крім центру) за кутом з півночі
        sorted_vertices = [center] + sorted(vertices[1:], key=angle_from_north) + [center]

        # Заміна вершин відсортованими
        vertices = sorted_vertices

        # polygon = Polygon(vertices)
        # print(polygon)
        geod = Geod(ellps="WGS84")
        lons, lats = zip(*vertices)
        polygon = Polygon(zip(lats, lons))
        
        # Debug: Побудова багатокутника
        # plt.figure(figsize=(8, 6))
        # plt.plot(lats, lons, marker='o', label='Polygon Vertices')
        # plt.title("Debug: Polygon")
        # plt.xlabel("Longitude")
        # plt.ylabel("Latitude")
        # plt.legend()
        # plt.grid(True)
        # plt.show()

        area, perimeter = geod.geometry_area_perimeter(orient(polygon))

        return area / 1e6 # у км^2

class TabManager(Ui_MainWindow):
    """
    Менеджер вкладок, що зберігають пресети та дозволяють маніпулювати
    параметрами РЕЗ, що будуть розташовані на мапі
    """
    def __init__(self, tab_widget, parent):
        super().__init__()
        self.tab_widget = tab_widget
        self.tabs_data = {}
        self.parent = parent

    def create_tab(self, tab_name, title, settings_defaults):
        """
        Створює нову вкладку з вказаними параметрами.
        :param tab_name: Назва нової вкладки.
        :title: Підпис.
        :param settings_defaults: Значення за замовчуванням для слайдерів та інших віджетів.
               Формат: {"Setting Name": (default, min, max, step)}
        """
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        # Title
        title_layout = QHBoxLayout()
        label = QLabel(f"Шаблон: {title}", parent=tab)
        title_layout.addWidget(label)

        # Кнопка вибору кольору
        color_button = QPushButton("Колір", parent=tab)
        color_button.setFixedWidth(80)
        color_button.setStyleSheet("background-color: #ff0000;")  # За замовчуванням білий фон

        def open_color_dialog():
            color = QColorDialog.getColor(parent=tab)
            if color.isValid():
                color_button.setStyleSheet(f"background-color: {color.name()};")
                self.tabs_data[tab_name]["color"] = color.name()

        color_button.clicked.connect(open_color_dialog)
        title_layout.addWidget(color_button)

        title_layout.addStretch()  # Сортування по лівому боці
        tab_layout.addLayout(title_layout)

        # Макет форми для слайдерів
        form_layout = QFormLayout()

        sliders = {}
        inputs = {}
        for setting, (default, min_val, max_val, step) in dict(list(settings_defaults.items())).items():
            # Визначити коефіцієнт масштабування для роботи з флоатами (для герцовки частоти)
            scale_factor = int(1 / step) if step < 1 else 1

            # Створення слайдера та налаштування його властивостей
            slider = QSlider(Qt.Orientation.Horizontal, parent=tab)
            slider.setMinimum(int(min_val * scale_factor))
            slider.setMaximum(int(max_val * scale_factor))
            slider.setValue(int(default * scale_factor))
            slider.setSingleStep(1)

            # Створення поля вводу для числового значення
            input_field = QLineEdit(parent=tab)
            input_field.setValidator(QtGui.QDoubleValidator(min_val, max_val, 1))  # Валідатор для обмежень
            if isinstance(step, float): # рівень точності числа в полі
                input_field.setText(f"{default:.{len(str(step).split('.')[1])}f}" if isinstance(step, float) else f"{int(default)}")
            else:
                input_field.setText(f"{int(default)}")
            input_field.setFixedWidth(80)

            # Створення мітки для відображення поточного налаштування
            setting_label = QLabel(setting, parent=tab)

            # Підключити сигнал повзунка valueChanged для оновлення мітки
            slider.valueChanged.connect(
                lambda value, field=input_field, sf=scale_factor, step=step: 
                field.setText(f"{value / sf:.{len(str(step).split('.')[1])}f}" if isinstance(step, float) else f"{int(value / sf)}") # рівень точності числа в полі
            )

            # Підключити сигнал зміни тексту для оновлення слайдера
            input_field.textChanged.connect(
                lambda _, slider=slider, field=input_field, sf=scale_factor: 
                self.update_slider_from_input(slider, field, sf)
            )

            sliders[setting] = slider
            inputs[setting] = input_field

            # Додавання до макету
            row_layout = QHBoxLayout()
            row_layout.addWidget(setting_label)
            row_layout.addWidget(input_field)
            row_layout.addWidget(slider)

            row_layout.setStretch(0, 5)  # Динамічний розмір для назви
            row_layout.setStretch(1, 0)  # Фіксований розмір для поля вводу
            row_layout.setStretch(2, 3)  # Динамічний розмір для слайдера

            form_layout.addRow(row_layout)

        # Зберігання віджетів в даних вкладки
        self.tabs_data[tab_name] = {
            "sliders": sliders,
            "inputs": inputs,
            "color": "#ff0000",  # Припустим, постріл, колір ред
        }

        # Помістити форму у віджет
        form_widget = QWidget()
        form_widget.setLayout(form_layout)

        # Створити область прокручування
        scroll_area = QScrollArea(parent=tab)
        scroll_area.setWidgetResizable(True)  # Дозволяє автоматично підлаштовувати розміри
        scroll_area.setWidget(form_widget)

        # Додати область прокручування до основного макета вкладки
        tab_layout.addWidget(scroll_area)

        # Кнопка збереження точки
        apply_button = QPushButton("Зберегти", parent=tab)
        apply_button.clicked.connect(lambda: self.save_point(tab_name))  # пам'ятає до якої вкладки належить
        tab_layout.addWidget(apply_button)

        # Збереження вкладки
        self.tab_widget.addTab(tab, tab_name)

    def get_tab_settings(self, tab_name):
        """
        Отримує параметри певної вкладки.
        :param tab_name: Назва вкладки, для якої потрібно отримати налаштування.
        :return: Словник значень налаштувань.
        """
        if tab_name not in self.tabs_data:
            raise ValueError(f"No settings found for tab {tab_name}")

        tab_data = self.tabs_data[tab_name]

        sliders_values = {}

        for setting, slider in tab_data["sliders"].items():
            # Get the scaled value from the slider
            scaled_value = slider.value()

            # Retrieve the default, min, max, and step values for scaling
            default, min_val, max_val, step = DEFAULT_TAB_SETTINGS[setting]
            scale_factor = int(1 / step) if step < 1 else 1

            # Convert the scaled value back to the true float value
            true_value = scaled_value / scale_factor

            sliders_values[setting] = true_value

        return {
            "sliders": sliders_values,
        }

    def save_point(self, tab_name):
        """
        Дає команду зберегти точку в groupBox передавши налаштування вкладки
        :param tab_name: Назва вкладки, налаштування котрої збережено.
        """
        if self.parent.map_area and self.parent.map_area.last_point:
            print(f"Last clicked position: {self.parent.map_area.last_point.get_xydata()}")
            self.parent.save_location_data(tab_name)
        else:
            print("No point selected yet.")

    def update_slider_from_input(self, slider, field, scale_factor):
        """
        Зв'язок між написаними параметрами та слайдерами
        """
        try:
            value = float(field.text())
            slider.setValue(int(value * scale_factor))
        except ValueError:
            pass  # Ігнорувати помилки, якщо введення некоректне

    def get_color(self, tab_name):
        """
        Повертає вибраний колір для вкладки.
        """
        return self.tabs_data.get(tab_name, {}).get("color", "#ffffff")


if __name__ == "__main__":
    matplotlib.use("qtagg")
    app = QApplication(sys.argv)
    MainWindow = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec())
