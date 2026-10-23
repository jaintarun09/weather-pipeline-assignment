import requests
import pandas as pd

pop = pd.read_csv("data/population.csv")
print(pop.columns.tolist())   # verify column names

# Take 50 rows that have coordinates
locations = pop.dropna(subset=["Latitude", "Longitude"]).head(50)

rows = []
for _, loc in locations.iterrows():
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={loc['Latitude']}"
           f"&longitude={loc['Longitude']}&current_weather=true")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        cw = r.json()["current_weather"]
        rows.append({
            "Country": loc["Country"],
            "Temperature": cw["temperature"],
            "Windspeed": cw["windspeed"],
        })
    except Exception as e:
        print(f"Failed for {loc['Country']}: {e}")

weather = pd.DataFrame(rows)
print(weather.head())

merged = pd.merge(weather, pop[["Country", "Population"]], on="Country", how="inner")
print(merged.shape)

print(merged.isnull().sum())
merged = merged.dropna(subset=["Country", "Temperature", "Population"])

merged["Population"] = merged["Population"].astype("int64")
merged["Temperature"] = merged["Temperature"].astype("float64")

def categorize(t):
    if t < 10:
        return "Cold"
    elif t < 25:
        return "Mild"
    return "Hot"

merged["Temperature_Category"] = merged["Temperature"].apply(categorize)
merged["Temperature_F"] = merged["Temperature"] * 9 / 5 + 32
print(merged.dtypes)
print(merged.head())

from google.cloud import bigquery

PROJECT_ID = "YOUR_PROJECT_ID"
client = bigquery.Client.from_service_account_json("scripts/gcp-key.json", project=PROJECT_ID)

table_id = f"{PROJECT_ID}.global_weather_data.current_weather_stats"
job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
job = client.load_table_from_dataframe(merged, table_id, job_config=job_config)
job.result()
print(f"Loaded {job.output_rows} rows into {table_id}")

