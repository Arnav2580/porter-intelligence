"""
Porter-scale digital twin city profiles.

Profiles are weighted to simulate a 22-city operating footprint with
city-specific zone hubs, demand curves, and fraud pressure. The city set
matches Porter's current public city footprint and is used by the live
simulator to create a more credible operating environment.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class TwinZone:
    zone_id: str
    name: str
    lat: float
    lon: float
    demand_bias: float
    fraud_bias: float
    zone_type: str


@dataclass(frozen=True)
class CityTwinProfile:
    city_id: str
    display_name: str
    base_trip_share: float
    fraud_bias: float
    weekday_peak_hours: Tuple[int, ...]
    weekend_peak_hours: Tuple[int, ...]
    vehicle_weights: Dict[str, float]
    zones: Tuple[TwinZone, ...]


def _profile(
    city_id: str,
    display_name: str,
    share: float,
    fraud_bias: float,
    weekday_peaks: Tuple[int, ...],
    weekend_peaks: Tuple[int, ...],
    vehicle_weights: Dict[str, float],
    zones: Tuple[TwinZone, ...],
) -> CityTwinProfile:
    return CityTwinProfile(
        city_id=city_id,
        display_name=display_name,
        base_trip_share=share,
        fraud_bias=fraud_bias,
        weekday_peak_hours=weekday_peaks,
        weekend_peak_hours=weekend_peaks,
        vehicle_weights=vehicle_weights,
        zones=zones,
    )


CITY_TWIN_PROFILES: Dict[str, CityTwinProfile] = {
    "ahmedabad": _profile(
        "ahmedabad",
        "Ahmedabad",
        0.05,
        1.02,
        (9, 10, 13, 18, 19),
        (11, 12, 18, 19),
        {
            "two_wheeler": 0.38,
            "three_wheeler": 0.17,
            "mini_truck": 0.28,
            "truck_14ft": 0.11,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("amd_cg_road", "CG Road", 23.0275, 72.5600, 1.20, 1.08, "commercial"),
            TwinZone("amd_sg_highway", "SG Highway", 23.0600, 72.5200, 1.08, 1.00, "commercial"),
        ),
    ),
    "bangalore": _profile(
        "bangalore",
        "Bangalore",
        0.18,
        1.05,
        (8, 9, 13, 18, 19, 20),
        (10, 11, 18, 19, 20),
        {
            "two_wheeler": 0.45,
            "three_wheeler": 0.20,
            "mini_truck": 0.22,
            "truck_14ft": 0.08,
            "truck_17ft": 0.05,
        },
        (
            TwinZone("blr_koramangala", "Koramangala", 12.9352, 77.6245, 1.25, 1.10, "commercial"),
            TwinZone("blr_whitefield", "Whitefield", 12.9698, 77.7500, 1.18, 1.04, "commercial"),
            TwinZone("blr_electronic_city", "Electronic City", 12.8458, 77.6603, 1.05, 0.98, "industrial"),
        ),
    ),
    "chandigarh": _profile(
        "chandigarh",
        "Chandigarh",
        0.02,
        0.98,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.34,
            "three_wheeler": 0.15,
            "mini_truck": 0.31,
            "truck_14ft": 0.13,
            "truck_17ft": 0.07,
        },
        (
            TwinZone("cdg_sector17", "Sector 17", 30.7390, 76.7820, 1.15, 1.02, "commercial"),
            TwinZone("cdg_industrial_area", "Industrial Area", 30.7040, 76.8010, 0.96, 0.95, "industrial"),
        ),
    ),
    "chennai": _profile(
        "chennai",
        "Chennai",
        0.07,
        1.01,
        (8, 9, 12, 18, 19),
        (10, 11, 17, 18),
        {
            "two_wheeler": 0.41,
            "three_wheeler": 0.16,
            "mini_truck": 0.25,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("maa_omr", "OMR", 12.9140, 80.2290, 1.16, 1.02, "commercial"),
            TwinZone("maa_koyambedu", "Koyambedu", 13.0690, 80.1940, 1.08, 0.99, "commercial"),
        ),
    ),
    "coimbatore": _profile(
        "coimbatore",
        "Coimbatore",
        0.02,
        0.97,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.33,
            "three_wheeler": 0.14,
            "mini_truck": 0.34,
            "truck_14ft": 0.13,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("cjb_gandhipuram", "Gandhipuram", 11.0180, 76.9670, 1.08, 0.98, "commercial"),
            TwinZone("cjb_peelamedu", "Peelamedu", 11.0300, 77.0170, 1.00, 0.95, "commercial"),
        ),
    ),
    "delhi_ncr": _profile(
        "delhi_ncr",
        "Delhi NCR",
        0.11,
        1.07,
        (8, 9, 13, 18, 19, 20),
        (10, 11, 18, 19),
        {
            "two_wheeler": 0.37,
            "three_wheeler": 0.17,
            "mini_truck": 0.28,
            "truck_14ft": 0.11,
            "truck_17ft": 0.07,
        },
        (
            TwinZone("del_cp", "Connaught Place", 28.6315, 77.2167, 1.26, 1.12, "commercial"),
            TwinZone("del_gurgaon_cybercity", "Gurgaon Cyber City", 28.4940, 77.0890, 1.20, 1.06, "commercial"),
            TwinZone("del_noida_62", "Noida Sector 62", 28.6272, 77.3690, 1.10, 1.01, "commercial"),
        ),
    ),
    "hyderabad": _profile(
        "hyderabad",
        "Hyderabad",
        0.09,
        1.03,
        (8, 9, 13, 18, 19),
        (10, 11, 18, 19),
        {
            "two_wheeler": 0.40,
            "three_wheeler": 0.15,
            "mini_truck": 0.27,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("hyd_hitec_city", "HITEC City", 17.4490, 78.3910, 1.22, 1.07, "commercial"),
            TwinZone("hyd_secunderabad", "Secunderabad", 17.4390, 78.4980, 1.08, 0.99, "commercial"),
        ),
    ),
    "indore": _profile(
        "indore",
        "Indore",
        0.02,
        0.99,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.35,
            "three_wheeler": 0.14,
            "mini_truck": 0.33,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("idr_vijay_nagar", "Vijay Nagar", 22.7530, 75.8930, 1.12, 1.00, "commercial"),
            TwinZone("idr_rajwada", "Rajwada", 22.7170, 75.8570, 1.00, 0.96, "commercial"),
        ),
    ),
    "jaipur": _profile(
        "jaipur",
        "Jaipur",
        0.03,
        0.99,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.36,
            "three_wheeler": 0.15,
            "mini_truck": 0.31,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("jpr_malviya_nagar", "Malviya Nagar", 26.8550, 75.8060, 1.08, 0.99, "commercial"),
            TwinZone("jpr_vaishali_nagar", "Vaishali Nagar", 26.9110, 75.7450, 0.98, 0.95, "residential"),
        ),
    ),
    "kanpur": _profile(
        "kanpur",
        "Kanpur",
        0.015,
        0.98,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.32,
            "three_wheeler": 0.16,
            "mini_truck": 0.34,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("knp_swaroop_nagar", "Swaroop Nagar", 26.4810, 80.3180, 1.02, 0.96, "commercial"),
            TwinZone("knp_govind_nagar", "Govind Nagar", 26.4490, 80.2960, 0.96, 0.93, "industrial"),
        ),
    ),
    "kochi": _profile(
        "kochi",
        "Kochi",
        0.03,
        0.99,
        (9, 10, 18, 19),
        (10, 11, 17, 18),
        {
            "two_wheeler": 0.34,
            "three_wheeler": 0.14,
            "mini_truck": 0.34,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("koch_edappally", "Edappally", 10.0270, 76.3080, 1.08, 0.97, "commercial"),
            TwinZone("koch_kakkanad", "Kakkanad", 10.0150, 76.3410, 1.04, 0.95, "commercial"),
        ),
    ),
    "kolkata": _profile(
        "kolkata",
        "Kolkata",
        0.05,
        1.02,
        (8, 9, 13, 18, 19),
        (11, 12, 18, 19),
        {
            "two_wheeler": 0.37,
            "three_wheeler": 0.18,
            "mini_truck": 0.28,
            "truck_14ft": 0.11,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("kol_salt_lake", "Salt Lake", 22.5760, 88.4330, 1.15, 1.02, "commercial"),
            TwinZone("kol_park_street", "Park Street", 22.5530, 88.3520, 1.12, 1.05, "commercial"),
        ),
    ),
    "lucknow": _profile(
        "lucknow",
        "Lucknow",
        0.03,
        0.98,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.34,
            "three_wheeler": 0.15,
            "mini_truck": 0.33,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("lko_gomti_nagar", "Gomti Nagar", 26.8510, 81.0060, 1.08, 0.97, "commercial"),
            TwinZone("lko_alambagh", "Alambagh", 26.8100, 80.8960, 0.98, 0.94, "residential"),
        ),
    ),
    "ludhiana": _profile(
        "ludhiana",
        "Ludhiana",
        0.015,
        0.97,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.31,
            "three_wheeler": 0.14,
            "mini_truck": 0.35,
            "truck_14ft": 0.14,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("ldh_firoz_gandhi", "Feroze Gandhi Market", 30.9000, 75.8200, 1.00, 0.95, "commercial"),
            TwinZone("ldh_industrial_area", "Industrial Area", 30.8910, 75.8700, 0.94, 0.93, "industrial"),
        ),
    ),
    "mumbai": _profile(
        "mumbai",
        "Mumbai",
        0.12,
        1.08,
        (8, 9, 13, 18, 19, 20),
        (11, 12, 18, 19, 20),
        {
            "two_wheeler": 0.39,
            "three_wheeler": 0.16,
            "mini_truck": 0.25,
            "truck_14ft": 0.12,
            "truck_17ft": 0.08,
        },
        (
            TwinZone("mum_andheri", "Andheri", 19.1136, 72.8697, 1.23, 1.08, "commercial"),
            TwinZone("mum_bkc", "BKC", 19.0610, 72.8650, 1.20, 1.06, "commercial"),
            TwinZone("mum_thane", "Thane", 19.2183, 72.9781, 1.02, 0.97, "residential"),
        ),
    ),
    "nagpur": _profile(
        "nagpur",
        "Nagpur",
        0.02,
        0.97,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.31,
            "three_wheeler": 0.15,
            "mini_truck": 0.35,
            "truck_14ft": 0.13,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("ngp_sitabuldi", "Sitabuldi", 21.1460, 79.0840, 1.00, 0.95, "commercial"),
            TwinZone("ngp_hingna", "Hingna", 21.1050, 78.9970, 0.94, 0.92, "industrial"),
        ),
    ),
    "nashik": _profile(
        "nashik",
        "Nashik",
        0.02,
        0.96,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.32,
            "three_wheeler": 0.14,
            "mini_truck": 0.35,
            "truck_14ft": 0.13,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("nsk_satpur", "Satpur", 19.9980, 73.7310, 0.96, 0.92, "industrial"),
            TwinZone("nsk_college_road", "College Road", 20.0050, 73.7600, 1.02, 0.95, "commercial"),
        ),
    ),
    "pune": _profile(
        "pune",
        "Pune",
        0.07,
        1.01,
        (8, 9, 13, 18, 19),
        (10, 11, 18, 19),
        {
            "two_wheeler": 0.40,
            "three_wheeler": 0.15,
            "mini_truck": 0.27,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("pne_hinjawadi", "Hinjawadi", 18.5910, 73.7380, 1.16, 1.02, "commercial"),
            TwinZone("pne_kharadi", "Kharadi", 18.5510, 73.9400, 1.10, 0.99, "commercial"),
        ),
    ),
    "surat": _profile(
        "surat",
        "Surat",
        0.04,
        0.99,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.35,
            "three_wheeler": 0.15,
            "mini_truck": 0.32,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("srt_adajan", "Adajan", 21.1950, 72.7930, 1.04, 0.96, "commercial"),
            TwinZone("srt_sachin", "Sachin", 21.0870, 72.8810, 0.96, 0.94, "industrial"),
        ),
    ),
    "trivandrum": _profile(
        "trivandrum",
        "Trivandrum",
        0.015,
        0.96,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.33,
            "three_wheeler": 0.14,
            "mini_truck": 0.35,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("tvm_technopark", "Technopark", 8.5580, 76.8810, 1.08, 0.97, "commercial"),
            TwinZone("tvm_palayam", "Palayam", 8.5080, 76.9500, 0.96, 0.93, "commercial"),
        ),
    ),
    "vadodara": _profile(
        "vadodara",
        "Vadodara",
        0.02,
        0.96,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.33,
            "three_wheeler": 0.14,
            "mini_truck": 0.35,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("vad_alkapuri", "Alkapuri", 22.3100, 73.1710, 1.02, 0.95, "commercial"),
            TwinZone("vad_makarpura", "Makarpura", 22.2800, 73.1900, 0.96, 0.92, "industrial"),
        ),
    ),
    "visakhapatnam": _profile(
        "visakhapatnam",
        "Visakhapatnam",
        0.02,
        0.98,
        (9, 10, 18, 19),
        (11, 12, 18),
        {
            "two_wheeler": 0.34,
            "three_wheeler": 0.14,
            "mini_truck": 0.34,
            "truck_14ft": 0.12,
            "truck_17ft": 0.06,
        },
        (
            TwinZone("viz_maddilapalem", "Maddilapalem", 17.7380, 83.3180, 1.04, 0.96, "commercial"),
            TwinZone("viz_gajuwaka", "Gajuwaka", 17.7000, 83.2000, 0.98, 0.94, "industrial"),
        ),
    ),
}


def city_peak_multiplier(profile: CityTwinProfile, hour: int, day_of_week: int) -> float:
    is_weekend = day_of_week >= 5
    peaks = profile.weekend_peak_hours if is_weekend else profile.weekday_peak_hours
    if hour in peaks:
        return 1.35
    if hour >= 22 or hour < 5:
        return 0.45
    if 6 <= hour <= 7 or 20 <= hour <= 21:
        return 0.92
    return 1.0


def zone_demand_multiplier(
    profile: CityTwinProfile,
    zone: TwinZone,
    hour: int,
    day_of_week: int,
) -> float:
    demand = city_peak_multiplier(profile, hour, day_of_week) * zone.demand_bias
    return max(0.35, min(3.5, round(demand, 3)))


def normalised_city_weights(
    hour: int,
    day_of_week: int,
    active_cities: Iterable[str],
) -> Dict[str, float]:
    weighted: Dict[str, float] = {}
    total = 0.0
    for city_id in active_cities:
        profile = CITY_TWIN_PROFILES[city_id]
        weight = profile.base_trip_share * city_peak_multiplier(profile, hour, day_of_week)
        weighted[city_id] = weight
        total += weight

    if total <= 0:
        n = max(len(weighted), 1)
        return {city_id: 1.0 / n for city_id in weighted}

    return {city_id: weight / total for city_id, weight in weighted.items()}

