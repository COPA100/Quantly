# Quantly

## Goal
Quantly is a hybrid Python/C++ portfolio analytics platform that evaluates a user’s stock portfolio across historical performance and risk metrics. Users authenticate via JWT-secured APIs and upload portfolio CSVs through a FastAPI backend. The backend then validates user identity, stores portfolio files in AWS S3, and stores portfolio information and computed results in AWS RDS.

Historical market data is fetched from the Yahoo Finance API and processed through a high-performance analytics engine. Computationally intensive calculations are implemented in C++ and exposed to Python via pybind, allowing the system to scale efficiently as data size and user count grow. Results are then returned to the frontend for interactive visualization.

## Motivation
Quantly is both a personal and technical project for me. The scale and richness of financial data allow for advanced analytics, algorithmic modeling, and meaningful performance insights that I can apply to my own portfolio. Building a tool that helps with real investing decisions makes the project personally motivating and technically challenging. Developing Quantly will help me learn AWS cloud services, Docker, and JWT, while solidifying my knowledge of everything else.

## Tech Stack

### Frontend
- React
- TypeScript
- Tailwind CSS
- Lightweight Charts (TradingView)
- TanStack Query

### Backend
- FastAPI
- Python (pandas, NumPy)
- C++ (via pybind)
- JWT authentication (PyJWT)
- SQL

### Data & Infrastructure
- AWS S3 (portfolio file storage)
- AWS RDS (user, portfolio, and analytics metadata)
- AWS EC2 (application hosting)
- Docker