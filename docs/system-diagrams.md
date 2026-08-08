# GBB Terminal System Diagrams

These diagrams describe the current local-first architecture. They distinguish generated frontend assets, application services, external providers, and persisted research records.

## Runtime Architecture

```mermaid
flowchart LR
    Investor[Hobbyist Investor]

    subgraph Browser[Browser]
        ReactUI[React Strategy Lab<br/>Vite + TypeScript + shadcn/ui]
        LegacyUI[Legacy Panels<br/>Option Lab + Stock + Market]
        Charts[Lightweight Charts]
        Workspace[Research Workspace Reducer]
        ReactUI --> Workspace
        Workspace --> Charts
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

    STRATEGY_CATALOGUE ||--o{ BACKTEST_RUNS : defines
    BACKTEST_RUNS ||--o{ BACKTEST_TRADES : contains
    STRATEGY_CATALOGUE o|--o{ RESEARCH_RUNS : catalogues
    OPTION_POSITIONS ||--o{ OPTION_POSITION_EVENTS : journals
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

When the React build exists, `/` serves Strategy Lab from `app/static/react/`. Without generated assets, `/` falls back to the vanilla application. `/legacy` always remains available during the panel-by-panel migration.
