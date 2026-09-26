import os
import uuid
import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz
from django.shortcuts import render
from django.conf import settings
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ── Dataset ──
file_path = os.path.join(settings.BASE_DIR, 'analysis', 'data', 'river.csv')

if not os.path.exists(file_path):
    raise FileNotFoundError(f"CSV file not found at: {file_path}")

df = pd.read_csv(file_path)
df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")
df["PH"] = pd.to_numeric(df["PH"], errors="coerce")
df.dropna(subset=["PH"], inplace=True)

required_cols = {"RIVER", "PH", "CITY"}
if not required_cols.issubset(df.columns):
    raise ValueError("Dataset must contain RIVER, CITY, and PH columns.")


# ── Classification ──
def classify_ph(ph):
    if ph < 6.5:
        return "Acidic (Unsafe)"
    elif ph <= 8.5:
        return "Normal (Safe)"
    else:
        return "Alkaline (Unsafe)"


df["PH_QUALITY"] = df["PH"].apply(classify_ph)


# ── Views ──
def front(request):
    return render(request, 'front.html')


def analysis_page(request):
    return render(request, 'analysis.html')


def about(request):
    return render(request, 'about.html')


def map_view(request):
    """Build a JSON-serialisable list of every city reading for the Leaflet map."""
    # keep only rows that have valid lat/lon
    map_df = df.dropna(subset=["LATITUDE", "LONGITUDE"]).copy()
    map_df["LATITUDE"]  = pd.to_numeric(map_df["LATITUDE"],  errors="coerce")
    map_df["LONGITUDE"] = pd.to_numeric(map_df["LONGITUDE"], errors="coerce")
    map_df.dropna(subset=["LATITUDE", "LONGITUDE"], inplace=True)

    # one representative row per city (avg pH, first lat/lon)
    city_map = (
        map_df.groupby(["CITY", "RIVER"])
        .agg(
            avg_ph=("PH", "mean"),
            lat=("LATITUDE", "first"),
            lon=("LONGITUDE", "first"),
            readings=("PH", "count"),
        )
        .reset_index()
    )
    city_map["avg_ph"] = city_map["avg_ph"].round(2)
    city_map["quality"] = city_map["avg_ph"].apply(classify_ph)

    markers_json = json.dumps(city_map.to_dict("records"))
    return render(request, "map.html", {"markers_json": markers_json})


