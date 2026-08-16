# zoomies

## What Zoomies Does

Zoomies is a real-time ranking system that identifies and displays volatile assets based on return and volatility metrics. The system provides investors with a transparent, data-driven view of market movement with minimal UI overhead.

## Universe and Ranking Methodology

The ranking system operates on a configurable universe of assets and applies the following methodology:

- **Primary Score**: Combines return and volatility using a consistent formula
- **Scoring Model**: `score = return + volatility`
- **Ranking**: Assets ranked by score in descending order
- **Refresh Frequency**: Data updates automatically on a configured schedule
- **Universe Selection**: Configurable asset lists by market, sector, or custom filters

## Current Features

- Real-time ranking display with live score updates
- Asset universe management and filtering
- Return and volatility metric calculation
- Historical score tracking for trend analysis
- Minimal, phone-first interface design
- Progressive information disclosure

## Analytics

- Asset performance tracking
- Volatility distribution analysis
- Score movement history
- Return distribution patterns

## Architecture

### Data Flow

1. **Source Data**: Asset prices and metrics from configured data sources
2. **Calculation**: Score computation using return and volatility
3. **Storage**: Results persisted with timestamp for historical tracking
4. **Delivery**: API and UI serve current rankings and historical data

### Components

- **Calculator**: Computes return, volatility, and combined score
- **Database**: Stores rankings, scores, and metadata
- **API**: Serves rankings and historical data
- **UI**: Phone-first web interface displaying current rankings

## Data Refresh and Rebuild

### Regular Data Refresh

Data is refreshed on a scheduled interval (default: hourly). Each refresh:

1. Fetches latest asset data
2. Recalculates scores for all assets in the universe
3. Updates rankings
4. Preserves historical data for trend analysis

### Full Rebuild

To rebuild the entire ranking system from scratch:

```bash
# Rebuild rankings and history
npm run rebuild

# Or with options
npm run rebuild -- --from-date YYYY-MM-DD
```

This operation:
- Clears existing calculated data
- Reprocesses all historical data
- Rebuilds score history
- Recalculates all rankings

### Configuration

Edit `config.json` to customize:

- Asset universe definitions
- Refresh frequency
- Score calculation parameters
- Data retention policies

## Development

See [AGENTS.md](AGENTS.md) for contribution guidelines, code review processes, and collaboration workflow.

See [DESIGN.md](DESIGN.md) for product principles and design intent.
