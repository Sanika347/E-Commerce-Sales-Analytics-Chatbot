# E-Commerce Sales Analytics Chatbot

An AI-powered data analyst chatbot and persistent dashboard designed for querying the Brazilian Olist E-Commerce dataset using plain natural language, generating automated Chart.js visualizations, providing business insights, and managing interactive dashboard pins.

---

## 🏗️ Architecture Overview

The system follows a modular, decoupled agent architecture:

```text
[ User Interface ]  <--->  [ FastAPI Backend ]
  (Vanilla JS/HTML/CSS)          │
                                 ├──> [ Agent Layer ]
                                 │     ├── GeminiAgent (LLM Mode via Gemini 1.5 Pro)
                                 │     └── FallbackAgent (Deterministic Parser Mode)
                                 │
                                 ├──> [ MCP Tool Server (Stdio / FastMCP) ]
                                 │     ├── get_order_trends
                                 │     ├── get_product_category_performance
                                 │     ├── get_seller_performance
                                 │     ├── get_payment_breakdown
                                 │     ├── get_customer_reviews
                                 │     └── get_seller_delivery_review_correlation
                                 │
                                 └──> [ SQLite Databases ]
                                       ├── data/ecommerce.db (Olist Dataset)
                                       └── data/dashboard.db (Pinned Dashboard Items)
```

---

## ⚡ Quick Start (One-Command Setup)

