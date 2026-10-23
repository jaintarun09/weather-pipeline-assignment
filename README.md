import os
from pathlib import Path

import requests
import pandas as pd
from google.cloud import bigquery

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
if not project_id:
    raise RuntimeError(
        "Set GOOGLE_CLOUD_PROJECT to your Google Cloud project ID before running this script."
    )

data_file = Path(__file__).resolve().parent.parent / "data" / "population.csv.xlsx"
pop = pd.read_excel(data_file)
print(pop.columns.tolist())

locations = pop.dropna(subset=["Latitude", "Longitude"]).head(50)

rows = []
for _, loc in locations.iterrows():
	url = (f"https://api.open-meteo.com/v1/forecast?latitude={loc['Latitude']}"
		   f"&longitude={loc['Longitude']}&current_weather=true")
	try:
		r = requests.get(url, timeout=20)
		r.raise_for_status()
		cw = r.json()["current_weather"]
		rows.append({"City": loc["City"],
					 "Country": loc["Country"],
					 "Temperature": cw["temperature"],
					 "Windspeed": cw["windspeed"]})
	except Exception as e:
		print("Failed:", loc["Country"], e)

weather = pd.DataFrame(rows)
print(weather.head())

merged = pd.merge(
	weather,
	pop[["City", "Country", "Population"]],
	on=["City", "Country"],
	how="inner",
)
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

client = bigquery.Client(project=project_id)
table_id = f"{project_id}.global_weather_data.current_weather_stats"
job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
job = client.load_table_from_dataframe(merged, table_id, job_config=job_config)
job.result()
print(f"Loaded {job.output_rows} rows into {table_id}")
