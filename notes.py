def calculate_coverage(self, lon_center, lat_center):
        """
        Calculate the coverage area around the transmitter by sweeping 360°.
        """
        angles = np.linspace(0, 2 * np.pi, 360)  # 1° resolution
        max_distance = 1000  # Maximum range in meters
        cellsize = self.header['cellsize']  # Cell size in meters
        min_step_size = 10  # Minimum step size to avoid rounding errors (in meters)
        coverage_points = []

        for angle in angles:
            for d in range(0, max_distance, min_step_size):
                # Convert distance to x, y offsets in meters
                delta_x = d * np.cos(angle)
                delta_y = d * np.sin(angle)

                # Calculate the corresponding grid indices
                row = int((lat_center - self.header['yllcorner'] - delta_y) / cellsize)
                col = int((lon_center - self.header['xllcorner'] + delta_x) / cellsize)

                if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
                    terrain_height = self.data[row, col]
                    los_height = 700  # Example transmitter height

                    # Stop if terrain obstructs LOS
                    if terrain_height > los_height:
                        pass

                    # Convert grid indices back to coordinates
                    coverage_lon = self.header['xllcorner'] + col * cellsize
                    coverage_lat = self.header['yllcorner'] + row * cellsize
                    coverage_points.append((coverage_lon, coverage_lat))

        return coverage_points


def calculate_coverage(self, lon_center, lat_center):
        """
        Calculate the coverage area around the transmitter by sweeping 360°.
        """
        angles = np.linspace(0, 2 * np.pi, 360)  # 1° resolution
        max_distance = 1000  # Maximum range in meters
        num_points = 100      # Number of points per LOS line

        coverage_points = []

        for angle in angles:
            delta_lat = (max_distance * np.sin(angle)) / 111320
            delta_lon = (max_distance * np.cos(angle)) / (111320 * np.cos(np.radians(lat_center)))

            # End point of the LOS line
            lat_end = lat_center + delta_lat
            lon_end = lon_center + delta_lon

            # Get LOS heights for this direction
            distances, terrain_heights, los_heights = self.calculate_los(lon_center, lat_center, lon_end, lat_end)
            
            # Determine the maximum visible point (where LOS is not obstructed)
            for d, t, l in zip(distances, terrain_heights, los_heights):
                if l < t:  # Obstruction
                    break
                coverage_points.append((lon_center + d * np.cos(angle), lat_center + d * np.sin(angle)))

        return distances, coverage_points



#######################


