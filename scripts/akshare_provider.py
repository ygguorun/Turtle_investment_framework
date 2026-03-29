"""AkShare fallback provider for A-share endpoints.

This module maps a subset of Tushare-style endpoint names to AkShare and
returns DataFrames with Tushare-like columns used by this project.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd

try:
    import akshare as ak
except ImportError:  # pragma: no cover
    ak = None


def _require_ak() -> None:
    if ak is None:
        raise RuntimeError("AkShare is not installed")


def _to_ts_code(code: str) -> str:
    c = str(code).strip().upper()
    if c.endswith(".SH") or c.endswith(".SZ"):
        return c
    digits = "".join(ch for ch in c if ch.isdigit())
    if len(digits) != 6:
        return c
    if digits.startswith(("6", "9")):
        return f"{digits}.SH"
    return f"{digits}.SZ"


def _a_code(ts_code: str) -> str:
    return str(ts_code).split(".")[0]


def _a_prefixed(ts_code: str) -> str:
    code = _a_code(ts_code)
    if str(ts_code).upper().endswith(".SH"):
        return f"sh{code}"
    return f"sz{code}"


def _ak_market(ts_code: str) -> str:
    return "SSE" if str(ts_code).upper().endswith(".SH") else "SZSE"


def _normalize_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val)
    if len(s) >= 10 and "-" in s:
        return s[:10].replace("-", "")
    if len(s) == 8 and s.isdigit():
        return s
    try:
        return pd.to_datetime(val).strftime("%Y%m%d")
    except Exception:
        return s[:8]


def _filter_fields(df: pd.DataFrame, fields: str | None) -> pd.DataFrame:
    if not fields:
        return df
    want = [x.strip() for x in fields.split(",") if x.strip()]
    for col in want:
        if col not in df.columns:
            df[col] = pd.NA
    return df[want]


def _derive_dividend_end_date(row: pd.Series) -> str:
    """Infer fiscal year end for dividend rows.

    Align with project dividend fixture semantics where announcement/record/ex
    dates are usually in the following year of the profit year.
    """
    for key in ("除权除息日", "股权登记日", "公告日期"):
        d = _normalize_date(row.get(key))
        if len(d) >= 4 and d[:4].isdigit():
            y = int(d[:4]) - 1
            if y >= 1900:
                return f"{y}1231"
    return ""


@lru_cache(maxsize=1)
def _spot_df() -> pd.DataFrame:
    _require_ak()
    return ak.stock_zh_a_spot_em()


@lru_cache(maxsize=1)
def _a_code_name_df() -> pd.DataFrame:
    _require_ak()
    return ak.stock_info_a_code_name()


def _latest_pledge_date() -> str:
    today = datetime.now().date()
    for i in range(0, 90):
        d = today - timedelta(days=i)
        if d.weekday() < 5:
            return d.strftime("%Y%m%d")
    return today.strftime("%Y%m%d")


def _latest_quarter_dates() -> list[str]:
    y = datetime.now().year
    out = []
    for yy in range(y, y - 6, -1):
        out.extend([f"{yy}1231", f"{yy}0930", f"{yy}0630", f"{yy}0331"])
    return out


def _map_income(ts_code: str) -> pd.DataFrame:
    df = ak.stock_financial_report_sina(stock=_a_prefixed(ts_code), symbol="利润表")
    mapped = pd.DataFrame({
        "ts_code": ts_code,
        "end_date": df["报告日"].astype(str),
        "revenue": df.get("营业收入"),
        "oper_cost": df.get("营业成本"),
        "biz_tax_surch": df.get("营业税金及附加"),
        "sell_exp": df.get("销售费用"),
        "admin_exp": df.get("管理费用"),
        "rd_exp": df.get("研发费用"),
        "finance_exp": df.get("财务费用"),
        "assets_impair_loss": df.get("资产减值损失"),
        "credit_impair_loss": df.get("信用减值损失"),
        "fv_value_chg_gain": df.get("公允价值变动收益"),
        "invest_income": df.get("投资收益"),
        "asset_disp_income": df.get("资产处置收益"),
        "operate_profit": df.get("营业利润"),
        "non_oper_income": df.get("营业外收入"),
        "non_oper_exp": df.get("营业外支出"),
        "total_profit": df.get("利润总额"),
        "income_tax": df.get("所得税费用"),
        "n_income": df.get("净利润"),
        "n_income_attr_p": df.get("归属于母公司所有者的净利润"),
        "minority_gain": df.get("少数股东损益"),
        "basic_eps": df.get("基本每股收益"),
        "diluted_eps": df.get("稀释每股收益"),
        "oth_income": df.get("其他收益"),
        "report_type": "1",
    })
    return mapped


def _map_balance(ts_code: str) -> pd.DataFrame:
    df = ak.stock_financial_report_sina(stock=_a_prefixed(ts_code), symbol="资产负债表")
    mapped = pd.DataFrame({
        "ts_code": ts_code,
        "end_date": df["报告日"].astype(str),
        "money_cap": df.get("货币资金"),
        "trad_asset": df.get("交易性金融资产"),
        "notes_receiv": df.get("应收票据"),
        "accounts_receiv": df.get("应收账款"),
        "oth_receiv": df.get("其他应收款(合计)"),
        "inventories": df.get("存货"),
        "oth_cur_assets": df.get("其他流动资产"),
        "total_cur_assets": df.get("流动资产合计"),
        "lt_eqt_invest": df.get("长期股权投资"),
        "fix_assets": df.get("固定资产及清理合计").combine_first(df.get("固定资产净额")),
        "cip": df.get("在建工程合计").combine_first(df.get("在建工程")),
        "intang_assets": df.get("无形资产"),
        "goodwill": df.get("商誉"),
        "total_assets": df.get("资产总计"),
        "st_borr": df.get("短期借款"),
        "notes_payable": df.get("应付票据"),
        "acct_payable": df.get("应付账款"),
        "contract_liab": df.get("合同负债"),
        "adv_receipts": df.get("预收款项"),
        "non_cur_liab_due_1y": df.get("一年内到期的非流动负债"),
        "oth_cur_liab": df.get("其他流动负债"),
        "total_cur_liab": df.get("流动负债合计"),
        "lt_borr": df.get("长期借款"),
        "bond_payable": df.get("应付债券"),
        "total_liab": df.get("负债合计"),
        "defer_tax_assets": df.get("递延所得税资产"),
        "defer_tax_liab": df.get("递延所得税负债"),
        "total_hldr_eqy_exc_min_int": df.get("归属于母公司股东权益合计"),
        "minority_int": df.get("少数股东权益"),
        "report_type": "1",
    })
    return mapped


def _map_cashflow(ts_code: str) -> pd.DataFrame:
    df = ak.stock_financial_report_sina(stock=_a_prefixed(ts_code), symbol="现金流量表")
    mapped = pd.DataFrame({
        "ts_code": ts_code,
        "end_date": df["报告日"].astype(str),
        "n_cashflow_act": df.get("经营活动产生的现金流量净额"),
        "n_cashflow_inv_act": df.get("投资活动产生的现金流量净额"),
        "n_cash_flows_fnc_act": df.get("筹资活动产生的现金流量净额"),
        "c_pay_acq_const_fiolta": df.get("购建固定资产、无形资产和其他长期资产所支付的现金"),
        "depr_fa_coga_dpba": df.get("固定资产折旧、油气资产折耗、生产性生物资产折旧"),
        "amort_intang_assets": df.get("无形资产摊销"),
        "lt_amort_deferred_exp": df.get("长期待摊费用摊销"),
        "c_pay_dist_dpcp_int_exp": df.get("分配股利、利润或偿付利息所支付的现金"),
        "c_pay_to_staff": df.get("支付给职工以及为职工支付的现金"),
        "c_paid_for_taxes": df.get("支付的各项税费"),
        "n_recp_disp_fiolta": df.get("处置固定资产、无形资产和其他长期资产收回的现金净额"),
        "receiv_tax_refund": df.get("收到的税费返还"),
        "c_recp_return_invest": df.get("收回投资所收到的现金"),
        "report_type": "1",
    })
    return mapped


def _map_fina_indicator(ts_code: str) -> pd.DataFrame:
    src = ak.stock_financial_abstract(symbol=_a_code(ts_code))
    if src.empty:
        return pd.DataFrame()
    date_cols = [c for c in src.columns if c.isdigit() and len(c) == 8]
    idx = src.set_index("指标")

    def _row(name: str):
        if name in idx.index:
            v = idx.loc[name]
            if isinstance(v, pd.DataFrame):
                v = v.iloc[0]
            return v
        return None

    metric_map = {
        "roe": _row("净资产收益率(ROE)"),
        "roe_waa": _row("净资产收益率_平均"),
        "grossprofit_margin": _row("毛利率"),
        "netprofit_margin": _row("销售净利率"),
        "current_ratio": _row("流动比率"),
        "quick_ratio": _row("速动比率"),
        "assets_turn": _row("总资产周转率"),
        "debt_to_assets": _row("资产负债率"),
        "revenue_yoy": _row("营业总收入增长率"),
        "netprofit_yoy": _row("归属母公司净利润增长率"),
        "ocfps": _row("每股经营现金流"),
        "bps": _row("每股净资产"),
        "profit_dedt": _row("扣非净利润"),
    }

    rows = []
    for d in date_cols:
        row = {"ts_code": ts_code, "end_date": d}
        for k, series in metric_map.items():
            row[k] = series.get(d) if series is not None else pd.NA
        row["ebitda"] = pd.NA
        row["fcff"] = pd.NA
        row["netdebt"] = pd.NA
        row["interestdebt"] = pd.NA
        rows.append(row)
    return pd.DataFrame(rows)


def _map_dividend(ts_code: str) -> pd.DataFrame:
    df = ak.stock_history_dividend_detail(symbol=_a_code(ts_code), indicator="分红")
    if df.empty:
        return pd.DataFrame()
    # Approximate base_share with latest outstanding shares (万股).
    # This keeps downstream total-dividend calculations usable when source
    # does not expose historical share base per announcement.
    base_share = pd.NA
    try:
        spot = _spot_df().copy()
        spot["ts_code"] = spot["代码"].astype(str).map(_to_ts_code)
        row = spot[spot["ts_code"] == ts_code]
        if not row.empty:
            close = pd.to_numeric(row.iloc[0].get("最新价"), errors="coerce")
            total_mv = pd.to_numeric(row.iloc[0].get("总市值"), errors="coerce")
            if close and close == close and close > 0 and total_mv and total_mv == total_mv:
                base_share = float(total_mv) / float(close) / 10000.0
    except Exception:
        pass

    mapped = pd.DataFrame({
        "ts_code": ts_code,
        "ann_date": df["公告日期"].map(_normalize_date),
        "end_date": df.apply(_derive_dividend_end_date, axis=1),
        "div_proc": df.get("进度").fillna(""),
        "stk_div": df.get("送股").fillna(0) + df.get("转增").fillna(0),
        "cash_div_tax": pd.to_numeric(df.get("派息"), errors="coerce") / 10.0,
        "record_date": df.get("股权登记日").map(_normalize_date),
        "ex_date": df.get("除权除息日").map(_normalize_date),
        "base_share": base_share,
    })
    return mapped


def _map_top10_holders(ts_code: str) -> pd.DataFrame:
    last_err = None
    for d in _latest_quarter_dates():
        try:
            df = ak.stock_gdfx_top_10_em(symbol=_a_prefixed(ts_code), date=d)
            if df.empty:
                continue
            return pd.DataFrame({
                "ts_code": ts_code,
                "end_date": d,
                "holder_name": df.get("股东名称"),
                "hold_amount": pd.to_numeric(df.get("持股数"), errors="coerce") / 10000.0,
                "hold_ratio": df.get("占总股本持股比例"),
            })
        except Exception as e:
            last_err = e
    if last_err is not None:
        raise last_err
    return pd.DataFrame()


def _map_mainbz(ts_code: str) -> pd.DataFrame:
    df = ak.stock_zygc_em(symbol=_a_prefixed(ts_code).upper())
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "ts_code": ts_code,
        "end_date": df["报告日期"].map(_normalize_date),
        "bz_item": df.get("主营构成"),
        "bz_sales": df.get("主营收入"),
        "bz_profit": df.get("主营利润"),
        "bz_cost": df.get("主营成本"),
    })


def _map_repurchase(ts_code: str) -> pd.DataFrame:
    df = ak.stock_repurchase_em()
    code = _a_code(ts_code)
    df = df[df["股票代码"].astype(str) == code].copy()
    if df.empty:
        return pd.DataFrame()
    amount = pd.to_numeric(df.get("已回购金额"), errors="coerce")
    amount = amount.where(amount.notna(), pd.to_numeric(df.get("计划回购金额区间-上限"), errors="coerce"))
    vol = pd.to_numeric(df.get("已回购股份数量"), errors="coerce")
    vol = vol.where(vol.notna(), pd.to_numeric(df.get("计划回购数量区间-上限"), errors="coerce"))
    return pd.DataFrame({
        "ts_code": ts_code,
        "ann_date": df.get("最新公告日期").map(_normalize_date),
        "end_date": df.get("最新公告日期").map(_normalize_date),
        "proc": df.get("实施进度"),
        "exp_date": pd.NA,
        "vol": vol,
        "amount": amount,
        "high_limit": df.get("计划回购价格区间"),
        "low_limit": pd.NA,
    })


def _map_pledge_stat(ts_code: str) -> pd.DataFrame:
    date = _latest_pledge_date()
    last_err = None
    for i in range(0, 40):
        d = (datetime.strptime(date, "%Y%m%d") - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = ak.stock_gpzy_pledge_ratio_em(date=d)
            code = _a_code(ts_code)
            row = df[df["股票代码"].astype(str) == code]
            if row.empty:
                continue
            row = row.iloc[[0]].copy()
            return pd.DataFrame({
                "ts_code": ts_code,
                "end_date": row["交易日期"].map(_normalize_date),
                "pledge_count": row.get("质押笔数"),
                "unrest_pledge": row.get("无限售股质押数") * 10000,
                "rest_pledge": row.get("限售股质押数") * 10000,
                "total_share": pd.NA,
                "pledge_ratio": row.get("质押比例"),
            })
        except Exception as e:
            last_err = e
    if last_err is not None:
        raise last_err
    return pd.DataFrame()


def _map_yc_cb(**kwargs) -> pd.DataFrame:
    start = kwargs.get("start_date") or (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    end = kwargs.get("end_date") or datetime.now().strftime("%Y%m%d")
    df = ak.bond_china_yield(start_date=start, end_date=end)
    if df.empty:
        return pd.DataFrame()
    df = df[df["曲线名称"].astype(str).str.contains("国债收益率曲线", na=False)].copy()
    if df.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "trade_date": df["日期"].map(_normalize_date),
        "yield": pd.to_numeric(df.get("10年"), errors="coerce"),
    })


def _map_trade_cal(**kwargs) -> pd.DataFrame:
    start = kwargs.get("start_date", "19900101")
    end = kwargs.get("end_date", datetime.now().strftime("%Y%m%d"))
    cal = ak.tool_trade_date_hist_sina()
    cal["cal_date"] = pd.to_datetime(cal["trade_date"]).dt.strftime("%Y%m%d")
    cal = cal[(cal["cal_date"] >= start) & (cal["cal_date"] <= end)].copy()
    cal["is_open"] = 1
    return cal[["cal_date", "is_open"]]


def _map_fina_audit(ts_code: str) -> pd.DataFrame:
    df = ak.stock_financial_report_sina(stock=_a_prefixed(ts_code), symbol="利润表")
    if df.empty:
        return pd.DataFrame()
    report_dates = df.get("报告日").astype(str)
    annual_mask = report_dates.str.endswith("1231")
    if annual_mask.any():
        df = df[annual_mask].copy()

    raw_audit = df.get("是否审计")
    audit_result = raw_audit.astype(str)
    # Avoid false risk warnings from interim "未审计" status.
    audit_result = audit_result.where(~audit_result.str.contains("未审计", na=False), "")
    audit_result = audit_result.replace({"是": "标准无保留意见", "已审计": "标准无保留意见"})

    out = pd.DataFrame({
        "ts_code": ts_code,
        "end_date": df.get("报告日").astype(str),
        "audit_result": audit_result,
        "audit_agency": pd.NA,
        "audit_fees": pd.NA,
    })
    out = out.drop_duplicates(subset=["end_date"]).sort_values("end_date", ascending=False)
    return out


def fetch(api_name: str, **kwargs) -> pd.DataFrame:
    _require_ak()
    fields = kwargs.get("fields")
    ts_code = kwargs.get("ts_code")
    if ts_code:
        ts_code = _to_ts_code(ts_code)

    if api_name == "stock_basic":
        if ts_code:
            info = ak.stock_individual_info_em(symbol=_a_code(ts_code))
            kv = dict(zip(info["item"].astype(str), info["value"])) if not info.empty else {}
            df = pd.DataFrame([{
                "ts_code": ts_code,
                "name": str(kv.get("股票简称", "")),
                "industry": str(kv.get("行业", "")),
                "area": "",
                "market": "",
                "exchange": _ak_market(ts_code),
                "list_date": _normalize_date(kv.get("上市时间", "")),
                "fullname": str(kv.get("股票简称", "")),
            }])
        else:
            base = _a_code_name_df().copy()
            base["ts_code"] = base["code"].map(_to_ts_code)
            base["name"] = base["name"].astype(str)
            base["industry"] = ""
            base["area"] = ""
            base["market"] = ""
            base["exchange"] = base["ts_code"].map(_ak_market)
            base["list_date"] = "20000101"
            base["fullname"] = base["name"]
            df = base
        return _filter_fields(df, fields)

    if api_name == "daily_basic":
        spot = _spot_df().copy()
        spot["ts_code"] = spot["代码"].astype(str).map(_to_ts_code)
        if ts_code:
            spot = spot[spot["ts_code"] == ts_code]
        total_mv_yuan = pd.to_numeric(spot.get("总市值"), errors="coerce")
        circ_mv_yuan = pd.to_numeric(spot.get("流通市值"), errors="coerce")
        close = pd.to_numeric(spot.get("最新价"), errors="coerce")
        shares = total_mv_yuan / close
        df = pd.DataFrame({
            "ts_code": spot["ts_code"],
            "trade_date": kwargs.get("trade_date") or datetime.now().strftime("%Y%m%d"),
            "close": close,
            "pe_ttm": pd.to_numeric(spot.get("市盈率-动态"), errors="coerce"),
            "pb": pd.to_numeric(spot.get("市净率"), errors="coerce"),
            "total_mv": total_mv_yuan / 10000.0,
            "circ_mv": circ_mv_yuan / 10000.0,
            "total_share": shares / 10000.0,
            "float_share": shares / 10000.0,
            "dv_ttm": pd.NA,
            "turnover_rate": pd.to_numeric(spot.get("换手率"), errors="coerce"),
        })
        return _filter_fields(df, fields)

    if api_name in ("daily", "weekly"):
        if not ts_code:
            return pd.DataFrame()
        period = "weekly" if api_name == "weekly" else "daily"
        hist = ak.stock_zh_a_hist(
            symbol=_a_code(ts_code),
            period=period,
            start_date=kwargs.get("start_date", "19900101"),
            end_date=kwargs.get("end_date", datetime.now().strftime("%Y%m%d")),
            adjust="",
        )
        if hist.empty:
            return pd.DataFrame()
        df = pd.DataFrame({
            "ts_code": ts_code,
            "trade_date": hist["日期"].map(_normalize_date),
            "open": pd.to_numeric(hist.get("开盘"), errors="coerce"),
            "high": pd.to_numeric(hist.get("最高"), errors="coerce"),
            "low": pd.to_numeric(hist.get("最低"), errors="coerce"),
            "close": pd.to_numeric(hist.get("收盘"), errors="coerce"),
            "vol": pd.to_numeric(hist.get("成交量"), errors="coerce"),
            "amount": pd.to_numeric(hist.get("成交额"), errors="coerce"),
        })
        df = df.sort_values("trade_date", ascending=False)
        return _filter_fields(df, fields)

    if api_name == "income":
        return _filter_fields(_map_income(ts_code), fields)
    if api_name == "balancesheet":
        return _filter_fields(_map_balance(ts_code), fields)
    if api_name == "cashflow":
        return _filter_fields(_map_cashflow(ts_code), fields)
    if api_name == "fina_indicator":
        return _filter_fields(_map_fina_indicator(ts_code), fields)
    if api_name == "dividend":
        return _filter_fields(_map_dividend(ts_code), fields)
    if api_name == "top10_holders":
        return _filter_fields(_map_top10_holders(ts_code), fields)
    if api_name == "fina_mainbz":
        return _filter_fields(_map_mainbz(ts_code), fields)
    if api_name == "repurchase":
        return _filter_fields(_map_repurchase(ts_code), fields)
    if api_name == "pledge_stat":
        return _filter_fields(_map_pledge_stat(ts_code), fields)
    if api_name == "yc_cb":
        return _filter_fields(_map_yc_cb(**kwargs), fields)
    if api_name == "trade_cal":
        return _filter_fields(_map_trade_cal(**kwargs), fields)

    if api_name == "fina_audit":
        return _filter_fields(_map_fina_audit(ts_code), fields)

    raise RuntimeError(f"AkShare fallback does not support endpoint: {api_name}")


def can_fallback(exc: Exception) -> bool:
    s = str(exc)
    key_phrases = [
        "没有接口访问权限",
        "接口访问权限",
        "积分",
        "Permission",
        "forbidden",
        "403",
    ]
    return any(k.lower() in s.lower() for k in key_phrases)
