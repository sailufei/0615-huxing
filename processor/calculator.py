"""指标计算器：户配、去化率等"""
import pandas as pd


def calculate_all(
    merged_supply: pd.DataFrame,
    merged_transaction: pd.DataFrame,
    monthly_data: dict[str, pd.DataFrame],
    month_labels: list[str],
) -> pd.DataFrame:
    """计算全部模板指标"""
    df = merged_supply.copy()
    trans_index = {r["编码"]: r for _, r in merged_transaction.iterrows()}

    # 成交字段（全部用数字填充，避免 str/float 类型冲突）
    for code in df["编码"]:
        if code in trans_index:
            t = trans_index[code]
            df.loc[df["编码"] == code, "成交套数"] = t["成交套数"]
            df.loc[df["编码"] == code, "成交面积"] = t["成交面积"]
            df.loc[df["编码"] == code, "成交均价"] = t["成交均价"]
        else:
            df.loc[df["编码"] == code, "成交套数"] = 0
            df.loc[df["编码"] == code, "成交面积"] = 0
            df.loc[df["编码"] == code, "成交均价"] = 0

    df["成交套数"] = pd.to_numeric(df["成交套数"], errors='coerce').fillna(0).astype(int)
    df["成交面积"] = pd.to_numeric(df["成交面积"], errors='coerce').fillna(0)
    df["成交均价"] = pd.to_numeric(df["成交均价"], errors='coerce').fillna(0)

    total_supply = int(df["供应套数"].sum())
    total_trans = int(df["成交套数"].sum())

    # 整盘套数 = 供应套数
    df["整盘套数"] = df["供应套数"]

    # 项目整盘套数（所有户型整盘套数之和）
    project_total = int(df["整盘套数"].sum())

    # 户配 = 各户型整盘套数 / 项目整盘套数
    df["户配"] = df["整盘套数"] / project_total if project_total > 0 else 0

    # 整盘去化率 = 各户型成交套数 / 各户型整盘套数
    df["整盘去化率"] = df.apply(lambda r: r["成交套数"] / r["整盘套数"] if r["整盘套数"] > 0 else 0, axis=1)

    # 已供去化率 = 各户型成交套数 / 各户型供应套数
    df["已供去化率"] = df.apply(lambda r: r["成交套数"] / r["供应套数"] if r["供应套数"] > 0 else 0, axis=1)

    # 已供去化占比 = 各户型成交套数 / 整盘成交总套数
    df["已供去化占比"] = df["成交套数"] / total_trans if total_trans > 0 else 0

    # 新增：已取证库存 = 供应套数 - 成交套数
    df["已取证库存"] = df["供应套数"] - df["成交套数"]

    # 新增：整盘库存 = 整盘套数 - 成交套数
    df["整盘库存"] = df["整盘套数"] - df["成交套数"]

    # 月度数据
    monthly_units_list = []
    for ml in month_labels:
        m_df = monthly_data.get(ml, pd.DataFrame())
        if not m_df.empty and "编码" in m_df.columns:
            m_index = {r["编码"]: r for _, r in m_df.iterrows()}
        else:
            m_index = {}

        units_col = []
        price_col = []
        for code in df["编码"]:
            if code in m_index:
                m_row = m_index[code]
                units_col.append(int(m_row.get("成交套数", 0)))
                price_col.append(m_row.get("成交均价", ''))
            else:
                units_col.append(0)
                price_col.append('')

        combined = []
        for u, p in zip(units_col, price_col):
            u_str = str(u) if u else '0'
            p_str = str(int(p)) if p and str(p) != 'nan' and p != '' else '-'
            combined.append(f"{u_str}\n{p_str}")

        df[ml] = combined
        monthly_units_list.append(units_col)

    # 近3月月均销量
    if monthly_units_list:
        monthly_matrix = list(zip(*monthly_units_list))
        df["近3月月均销量"] = [round(sum(vals) / len(vals)) if vals else 0 for vals in monthly_matrix]
    else:
        df["近3月月均销量"] = 0

    # 近3月月均销量占比 = 每行近3月月均销量 / 所有户型近3月月均销量之和（即合并行的近3月月均销量）
    total_monthly_avg = df["近3月月均销量"].sum()
    df["近3月月均销量占比"] = df["近3月月均销量"] / total_monthly_avg if total_monthly_avg > 0 else 0

    # 数值列
    pct_cols = ["户配", "整盘去化率", "已供去化率", "已供去化占比", "近3月月均销量占比"]
    for col in pct_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df, total_supply, total_trans, project_total
