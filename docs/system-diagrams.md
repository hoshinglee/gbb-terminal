# GBB Terminal System Diagrams

These diagrams describe the current local-first architecture. They distinguish generated frontend assets, application services, external providers, and persisted research records.

## Runtime Architecture

```mermaid
flowchart LR
    Investor[Hobbyist Investor]

    subgraph Browser[Browser]
        ReactUI[React Research App<br/>Strategy + Options + Stock + Market]
        LegacyUI[Explicit Vanilla Migration Fallback]
        Charts[Lightweight Charts]
        Scenarios[Accessible Scenario SVG]
        Workspace[Domain-Isolated Workspace State]
        ReactUI --> Workspace
        Workspace --> Charts
        Workspace --> Scenarios
    end

    subgraph Server[FastAPI Process]
        Static[Static Frontend Serving]
        Routes[API Routes<br/>Strategy + Backtest + Stock + Options + Market]
        Settings[Settings + Path Resolution]
        Logging[Structured Logging]
    end

    subgraph Domain[Python Domain Services]
        Strategy[Strategy Catalogue + Safe Factory]
        Backtest[Backtesting + Portfolio + Parameter Search]
        Options[Option Pricing + Lifecycle Simulation]
        MarketData[Provider-Neutral Market Data]
        Translator[Validated LLM Translator]
    end

    subgraph LocalState[Local Machine State]
        DuckDB[(DuckDB<br/>data/gbb_terminal.duckdb)]
        LogFiles[(Rotating Logs<br/>log/)]
        Config[conf/app.yaml + .env]
    end

    subgraph PublicSources[Free External Sources]
        Yahoo[Yahoo Finance]
        SEC[SEC EDGAR]
        FINRA[FINRA]
        FRED[FRED]
        OCC[OCC]
        LLMs[Google AI Studio<br/>OpenAI<br/>Anthropic]
    end

    Investor --> ReactUI
    Investor --> LegacyUI
    ReactUI -->|JSON over /api| Routes
    LegacyUI -->|JSON over /api| Routes
    Static --> ReactUI
    Static --> LegacyUI
    Settings --> Static
    Settings --> Config
    Routes --> Strategy
    Routes --> Backtest
    Routes --> Options
    Routes --> MarketData
    Routes --> Translator
    Routes --> Logging
    Strategy --> DuckDB
    Backtest --> DuckDB
    Options --> DuckDB
    MarketData --> DuckDB
    Logging --> LogFiles
    MarketData --> Yahoo
    MarketData --> SEC
    MarketData --> FINRA
    MarketData --> FRED
    MarketData --> OCC
    Translator --> LLMs
```

## Frontend Research Canvas

```mermaid
flowchart TB
    subgraph Entry[Strategy Entry]
        Natural[Natural-Language Composer]
        Templates[Validated Templates]
        Catalogue[Saved Strategy Catalogue]
        Command[Command Search<br/>Cmd or Ctrl + K]
        Command --> Templates
        Command --> Catalogue
        Command --> Natural
    end

    subgraph State[Single Research Workspace]
        Selection{Strategy Selection<br/>Mutually Exclusive}
        Instruction[Instruction State]
        Template[Template Instance<br/>Typed Parameters]
        Saved[Catalogue Strategy]
        Context[Research Design<br/>Ticker + Window + Benchmark]
        Assumptions[Execution + Validation Assumptions]
        Result[Latest Result + Search Evidence]
        Selection --> Instruction
        Selection --> Template
        Selection --> Saved
    end

    subgraph Canvas[Persistent Canvas]
        Composer[Readable Rule + Editable Chips]
        Layout[Side By Side or Stacked]
        Preview[Candles + Volume + RSI + MACD]
        ContextBar[Compact Context Bar + Run]
        Evidence[Evidence Tabs<br/>Overview + Equity + Trades + Robustness]
        Layout --> Composer
        Layout --> Preview
    end

    subgraph APIFlow[Run Controller]
        Proposal[LLM Proposal Review]
        ResearchRun[Research Run]
        ParameterSearch[Guarded Parameter Search]
        LegacyRun[Legacy Catalogue Run]
    end

    Natural --> Selection
    Templates --> Selection
    Catalogue --> Selection
    Instruction --> Composer
    Template --> Composer
    Saved --> Composer
    Context --> ContextBar
    Assumptions --> ContextBar
    State --> Preview
    ContextBar --> Proposal
    ContextBar --> ResearchRun
    ContextBar --> ParameterSearch
    ContextBar --> LegacyRun
    Proposal --> Result
    ResearchRun --> Result
    ParameterSearch --> Result
    LegacyRun --> Result
    Result --> Preview
    Result --> Evidence
```

