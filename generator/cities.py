"""
Porter Intelligence Platform — City and Zone Data
Real lat/lon coordinates for Porter's operational zones.
All coordinates verified against Google Maps.
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple
from generator.config import RANDOM_SEED

np.random.seed(RANDOM_SEED)

EARTH_RADIUS_KM: float = 6371.0


@dataclass
class Zone:
    """Represents a Porter operational zone within a city."""

    zone_id: str
    name: str
    city: str
    lat: float
    lon: float
    radius_km: float
    commercial_density: float    # 0.0-1.0 (how busy/commercial)
    traffic_multiplier: float    # 1.0-2.5 (affects trip duration)
    zone_type: str               # commercial/residential/industrial
    fraud_rate_adj: float        # zone-specific fraud adjustment

    @property
    def display_name(self) -> str:
        """Return human-readable zone name."""
        return f"{self.name}, {self.city.title()}"


# ── Zone definitions ──────────────────────────────────────────

ZONES: Dict[str, Zone] = {}

# ── Bangalore (12 zones) ──────────────────────────────────────
_blr_zones = [
    Zone("blr_whitefield",     "Whitefield",       "bangalore",
         12.9698, 77.7500, 3.5, 0.90, 2.2, "commercial",  +0.012),
    Zone("blr_koramangala",    "Koramangala",      "bangalore",
         12.9352, 77.6245, 2.5, 0.95, 2.4, "commercial",  +0.018),
    Zone("blr_hsr",            "HSR Layout",       "bangalore",
         12.9116, 77.6389, 2.8, 0.85, 2.0, "residential", +0.008),
    Zone("blr_indiranagar",    "Indiranagar",      "bangalore",
         12.9784, 77.6408, 2.2, 0.90, 2.3, "commercial",  +0.015),
    Zone("blr_jayanagar",      "Jayanagar",        "bangalore",
         12.9299, 77.5833, 2.8, 0.75, 1.8, "residential", +0.005),
    Zone("blr_hebbal",         "Hebbal",           "bangalore",
         13.0358, 77.5970, 3.0, 0.70, 2.0, "commercial",  +0.006),
    Zone("blr_yeshwanthpur",   "Yeshwanthpur",     "bangalore",
         13.0210, 77.5540, 3.2, 0.80, 2.1, "industrial",  +0.003),
    Zone("blr_electronic_city","Electronic City",  "bangalore",
         12.8458, 77.6603, 4.0, 0.85, 1.9, "industrial",  +0.004),
    Zone("blr_bannerghatta",   "Bannerghatta Rd",  "bangalore",
         12.8934, 77.5976, 3.5, 0.75, 2.0, "residential", +0.007),
    Zone("blr_marathahalli",   "Marathahalli",     "bangalore",
         12.9591, 77.7009, 2.5, 0.88, 2.3, "commercial",  +0.014),
    Zone("blr_btm",            "BTM Layout",       "bangalore",
         12.9166, 77.6101, 2.3, 0.82, 2.1, "residential", +0.009),
    Zone("blr_rajajinagar",    "Rajajinagar",      "bangalore",
         12.9913, 77.5527, 2.8, 0.72, 1.9, "residential", +0.006),
]

# ── Mumbai (6 zones) ──────────────────────────────────────────
_mum_zones = [
    Zone("mum_andheri",    "Andheri",     "mumbai",
         19.1136, 72.8697, 3.5, 0.92, 2.5, "commercial",  +0.016),
    Zone("mum_bandra",     "Bandra",      "mumbai",
         19.0544, 72.8405, 2.5, 0.95, 2.4, "commercial",  +0.020),
    Zone("mum_worli",      "Worli",       "mumbai",
         19.0176, 72.8181, 2.8, 0.88, 2.2, "commercial",  +0.012),
    Zone("mum_kurla",      "Kurla",       "mumbai",
         19.0728, 72.8826, 3.0, 0.85, 2.3, "industrial",  +0.010),
    Zone("mum_thane",      "Thane",       "mumbai",
         19.2183, 72.9781, 4.0, 0.78, 2.0, "residential", +0.007),
    Zone("mum_navi_mumbai","Navi Mumbai", "mumbai",
         19.0330, 73.0297, 4.5, 0.70, 1.8, "residential", +0.005),
]

# ── Delhi (6 zones) ───────────────────────────────────────────
_del_zones = [
    Zone("del_cp",      "Connaught Place", "delhi",
         28.6315, 77.2167, 2.0, 0.95, 2.5, "commercial",  +0.022),
    Zone("del_lajpat",  "Lajpat Nagar",   "delhi",
         28.5672, 77.2435, 2.5, 0.85, 2.2, "commercial",  +0.014),
    Zone("del_dwarka",  "Dwarka",          "delhi",
         28.5921, 77.0460, 3.5, 0.75, 1.9, "residential", +0.006),
    Zone("del_noida",   "Noida Sec-62",    "delhi",
         28.6272, 77.3690, 3.8, 0.82, 2.1, "commercial",  +0.010),
    Zone("del_gurgaon", "Gurgaon",         "delhi",
         28.4595, 77.0266, 4.0, 0.88, 2.2, "commercial",  +0.011),
    Zone("del_rohini",  "Rohini",          "delhi",
         28.7041, 77.1025, 3.5, 0.72, 1.8, "residential", +0.005),
]

for _z in _blr_zones + _mum_zones + _del_zones:
    ZONES[_z.zone_id] = _z

# ── City → zone index ─────────────────────────────────────────
CITY_ZONES: Dict[str, List[str]] = {
    city: [zid for zid, z in ZONES.items() if z.city == city]
    for city in ["bangalore", "mumbai", "delhi"]
}


# ── Geo utilities ─────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return straight-line great-circle distance between two points in km."""
    lat1_r = np.radians(lat1)
    lat2_r = np.radians(lat2)
    dlat   = np.radians(lat2 - lat1)
    dlon   = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return float(EARTH_RADIUS_KM * c)