### Requirements
- [Docker](https://www.docker.com/) & Docker Compose
- Google Gemini API key (Optional if running in `fallback` mode)

### Setup Steps

1. **Configure Environment Variables**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   *For Windows (PowerShell):*
   ```powershell
   copy .env.example .env
   ```

2. **Set your API Key (Optional for LLM Mode)**
   Open `.env` and insert your Gemini API Key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   AGENT_MODE=fallback
   ```
   *(Note: Setting `AGENT_MODE=fallback` allows full offline evaluation without requiring an external LLM API key!)*

3. **Launch the Containerized Application**
   Run the single command:
   ```bash
   docker compose up
   ```

4. **Access the Chatbot**
   Open your browser and navigate to:
   [http://localhost:8000](http://localhost:8000)

---

## 📊 5-Query Demo Walkthrough

The chatbot supports 5 core analytical capabilities demonstrated below in sequence:

### Query 1: Time Series Trend Analysis
- **Query:** `"Show monthly revenue trend for 2017"`
- **Parameter Extraction:** `metric='revenue'`, `start_date='2017-01-01'`, `end_date='2017-12-31'`, `group_by='month'`.
- **MCP Tool Invoked:** `get_order_trends`
- **Chart Selection:** `line` (Line chart)
- **Justification:** A line chart is appropriate for displaying single-metric continuous time series trends over monthly intervals.

### Query 2: Ranked Category Performance
- **Query:** `"Which product categories generate the most revenue?"`
- **Parameter Extraction:** `sort_by='revenue'`, `limit=10`.
- **MCP Tool Invoked:** `get_product_category_performance`
- **Chart Selection:** `bar` with `indexAxis: 'y'` (Horizontal Bar chart)
- **Justification:** A horizontal bar chart is appropriate for ranking product categories by total revenue and clearly showing which categories generate the most revenue.

### Query 3: Payment Method Comparison & Filtering
- **Query:** `"What share of payments are credit card vs boleto?"`
- **Parameter Extraction:** `payment_types=['credit_card', 'boleto']`.
- **MCP Tool Invoked:** `get_payment_breakdown`
- **Chart Selection:** `doughnut` (Donut / Pie chart)
- **Justification:** A doughnut chart is appropriate because the user is comparing the share of two payment methods (Credit Card vs Boleto) as parts of the total selected payment methods.

### Query 4: Review Score Distribution
- **Query:** `"Show review score distribution"`
- **Parameter Extraction:** No filters applied, queries full star distribution (1 to 5 stars).
- **MCP Tool Invoked:** `get_customer_reviews`
- **Chart Selection:** `bar` with `indexAxis: 'y'` (Horizontal Bar chart)
- **Justification:** Stacked horizontal bar chart chosen because the data represents a score distribution (1-5 stars).

### Query 5: Seller Correlation & Entity Relationship Analysis
- **Query:** `"Do sellers with faster delivery get better reviews?"`
- **Parameter Extraction:** Evaluates `avg_delivery_delay` vs `avg_review_score` across sellers with $\ge 10$ orders.
- **MCP Tool Invoked:** `get_seller_delivery_review_correlation`
- **Chart Selection:** `scatter` (Scatter Plot)
- **Justification:** A scatter plot is appropriate because it shows the relationship between average delivery delay and average review score across sellers. Each point represents one seller.

---

## 🎯 Design Decisions

### 1. Chart Type Selection Logic
Chart selection is determined deterministically by inspecting the data shape, metadata, and user intent rather than relying solely on arbitrary LLM preferences:
- **Single Metric Time Series:** Configured as `line` chart with continuous X-axis.
- **Ranked Entity Lists (Top N Categories / Sellers / State Performance):** Configured as horizontal bar chart (`indexAxis: 'y'`) sorted descending.
- **Part-to-Whole / Share Breakdown:** Configured as `doughnut` chart showing percentage distribution.
- **Continuous Bivariate Correlation:** Configured as `scatter` plot with linear X & Y scales.
- **Score Distribution (1-5 Stars):** Configured as a horizontal bar chart.
- **Multi-Metric State Comparison:** Configured as dual-axis bar chart (`y` and `y1` axes).

### 2. Refresh & Diff Detection
Pinned dashboard items allow live updates via the `/api/dashboard/{id}/refresh` endpoint:
- **Execution:** Re-runs the exact underlying MCP tool parameters captured when the chart was pinned.
- **Snapshot Comparison:** Compares the newly fetched dataset snapshot against the previously saved `raw_data`.
- **Diff Metric:** Evaluates the primary numerical value of the top record. If the percentage change $|V_{new} - V_{old}| / V_{old} > 5.0\%$, or if row counts change, it flags a **Significant Change Detected** notification and automatically updates the database & UI.

### 3. Fallback Agent vs. Normal Agent
- **Normal LLM Agent (`GeminiAgent`):** Uses Google Gemini 1.5 Pro native function calling (`types.Tool`) to dynamically infer tool requirements, parse relative dates, and synthesize single-sentence business summaries (`generate_insight_llm`).
- **Fallback Agent (`FallbackAgent`):** A lightweight, deterministic rule-based agent using regex pattern matching and semantic entity extractors. It operates completely offline, executing MCP tools directly, detecting data shapes, and utilizing template-based fallback insight logic (`generate_insight_fallback`).

---

## 🎥 Demo Video

Watch the complete project demo walkthrough:

[![Demo Video Placeholder](https://img.shields.io/badge/Demo_Video-Watch_Walkthrough-blue?style=for-the-badge&logo=youtube)](https://github.com/Sanika347/E-Commerce-Sales-Analytics-Chatbot#demo-walkthrough)

*A video demonstration showing container startup, execution of all 5 demo queries, live dashboard pinning, chart refresh diff detection, and fallback agent execution.*

---

## 📂 Project Structure

```text
E-Commerce-Sales-Analytics-Chatbot/
├── app/
│   ├── main.py              # FastAPI server & route initialization
│   ├── config.py            # Environment & Pydantic settings
│   ├── agents/
│   │   ├── base.py          # Abstract Agent interface
│   │   ├── gemini_agent.py  # LLM-based agent using Gemini 1.5 Pro
│   │   ├── fallback_agent.py# Rule-based fallback agent
│   │   └── mcp_client.py    # Stdio client helper for MCP server
│   ├── engine/
│   │   ├── chart_selector.py# Deterministic Chart.js selection logic
│   │   └── insight_gen.py   # Business insight generation engine
│   ├── mcp_server/
│   │   └── server.py        # FastMCP tool server definitions
│   ├── database/
│   │   ├── loader.py        # Olist CSV dataset loader & SQLite init
│   │   └── db.py            # SQLite execution helper
│   └── api/
│       └── endpoints.py     # FastAPI REST API endpoints
├── frontend/                # Vanilla HTML5/JS/CSS dashboard interface
├── data/                    # SQLite database storage (ecommerce.db, dashboard.db)
├── Dockerfile               # Production Container Definition
├── docker-compose.yml       # Docker Compose service definition
├── requirements.txt         # Pinned Python dependencies (mcp<2)
├── .env.example             # Environment variable template
└── README.md                # Project documentation
```

---

## 🔧 Troubleshooting

- **Database Missing / First Run Delay:** On the first execution, SQLite automatically creates `data/ecommerce.db`. If Kaggle credentials are missing, the system uses existing local database files or cached datasets.
- **Port 8000 Conflict:** If port 8000 is already in use on your host machine, modify the port mapping in `docker-compose.yml`: `"8001:8000"`.
- **API Key Errors:** If running without a Gemini API key, ensure `AGENT_MODE=fallback` is set in `.env`.
