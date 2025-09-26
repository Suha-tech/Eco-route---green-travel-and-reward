# app.py
"""
EcoRoute – Green Travel Assistant
Features:
- Route planning (OpenCage + OSRM)
- CO₂ Calculator
- Leaderboard & Gamification (only real user)
- Eco Rewards Marketplace
- Impact Dashboard
- Best Eco-Time Suggestion
- Pollution Heatmap
"""

import math
import time
import requests
import streamlit as st
import pandas as pd
import folium
from geopy.geocoders import OpenCage
from streamlit_folium import st_folium
import random

# ---------------------------
# Config
# ---------------------------
OPENCAGE_KEY = "b007205c29cd4059a80ea15029950bba"  # 🔑 Your API key
geolocator = OpenCage(api_key=OPENCAGE_KEY)
OSRM_BASE = "http://router.project-osrm.org"

st.set_page_config(page_title="EcoRoute", layout="wide")

# ---------------------------
# Helper functions
# ---------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = map(math.radians, [lat1, lat2])
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def geocode_place(place_name):
    try:
        loc = geolocator.geocode(place_name, exactly_one=True, timeout=10)
        if loc:
            return (loc.address, loc.latitude, loc.longitude)
    except:
        return (None, None, None)
    return (None, None, None)

def mode_to_osrm_profile(mode):
    if mode in ("cycle", "cycling", "bicycle"):
        return "cycling"
    if mode in ("walk", "walking", "pedestrian"):
        return "walking"
    return "driving"

def get_route_osrm(lat1, lon1, lat2, lon2, profile="driving", retries=3):
    coords = f"{lon1},{lat1};{lon2},{lat2}"
    url = f"{OSRM_BASE}/route/v1/{profile}/{coords}?overview=full&geometries=geojson"
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("routes"):
                    route = data["routes"][0]
                    dist_km = route["distance"] / 1000
                    dur_min = route["duration"] / 60
                    geom = [[c[1], c[0]] for c in route["geometry"]["coordinates"]]
                    return {"distance_km": dist_km, "duration_min": dur_min, "geometry": geom}
        except:
            pass
        time.sleep(1)
    return None

def fallback_straight_line(lat1, lon1, lat2, lon2):
    dist_km = haversine_km(lat1, lon1, lat2, lon2)
    dur_min = (dist_km / 40.0) * 60
    return {"distance_km": dist_km, "duration_min": dur_min, "geometry": [[lat1, lon1], [lat2, lon2]]}

# Emission factors (kg CO₂ per km)
EMISSION_FACTORS = {
    "car": 0.192,
    "bus": 0.105,
    "ev": 0.050,
    "cycle": 0.0,
    "walk": 0.0,
    "metro": 0.041
}

def estimate_co2(distance_km, mode):
    return round(distance_km * EMISSION_FACTORS.get(mode, 0.0), 3)

def trees_equivalent(co2_kg):
    return round(co2_kg / 21.0, 2) if co2_kg > 0 else 0

# ---------------------------
# UI Layout
# ---------------------------
st.title("🌱 EcoRoute – Green Travel & Rewards")
st.markdown("Plan eco-friendly trips, save CO₂, earn Green Points, and redeem rewards!")

# Sidebar – user profile
st.sidebar.header("👤 User Profile")
username = st.sidebar.text_input("Enter your name", "guest")
if "green_points" not in st.session_state:
    st.session_state.green_points = 50
st.sidebar.metric("Your Green Points", st.session_state.green_points)

# Tabs for navigation
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚦 Trip Planner", "📊 Dashboard", "🏆 Leaderboard", "🛍️ Rewards Marketplace", "🌍 Pollution Heatmap"
])

