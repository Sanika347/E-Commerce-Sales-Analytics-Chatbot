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
   [http://localhost:8000](https://e-commerce-sales-analytics-chatbot.onrender.com/)

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

## 🧠 Design Decisions

The application is designed to separate **natural-language understanding, data retrieval, visualization, and error handling** into independent components. The main goal was to make the system predictable and explainable while still allowing an LLM to understand flexible user queries.

The following design decisions were made to ensure that the application remains reliable, deterministic where possible, and easy to extend.

---

### 1. 📊 Chart Type Selection Logic

The application does not allow the LLM to arbitrarily decide which chart should be displayed.

Instead, chart selection is handled through a **deterministic chart-selection layer** that examines:

* The user's query intent
* The type of data returned by the MCP tool
* The number of metrics
* Whether the data represents a time series
* Whether the data is ranked
* Whether the data represents a percentage/share
* Whether the data contains two continuous variables
* Whether the data represents a score distribution

This approach makes visualization behavior consistent even when the LLM produces slightly different interpretations of the same question.

#### Decision Rules

| Data / Query Pattern                      | Chart Type     | Reason                                             |
| ----------------------------------------- | -------------- | -------------------------------------------------- |
| One numerical metric over time            | Line           | Best for identifying trends                        |
| Top N categories/entities                 | Horizontal Bar | Makes ranking and category names easy to read      |
| Percentage/share of a total               | Doughnut       | Clearly represents part-to-whole relationships     |
| Two continuous numerical variables        | Scatter        | Shows correlation and distribution                 |
| Review scores from 1–5                    | Horizontal Bar | Clearly represents the frequency of each score     |
| Multiple metrics across states/categories | Dual-axis Bar  | Allows comparison of metrics with different scales |

#### Single Metric Time Series

For queries such as:

> "Show monthly revenue trend for 2017"

the returned data contains a continuous time dimension such as:

```text
Month       Revenue
2017-01     ...
2017-02     ...
2017-03     ...
```

Because the primary purpose is to understand how a metric changes over time, the system selects a **line chart**.

The X-axis represents the time period and the Y-axis represents the numerical metric.

This makes increases, decreases, seasonal patterns, and unusual changes easier to identify.

---

#### Ranked Entity Lists

For queries such as:

> "Show top 10 product categories by revenue"

the system identifies the query as a **ranking problem**.

The returned data contains entities and their corresponding numerical values:

```text
Category        Revenue
Category A      ...
Category B      ...
Category C      ...
```

The system sorts the records in descending order and selects a **horizontal bar chart**.

A horizontal orientation is used because category names can be relatively long. This prevents labels from becoming difficult to read.

The chart therefore communicates both:

1. The value of each category
2. The relative ranking between categories

---

#### Part-to-Whole / Share Analysis

For queries such as:

> "Show payment share of credit card vs boleto"

the user is asking how a total is divided between different payment methods.

The system therefore selects a **doughnut chart**.

For example:

```text
Credit Card → 70%
Boleto      → 30%
```

The values are normalized into percentages so that the visualization represents the contribution of each payment method to the selected total.

The backend also filters the requested payment types rather than displaying unrelated payment methods when the user explicitly asks for a comparison such as credit card vs. boleto.

---

#### Continuous Bivariate Analysis

For queries such as:

> "Show seller delivery time vs review score"

the result contains two numerical variables for each seller:

```text
Seller        Delivery Time       Review Score
Seller A      8.2 days            4.5
Seller B      12.1 days           3.8
Seller C      6.4 days            4.7
```

Since both variables are continuous numerical values, the system selects a **scatter plot**.

The X-axis represents delivery time and the Y-axis represents review score.

This allows the user to visually determine whether longer delivery times appear to be associated with lower review scores.

Importantly, the system does not claim that the visualization proves causation. It only exposes the relationship present in the data.

---

#### Review Score Distribution

For queries such as:

> "Show review score distribution"

the returned data represents the number of reviews associated with each score from 1 to 5.

Example:

```text
Score    Number of Reviews
1        ...
2        ...
3        ...
4        ...
5        ...
```

A **horizontal bar chart** is selected because this is a frequency/distribution problem rather than a time-series or correlation problem.

This makes it easy to identify the most common review score and compare the frequency of each rating.

---

#### Multi-Metric Comparison

When multiple metrics need to be compared across the same dimension, such as states, the application can use separate Y-axes.

For example:

```text
State       Orders       Revenue
SP          ...          ...
RJ          ...          ...
MG          ...          ...
```

Orders and revenue can have very different numerical scales.

Using a single Y-axis could make one metric visually insignificant. Therefore, the application can configure:

```text
Y-axis  → Metric 1
Y1-axis → Metric 2
```

This allows both metrics to remain readable while sharing the same X-axis dimension.

---

### 2. 🔄 Refresh & Diff Detection

The dashboard supports pinned charts so that users can refresh an existing analysis without manually rebuilding the query.

Each pinned dashboard item stores the information required to reproduce the original analysis.

This includes the underlying:

* MCP tool
* Tool parameters
* Chart configuration
* Previous `raw_data` snapshot

When a user requests a refresh, the system re-executes the original MCP tool with the stored parameters.

The refresh process is therefore:

```text
Pinned Chart
     ↓
Read Stored MCP Tool + Parameters
     ↓
Execute MCP Tool Again
     ↓
Fetch Latest Data
     ↓
Compare With Previous Snapshot
     ↓
Detect Significant Change
     ↓
Update Dashboard
```

#### Why Store the Original Parameters?

The system does not attempt to reconstruct the user's natural-language query during refresh.

Instead, it stores the exact structured parameters used during the original execution.

For example:

```text
Tool:
get_order_trends

Parameters:
metric = revenue
start_date = 2017-01-01
end_date = 2017-12-31
group_by = month
```

This guarantees that a refresh executes the **same analysis** rather than accidentally changing the interpretation of the original request.

---

#### Snapshot Comparison

After the MCP tool returns new data, the system compares the new result with the previously stored `raw_data`.

Two important conditions are checked:

**1. Numerical value change**

The primary numerical value is compared using:

```text
percentage_change =
abs(new_value - old_value) / old_value
```

If the change exceeds the configured threshold, the dashboard reports a significant change.

The current implementation uses a **5% threshold**.

Conceptually:

```text
If percentage_change > 5%
    → Significant Change Detected
```

**2. Row-count change**

The system also compares the number of returned records.

For example:

```text
Previous result → 12 rows
New result      → 13 rows
```

Even if the existing numerical values have not changed significantly, the additional row indicates that the underlying result set has changed.

Therefore:

```text
If row_count changes
    → Significant Change Detected
```

This provides protection against cases where a new category, month, seller, or state appears in the refreshed dataset.

---

#### Updating the Dashboard

When a significant change is detected:

1. The latest data replaces the previous snapshot.
2. The chart configuration is updated.
3. The dashboard record is updated in the database.
4. The UI displays a **"Significant Change Detected"** notification.

This allows pinned analytics to behave more like live dashboard components rather than static charts.

---

### 3. 🤖 Normal Agent vs. Fallback Agent

The application uses two execution paths:

```text
                    User Query
                       │
                       ▼
                Normal LLM Agent
                       │
              ┌────────┴────────┐
              │                 │
          Successful         Failure
              │                 │
              ▼                 ▼
          Final Result     Fallback Agent
                                │
                                ▼
                         Deterministic Result
```

The purpose of the fallback agent is not to duplicate the LLM agent.

Instead, it provides a **reliable execution path when the LLM-based workflow cannot successfully complete the request**.

---

### 3.1 Normal LLM Agent — `GeminiAgent`

The normal execution path uses the Gemini model to interpret natural-language questions.

The LLM is responsible for understanding user intent and determining which MCP tools are appropriate.

For example, when the user asks:

> "Show monthly revenue trend for 2017"

the agent needs to understand that:

* The requested metric is revenue.
* The user wants a time-based analysis.
* The requested period is the year 2017.
* Monthly grouping is required.
* The appropriate MCP tool is the order-trend tool.

The agent then calls the required MCP tool using structured parameters.

The result is subsequently passed through the visualization and insight-generation layers.

The normal pipeline can therefore be represented as:

```text
Natural Language Query
        ↓
Gemini LLM
        ↓
Intent Understanding
        ↓
Tool Selection
        ↓
Parameter Extraction
        ↓
MCP Tool Execution
        ↓
Structured Data
        ↓
Chart Selection
        ↓
Insight Generation
        ↓
Response
```

The LLM-based path provides flexibility because users do not need to follow a rigid command format.

For example, these queries can represent the same intent:

```text
"Show monthly revenue for 2017"

"Give me the revenue trend month by month in 2017"

"How did revenue change during 2017?"
```

The LLM can recognize the underlying intent and map the requests to the appropriate data operation.

---

### 3.2 Fallback Agent — `FallbackAgent`

The fallback agent is intentionally designed differently.

It does not depend on the LLM to understand every aspect of the query.

Instead, it uses deterministic techniques such as:

* Regular expressions
* Keyword matching
* Semantic entity extraction
* Explicit parameter rules
* Direct MCP tool execution
* Deterministic chart selection
* Template-based insight generation

For example, the fallback agent can identify patterns such as:

```text
"top 10"
"last year"
"2017"
"monthly"
"revenue"
"seller"
"review"
"delivery"
"credit card"
"boleto"
```

and convert them into structured parameters.

For example:

```text
User:
"Show top 10 product categories by revenue"

Fallback interpretation:

metric      = revenue
entity      = product_category
limit       = 10
sort_order  = descending
```

The fallback agent then directly executes the corresponding MCP operation.

---

### Why Have a Fallback Agent?

LLM-based systems can fail for reasons that are unrelated to the underlying data.

For example:

* Model/API failure
* Invalid function-call generation
* Unexpected response format
* MCP response parsing problems
* Temporary external service failure
* Ambiguous LLM output

Without a fallback mechanism, the user could receive a generic error even though the requested analysis itself is straightforward.

The fallback agent provides a second execution path for common analytical requests.

Therefore, the system follows the principle:

> **Use the LLM for flexibility, but use deterministic logic for reliability.**

---

### 3.3 Difference Between the Two Agents

| Feature                 | Normal `GeminiAgent`       | `FallbackAgent`               |
| ----------------------- | -------------------------- | ----------------------------- |
| Query understanding     | LLM-based                  | Rule-based                    |
| Tool selection          | Dynamically inferred       | Deterministically selected    |
| Parameter extraction    | LLM function calling       | Regex / semantic rules        |
| External LLM dependency | Yes                        | No                            |
| Chart selection         | Deterministic chart engine | Deterministic chart engine    |
| Insight generation      | LLM-generated              | Template/fallback-generated   |
| Flexibility             | High                       | Focused on supported patterns |
| Reliability             | Dependent on LLM/API       | More predictable              |
| Purpose                 | Primary execution path     | Recovery / backup path        |

This separation ensures that the fallback path is genuinely different from the primary path rather than simply calling the same LLM again.

---

### 4. 🧩 Separation of Responsibilities

The application follows a modular architecture where each component has a specific responsibility.

```text
Frontend
   ↓
FastAPI API
   ↓
Agent Layer
   ↓
MCP Client
   ↓
MCP Server
   ↓
SQLite Database
```

The visualization and insight layers operate on the structured result returned by the agent.

This separation prevents business logic from being tightly coupled to the frontend.

For example:

* The **agent layer** understands the query.
* The **MCP layer** performs data operations.
* The **chart engine** determines visualization.
* The **insight engine** generates the explanation.
* The **database layer** stores analytical/dashboard state.
* The **frontend** displays the final result.

This makes individual components easier to test and replace.

---

### 5. 🔌 MCP as the Data Access Layer

The application uses the Model Context Protocol (MCP) to expose analytics operations as structured tools.

Instead of allowing the LLM to directly construct arbitrary SQL queries, the system exposes predefined analytical operations such as:

```text
get_order_trends()
get_product_category_performance()
get_seller_performance()
get_payment_breakdown()
get_customer_reviews()
```

This provides a controlled interface between the agent and the database.

The architecture is therefore:

```text
LLM / Fallback Agent
        ↓
     MCP Client
        ↓
     MCP Server
        ↓
  Analytics Tools
        ↓
      SQLite
```

This design improves maintainability because database operations are centralized inside the MCP tools.

It also reduces the risk of the LLM generating incorrect or unsafe SQL directly.

---

### 6. 🗄️ SQLite as the Analytics Database

SQLite was selected because the Olist dataset is suitable for a lightweight analytical application and does not require a separate database server.

The database contains the relevant Olist datasets and relationships between:

* Orders
* Customers
* Sellers
* Products
* Payments
* Reviews
* Order items

The application initializes the database and loads the required data during startup when necessary.

This keeps the project easy to run locally and simplifies the Docker deployment.

---

### 7. 🧠 Intent-Driven Data Processing

The system determines the expected data shape from the **user's intent**, rather than relying only on which tool happened to execute last.

For example:

```text
Monthly revenue
        ↓
Time-series data
        ↓
Line chart
```

while:

```text
Top 10 categories
        ↓
Ranked categorical data
        ↓
Horizontal bar chart
```

and:

```text
Seller delivery vs review
        ↓
Two continuous variables
        ↓
Scatter plot
```

This prevents visualization logic from becoming tightly coupled to individual MCP tool names.

The same tool can potentially return different analytical shapes depending on parameters, so intent and returned data structure are more reliable signals for visualization.

---

### 8. ⚠️ Error Handling and Graceful Degradation

The application is designed to avoid exposing raw backend exceptions to the user.

Instead of displaying technical errors such as:

```text
unhandled errors in a TaskGroup
```

the system attempts to:

1. Detect the failure.
2. Identify whether the request can be handled by the fallback path.
3. Execute the deterministic fallback logic when appropriate.
4. Return a meaningful response if recovery is possible.
5. Return a clear user-facing error when recovery is not possible.

This is particularly important for an AI application because failures can occur at multiple layers:

```text
LLM
 ↓
MCP Client
 ↓
MCP Server
 ↓
Database
 ↓
Chart Engine
 ↓
Frontend
```

Each layer therefore has a defined responsibility for error handling.

---

### 9. 🔐 Environment and API-Key Management

External API credentials are not hard-coded into the application.

The application reads configuration values from environment variables.

For local development:

```text
.env
```

is used to provide the required API key.

The `.env` file is excluded from Git using `.gitignore`.

A `.env.example` file is committed to the repository so that another developer can understand which environment variables are required without exposing the actual secret.

Example:

```text
GOOGLE_API_KEY=your_api_key_here
```

For deployment, the secret is configured through the hosting platform's environment-variable settings rather than committed to GitHub.

This keeps credentials separate from source code.

---

### 10. 🐳 Docker-Based Deployment

The application is containerized so that the backend, dependencies, and runtime environment can be reproduced consistently.

The project is designed so that:

```bash
docker compose up
```

starts the required services.

This eliminates the need for users to manually install Python packages or configure the application environment individually.

The intended workflow is:

```text
Clone Repository
      ↓
Add API Key to .env
      ↓
docker compose up
      ↓
Application Starts
      ↓
Open Frontend
      ↓
Ask Analytical Questions
```

This design also makes the project easier to deploy on platforms that support Docker containers.

---

## Summary

The overall design prioritizes **reliability, explainability, and separation of responsibilities**.

The LLM provides flexible natural-language understanding, while deterministic components control important downstream behavior such as chart selection, parameter handling, refresh comparison, and fallback execution.

The key architectural principle is:

```text
LLM → Flexible Understanding
MCP → Controlled Data Access
Chart Engine → Deterministic Visualization
Fallback Agent → Reliable Recovery
Database → Persistent Analytical State
Docker → Reproducible Deployment
```

This combination allows the application to behave like an AI-powered analytics assistant without making every part of the system dependent on probabilistic LLM behavior.

## 🎥 Demo Video

Watch the complete project demo walkthrough:

[Demo Video Placeholder](https://drive.google.com/file/d/1JfYIrovoDoj4uonJA6zWY6lRU595CEEe/view?usp=drive_link)

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