def onclick(self, event):
        """
        Натискання колесиком по мапі ставить точку випромінювача
        :param event: Обробник взаємодії з графіком = натиск кнопки.
        """
        # event.button == 1 ЛКМ 2 колесико 3 ПКМ
        if event.button == 2 and event.xdata is not None and event.ydata is not None:
            print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
              ('double' if event.dblclick else 'single', event.button,
               event.x, event.y, event.xdata, event.ydata))

            # Видаляє останню точку, якщо вона існує
            if self.last_point is not None:
                self.last_point.remove()
                self.last_point = None
            self.last_point, = self.ax.plot(event.xdata, event.ydata, 'o', color='red', markersize=5) #точечна точка

            # Transmitter coordinates
            t_point = [round(coord) for coord in self.last_point.get_xydata()[0]] #координати обраної точки
            lon_center, lat_center = self.get_coordinates(t_point[0], t_point[1], self.header, self.downsample_factor)
            print(f"Ірл широта, довгота: {lat_center}, {lon_center}")

            print("calculating coverage...")

            # Calculate coverage area
            coverage_points = self.calculate_coverage(lon_center, lat_center)
            print(f"coverage: {coverage_points}")

            print("visualising...")

            # Plot the coverage as a filled polygon
            coverage_lon, coverage_lat = zip(*coverage_points)

            self.ax.fill(coverage_lon, coverage_lat, color='blue', alpha=0.3, label='Coverage Area')
            self.ax.legend()
            self.canvas.draw()

            print("done.")

    def get_last_point(self):
        """
        Повертає останню вибрану точку на мапі
        """
        return self.last_point

    def calculate_los(self, lon_start, lat_start, lon_end, lat_end):
        """
        Calculate the LOS profile and terrain heights between two points.
        """

        total_distance = haversine_distance(lon_start, lat_start, lon_end, lat_end)
        num_points = int(total_distance / 60)  # Adjust point density
        distances = np.linspace(0, total_distance, num_points)
        lons = np.linspace(lon_start, lon_end, num_points)
        lats = np.linspace(lat_start, lat_end, num_points)

        print(f"Кінцева широта, довгота: {lat_end}, {lon_end}")

        # Get terrain heights for the LOS path
        terrain_heights = np.array([
            get_height_for_coordinates(lon, lat, self.data, self.header) for lon, lat in zip(lons, lats)
        ])

        pprint(f"terrain_heights: {terrain_heights}")
        # print(' '.join(map(str, terrain_heights)))

        if len([x for x in terrain_heights if x is not None]) < 2:
            print(f"Insufficient valid terrain heights: {terrain_heights}")
            raise ValueError("Insufficient valid terrain data for LOS calculation.")


        # Smooth terrain heights
        spl = make_interp_spline(distances, terrain_heights, k=3)
        smooth_distances = np.linspace(distances.min(), distances.max(), 200)
        smooth_terrain_heights = spl(smooth_distances)

        # Calculate LOS heights
        tx_height = 700  # Example transmitter height
        rx_height = 500  # Example receiver height
        los_heights = calculate_los_with_antenna(smooth_distances, smooth_terrain_heights, tx_height, rx_height)

        return smooth_distances, smooth_terrain_heights, los_heights

    def calculate_coverage(self, lon_center, lat_center):
        """
        Calculate the coverage area around the transmitter by sweeping 360°.
        """
        angles = np.linspace(0, 2 * np.pi, 360)  # 1° resolution
        max_distance = 1000  # Maximum range in meters
        cellsize = self.header['cellsize']  # Cell size in meters
        min_step_size = 10  # Minimum step size to avoid rounding errors (in meters)
        coverage_points = []

        for angle in angles:
            for d in range(0, max_distance, min_step_size):
                # Convert distance to x, y offsets in meters
                delta_x = d * np.cos(angle)
                delta_y = d * np.sin(angle)

                # Calculate the corresponding grid indices
                row = int((lat_center - self.header['yllcorner'] - delta_y) / cellsize)
                col = int((lon_center - self.header['xllcorner'] + delta_x) / cellsize)

                if 0 <= row < self.data.shape[0] and 0 <= col < self.data.shape[1]:
                    terrain_height = self.data[row, col]
                    los_height = 700  # Example transmitter height

                    # Stop if terrain obstructs LOS
                    if terrain_height > los_height:
                        pass

                    # Convert grid indices back to coordinates
                    coverage_lon = self.header['xllcorner'] + col * cellsize
                    coverage_lat = self.header['yllcorner'] + row * cellsize
                    coverage_points.append((coverage_lon, coverage_lat))

        return coverage_points



# ###################