def home(request):
    context = {}

    if request.method == "POST":
        query = request.POST.get("river_name", "").strip()

        if not query:
            context["error"] = "Please enter a river name."
            return render(request, "home.html", context)

        river_list = df["RIVER"].dropna().astype(str).unique()
        best_match = process.extractOne(query, river_list, scorer=fuzz.WRatio)

        if best_match is None or best_match[1] < 70:
            context["error"] = "No close river name found."
            return render(request, "home.html", context)

        matched_name = best_match[0]
        results = df[df["RIVER"].str.lower() == matched_name.lower()].copy()

        if results.empty:
            context["error"] = "No data available for this river."
            return render(request, "home.html", context)

        if results["PH"].dropna().empty:
            context["error"] = "No valid pH data found."
            return render(request, "home.html", context)

        summary = {
            "matched_name": matched_name,
            "total_cities": results["CITY"].nunique(),
            "total_locations": len(results),
            "avg_ph": round(results["PH"].mean(), 2),
            "min_ph": round(results["PH"].min(), 2),
            "max_ph": round(results["PH"].max(), 2),
        }

        best_city = results.loc[results["PH"].idxmin()]
        worst_city = results.loc[results["PH"].idxmax()]

        city_analysis = {
            "best_city": best_city["CITY"],
            "best_ph": round(best_city["PH"], 2),
            "worst_city": worst_city["CITY"],
            "worst_ph": round(worst_city["PH"], 2),
        }

        table_data = results[["RIVER", "CITY", "PH", "PH_QUALITY"]] \
            .sort_values("CITY").to_dict("records")

        city_count = list(results["CITY"].value_counts().items())
        city_ph = results.groupby("CITY")["PH"].mean().sort_values()
        ph_counts = results["PH_QUALITY"].value_counts()

        # ── Graphs ──
        graph_dir = os.path.join(settings.BASE_DIR, "analysis", "static", "graphs")
        os.makedirs(graph_dir, exist_ok=True)

        for f in os.listdir(graph_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(graph_dir, f))

        uid = str(uuid.uuid4())[:8]
        graphs = []

        ph_colors = {
            "Acidic (Unsafe)":   "#ff6b6b",
            "Normal (Safe)":     "#51cf66",
            "Alkaline (Unsafe)": "#ffa94d",
        }

        # 1. Line Graph — pH Trend
        g1 = f"line_{uid}.png"
        plt.figure(figsize=(10, 5))
        plt.plot(city_ph.index, city_ph.values, marker='o', color='#0ea5c9')
        plt.xlabel("City")
        plt.ylabel("Average pH")
        plt.title(f"City-wise Average pH of {matched_name} River")
        plt.xticks(rotation=45, ha="right")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(graph_dir, g1))
        plt.close()
        graphs.append((f"/static/graphs/{g1}", "pH Trend (Line)"))

        # 2. Bar Graph with safe pH reference lines
        g2 = f"bar_{uid}.png"
        plt.figure(figsize=(10, 5))
        plt.bar(city_ph.index, city_ph.values, width=0.5, color='#2e7dd1')
        plt.axhline(y=6.5, color='red',   linestyle='--', label='Min Safe pH (6.5)')
        plt.axhline(y=8.5, color='green', linestyle='--', label='Max Safe pH (8.5)')
        plt.xlabel("City")
        plt.ylabel("Average pH")
        plt.title(f"City-wise Average pH of {matched_name} River")
        plt.xticks(rotation=45, ha="right")
        plt.legend()
        plt.grid(axis='y')
        plt.tight_layout()
        plt.savefig(os.path.join(graph_dir, g2))
        plt.close()
        graphs.append((f"/static/graphs/{g2}", "pH Comparison (Bar with Safe Range)"))

        # 3. Pie Chart — Quality Distribution
        g3 = f"pie_{uid}.png"
        pie_colors = [ph_colors.get(lbl, "#aaa") for lbl in ph_counts.index]
        plt.figure(figsize=(8, 6))
        plt.pie(
            ph_counts.values,
            labels=ph_counts.index,
            autopct="%1.1f%%",
            startangle=90,
            colors=pie_colors,
            wedgeprops={"edgecolor": "black"},
        )
        plt.title(f"pH Quality Distribution of {matched_name} River")
        plt.tight_layout()
        plt.savefig(os.path.join(graph_dir, g3))
        plt.close()
        graphs.append((f"/static/graphs/{g3}", "Quality Distribution (Pie)"))

        # 4. Per-category ranked bar charts
        grouped = results.groupby(["PH_QUALITY", "CITY"]).size().reset_index(name="COUNT")
        for category in ph_counts.index:
            subset = grouped[grouped["PH_QUALITY"] == category].sort_values("COUNT", ascending=False)
            if subset.empty:
                continue
            safe_cat = category.replace(" ", "_").replace("(", "").replace(")", "")
            g_cat = f"cat_{safe_cat}_{uid}.png"
            plt.figure(figsize=(10, 5))
            plt.bar(subset["CITY"], subset["COUNT"],
                    color=ph_colors.get(category, "#aaa"), width=0.5)
            plt.xlabel("City")
            plt.ylabel("Number of Readings")
            plt.title(f"{category} — Cities Ranked for {matched_name} River")
            plt.xticks(rotation=45, ha="right")
            plt.grid(axis='y')
            plt.tight_layout()
            plt.savefig(os.path.join(graph_dir, g_cat))
            plt.close()
            graphs.append((f"/static/graphs/{g_cat}", f"{category} — City Readings"))

        
        BASE_YEAR  = 2015
        END_YEAR   = 2024
        CURR_YEAR  = 2026

        city_predictions = []

        for city in sorted(results["CITY"].dropna().unique()):
            city_data = results[results["CITY"] == city].reset_index(drop=True)
            ph_values = city_data["PH"].values
            n         = len(ph_values)
            avg_ph    = round(float(np.mean(ph_values)), 2)
            min_ph    = round(float(np.min(ph_values)), 2)
            max_ph    = round(float(np.max(ph_values)), 2)
            quality   = classify_ph(avg_ph)
            gauge_pct = round((avg_ph / 14) * 100, 1)

            # Assign a year to each reading spread across 2015–2024
            if n == 1:
                years = np.array([BASE_YEAR], dtype=float)
            else:
                years = np.linspace(BASE_YEAR, END_YEAR, n)

            # Linear regression: pH = slope * year + intercept
            coeffs    = np.polyfit(years, ph_values, 1)
            slope     = float(coeffs[0])   # pH change per year
            intercept = float(coeffs[1])

            # % change per year relative to avg pH
            pct_per_year = round((slope / avg_ph) * 100, 2) if avg_ph != 0 else 0.0

            # Historical year-by-year table (2015–2024 using the fitted line)
            year_table = []
            for yr in range(BASE_YEAR, END_YEAR + 1):
                fitted_ph = round(float(np.clip(slope * yr + intercept, 0, 14)), 2)
                year_table.append({
                    "year":    yr,
                    "ph":      fitted_ph,
                    "quality": classify_ph(fitted_ph),
                })

            # Forecasts: 2025, 2026, 2027
            forecasts = []
            for yr in [CURR_YEAR - 1, CURR_YEAR, CURR_YEAR + 1]:
                fph = round(float(np.clip(slope * yr + intercept, 0, 14)), 2)
                forecasts.append({
                    "year":    yr,
                    "ph":      fph,
                    "quality": classify_ph(fph),
                })

            # Trend direction
            if pct_per_year > 0.05:
                trend = "rising"    
            elif pct_per_year < -0.05:
                trend = "falling"
            else:
                trend = "stable"

            city_predictions.append({
                "city":         city,
                "avg_ph":       avg_ph,
                "min_ph":       min_ph,
                "max_ph":       max_ph,
                "readings":     n,
                "quality":      quality,
                "gauge_pct":    gauge_pct,
                "trend":        trend,
                "pct_per_year": abs(round(pct_per_year, 2)),
                "pct_sign":     "+" if pct_per_year >= 0 else "-",
                "slope":        round(slope, 4),
                "year_table":   year_table,
                "forecasts":    forecasts,
            })

        context = {
            "summary": summary,
            "city_analysis": city_analysis,
            "table_data": table_data,
            "city_count": city_count,
            "graphs": graphs,
            "city_predictions": city_predictions,
            "matched_name": matched_name,
        }

    return render(request, "home.html", context)
