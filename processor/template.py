"""模板映射器：编码提取 + 室厅卫→户型 + 建面分段"""

import re

# 数字→中文
_NUM_CN = {'1': '一', '2': '二', '3': '三', '4': '四', '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'}

# 建面分段定义
AREA_SEGMENTS = [
    (0, 65, '(0,65]'), (65, 75, '(65,75]'), (75, 85, '(75,85]'),
    (85, 95, '(85,95]'), (95, 105, '(95,105]'), (105, 115, '(105,115]'),
    (115, 125, '(115,125]'), (125, 135, '(125,135]'), (135, 150, '(135,150]'),
    (150, 165, '(150,165]'), (165, 180, '(165,180]'), (180, 200, '(180,200]'),
    (200, 220, '(200,220]'), (220, 240, '(220,240]'), (240, 260, '(240,260]'),
    (260, float('inf'), '(260,+∞)')
]


def map_room_type(room_detail: str) -> str:
    """
    室厅卫 → 户型映射

    Examples:
        "3室2厅1卫" → "三室一卫"
        "4室2厅2卫" → "四室二卫"
        "2室2厅1卫" → "二室一卫"
        "复式"      → "复式"
        "无室厅卫"  → "无室厅卫"
    """
    if not room_detail:
        return ''

    # 特殊户型直接返回
    if room_detail in ('复式', '无室厅卫'):
        return room_detail

    shi = re.search(r'(\d+)室', room_detail)
    wei = re.search(r'(\d+)卫', room_detail)

    result = ''
    if shi:
        n = shi.group(1)
        result = _NUM_CN.get(n, n) + '室'
    if wei:
        n = wei.group(1)
        result += _NUM_CN.get(n, n) + '卫'

    return result if result else room_detail


def classify_area(area_str: str) -> str:
    """
    根据面积范围字符串判断建面分段

    取面积范围中位数，判断落入哪个分段区间。

    Examples:
        "75"       → "(65,75]"
        "95"       → "(85,95]"
        "71~73.5"  → "(65,75]"
        "159~197"  → "(150,165]"
    """
    if not area_str:
        return ''

    # 提取所有数字
    nums = re.findall(r'[\d.]+', str(area_str))
    if not nums:
        return ''

    nums = [float(n) for n in nums]
    mid = sum(nums) / len(nums)

    for lo, hi, label in AREA_SEGMENTS:
        if lo < mid <= hi:
            return label

    return ''