####### Original maths #######
            # def i_want_the_comment_to_collapse():
                # lon_end, lat_end = 27.354856, 45.905709

                # # Розрахунок реальної відстані між двома точками за допомогою формули Хаверсінуса
                # d_total = haversine_distance(lon_start, lat_start, lon_end, lat_end)

                # # Кількість точок уздовж маршруту (дистанція буде автоматично змінюватися залежно від довжини маршруту)
                # num_points = int(d_total/60)

                # # Генерація точок за маршрутом
                # distances = np.linspace(0, d_total, num_points)
                # lons = np.linspace(lon_start, lon_end, num_points)
                # lats = np.linspace(lat_start, lat_end, num_points)

                # terrain_heights = np.array([
                #     get_height_for_coordinates(lon, lat, height_data, header) for lon, lat in zip(lons, lats)
                # ])

                # # Згладжування профілю рельєфу
                # spl = make_interp_spline(distances, terrain_heights, k=3)
                # smooth_distances = np.linspace(distances.min(), distances.max(), num_points)
                # smooth_terrain_heights = spl(smooth_distances)

                # # Генерація точок для більш гладкого графіка
                # smooth_graph_points = num_points * 10  # Збільшуємо кількість точок тільки для графіка
                # smooth_graph_distances = np.linspace(distances.min(), distances.max(), smooth_graph_points)
                # smooth_graph_terrain_heights = spl(smooth_graph_distances)

                # # Перераховуємо LOS тільки для побудови графіка
                # smooth_los_heights = calculate_los_with_antenna(
                #     smooth_graph_distances,
                #     smooth_graph_terrain_heights,
                #     tx_height,
                #     rx_height
                # )

                # # Розрахунок сумарних втрат
                # total_losses_linear, total_losses_db = calculate_total_losses(smooth_distances, 
                #     smooth_terrain_heights, smooth_los_heights, d_total, lambda_wave)


                # # Виведення сумарних втрат
                # print(f"\nЗагальні втрати дифракції (лінійні): {total_losses_linear:.2f}")
                # print(f"Загальні втрати дифракції (дБ): {total_losses_db:.2f}")


                # distance_km = d_total  # Відстань у км
                # total_loss_lr = longley_rice_fixed_with_propob_loc(freq_mhz, distance_km, q_percent, wa, lambda_wave)
                # total_loss = total_loss_lr + total_losses_db
                # print(f"Final Total Loss (Longley-Rice, propob_loc, Difr): {total_loss:.2f} dB")

                # # Виведення таблиці з результатами
                # print(
                #     "\nТочка    Відстань (м)    Висота рельєфу (м)  Висота LOS (м)  Радіус Френеля (м)      Втрати (м)      Втрати (дБ)")
                # for i in range(0, len(smooth_distances), 2):  # Виводимо для всіх точок
                #     losses_at_i = \
                #     calculate_integrated_losses(smooth_distances, smooth_terrain_heights, smooth_los_heights, d_total, lambda_wave)[i]
                #     losses_db_at_i = 10 * math.log10(losses_at_i) if losses_at_i > 1 else 0
                #     fresnel_r_at_i = fresnel_radius(smooth_distances[i], d_total, lambda_wave)

                #     print(
                #         f"{i + 1:<10}{smooth_distances[i]:<20.2f}{smooth_terrain_heights[i]:<20.2f}{smooth_los_heights[i]:<20.2f}"
                #         f"{fresnel_r_at_i:<20.2f}{losses_at_i:<20.2f}{losses_db_at_i:<20.2f}"
                #     )

                # # Виклик функції побудови
                # plot_updated_smooth_terrain(
                #     smooth_distances,
                #     smooth_terrain_heights,
                #     smooth_los_heights,
                #     smooth_graph_distances,
                #     smooth_graph_terrain_heights,
                #     smooth_los_heights
                # )


###########