The reducer clears incompatible selection data whenever the user switches among an instruction, template, or saved strategy. Canvas layout preference is presentation-only browser state and does not enter strategy identity or research reproducibility.

## Frontend Option Lifecycle Canvas

```mermaid
flowchart TB
    subgraph Build[Build Position]
        Recipes[Core Position Recipes]
        Legs[Editable Leg Cards]
        Chain[Current Chain Side Sheet]
        Assumptions[Model Assumptions Side Sheet]
        Recipes --> Legs
        Chain -->|Fill selected leg only| Legs
        Assumptions --> Draft
        Legs --> Draft[Typed Position Draft]
    end

    subgraph Explore[Explore Evidence]
        Simulate[American-Model Simulation]
        Run[Immutable Simulation Run]
        Payoff[Expiry Payoff]
        Surface[Price × Time Slices]
        Paths[Underlying + Position P&L Paths]
        Greeks[Scaled Greeks + Probability]
        Draft --> Simulate
        Simulate --> Run
        Simulate --> Payoff
        Simulate --> Surface
        Simulate --> Paths
        Simulate --> Greeks
    end

    subgraph Journal[Journal Lifecycle]
        Position[Persisted Paper Position]
        Decision{Validated Event}
        State[Complete State After Event]
        Ledger[Immutable Event Timeline]
        Run --> Position
        Position --> Decision
        Decision --> State
        State --> Ledger
        State --> Decision
    end

    Yahoo[Yahoo Current Chain] --> Chain
    OptionAPI[FastAPI Option Routes] --> Simulate
    OptionAPI --> Position
    OptionAPI --> Decision
    Run --> DuckDB[(DuckDB)]
    Position --> DuckDB
    Ledger --> DuckDB
```

Simulation state and persisted ledger state are intentionally separate. Editing a new draft invalidates stale scenario evidence but never rewrites an earlier paper-position event. The browser sends only validated JSON option contracts; all pricing, collateral, cash, share, and realized-P&L transitions remain in Python.

## Option Lifecycle Request Sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as React Option Lab
    participant API as FastAPI Option Routes
    participant Data as MarketData Service
    participant Engine as Option Pricing/Lifecycle
    participant DB as DuckDB
    participant Yahoo as Yahoo Finance

    User->>UI: Choose recipe and selected leg
    UI->>API: GET chain for selected expiry
    API->>Data: Request newest snapshot
    Data->>DB: Check daily/fresh cache
    alt Cached snapshot available
        DB-->>Data: Chain plus provenance
    else Provider required
        Data->>Yahoo: Fetch selected current expiry
        Yahoo-->>Data: All expiries and all selected-date contracts
        Data->>DB: Cache ticker/expiry snapshot independently
    end
    API-->>UI: Current/cached chain and warnings
    User->>UI: Simulate exact draft
    UI->>API: POST simulation
    API->>Engine: American pricing, payoff, Greeks, paths
    Engine-->>API: Theoretical evidence and limitations
    API->>DB: Append immutable simulation run
    API-->>UI: Evidence plus run ID and model version
    User->>UI: Create paper position
    UI->>API: POST position
    API->>Engine: Reconcile initial premium, shares, collateral
    API->>DB: Persist state plus opened event
    DB-->>UI: Position and event timeline
    User->>UI: Hold, close, roll, exercise, expire, or assign
    UI->>API: POST lifecycle event
    API->>Engine: Validate and calculate next complete state
    API->>DB: Transactionally append event and update current state
    DB-->>UI: Reconciled ledger
