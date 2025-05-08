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
st.title("🌍 Аналіз впливу транспорту на екологію міста")

city = st.text_input("Введіть назву міста:", value="Kyiv")

# Ініціалізація кнопок
if st.button("🔄 Ініціалізувати місто"):
    res = requests.get(f"{API_URL}/cities/{city}/initialize")
    st.write(res.json())

if st.button("📥 Зібрати дані"):
    res = requests.get(f"{API_URL}/cities/{city}/collect_data")
    st.write(res.json())

if "points" not in st.session_state:
    st.session_state.points = []
if "route_data" not in st.session_state:
    st.session_state.route_data = None

# --- 🔽 Вибір режиму відображення мапи ---
mode = st.selectbox("Оберіть режим карти:", [
    "🌍 Забруднення",
    "🗺️ Граф доріг",
    "📍 Побудова маршруту",
    "🧩 Кластери"
])

# --- Ініціалізація змінних сесії для точок маршруту ---
if 'points' not in st.session_state:
    st.session_state.points = []
if 'route_data' not in st.session_state:
    st.session_state.route_data = None

# --- Базова мапа ---
m = folium.Map(location=[50.45, 30.52], zoom_start=12)
folium.LatLngPopup().add_to(m)

# --- Перемикачі для оверлеїв ---
show_pollution = st.checkbox("Забруднення", value=True)
show_heatmap = st.checkbox("Теплова мапа", value=True)
show_routes = st.checkbox("Маршрути", value=False)
show_clusters = st.checkbox("Кластери", value=False)

# --- Базова карта ---
m = folium.Map(location=[50.45, 30.52], zoom_start=12)

output = st_folium(m, width=700, height=500)

# --- Рівень забруднення ---
if show_pollution:
    try:
        resp = requests.get(f"http://localhost:8000/cities/{city}/pollution")
        resp.raise_for_status()
        data = resp.json()

        fg_pollution = folium.FeatureGroup(name="Забруднення", overlay=True, control=True)

        if show_heatmap:
            # Підготовка даних для теплової карти
            heat_data = []
            for item in data:
                # Вага для теплової карти на основі AQI (чим нижче AQI, тим вище забруднення)
                weight = 6 - item['aqi']  # AQI 1 (найгірше) отримає вагу 5, AQI 5 (найкраще) отримає вагу 1
                heat_data.append([item["latitude"], item["longitude"], weight])

            # Додавання теплової карти
            from folium.plugins import HeatMap

            HeatMap(
                heat_data,
                min_opacity=0.9,
                max_val=5,
                radius=10,
                blur=15,
            ).add_to(fg_pollution)
        else:
            # Звичайні маркери, якщо теплова карта відключена
            for item in data:
                if item['aqi'] == 1:
                    color = "red"
                elif item['aqi'] == 2:
                    color = "orange"
                elif item['aqi'] == 3:
                    color = "yellow"
                elif item['aqi'] == 4:
                    color = "green"
                elif item['aqi'] == 5:
                    color = "blue"
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

# --- Рівень маршрутів ---
if show_routes:
    fg_routes = folium.FeatureGroup(name="Маршрути", overlay=True, control=True)

    # --- Додавання маркерів вибраних точок для маршруту ---
    if st.session_state.points:
        for i, point in enumerate(st.session_state.points):
            folium.Marker(
                location=point,
                popup=f"Точка {i + 1}",
                icon=folium.Icon(color="red" if i == 0 else "green", icon="flag")
            ).add_to(fg_routes)

    # --- Якщо є дані маршруту, відобразити їх ---
    if st.session_state.route_data:
        route_coords = st.session_state.route_data.get("route", [])
        if route_coords:
            folium.PolyLine(
                locations=route_coords,
                color="blue",
                weight=3,
                opacity=0.8
            ).add_to(fg_routes)

    fg_routes.add_to(m)

# --- Обробка кліків, якщо в режимі побудови маршруту ---
if mode == "📍 Побудова маршруту" and output and output.get("last_clicked"):
    latlon = output["last_clicked"]
    if len(st.session_state.points) < 2:
        st.session_state.points.append((latlon["lat"], latlon["lng"]))

# --- Інтерфейс для побудови маршруту ---
if mode == "📍 Побудова маршруту":
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
                        # Автоматично включити відображення маршрутів
                        show_routes = True
                    else:
                        st.error("Помилка побудови маршруту")
                except Exception as e:
                    st.error(f"Помилка: {e}")
        with col2:
            if st.button("🔄 Скинути"):
                st.session_state.points = []
                st.session_state.route_data = None

# --- Рівень кластерів ---
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

# --- Керування рівнями ---
folium.LayerControl(collapsed=False).add_to(m)

# --- Виведення карти ---
st_folium(m, width=700, height=500)
