# streamlit_app.py

import streamlit as st
import requests
import pandas as pd
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from io import BytesIO
from PIL import Image
import base64

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Аналіз транспорту", layout="wide")
st.title("Аналіз впливу транспорту на екологію міста")

# --- Ініціалізація змінних сесії ---
# Крайні точки маршруту
if 'points' not in st.session_state:
    st.session_state.points = []

# Повний маршрут
if 'route_data' not in st.session_state:
    st.session_state.route_data = None

# Стан ініціалізації мапи міста
if "initialized" not in st.session_state:
    st.session_state.initialized = False

# Наявність екологічних даних
if "collected_data" not in st.session_state:
    st.session_state.collected_data = False

# Результати статистичного аналізу
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

city = st.text_input("Введіть назву міста:", value="Kyiv")

# Ініціалізація кнопок
if st.button("Ініціалізувати місто"):
    res = requests.get(f"{API_URL}/cities/{city}/initialize")
    st.session_state.initialized = True
    st.write(res.json())

if st.button("Зібрати дані"):
    res = requests.get(f"{API_URL}/cities/{city}/collect_data")
    st.session_state.collected_data = True
    st.write(res.json())



# --- Вибір шарів для відображення ---
st.sidebar.header("Шари карти")
show_pollution = st.sidebar.checkbox("Показати забруднення", value=True)
show_heatmap = st.sidebar.checkbox("Теплова мапа", value=True)
show_routes = st.sidebar.checkbox("Показати маршрут", value=False)
show_clusters = st.sidebar.checkbox("Показати кластери", value=False)
enable_routing = st.sidebar.checkbox("Режим побудови маршруту", value=False)

st.write(st.session_state.initialized, st.session_state.collected_data)
if st.session_state.initialized and st.session_state.collected_data:

    if st.button("Аналіз даних"):
        res = requests.get(f"{API_URL}/cities/{city}/full_analysis")
        st.session_state.analysis_results = res.json()

    if st.session_state.analysis_results:
        st.write(st.session_state.analysis_results)

    # --- Базова мапа ---
    m = folium.Map(location=[50.45, 30.52], zoom_start=12)
    folium.LatLngPopup().add_to(m)

    # --- Забруднення ---
    if show_pollution:
        try:
            resp = requests.get(f"http://localhost:8000/cities/{city}/pollution")
            resp.raise_for_status()
            data = resp.json()

            fg_pollution = folium.FeatureGroup(name="Забруднення", overlay=True, control=True)

            if show_heatmap:
                heat_data = []
                for item in data:
                    weight = 6 - item['aqi']
                    heat_data.append([item["latitude"], item["longitude"], weight])
                HeatMap(
                    heat_data,
                    min_opacity=0.9,
                    max_val=5,
                    radius=10,
                    blur=15,
                ).add_to(fg_pollution)
            else:
                for item in data:
                    color = {
                        1: "red", 2: "orange", 3: "yellow", 4: "green", 5: "blue"
                    }.get(item['aqi'], "gray")
                    folium.CircleMarker(
                        location=[item["latitude"], item["longitude"]],
                        radius=6,
                        color=color,
                        fill=True,
                        fill_opacity=0.6,
                        popup=f"AQI: {item['aqi']}"
                    ).add_to(fg_pollution)

            fg_pollution.add_to(m)
        except Exception as e:
            st.error(f"Помилка при завантаженні забруднення: {e}")

    # --- Кластери ---
    if show_clusters:
        try:
            resp = requests.get(f"http://localhost:8000/cities/{city}/clusters")
            resp.raise_for_status()
            clusters = resp.json()

            fg_clusters = folium.FeatureGroup(name="Кластери", overlay=True, control=True)
            for item in clusters:
                folium.CircleMarker(
                    location=[item["latitude"], item["longitude"]],
                    radius=5,
                    color="green",
                    fill=True,
                    fill_opacity=0.5,
                    popup=f"Кластер: {item['cluster']}"
                ).add_to(fg_clusters)
            fg_clusters.add_to(m)
        except Exception as e:
            st.error(f"Помилка при завантаженні кластерів: {e}")

    # --- Маршрути ---
    fg_routes = None
    if show_routes or enable_routing:
        fg_routes = folium.FeatureGroup(name="Маршрути", overlay=True, control=True)

        if st.session_state.points:
            for i, point in enumerate(st.session_state.points):
                folium.Marker(
                    location=point,
                    popup=f"Точка {i + 1}",
                    icon=folium.Icon(color="red" if i == 0 else "green", icon="flag")
                ).add_to(fg_routes)

        if st.session_state.route_data:
            if st.session_state.route_data:
                folium.PolyLine(
                    locations=st.session_state.route_data,
                    color="blue",
                    weight=3,
                    opacity=0.8
                ).add_to(fg_routes)

        if fg_routes:
            fg_routes.add_to(m)

    # --- Обробка кліку по мапі ---
    output = st_folium(m, width=700, height=500)

    if enable_routing and output and output.get("last_clicked"):
        latlon = output["last_clicked"]
        if len(st.session_state.points) < 2:
            st.session_state.points.append((latlon["lat"], latlon["lng"]))

    # --- Інтерфейс побудови маршруту ---
    if enable_routing:
        st.markdown("### 📍 Побудова маршруту")
        if len(st.session_state.points) > 0:
            st.write(f"Вибрані точки ({len(st.session_state.points)}/2):")
            for i, point in enumerate(st.session_state.points):
                st.write(f"Точка {i + 1}: {point}")

        if len(st.session_state.points) == 2:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔁 Обчислити маршрут"):
                    try:
                        response = requests.post(
                            f"http://localhost:8000/cities/{city}/route",
                            json={
                                "start": st.session_state.points[0],
                                "end": st.session_state.points[1]
                            }
                        )
                        if response.status_code == 200:
                            st.session_state.route_data = response.json()
                        else:
                            st.error("Помилка побудови маршруту")
                    except Exception as e:
                        st.error(f"Помилка: {e}")
            with col2:
                if st.button("🔄 Скинути точки"):
                    st.session_state.points = []
                    st.session_state.route_data = None

    # --- Контролер шарів ---
    folium.LayerControl(collapsed=False).add_to(m)