```

## Frontend Observability Canvases

```mermaid
flowchart LR
    subgraph Stock[React Stock Observatory]
        StockContext[Ticker + Window]
        Watchlist[Browser-Local Watchlist]
        Quote[Quote + Provenance]
        Replay[Day/Week/Month/Year OHLCV<br/>Volume + RSI + MACD]
        OptionContext[Expiry-Aware Current Chain]
        StockContext --> Quote
        StockContext --> Replay
        StockContext --> OptionContext
        Watchlist --> StockContext
    end

    subgraph Market[React Market Pulse]
        Benchmark[SPY Context]
        Breadth[Sector Breadth]
        Relative[3M Relative Strength]
        Macro[Cross-Asset Proxies]
        Providers[Provider Readiness]
        Benchmark --> Breadth
        Benchmark --> Relative
    end

    StockAPI[GET /api/v2/stocks/:ticker] --> Quote
    StockAPI --> Replay
    ChainAPI[GET /api/v2/options/chains/:ticker] --> OptionContext
    MarketAPI[GET /api/v2/market-overview] --> Benchmark
    MarketAPI --> Breadth
    MarketAPI --> Relative
    MarketAPI --> Macro
    MarketAPI --> Providers
    DuckDB[(DuckDB Cache)] --> StockAPI
    DuckDB --> ChainAPI
    DuckDB --> MarketAPI
    Yahoo[Yahoo Finance] --> StockAPI
    Yahoo --> ChainAPI
    Yahoo --> MarketAPI
    Relative -->|Validated ticker link| StockContext
    StockContext -->|Ticker only| Strategy[Strategy Lab]
    StockContext -->|Ticker only| Options[Option Lab]
```

Stock and market state never becomes strategy identity or option-position state. Cross-lab navigation carries only a validated symbol. Market overview rows fail independently, so an unavailable ETF or macro proxy remains visible with warnings while successful current or cached rows continue rendering.

## Research Run And Data Retrieval

```mermaid
sequenceDiagram
    actor User
    participant UI as React Strategy Lab
    participant API as FastAPI Route
    participant Catalogue as Strategy Catalogue
    participant Data as MarketData Service
    participant DB as DuckDB
    participant Provider as Public Provider
    participant Engine as Backtest Engine

    User->>UI: Select strategy, ticker, window, assumptions
    UI->>API: POST research run or parameter search
    API->>Catalogue: Validate template version and parameters
    Catalogue-->>API: Declarative strategy
    API->>Data: Request ticker and benchmark histories
    Data->>DB: Check fresh cached observations

    alt Fresh local cache exists
        DB-->>Data: Return OHLCV and provenance
    else Cache missing or stale
        Data->>Provider: Fetch public data with retry and rate limits
        alt Provider responds
            Provider-->>Data: Data plus source timestamps
            Data->>DB: Persist normalized observations and metadata
        else Provider unavailable and stale cache exists
            DB-->>Data: Return stale data
            Data-->>API: Attach visible quality warning
        end
    end

    Data-->>API: Aligned histories and snapshot metadata
    API->>Engine: Run next-open execution and benchmark comparisons
    Engine-->>API: Metrics, equity, trades, regimes, market chart
    API->>DB: Persist immutable research run and reproducibility key
    API-->>UI: Return evidence payload
    UI-->>User: Render charts, trade ledger, robustness, assumptions
```

## Company Intelligence Metric Pipeline

```mermaid
flowchart LR
    SEC[SEC Company Facts + Submissions] --> FactService[FinancialFactService]
    Identity[Canonical company_id + CIK] --> FactService
    FactService --> RawCache[(provider_cache)]
    FactService --> Facts[(sec_financial_facts<br/>accession + known_at)]
    Facts --> AsOf{as_of filter}
    AsOf --> Definitions[Versioned Concept Precedence]
    Definitions --> Units[Explicit Unit Normalization]
    Units --> Periods[Annual / Discrete Quarter / TTM]
    Periods --> Derived[Growth / Margins / FCF / ROE / ROIC / Net Debt]
    Derived --> Evidence[Typed Values + Warnings + Source Fact IDs]
