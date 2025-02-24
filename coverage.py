import numpy as np
import math
from maths import haversine_distance, fresnel_radius, get_height_for_coordinates
from pprint import pprint

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


def calculate_coverage_area(tx_coords, terrain_data, header, tx_height, frequency, max_distance_km=300, step_azimuth=5, step_distance=1):
    """
    Calculate the coverage area of a transmitter.

    :param tx_coords: Tuple of (lon, lat) for the transmitter location.
    :param terrain_data: 2D array of terrain elevation data.
    :param header: Header information of the terrain file.
    :param tx_height: Height of the transmitter above ground level (in meters).
    :param frequency: Frequency of the signal in GHz.
    :param max_distance_km: Maximum distance to consider for coverage (in km).
    :param step_azimuth: Step size for azimuth calculation (in degrees).
    :param step_distance: Step size for distance calculation (in km).

    :return: A 2D array representing signal coverage.
    """
    # Constants
    c = 3e8  # Speed of light in m/s
    wavelength = c / (frequency * 1e9)  # Wavelength in meters
    
    # Convert maximum distance to meters
    max_distance_m = max_distance_km * 1000
    
    # Initialize results
    coverage_grid = []

    for azimuth in range(0, 360, step_azimuth):
        azimuth_results = []
        for distance_km in np.arange(0, max_distance_km + step_distance, step_distance):
            # Calculate distance in meters
            distance_m = distance_km * 1000

            # Compute endpoint coordinates
            delta_x = distance_m * math.cos(math.radians(azimuth))
            delta_y = distance_m * math.sin(math.radians(azimuth))
            
            lon_end = tx_coords[0] + (delta_x / 111320)  # Adjust longitude
            lat_end = tx_coords[1] + (delta_y / 110540)  # Adjust latitude

            # Get terrain height at the endpoint
            endpoint_height = get_height_for_coordinates(lon_end, lat_end, terrain_data, header)

            # Skip if endpoint is out of bounds
            if endpoint_height is None:
                azimuth_results.append((distance_km, None))
                continue

            # Calculate signal losses (simplified)
            los_height = tx_height + endpoint_height
            fresnel_r = fresnel_radius(distance_m, max_distance_m, wavelength)
            
            if endpoint_height > los_height - fresnel_r:
                signal_loss = (endpoint_height - (los_height - fresnel_r))**2 / fresnel_r
            else:
                signal_loss = 0

            total_loss_db = 10 * math.log10(1 + signal_loss)  # Logarithmic scale

            # Determine coverage
            threshold_db = 120  # Example threshold (in dB)
            coverage = total_loss_db < threshold_db

            azimuth_results.append((distance_km, coverage))

        coverage_grid.append(azimuth_results)

    return coverage_grid

# Example usage
if __name__ == "__main__":
    # Example transmitter coordinates (longitude, latitude)
    transmitter_coords = (25.375, 45.208333333333336)

    # Example parameters
    tx_height = 50  # Transmitter height in meters
    frequency = 2.4  # Frequency in GHz
    max_distance_km = 300  # Maximum coverage distance in km
    step_azimuth = 10  # Azimuth step in degrees
    step_distance = 5  # Distance step in km

    # Load terrain data
    terrain_data, header = load_asc("srtm_42_03.asc")

    # Calculate coverage
    coverage = calculate_coverage_area(transmitter_coords, terrain_data, header, tx_height, frequency, max_distance_km, step_azimuth, step_distance)

    # Output results
    print("Coverage area calculation complete.")
    pprint(coverage)
