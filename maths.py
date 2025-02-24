#!/usr/bin/env python3
import numpy as np
import math
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline

# Функція для обчислення відстані між двома точками за формулою гаверсинуса
def haversine_distance(lon1, lat1, lon2, lat2):
    R = 6371400 # Радіус Землі в метрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c # Відстань у метрах
    return distance

# Функція для читання даних висот із файлу SRTM
def load_asc(file_path):
    """
    Завантаження .asc файлу у numpy-масив.
    """
    header = {}
    with open(file_path, 'r') as file:
        for _ in range(6):
            line = file.readline()
            key, value = line.split()
            header[key] = float(value) if '.' in value else int(value)

        data = np.loadtxt(file, dtype=float)

    # Конвертуємо дані у Dask масив для ефективності
    # data = da.from_array(data, chunks=(1000, 1000))
    return data, header

# Функція для отримання висоти за географічними координатами
def get_height_for_coordinates(lon, lat, height_data, header):
    xllcorner = header['xllcorner']
    yllcorner = header['yllcorner']
    cellsize = header['cellsize']
    ncols = header['ncols']
    nrows = header['nrows']

    col = int((lon - xllcorner) / cellsize)
    row = int((yllcorner + nrows * cellsize - lat) / cellsize)
    if 0 <= col < ncols and 0 <= row < nrows:
        return height_data[row, col]
    else:
        return None

# Функція для обчислення лінії LOS з урахуванням висот антен
def calculate_los_with_antenna(smooth_distances, smooth_terrain_heights, tx_height, rx_height):
    los_heights = np.zeros_like(smooth_distances)
    los_heights[0] = smooth_terrain_heights[0] + tx_height
    los_heights[-1] = smooth_terrain_heights[-1] + rx_height
    los_heights[1:-1] = np.linspace(los_heights[0], los_heights[-1], len(smooth_distances))[1:-1]
    # Виняток крайових точок: Ми використовуємо [1:-1], щоб пропустити першу й останню точки,
    # які вже задані вручну (los_heights[0] і los_heights[-1]).
    # Цей підхід усуне проблему зі збігом другої та передостанньої точок із першою та останньою відповідно.
    return los_heights

# Функція для обчислення радіуса першої зони Френеля
def fresnel_radius(distance, total_distance, wavelength):
    return np.sqrt((wavelength * distance * (total_distance - distance)) / total_distance)

# Функція для обчислення втрат
def calculate_integrated_losses(smooth_distances, smooth_terrain_heights, smooth_los_heights, 
        total_distance, lambda_wave):
    losses = []
    for i in range(len(smooth_distances)):
        fresnel_r = fresnel_radius(smooth_distances[i], total_distance, lambda_wave)
        terrain_height = smooth_terrain_heights[i]
        los_height = smooth_los_heights[i]

        # Якщо висота рельєфу вище лінії прямої видимості (LOS) мінус радіус Френеля
        if fresnel_r > 0 and terrain_height > (los_height - fresnel_r):
            loss = (terrain_height - (los_height - fresnel_r)) ** 2 / fresnel_r
            losses.append(loss)
        else:
            losses.append(0)
    return losses

# Функція для обчислення сумарних втрат з використанням підсумовування
def calculate_total_losses(smooth_distances, smooth_terrain_heights, smooth_los_heights, 
        total_distance, lambda_wave):
    losses = calculate_integrated_losses(smooth_distances, smooth_terrain_heights, 
        smooth_los_heights, total_distance, lambda_wave)
    # Підсумовування втрат за маршрутом
    total_losses_linear = sum(losses)
    total_losses_db = 10 * math.log10(total_losses_linear) if total_losses_linear > 1 else 0
    return total_losses_linear, total_losses_db

