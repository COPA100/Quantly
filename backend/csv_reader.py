import numpy as np
import pandas as pd

# file goes here
CSV_FILE = "example_csv\ex1.csv"

# change to dataframe
CSV = pd.read_csv(CSV_FILE, skiprows=2, skipfooter=2)

print(CSV.columns)

investments = CSV[["Symbol", "Qty (Quantity)"]]

print(investments)