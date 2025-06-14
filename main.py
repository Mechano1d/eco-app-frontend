# streamlit_app.py

import streamlit as st
import requests
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
import plotly.graph_objects as go
from io import BytesIO
from PIL import Image
import base64
import plotly.express as px
from copy import deepcopy

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

# Наявність екологічних даних
if "pollution_data" not in st.session_state:
    st.session_state.pollution_data = False

# Наявність екологічних даних для мапи
if "map_pollution" not in st.session_state:
    st.session_state.map_pollution = None

# Результати статистичного аналізу
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None

# Мапа
if 'base_map' not in st.session_state:
    st.session_state.base_map = folium.Map(location=[50.45, 30.52], zoom_start=12)
    folium.LatLngPopup().add_to(st.session_state.base_map)

city = st.text_input("Введіть назву міста:", value="Kyiv")

# Ініціалізація кнопок
if st.button("Ініціалізувати місто"):
    res = requests.get(f"{API_URL}/cities/{city}/initialize")
    st.session_state.initialized = True
    st.write(res.json())

if not st.session_state.initialized:
    st.badge("Не ініціалізовано", icon=":material/exclamation:", color="red")
else:
    st.badge("Ініціалізовано", icon=":material/check:", color="green")

if st.button("Зібрати дані"):
    res = requests.get(f"{API_URL}/cities/{city}/collect_data")
    st.session_state.collected_data = True
    st.session_state.pollution_data = res.json()["data"]

if not st.session_state.collected_data:
    st.badge("Не зібрано екологічні дані", icon=":material/exclamation:", color="red")
else:
    st.badge("Екологічні дані зібрано", icon=":material/check:", color="green")


# --- Вибір шарів для відображення ---
st.sidebar.header("Шари карти")
show_pollution = st.sidebar.checkbox("Показати забруднення", value=True)
show_heatmap = st.sidebar.checkbox("Теплова мапа", value=True)
show_routes = st.sidebar.checkbox("Показати маршрут", value=False)
show_clusters = st.sidebar.checkbox("Показати кластери", value=False)
enable_routing = st.sidebar.checkbox("Режим побудови маршруту", value=False)

# Вибір типу візуалізації кластерів
cluster_display_type = st.sidebar.selectbox(
    "Тип відображення кластерів:",
    ("MarkerCluster", "CircleMarker")
)

