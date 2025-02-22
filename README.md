# Five Innings Back-End

## Overview

Welcome to the **Five Innings Back-End** repository! This project serves as the server-side component of a web application designed to provide real-time Major League Baseball (MLB) statistics for betting enthusiasts. The back-end is powered by the [MLB Stats API](https://statsapi.mlb.com), which provides comprehensive data on players, teams, games, and historical performance.

This repository contains the **back-end codebase**, built using **Flask**, **asyncio**, and **LRU caching** to ensure efficient data retrieval and processing. The back-end handles requests from the front-end, fetches data from the MLB Stats API, processes it, and delivers it in a structured format for consumption by the front-end.

---

## Features

- **Real-Time Data Fetching**: Fetch live MLB statistics using the official MLB Stats API.
- **Efficient Caching**: Utilize LRU caching to minimize redundant API calls and improve performance.
- **Asynchronous Processing**: Use `asyncio` to handle multiple API requests concurrently, reducing latency.
- **RESTful API Endpoints**: Provide clean, well-documented endpoints for front-end integration.
- **Error Handling**: Robust error handling ensures graceful degradation in case of API failures or invalid requests.

---

## Technologies Used

- **Framework**: [Flask](https://flask.palletsprojects.com/)
- **Asynchronous Programming**: Python's `asyncio`
- **Caching**: LRU Cache (`functools.lru_cache`)
- **HTTP Requests**: `aiohttp` for asynchronous HTTP requests
- **Data Parsing**: JSON parsing and manipulation
- **Version Control**: Git / GitHub
- **Deployment**: Heroku

---

## Installation & Setup

Follow these steps to set up the project locally:

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git
- Virtualenv (optional but recommended)

### Steps

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment Variables**
   Create a `.env` file in the root directory and add the following:
   ```env
   FLASK_APP=app.py
   FLASK_ENV=development
   MLB_STATS_API_BASE_URL=https://statsapi.mlb.com/api/v1
   CACHE_SIZE=128
   ```
   Adjust the `CACHE_SIZE` based on your caching needs.

3 **Run the Flask Development Server**
   ```bash
   flask run
   ```

4. **Access the API**
   Navigate to `http://localhost:5000` in your browser or use tools like Postman to test the API endpoints.

---

## Caching Strategy

To optimize performance and reduce the number of API calls to the MLB Stats API, we implement an **LRU (Least Recently Used) Cache**. This ensures that frequently requested data is stored in memory, reducing latency and improving response times.

- **Cache Size**: Configurable via the `CACHE_SIZE` environment variable.
- **Cache Invalidation**: Cache entries are automatically invalidated after a certain period or when new data is fetched.

---

## Asynchronous Processing

The back-end leverages Python's `asyncio` library to handle multiple API requests concurrently. This is particularly useful when fetching data for multiple players, teams, or games simultaneously, ensuring that the application remains responsive even under heavy load.

---

## Deployment

The back-end can be deployed using various platforms such as **Heroku**, **AWS**, or **Docker**. Below are some common deployment options:


## Contributing

We welcome contributions from the community! If you'd like to contribute, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add your commit message here"
   ```
4. Push your changes to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
5. Open a pull request against the `main` branch of this repository.

Please ensure your code adheres to the project's coding standards and includes appropriate tests.

---


## Contact

If you have any questions, suggestions, or feedback, feel free to reach out:

- **Email**: brianzanoni@outlook.com
- **GitHub**: [@brianzzs](https://github.com/brianzzs)
- **LinkedIn**: https://www.linkedin.com/in/brianzan/

---

Thank you for checking out the **Five Innings Back-End**! We hope this tool helps power your front-end application and provides valuable insights for MLB fans and bettors alike. 🚀⚾

--- 
