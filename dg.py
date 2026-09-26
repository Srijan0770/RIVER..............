import pandas as pd
from rapidfuzz import process, fuzz
import matplotlib.pyplot as plt
from tabulate import tabulate

file_path = r"C:\Users\SRIJAN JANA\OneDrive\Desktop\river.csv"
df = pd.read_csv(file_path)

df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")

required_cols = {"RIVER", "PH", "CITY"}
if not required_cols.issubset(df.columns):
    raise ValueError("Dataset must contain RIVER, CITY, and PH columns.")
    
df["PH"] = pd.to_numeric(df["PH"], errors="coerce")
df.dropna(subset=["PH"], inplace=True)

def classify_ph(ph):
    if ph < 6.5:
        return "Acidic (Unsafe)"
    elif 6.5 <= ph <= 8.5:
        return "Normal (Safe)"
    else:
        return "Alkaline (Unsafe)"

def get_ph_by_river(query):

    if not query.strip():
        print(" Please enter a valid river name.")
        return

    river_list = df["RIVER"].dropna().astype(str).unique()
    best_match = process.extractOne(query, river_list, scorer=fuzz.WRatio)

    if best_match is None or best_match[1] < 70:
        print(" No close river name found.")
        return

    matched_name = best_match[0]
    print(f"\n Best Match Found: {matched_name}")

    results = df[df["RIVER"].astype(str).str.contains(matched_name, case=False, na=False)].copy()

    if results.empty:
        print(" No data available for this river.")
        return

    results["PH_QUALITY"] = results["PH"].apply(classify_ph)

    print("\n pH Summary:")
    print(f" Total Cities     : {results['CITY'].nunique()}")
    print(f" Total Locations  : {len(results)}")
    print(f" Average PH       : {results['PH'].mean():.2f}")
    print(f" Minimum PH       : {results['PH'].min():.2f}")
    print(f" Maximum PH       : {results['PH'].max():.2f}")

    best_city = results.loc[results["PH"].idxmin()]
    worst_city = results.loc[results["PH"].idxmax()]

    print("\n City Analysis:")
    print(f" Best Quality City  : {best_city['CITY']} (PH = {best_city['PH']:.2f})")
    print(f" Worst Quality City : {worst_city['CITY']} (PH = {worst_city['PH']:.2f})")

    print("\n Detailed PH Table:")
    print(tabulate(
        results[["RIVER", "CITY", "PH", "PH_QUALITY"]].sort_values("CITY"),
        headers="keys",
        tablefmt="psql",
        showindex=False
    ))

    city_count = results["CITY"].value_counts()
    print("\n City-wise Total Data Count:")
    for city, count in city_count.items():
        print(f" {city} : {count}")

    output_file = f"{matched_name}_PH_ANALYSIS.csv"
    results.to_csv(output_file, index=False)
    print(f"\n Full river data saved as: {output_file}")

    city_ph = results.groupby("CITY")["PH"].mean().sort_values()
    city_ph_file = f"{matched_name}_CITY_AVG_PH.csv"
    city_ph.to_csv(city_ph_file)
    print(f" City-wise average PH saved as: {city_ph_file}")

    grouped = results.groupby(["PH_QUALITY", "CITY"]).size().reset_index(name="COUNT")
    grouped_file = f"{matched_name}_CITIES_BY_PH_CATEGORY.csv"
    grouped.to_csv(grouped_file, index=False)
    print(f" Cities by PH category saved as: {grouped_file}")

    plt.figure(figsize=(10,8))
    plt.plot(city_ph.index, city_ph.values, marker='o')
    plt.xlabel("City")
    plt.ylabel("Average PH")
    plt.title(f"City-wise Average PH of {matched_name} River")
    plt.xticks(rotation=45, ha="right")
    plt.grid(True)
    plt.tight_layout()
    plt.show()
    print("\n Minimum Safe PH = 6.5, Maximum Safe PH = 8.5")

    plt.figure(figsize=(8, 5))
    plt.bar(city_ph.index, city_ph.values, width=0.5)
    plt.axhline(y=6.5, color='red', linestyle='--', label='Min Safe PH')
    plt.axhline(y=8.5, color='green', linestyle='--', label='Max Safe PH')
    plt.xlabel("City")
    plt.ylabel("Average PH")
    plt.title(f"City-wise Average PH of {matched_name} River")
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    plt.grid(axis='y')
    plt.tight_layout()
    plt.show()

    ph_counts = results["PH_QUALITY"].value_counts()
    colors = {
        "Acidic (Unsafe)": "#ff6b6b",
        "Normal (Safe)": "#51cf66",
        "Alkaline (Unsafe)": "#ffa94d"
    }
    pie_colors = [colors[label] for label in ph_counts.index]

    plt.figure(figsize=(10, 7))
    plt.pie(
        ph_counts.values,
        labels=ph_counts.index,
        autopct="%1.1f%%",
        startangle=90,
        colors=pie_colors,
        wedgeprops={"edgecolor": "black"}
    )
    plt.title(f"PH Quality Distribution of {matched_name} River")
    plt.show()

    for category in ph_counts.index:
        subset = grouped[grouped["PH_QUALITY"] == category]
        subset = subset.sort_values("COUNT", ascending=False)
        plt.figure(figsize=(8, 5))
        plt.bar(subset["CITY"], subset["COUNT"], color=colors[category], width=0.5)
        plt.xlabel("City")
        plt.ylabel("Number of Readings")
        plt.title(f"{category} - Cities Count for {matched_name} River (Ranked)")
        plt.xticks(rotation=45, ha="right")
        plt.grid(axis="y")
        plt.tight_layout()
        plt.show()

while True:
    user_inp = input("\n Enter river name to check PH (or type EXIT): ")
    if user_inp.lower() in ["exit", "quit"]:
        print(" The Program Is Closed ")
        break
    get_ph_by_river(user_inp)