```

Provider extraction does not choose business metrics. The intelligence engine can be rerun deterministically against the same `as_of` boundary and definition version, while every result retains source-fact lineage.

## DuckDB Logical Model

```mermaid
erDiagram
    STRATEGY_CATALOGUE {
        string strategy_id PK
        string strategy_key UK
        string family
        string template_id
        int template_version
        json strategy_json
        string strategy_yaml
        timestamp updated_at
    }

    BACKTEST_RUNS {
        string run_id PK
        string strategy_id
        string ticker
        string run_window
        json metrics
        timestamp created_at
    }

    BACKTEST_TRADES {
        string run_id PK
        int trade_number PK
        date entry_date
        date exit_date
        double pnl
        double pnl_percent
    }

    RESEARCH_RUNS {
        string run_id PK
        string strategy_id
        string strategy_key
        string reproducibility_key
        json strategy_json
        json research_design
        json data_snapshot
        json validation
        json tested_parameters
        json results
    }

    PRICE_HISTORY {
        string symbol PK
        date price_date PK
        double open
        double high
        double low
        double close
        double volume
        timestamp fetched_at
    }

    OPTION_CHAINS {
        string symbol PK
        timestamp fetched_at
        json payload
    }

    OPTION_CHAIN_SNAPSHOTS {
        string symbol PK
        date expiration PK
        date snapshot_date PK
        timestamp known_at
        string source
        json payload
    }

    OPTION_POSITIONS {
        string position_id PK
        string owner_id
        string ticker
        string status
        json state
        timestamp updated_at
    }

    OPTION_POSITION_EVENTS {
        string event_id PK
        string position_id
        int event_number UK
        string event_type
        json event_payload
        json state_after
    }

    PROVIDER_CACHE {
        string provider PK
        string dataset PK
        string symbol PK
        timestamp observation_timestamp
        timestamp known_at
        timestamp retrieved_at
        string status
        json payload
    }

    LOCAL_JOBS {
        string job_id PK
        string job_type
        string status
        double progress
        json request
        json result
        boolean cancel_requested
    }

    COMPANIES {
        string company_id PK
        string cik UK
        string legal_name
        string status
        string sector
        string industry
        string fiscal_year_end
        json provenance
    }

    COMPANY_SECURITY_MAPPINGS {
        string security_id PK
        string company_id FK
        string ticker
        string exchange
        date valid_from
        date valid_to
        boolean is_primary
        string status
        json provenance
    }

    SEC_FINANCIAL_FACTS {
        string fact_id PK
        string company_id FK
        string taxonomy
        string concept
        double value
        string unit
        date period_end
        timestamp known_at
        string accession_number
        string form
        json source_metadata
    }

    STRATEGY_CATALOGUE ||--o{ BACKTEST_RUNS : defines
    BACKTEST_RUNS ||--o{ BACKTEST_TRADES : contains
    STRATEGY_CATALOGUE o|--o{ RESEARCH_RUNS : catalogues
    OPTION_POSITIONS ||--o{ OPTION_POSITION_EVENTS : journals
    COMPANIES ||--o{ COMPANY_SECURITY_MAPPINGS : identifies
    COMPANIES ||--o{ SEC_FINANCIAL_FACTS : reports
```

The relationships shown are logical domain relationships; DuckDB does not currently declare every one as a foreign-key constraint. Cache tables are intentionally independent so provider outages and schema evolution do not block research records.

## Frontend Build And Fallback

```mermaid
flowchart LR
    Source[app/web<br/>React + TypeScript Source]
    Build[npm run build]
    Generated[app/static/react<br/>Ignored Generated Assets]
    Legacy[app/index.html<br/>Vanilla Fallback]
    Settings{React index exists?}
    Root[GET /]
    LegacyRoute[GET /legacy]

    Source --> Build --> Generated
    Root --> Settings
    Settings -->|Yes| Generated
    Settings -->|No| Legacy
    LegacyRoute --> Legacy
```

When the React build exists, `/` serves Strategy Lab while `/?lab=options`, `/?lab=stock`, and `/?lab=market` select the other lazy-loaded canvases from the same generated application. Without generated assets, `/` falls back to the vanilla application. `/legacy` remains available until connected-browser parity gates allow explicit retirement.