# ---------------------------
# Trip Planner
# ---------------------------
with tab1:
    st.subheader("Plan a Trip")

    col1, col2 = st.columns(2)
    with col1:
        origin = st.text_input("From", "Connaught Place, Delhi, India")
    with col2:
        destination = st.text_input("To", "Qutub Minar, Delhi, India")

    mode = st.selectbox("Transport mode", ["car", "bus", "metro", "ev", "cycle", "walk"])

    if st.button("Get Route & Compute CO₂"):
        o_name, o_lat, o_lon = geocode_place(origin)
        d_name, d_lat, d_lon = geocode_place(destination)

        if not (o_lat and d_lat):
            st.error("❌ Failed to geocode. Try a more specific address.")
        else:
            st.success(f"From: **{o_name}** → To: **{d_name}**")

            profile = mode_to_osrm_profile(mode)
            route = get_route_osrm(o_lat, o_lon, d_lat, d_lon, profile) or fallback_straight_line(o_lat, o_lon, d_lat, d_lon)

            dist, dur = route["distance_km"], route["duration_min"]
            co2 = estimate_co2(dist, mode)
            trees = trees_equivalent(co2)
            saved = estimate_co2(dist, "car") - co2

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Distance (km)", f"{dist:.2f}")
            c2.metric("Duration (min)", f"{dur:.1f}")
            c3.metric("CO₂ (kg)", f"{co2:.2f}")
            c4.metric("🌳 Trees offset", f"{trees:.2f}")

            if mode != "car":
                earned = int(saved * 10)
                st.session_state.green_points += earned
                st.success(f"🎉 You earned {earned} Green Points! Total = {st.session_state.green_points}")

            # Map visualization
            fmap = folium.Map(location=[(o_lat+d_lat)/2, (o_lon+d_lon)/2], zoom_start=12)
            folium.PolyLine(route["geometry"], color="blue", weight=5).add_to(fmap)
            folium.Marker([o_lat, o_lon], popup="Origin", icon=folium.Icon(color="green")).add_to(fmap)
            folium.Marker([d_lat, d_lon], popup="Destination", icon=folium.Icon(color="red")).add_to(fmap)
            st_folium(fmap, width=800, height=450)

# ---------------------------
# Impact Dashboard
# ---------------------------
with tab2:
    st.subheader("📊 Impact Dashboard")
    impact_data = {
        "Metric": ["Total CO₂ saved", "Fuel saved", "Equivalent trees planted"],
        "Value": ["125 kg", "45 L", "6 trees"]
    }
    st.table(pd.DataFrame(impact_data))

    best_time = random.choice(["7:30 AM", "11:00 AM", "4:30 PM"])
    st.info(f"⏰ Best Eco-Time to Travel: **{best_time}**")

# ---------------------------
# Leaderboard (only real user)
# ---------------------------
with tab3:
    st.subheader("🏆 Eco-Friendly Leaderboard")
    leaderboard = pd.DataFrame({
        "User": [username],
        "Green Points": [st.session_state.green_points]
    })
    st.table(leaderboard)

# ---------------------------
# Rewards Marketplace
# ---------------------------
with tab4:
    st.subheader("🛍️ Eco Rewards Marketplace")
    st.write("Redeem your Green Points for real eco-friendly perks:")

    rewards = [
        {"item": "🌿 10% Discount at Organic Store", "cost": 50},
        {"item": "🚴 Free Bicycle Rental (1 day)", "cost": 100},
        {"item": "☕ Free Coffee at Eco Café", "cost": 30},
        {"item": "🎫 Metro Travel Pass (1 day)", "cost": 80},
    ]

    for reward in rewards:
        col1, col2 = st.columns([3,1])
        with col1:
            st.write(f"{reward['item']} — {reward['cost']} Green Points")
        with col2:
            if st.button(f"Redeem {reward['item']}"):
                if st.session_state.green_points >= reward["cost"]:
                    st.session_state.green_points -= reward["cost"]
                    st.success(f"✅ Redeemed {reward['item']}! Remaining Points = {st.session_state.green_points}")
                else:
                    st.error("Not enough Green Points.")

# ---------------------------
# Smart Pollution Heatmap (demo)
# ---------------------------
with tab5:
    st.subheader("🌍 Traffic Pollution Heatmap (Demo)")
    pollution_map = folium.Map(location=[28.61, 77.23], zoom_start=11)
    for lat, lon, level in [(28.61, 77.20, "High"), (28.65, 77.25, "Medium"), (28.55, 77.28, "Low")]:
        folium.CircleMarker(
            location=[lat, lon],
            radius=20,
            color="red" if level=="High" else "orange" if level=="Medium" else "green",
            fill=True, fill_opacity=0.5,
            popup=f"Pollution: {level}"
        ).add_to(pollution_map)
    st_folium(pollution_map, width=800, height=400)


