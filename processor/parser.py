"""OCR 结果解析器：将 OCR 返回的 JSON 转为结构化数据"""
import pandas as pd


def parse_to_dataframe(rows: list[dict], table_type: str) -> pd.DataFrame:
    """
    解析 OCR 返回的 JSON 行列表为 DataFrame

    Args:
        rows: OCR 返回的 [{type, 居室, ...}, ...]
        table_type: "supply" | "transaction"
    Returns:
        DataFrame，只包含户型明细行（过滤掉 group 行）
    """
    if not rows:
        return pd.DataFrame()

    # 只取明细行，排除 OCR 识别到的"合计"行（由 Excel 生成器统一添加合并行）
    details = [r for r in rows if r.get("type") == "detail" and "合计" not in r.get("居室", "")]

    df = pd.DataFrame(details)

    # 根据类型确定需要的列
    if table_type == "supply":
        required_cols = ["居室", "面积范围", "供应套数"]
    else:
        required_cols = ["居室", "面积范围", "成交套数", "成交面积", "成交均价"]

    # 确保必要列存在
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0 if col != "居室" and col != "面积范围" else ""

    # 数值列填充
    numeric_cols = [c for c in required_cols if c not in ("居室", "面积范围")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df[required_cols]


def get_total_price(rows: list[dict]) -> str:
    """
    从 OCR 成交数据中提取合计行的成交均价

    Args:
        rows: OCR 返回的完整行列表
    Returns:
        合计行成交均价（数字或空字符串）
    """
    for r in rows:
        if "合计" in r.get("居室", ""):
            price = r.get("成交均价", 0)
            if price and price != 0:
                return int(price) if price == int(price) else price
    return ''