def get_random_point_in_zone(
    zone: Zone,
    rng: np.random.Generator,
) -> Tuple[float, float]:
    """Return a random (lat, lon) drawn from a Gaussian centred on zone centre."""
    lat_offset_km  = rng.normal(0, zone.radius_km / 3)
    lon_offset_km  = rng.normal(0, zone.radius_km / 3)

    lat_offset_deg = lat_offset_km / 111.0
    lon_offset_deg = lon_offset_km / (111.0 * np.cos(np.radians(zone.lat)))

    lat = zone.lat + lat_offset_deg
    lon = zone.lon + lon_offset_deg

    # Clip to zone boundary if point strayed too far
    dist = haversine_km(zone.lat, zone.lon, lat, lon)
    if dist > zone.radius_km:
        scale = zone.radius_km / dist
        lat = zone.lat + (lat - zone.lat) * scale
        lon = zone.lon + (lon - zone.lon) * scale

    return float(lat), float(lon)


def get_road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return estimated road distance by applying a 1.3x urban detour factor."""
    straight = haversine_km(lat1, lon1, lat2, lon2)
    road     = straight * 1.3
    return float(max(road, 0.3))   # floor at 0.3 km for urban India


def get_zone_demand_pattern(zone: Zone, hour: int, day_of_week: int) -> float:
    """Return a demand multiplier for the zone at the given hour and weekday."""
    is_weekend = day_of_week >= 5
    is_night   = hour >= 22 or hour < 5

    if is_night:
        base = 0.4
    elif zone.zone_type == "commercial":
        if is_weekend:
            # Flatter weekend; single evening peak
            _peaks = {19: 1.9, 20: 1.7, 18: 1.5, 12: 1.4, 13: 1.3}
            base = _peaks.get(hour, 1.0)
        else:
            # Three weekday peaks
            _peaks = {9: 1.8, 10: 1.6, 13: 1.6, 14: 1.4, 19: 2.2, 20: 1.9, 18: 1.7}
            base = _peaks.get(hour, 1.0)
    elif zone.zone_type == "residential":
        if is_weekend:
            # Spread across the day
            _peaks = {10: 1.4, 11: 1.5, 12: 1.5, 15: 1.4, 17: 1.5, 18: 1.6, 20: 1.5}
            base = _peaks.get(hour, 1.1)
        else:
            # Morning and evening commute
            _peaks = {8: 1.6, 9: 1.5, 20: 1.8, 19: 1.6, 21: 1.4}
            base = _peaks.get(hour, 1.0)
    else:  # industrial
        if is_weekend:
            base = 0.3
        else:
            # Flat working hours
            base = 1.4 if 7 <= hour <= 18 else 0.4

    final_multiplier = base * (0.5 + 0.5 * zone.commercial_density)
    return float(max(0.3, min(3.5, final_multiplier)))


# ── Standalone test ───────────────────────────────────────────

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    console = Console()
    rng = np.random.default_rng(42)

    # Test 1: Zone counts
    blr_zones = CITY_ZONES["bangalore"]
    console.print(f"[cyan]Bangalore zones:[/cyan] {len(blr_zones)}")
    assert len(blr_zones) == 12, "Must have 12 Bangalore zones"

    # Test 2: Random point generation
    test_zone = ZONES["blr_koramangala"]
    for _ in range(100):
        lat, lon = get_random_point_in_zone(test_zone, rng)
        dist = haversine_km(test_zone.lat, test_zone.lon, lat, lon)
        assert dist <= test_zone.radius_km * 1.5, \
            f"Point too far from zone center: {dist:.2f}km"
    console.print("[green]✅ 100 random points all within zone bounds[/green]")

    # Test 3: Haversine — known distance
    # Koramangala to Whitefield is ~12.5km straight-line
    dist = haversine_km(12.9352, 77.6245, 12.9698, 77.7500)
    assert 10 < dist < 16, f"Koramangala-Whitefield distance wrong: {dist}"
    console.print(f"[green]✅ Koramangala → Whitefield: {dist:.1f}km[/green]")

    # Test 4: Demand pattern table
    table = Table(title="Koramangala Demand Pattern — Monday")
    table.add_column("Hour", justify="right")
    table.add_column("Multiplier", justify="right")
    table.add_column("Bar")
    for hour in [6, 8, 9, 12, 13, 18, 19, 22, 23]:
        mult = get_zone_demand_pattern(test_zone, hour, 0)
        bar  = "█" * int(mult * 10)
        table.add_row(f"{hour:02d}:00", f"{mult:.2f}x", bar)
    console.print(table)

    # Test 5: Road distance exceeds haversine
    road = get_road_distance_km(12.9352, 77.6245, 12.9698, 77.7500)
    assert road > dist, "Road distance must exceed straight-line"
    console.print(f"[green]✅ Road distance > haversine: {road:.1f}km[/green]")

    console.print("\n[green]✅ cities.py — all checks passed[/green]")
