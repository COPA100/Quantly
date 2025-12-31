import numpy as np
import pandas as pd

# file goes here
CSV_FILE = "example_csv\ex1.csv"

# change to dataframe
CSV = pd.read_csv(CSV_FILE, skiprows=2, skipfooter=2)
print(CSV.columns)

investments = []
for s,q in zip(CSV["Symbol"], CSV["Qty (Quantity)"]):
    investments.append((s,q))
print(investments)

investment_names = []
for name, qty in investments:
    investment_names.append(name)
print(investment_names)

investment_qty = []
for name, qty in investments:
    investment_qty.append(qty)
print(investment_qty)