# Побудова гладкого графіка
def plot_updated_smooth_terrain(smooth_distances, smooth_terrain_heights, smooth_los_heights,
        graph_distances, graph_terrain_heights, graph_los_heights):
    max_height = max(max(graph_terrain_heights), max(graph_los_heights))
    min_height = min(min(graph_terrain_heights), min(graph_los_heights))

    # plt.clf()
    plt.figure(figsize=(12, 7))
    plt.plot(graph_distances, graph_terrain_heights, label="Smoothed Terrain Profile (Graph)", color="green")
    plt.plot(graph_distances, graph_los_heights, label="Line of Sight (Graph)", linestyle="--", color="red")

    # Для порівняння додамо оригінальні точки розрахунків
    plt.scatter(smooth_distances, smooth_terrain_heights, label="Calculation Points", color="blue", s=10)

    plt.ylim(min_height - 50, max_height + 50)
    plt.title("Smoothed Terrain Profile and Updated Line of Sight")
    plt.xlabel("Distance (m)")
    plt.ylabel("Elevation (meters)")
    plt.legend()
    plt.grid()
    plt.show()

def get_propob_loc(q_percent, f, wa):
    # Таблиця значень Q_i для різних відсотків
    qi_table = {
        1: 2.327, 2: 2.054, 3: 1.881, 4: 1.751, 5: 1.645, 6: 1.555, 7: 1.476,
        8: 1.405, 9: 1.341, 10: 1.282, 11: 1.227, 12: 1.175, 13: 1.126, 14: 1.080,
        15: 1.036, 16: 0.994, 17: 0.954, 18: 0.915, 19: 0.878, 20: 0.841, 21: 0.806,
        22: 0.772, 23: 0.739, 24: 0.706, 25: 0.674, 26: 0.643, 27: 0.612, 28: 0.582,
        29: 0.553, 30: 0.524, 31: 0.495, 32: 0.467, 33: 0.439, 34: 0.412, 35: 0.385,
        36: 0.358, 37: 0.331, 38: 0.305, 39: 0.279, 40: 0.253, 41: 0.227, 42: 0.202,
        43: 0.176, 44: 0.151, 45: 0.125, 46: 0.100, 47: 0.075, 48: 0.050, 49: 0.025,
        50: 0.000, 51: -0.025, 52: -0.050, 53: -0.075, 54: -0.100, 55: -0.125, 56: -0.151,
        57: -0.176, 58: -0.202, 59: -0.227, 60: -0.253, 61: -0.279, 62: -0.305, 63: -0.331,
        64: -0.358, 65: -0.385, 66: -0.412, 67: -0.439, 68: -0.467, 69: -0.495, 70: -0.524,
        71: -0.553, 72: -0.582, 73: -0.612, 74: -0.643, 75: -0.674, 76: -0.706, 77: -0.739,
        78: -0.772, 79: -0.806, 80: -0.841, 81: -0.878, 82: -0.915, 83: -0.954, 84: -0.994,
        85: -1.036, 86: -1.080, 87: -1.126, 88: -1.175, 89: -1.227, 90: -1.282, 91: -1.341,
        92: -1.405, 93: -1.476, 94: -1.555, 95: -1.645, 96: -1.751, 97: -1.881, 98: -2.054,
        99: -2.327
    }

    # Отримуємо значення Qi для заданого відсотка
    qi_value = qi_table.get(q_percent, None)

    if qi_value is None:
        return "Відсоток має бути від 1 до 99"

    # Розрахунок стандартної девіації σ_L
    sigma_L = (0.024 * f / 1000 + 0.52) * wa ** 0.28

    # Розрахунок поправки на відсоток місць
    propob_loc = - qi_value * sigma_L
    return propob_loc, sigma_L, qi_value

