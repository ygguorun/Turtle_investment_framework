# Turtle Investment Framework — Skill Definition

## Skill Info
- **Name**: turtle-analysis
- **Description**: Run a full 龟龟投资策略 (Turtle Investment Framework) multi-phase fundamental analysis on Chinese A-share or HK stocks
- **Entry Point**: `prompts/coordinator.md`
- **Slash Command**: `/turtle-analysis <stock_code>`

## Dependencies
- **download-report**: Built-in `/download-annual-report` slash command for Phase 0 PDF acquisition
- **Python environment**: `.venv/` (via `bash init.sh`) or `uv` (`uv sync`)
- **Data provider**: `tushare` (default) or `akshare` via `DATA_PROVIDER`
- **Tushare Pro API**: Required when using `DATA_PROVIDER=tushare`

## Required Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `DATA_PROVIDER` | Data source provider (`tushare` or `akshare`) | No (default: `tushare`) |
| `TUSHARE_TOKEN` | Tushare Pro API token | Yes when `DATA_PROVIDER=tushare`; No when `akshare` |

## Pipeline Phases
1. **Phase 0**: PDF acquisition (`/download-annual-report` slash command)
2. **Phase 1A**: Provider-routed market data collection (`scripts/tushare_collector.py`)
3. **Phase 1B**: Agent WebSearch for qualitative data
4. **Phase 2A**: PDF preprocessing (`scripts/pdf_preprocessor.py`)
5. **Phase 2B**: Agent PDF structured extraction
6. **Phase 3**: 4-factor analysis and report generation

## Output
- `output/{code}_{company}/` — all intermediate and final files
- Final report: `{company}_{code}_分析报告.md`

## Notes
- In `tushare` mode, permission errors on supported A-share endpoints automatically fallback to AkShare.
