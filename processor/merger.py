"""户型变体合并器：处理顶/底变体的核心逻辑"""
import re
import pandas as pd


def extract_code(room_text: str) -> str:
    """
    从居室文本提取编码

    规则：去掉 -顶/-底 后缀，取最后一个空格之前的部分。
    如无空格，整个文本作为编码。

    Examples:
        "A户型 3室2厅1卫"   → "A户型"
        "A户型-底 2室2厅1卫" → "A户型"
        "B户型-底1 2室2厅1卫"→ "B户型"
        "C1户型-顶 4室2厅2卫"→ "C1户型"
        "复式"               → "复式"
    """
    text = room_text.strip()
    # 去掉 -顶/-底/-顶1/-底2 以及 顶层/底层/顶层1/底层2 后缀
    text = re.sub(r'-?[顶底]层?\d*', '', text)

    # 找最后一个空格
    last_space = text.rfind(' ')
    if last_space > 0:
        return text[:last_space]
    return text


def extract_room_detail(room_text: str) -> str:
    """
    从居室文本提取室厅卫部分

    Examples:
        "A户型 3室2厅1卫"   → "3室2厅1卫"
        "A户型-底 2室2厅1卫" → "2室2厅1卫"
        "复式"               → "复式"
    """
    text = room_text.strip()
    # 去掉顶/底后缀（-底、-底1、底层、底层1、-顶、顶层 等）
    text = re.sub(r'-?[顶底]层?\d*', '', text)

    last_space = text.rfind(' ')
    if last_space > 0:
        return text[last_space + 1:]
    return text


def get_bottom_number(name: str) -> int | None:
    """获取底后缀的数字（支持 -底、-底1、底层、底层1 等）"""
    m = re.search(r'-?底层?(\d*)', name.strip())
    # 也匹配旧格式
    if not m:
        m = re.search(r'-底(\d*)', name.strip())
    if m:
        if m.group(1) == '':
            return 0
        return int(m.group(1))
    return None


def is_variant(name: str) -> bool:
    """判断是否是变体（含顶/底后缀，支持 -底、底层、-顶、顶层 等）"""
    return bool(re.search(r'-?[顶底]层?\d*', name.strip()))


def merge_supply(df: pd.DataFrame) -> pd.DataFrame:
    """
    合并供应数据中的户型变体

    Args:
        df: 包含列 [居室, 面积范围, 供应套数]
    Returns:
        合并后的 DataFrame: [编码, 居室(标准户型), 面积范围, 供应套数, 室厅卫]
    """
    if df.empty:
        return pd.DataFrame(columns=["编码", "居室", "面积范围", "供应套数", "室厅卫"])

    df = df.copy()
    df["编码"] = df["居室"].apply(extract_code)
    df["室厅卫"] = df["居室"].apply(extract_room_detail)
    df["是否变体"] = df["居室"].apply(is_variant)

    # 按编码分组
    merged_rows = []
    for code, group in df.groupby("编码"):
        # 供应套数：组内求和
        supply = group["供应套数"].sum()

        # 找标准户型行（非变体）
        standard = group[~group["是否变体"]]
        if len(standard) > 0:
            canonical = standard.iloc[0]
        else:
            # 无标准户型：取 -底 数字最小的
            variants = group[group["是否变体"]]
            bottom_nums = [(get_bottom_number(r["居室"]), idx) for idx, r in variants.iterrows()]
            bottom_nums = [(n, idx) for n, idx in bottom_nums if n is not None]
            if bottom_nums:
                bottom_nums.sort(key=lambda x: x[0])
                canonical = variants.loc[bottom_nums[0][1]]
            else:
                canonical = group.iloc[0]

        merged_rows.append({
            "编码": code,
            "标准居室": canonical["居室"],
            "面积范围": canonical["面积范围"],
            "供应套数": supply,
            "室厅卫": canonical["室厅卫"],
        })

    return pd.DataFrame(merged_rows)


def merge_transaction(df: pd.DataFrame) -> pd.DataFrame:
    """
    合并成交数据中的户型变体

    Args:
        df: 包含列 [居室, 面积范围, 成交套数, 成交面积, 成交均价]
    Returns:
        合并后的 DataFrame: [编码, 成交套数, 成交面积, 成交均价, 室厅卫]
    """
    if df.empty:
        return pd.DataFrame(columns=["编码", "成交套数", "成交面积", "成交均价", "室厅卫"])

    df = df.copy()
    df["编码"] = df["居室"].apply(extract_code)
    df["室厅卫"] = df["居室"].apply(extract_room_detail)
    df["是否变体"] = df["居室"].apply(is_variant)

    merged_rows = []
    for code, group in df.groupby("编码"):
        # 成交套数：组内求和
        trans_units = group["成交套数"].sum()
        # 成交面积：不聚合，保留标准户型
        trans_area = group[~group["是否变体"]]["成交面积"].sum() if len(group[~group["是否变体"]]) > 0 else 0

        # 成交均价：优先标准户型
        standard = group[~group["是否变体"]]
        if len(standard) > 0:
            canonical = standard.iloc[0]
        else:
            variants = group[group["是否变体"]]
            bottom_nums = [(get_bottom_number(r["居室"]), idx) for idx, r in variants.iterrows()]
            bottom_nums = [(n, idx) for n, idx in bottom_nums if n is not None]
            if bottom_nums:
                bottom_nums.sort(key=lambda x: x[0])
                canonical = variants.loc[bottom_nums[0][1]]
            else:
                canonical = group.iloc[0]

        merged_rows.append({
            "编码": code,
            "成交套数": trans_units,
            "成交面积": trans_area if trans_area else canonical["成交面积"],
            "成交均价": canonical["成交均价"],
            "室厅卫": canonical["室厅卫"],
        })

    return pd.DataFrame(merged_rows)