def longley_rice_fixed_with_propob_loc(freq_mhz, d_total, q_percent, wa, lambda_wave):
    """
    Модель Лонглі-Райса з Popr_loc для відсотка локацій.
    Параметри:
    - freq_mhz (float): Частота у МГц.
    - distance_km (float): Відстань у км.
    - q_percent (int): Відсоток для ймовірності знаходження.
    - wa (float): Роздільна здатність у метрах.

    :return:
    - Total Loss (float): Втрати на шляху в дБ з Popr_loc.
    - Popr_loc(float): Значення Popr_loc, основане на відсотках локацій.
    """
    # Перетворити одиниці виміру

    # Розрахунок FSPL
    fspl = 10 * math.log10((4*math.pi*d_total)/lambda_wave)
    # print(f"FSPL (Free Space Path Loss): {fspl:.2f} dB")


    # Обчислення Popr_loc та sigma_L
    propob_loc, sigma_L, qi_value = get_propob_loc(q_percent, freq_mhz, wa)
    # print(f"Standard Deviation (σ_L): {sigma_L:.2f} dB")
    # print(f"Popr_loc for {q_percent}% probability: {propob_loc:.2f} dB (Q_i = {qi_value})")

    # Загальна втрата
    total_loss_lr = fspl + propob_loc
    return total_loss_lr