def get_coordinates(self, i, j, header, downsample_factor=1):
        """
        Calculates real-world coordinates (longitude, latitude) for a grid cell.
        
        :param i (int): Row index (starts from 0).
        :param j (int): Column index (starts from 0).
        :param header (dict): Metadata from the .asc file.
        :param downsample_factor (int): Downsampling factor (default is 1).
        
        :return (float, float): Longitude and latitude of the cell.
        """
        xllcorner = header['xllcorner']
        yllcorner = header['yllcorner']
        cellsize = header['cellsize'] # * downsample_factor  # Adjust cellsize for downsampling
        nrows = header['nrows']

        # Convert from grid indices to original array indices
        i_original = int(i * downsample_factor)
        j_original = int(j * downsample_factor)

        # Longitude and latitude calculations
        lon = xllcorner + j_original * cellsize
        lat = yllcorner + (nrows - i_original - 1) * cellsize  # Corrected for top-down grid ordering

        return lon, lat


    def get_row_col_for_coordinates(self, lon, lat, header, downsample_factor=1):
        xllcorner = header['xllcorner']
        yllcorner = header['yllcorner']
        cellsize = header['cellsize'] * downsample_factor  # Adjust for downsampling
        ncols = header['ncols']
        nrows = header['nrows']

        col = int((lon - xllcorner) / cellsize)
        row = int((yllcorner + nrows * cellsize - lat) / cellsize)
        return row, col