if st.session_state.initialized and st.session_state.collected_data:

    if st.button("Аналіз даних"):
        res = requests.get(f"{API_URL}/cities/{city}/full_analysis")
        st.session_state.analysis_results = res.json()

    if not st.session_state.analysis_results:
        st.badge("Аналіз даних не виконано", icon=":material/exclamation:", color="red")
    else:
        st.badge("Аналіз даних виконано", icon=":material/check:", color="green")

    if st.session_state.analysis_results:

        # Ключі до розподілів у session_state.analysis_results
        param_display_names = {
            "aqi_distribution": "AQI (індекс якості повітря)",
            "co_distribution": "CO (чадний газ)",
            "no2_distribution": "NO₂ (діоксид азоту)",
            "pm_2_5_distribution": "PM2.5 (дрібні частинки)",
            "pm_10_distribution": "PM10 (крупні частинки)"
        }

        selected_dist_key = st.selectbox(
            "Оберіть параметр для побудови гістограми:",
            options=list(param_display_names.keys()),
            format_func=lambda k: param_display_names[k]
        )

        try:
            distribution_data = st.session_state.analysis_results.get(selected_dist_key, {})

            if not distribution_data:
                st.warning("Немає даних для вибраного параметра.")
            else:
                dist_df = pd.DataFrame({
                    "Інтервал": list(distribution_data.keys()),
                    "Кількість точок": list(distribution_data.values())
                })

                fig = px.bar(
                    dist_df,
                    x="Кількість точок",
                    y="Інтервал",
                    orientation="h",
                    color="Інтервал",
                    color_discrete_sequence=px.colors.sequential.Plasma,
                    title=f"Розподіл значень: {param_display_names[selected_dist_key]}"
                )

                st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Помилка при візуалізації: {e}")

        # --- Кореляції ---
        st.subheader("Кореляція між трафіком та забрудненням")

        correlations = st.session_state.analysis_results.get("correlations", [])
        if correlations:
            df_corr = pd.DataFrame(correlations)
            df_corr["значущість"] = df_corr["significant"].apply(lambda x: "✔️" if x else "✖️")
            st.dataframe(df_corr[["parameter", "correlation", "p_value", "значущість"]])

        # --- Регресії ---
        st.subheader("Лінійна регресія: як трафік впливає на забруднення")

        regressions = st.session_state.analysis_results.get("regression_models", [])
        if regressions:
            df_reg = pd.DataFrame(regressions)
            st.dataframe(df_reg[["parameter", "equation", "r2_score"]])

        st.subheader("Лінійна регресія: Вплив трафіку на забруднення")
        regression_models = st.session_state.analysis_results["regression_models"]
        pollution_data = pd.DataFrame(st.session_state.pollution_data)

        for result in regression_models:
            param = result["parameter"]
            st.markdown(f"**{param}** — R² = {result['r2_score']:.3f}")

            # Витягуємо дані
            df = pollution_data[["traffic_intensity", param]].dropna()

            if df.empty:
                st.warning(f"Недостатньо даних для {param}")
                continue

            # Передбачення
            X = df["traffic_intensity"]
            y = df[param]
            y_pred = result["intercept"] + result["coefficient"] * X

            # Створюємо графік
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=X, y=y,
                mode='markers',
                name='Спостереження',
                marker=dict(color='blue', size=6)
            ))

            fig.add_trace(go.Scatter(
                x=X, y=y_pred,
                mode='lines',
                name='Лінія регресії',
                line=dict(color='red', width=2)
            ))

            fig.update_layout(
                title=f"Залежність {param} від трафіку",
                xaxis_title="Інтенсивність трафіку",
                yaxis_title=param,
                height=400
            )

            st.plotly_chart(fig, use_container_width=True)


    # --- Базова мапа ---
    m = deepcopy(st.session_state.base_map)
    folium.LatLngPopup().add_to(m)

    # --- Забруднення ---
    if show_pollution:
        try:
            if st.session_state.map_pollution is None:
                resp = requests.get(f"http://localhost:8000/cities/{city}/pollution")
                resp.raise_for_status()
                st.session_state.map_pollution = resp.json()

            data = st.session_state.map_pollution

            fg_pollution = folium.FeatureGroup(name="Забруднення", overlay=True, control=True)

            if show_heatmap:
                heat_data = []
                for item in data:
                    weight = 6 - item['aqi']
                    heat_data.append([item["latitude"], item["longitude"], weight])
                HeatMap(
                    heat_data,
                    min_opacity=0.9,
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
        if cluster_display_type == "MarkerCluster":
            try:
                clusters = st.session_state.analysis_results["clusters"]
                # st.write(clusters)

                fg_clusters = folium.FeatureGroup(name="Кластери", overlay=True, control=True)

                marker_cluster = MarkerCluster().add_to(fg_clusters)

                for item in clusters:
                    color = {
                        0: "red", 1: "orange", 2: "yellow", 3: "green", 4: "blue"
                    }.get(item['cluster'], "gray")

                    folium.CircleMarker(
                        location=[item["latitude"], item["longitude"]],
                        radius=5,
                        color=color,
                        fill=True,
                        fill_opacity=0.5,
                        popup=f"Кластер: {item['cluster']}"
                    ).add_to(marker_cluster)
                marker_cluster.add_to(m)
            except Exception as e:
                st.error(f"Помилка при завантаженні кластерів: {e}")
        else:
            try:
                clusters = st.session_state.analysis_results["clusters"]

                fg_clusters = folium.FeatureGroup(name="Кластери", overlay=True, control=True)

                for item in clusters:
                    color = {
                        0: "red", 1: "orange", 2: "yellow", 3: "green", 4: "blue"
                    }.get(item['cluster'], "gray")

                    folium.CircleMarker(
                        location=[item["latitude"], item["longitude"]],
                        radius=5,
                        color=color,
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
    output = st_folium(m, width=1000, height=1000)

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