if __name__ == "__main__":
    # Параметри
    freq_mhz = 300  # Частота в МГц
    lambda_wave = 3e8 / (freq_mhz * 1e6)  # Довжина хвилі в метрах
    tx_height = 80  # Висота передавача (у метрах)
    rx_height = 60  # Висота приймача (у метрах)
    q_percent = 70  # Відсоток імовірності ціле число від 1 до 99
    wa = 4000  # Роздільна здатність у метрах/Підібрано, щоб sigma_L = 5,5 дБ

    # Завантаження даних SRTM
    srtm_file_path = "maps/srtm_42_03.asc"  # Шлях до вашого файлу .asc
    height_data, header = load_asc(srtm_file_path)

    # Координати початкової та кінцевої точки маршруту
    lon_start, lat_start = 25.00, 45.00  # Початкова точка маршруту (довгота, широта)
    lon_end, lat_end = 25.060282, 45.290702  # Кінцева точка маршруту (довгота, широта)

    # Розрахунок реальної відстані між двома точками за допомогою формули Хаверсінуса
    d_total = haversine_distance(lon_start, lat_start, lon_end, lat_end)

    # Кількість точок уздовж маршруту (дистанція буде автоматично змінюватися залежно від довжини маршруту)
    num_points = int(d_total/60)

    # Генерація точок за маршрутом
    distances = np.linspace(0, d_total, num_points)
    lons = np.linspace(lon_start, lon_end, num_points)
    lats = np.linspace(lat_start, lat_end, num_points)

    # Отримуємо висоти рельєфу для всіх точок маршруту
    terrain_heights = np.array([
        get_height_for_coordinates(lon, lat, height_data, header) for lon, lat in zip(lons, lats)
    ])

    # Згладжування профілю рельєфу
    spl = make_interp_spline(distances, terrain_heights, k=3)
    smooth_distances = np.linspace(distances.min(), distances.max(), num_points)
    smooth_terrain_heights = spl(smooth_distances)

    # Генерація точок для більш гладкого графіка
    smooth_graph_points = num_points * 10  # Збільшуємо кількість точок тільки для графіка
    smooth_graph_distances = np.linspace(distances.min(), distances.max(), smooth_graph_points)
    smooth_graph_terrain_heights = spl(smooth_graph_distances)

    # Перераховуємо LOS тільки для побудови графіка
    smooth_los_heights = calculate_los_with_antenna(
        smooth_graph_distances,
        smooth_graph_terrain_heights,
        tx_height,
        rx_height
    )


    # Розрахунок сумарних втрат
    total_losses_linear, total_losses_db = calculate_total_losses(smooth_distances, 
        smooth_terrain_heights, smooth_los_heights, d_total, lambda_wave)


    # Виведення сумарних втрат
    print(f"\nЗагальні втрати дифракції (лінійні): {total_losses_linear:.2f}")
    print(f"Загальні втрати дифракції (дБ): {total_losses_db:.2f}")


    distance_km = d_total  # Відстань у км
    total_loss_lr = longley_rice_fixed_with_propob_loc(freq_mhz, distance_km, q_percent, wa, lambda_wave)
    total_loss = total_loss_lr + total_losses_db
    print(f"Final Total Loss (Longley-Rice, propob_loc, Difr): {total_loss:.2f} dB")

    P_trm = 50  # Потужність передавача (Вт)
    G_trm = 5  # Посилення антени передавача (дБ)
    L_dp = 1.5    # Втрати в дуплексному фільтри
    L_f_trm = 4 # Втрати в фідері передавального тракту (дБ)
    L_dop_trm = 2 # Додаткові втрати в передавальному тракті (дБ)
    G_rec = 2  # Коефіцієнт підсилення приймальної антени (дБ)
    L_f_rec = 0.5 # Втрати фідера приймача (дБ)
    L_dop_rec = 1 # Втрати через доплер приймача (дБ)
    P_rec = -85 # Мінімальний рівень сигналу (дБм)

    P_rec_real = (10 * np.log10(P_trm) + G_trm + G_rec - L_dp - L_f_trm - L_dop_trm -
              L_f_rec - L_dop_rec - total_loss)
    coverage_map = P_rec_real >= P_rec
    print(f"P_rec_real: {P_rec_real}, покриття: {coverage_map}")

    # Розрахунок рівня сигналу на кожній точці
    P_rec_real_points = []

    for i in range(1, num_points):
        # Відстань до поточної точки
        d_current = distances[i]
        
        # Загальні втрати на поточній точці
        losses_current = calculate_integrated_losses(
            smooth_distances[:i+1], smooth_terrain_heights[:i+1], smooth_los_heights[:i+1], 
            d_total, lambda_wave
        )
        total_loss_lr = longley_rice_fixed_with_propob_loc(freq_mhz, d_current, q_percent, wa, lambda_wave)
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
    for i, (lon, lat, P, coverage) in enumerate(zip(lons, lats, P_rec_real_points, coverage_map_points)):
        print(f"Точка {i + 1}: довгота {lon:.6f}, широта {lat:.6f}, P_rec_real = {P:.2f} дБм, покриття: {'Так' if coverage else 'Ні'}")

    print()
    # Виведення таблиці з результатами
    # print(
        # "\nТочка    Відстань (м)    Висота рельєфу (м)  Висота LOS (м)  Радіус Френеля (м)      Втрати (м)      Втрати (дБ)     P_rec_real (дБВт)       Покриття")
    # for i in range(0, len(smooth_distances), 2):  # Виводимо для всіх точок
    #     losses_at_i = calculate_integrated_losses(smooth_distances, smooth_terrain_heights, smooth_los_heights, d_total, lambda_wave)[i]
    #     losses_db_at_i = 10 * math.log10(losses_at_i) if losses_at_i > 1 else 0
    #     fresnel_r_at_i = fresnel_radius(smooth_distances[i], d_total, lambda_wave)

    #     loss_lr_at_i = longley_rice_fixed_with_propob_loc(freq_mhz, distance_km, q_percent, wa, lambda_wave)

    #     total_loss_at_i = loss_lr_at_i + losses_db_at_i

    #     P_rec_real = (10 * np.log10(P_trm) + G_trm + G_rec - L_dp - L_f_trm - L_dop_trm -
    #           L_f_rec - L_dop_rec - total_loss_at_i)
    #     coverage_map = P_rec_real >= P_rec

    #     print(
    #         f"{i + 1:<10}{smooth_distances[i]:<20.2f}{smooth_terrain_heights[i]:<20.2f}{smooth_los_heights[i]:<20.2f}"
    #         f"{fresnel_r_at_i:<20.2f}{losses_at_i:<20.2f}{losses_db_at_i:<20.2f}{P_rec_real:<20.2f}{coverage_map}"
    #     )

    # Виклик функції побудови
    plot_updated_smooth_terrain(
        smooth_distances,
        smooth_terrain_heights,
        smooth_los_heights,
        smooth_graph_distances,
        smooth_graph_terrain_heights,
        smooth_los_heights
    )

    