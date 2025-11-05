# Quantidel

Goal:
Quantidel is a hybrid Python/C++ tool that analyzes a stock portfolio’s historical performance and risk metrics. Users upload a CSV file of their portfolio, which is parsed and stored in a database with JWT-secured authentication. Historical stock data is fetched via the Yahoo Finance API, and performance metrics are computed efficiently in C++ before being returned to the frontend for visualization.

This is going to take a while to make so I will make the backend first and once that's done I will create the frontend. Also, I am using pybind to combine the C++ and python together. C++ makes more sense to utilize for more complex calculations and when scaled to many users.

Frontend:
React, TypeScript, Tailwind

Backend:
C++, Python, SQL (SQLite for dev, PostgreSQL for prod), FastAPI