###########

        self.default_settings_tab1 = {
            "Частота (GHz)": (3, 0.03, 6, 0.01), 
            "Радіус (m)": (20000, 150, 300000, 50), 
            "Кут (°)": (100, 10, 360, 10), 
            "Крок (°)": (1, 1, 15, 1), 
            "Азимут (°)": (0, 0, 360, 1), 
            # "Довжина хвилі (m)": (10, 0, 50, 1), 
            "Висота передавача (m)": (500, 0, 5000, 10), 
            "Висота приймача (m)": (300, 0, 5000, 10), 
            "Ймовірність (%)": (80, 1, 99, 1), 
            "Динамічний крок": (60, 50, 500, 10), 
            # "Тип місцевості": "Відкрита",
            # "Зона": "Земля",
            "Динамічнaй крок": (60, 50, 500, 10),
            "Динаміdний крок": (60, 50, 500, 10),
            "Динаwічнd крок": (60, 50, 500, 10),
            "Динdмічний крок": (60, 50, 500, 10),
            "Динамdний крок": (60, 50, 500, 10),
            "Динамічний крок": (60, 50, 500, 10),
            "Диaмdний крок": (60, 50, 500, 10),
            "Динdмічний крок": (60, 50, 500, 10),
        }


                # Зберігання віджетів в даних вкладки
        self.tabs_data[tab_name] = {
            "sliders": sliders,
            # "comboBox1": comboBox1,
            # "comboBox2": comboBox2,
            # "checkBox": checkBox,
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

###########

    # Низ
        self.bottom_layout = QHBoxLayout()

        self.gridLayout = QGridLayout()
        self.groupBoxes = []
        self.closeButtons = []
        for i in range(5): # автоматизація
            groupBox = QGroupBox(f"Збереження {i+1}", parent=self.centralwidget)
            pushButton = QPushButton("❌")
            pushButton.setText(str(i))
            pushButton.clicked.connect(lambda _, idx=i: self.delete_location_data(idx))

            groupLayout = QVBoxLayout(groupBox)
            for j in range(len(DEFAULT_TAB_SETTINGS) + 2): # кількість виведених параметрів
                label = QLabel(f"Label {i+1}.{j+1}", parent=groupBox)
                groupLayout.addWidget(label)

            self.gridLayout.addWidget(groupBox, 0, i)
            self.gridLayout.addWidget(pushButton, 1, i)

            self.groupBoxes.append(groupBox)
            self.closeButtons.append(pushButton)

        self.bottom_layout.addLayout(self.gridLayout)

        self.main_layout.addWidget(self.splitter)
        self.main_layout.addLayout(self.bottom_layout)





    def delete_location_data(self, idx):
        """
        Видалення та очищення слоту збережень
        """

        if self.check_labels_not_default(idx):
            selected_groupBox = self.groupBoxes[idx]
            labels = selected_groupBox.findChildren(QLabel)
            for i, label in enumerate(labels):
                if i < len(labels):
                    label.setText(f"Label {idx+1}.{i+1}")

            self.statusbar.showMessage(f"Дані видалено з {selected_groupBox.title()}!")
            self.current_save_index = idx

            ### ToDo: Видалення обраних збрежеих було рендерів
            # self.saved_collections.pop(idx)
            # self.map_area.collections[idx][1].remove()

    def check_labels_not_default(self, groupBoxIndex):
        default_pattern = f"Label {groupBoxIndex + 1}."
        selected_groupBox = self.groupBoxes[groupBoxIndex]

        for child in selected_groupBox.children():
            if isinstance(child, QLabel):
                if not child.text().startswith(default_pattern):
                    return True

        return False


############

self.default_settings_tab1 = {
            "Частота (GHz)": (3, 0.03, 6, 0.01), 
            "Радіус (m)": (20000, 150, 300000, 50), 
            "Кут (°)": (100, 10, 360, 10), 
            "Крок (°)": (1, 1, 15, 1), 
            "Азимут (°)": (0, 0, 360, 1), 
            # "Довжина хвилі (m)": (10, 0, 50, 1), 
            "Висота передавача (m)": (500, 0, 5000, 10), 
            "Висота приймача (m)": (300, 0, 5000, 10), 
            "Ймовірність (%)": (80, 1, 99, 1), 
            "Динамічний крок": (60, 50, 500, 10), 
            # "Тип місцевості": "Відкрита",
            # "Зона": "Земля",

            "Потужність передавача (W)": (50, 0, 300, 1), 
            "Коефіцієнт підсилення антени (dBi)": (5, 0, 20, 0.1),
            "Втрати в дуплексному фільтрі": (1.5, 0.1, 20, 0.1),
            "Втрати в фідері передавального тракту (dB)": (4, 0, 20, 0.1),
            "Додаткові втрати в передавальному тракті": (2, 0, 20, 0.1),
            "Коефіцієнт підсилення приймальної антени (dBi)": (2, 0, 20, 0.1),
            "Втрати в фідері приймального тракту (dB)": (0.5, 0, 20, 0.1),
            "Додаткові втрати в приймальному тракті": (1, 0, 20, 0.1),
            "Чутливість приймача (dbW)": (-110, -300, 100, 1),
        }

        self.tabManager.create_tab("Tab 1", "РЕЗ1", self.default_settings_tab1)

        default_settings_tab2 = {
            "Чутливість приймача (dbW)": (-110, -300, 100, 1),
            "Частота (GHz)": (1, 0.03, 6, 0.03), 
            "Радіус (m)": (10000, 150, 300000, 50),
            "Кут (°)": (360, 10, 360, 10), 
            "Крок (°)": (10, 1, 15, 1), 
            "Азимут (°)": (75, 0, 360, 1), 
            # "Довжина хвилі (m)": (10, 0, 50, 1), 
            "Висота передавача (m)": (2500, 0, 5000, 10), 
            "Висота приймача (m)": (2500, 0, 5000, 10), 
            "Ймовірність (%)": (70, 1, 99, 1), 
            "Динамічний крок": (60, 50, 500, 10), 
            # "Тип місцевості": "Відкрита",
            # "Зона": "Земля",

            "Потужність передавача (W)": (50, 0, 300, 1), 
            "Коефіцієнт підсилення антени (dBi)": (5, 0, 20, 0.1),
            "Втрати в дуплексному фільтрі": (1.5, 0.1, 20, 0.1),
            "Втрати в фідері передавального тракту (dB)": (4, 0, 20, 0.1),
            "Додаткові втрати в передавальному тракті": (2, 0, 20, 0.1),
            "Коефіцієнт підсилення приймальної антени (dBi)": (2, 0, 20, 0.1),
            "Втрати в фідері приймального тракту (dB)": (0.5, 0, 20, 0.1),
            "Додаткові втрати в приймальному тракті": (1, 0, 20, 0.1),
            "Чутливість приймача (dbW)": (-110, -300, 100, 1),
        }
        self.tabManager.create_tab("Tab 2", "РЕЗ2", default_settings_tab2)