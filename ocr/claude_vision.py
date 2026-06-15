"""Claude Vision API OCR 引擎 — 备选方案"""
import base64
import json
import os
from anthropic import Anthropic
from .base import BaseOCREngine

SUPPLY_PROMPT = """请识别这张房地产项目供应情况表格截图。

表格列名：居室、面积范围(m²)、供应套数。

请仔细区分两种行：
1. **分组行**（居室分类标题，如"两室"、"三室"、"四室"、"复式"）：这些行没有具体户型名，仅用于分类
2. **户型明细行**（如"A户型 3室2厅1卫"、"A户型-底 2室2厅1卫"）：包含完整的居室名称、面积范围和供应套数

返回 JSON 数组，每个元素包含：
{
  "type": "group" 或 "detail",
  "居室": "完整的居室列文字",
  "面积范围": "面积范围列文字",
  "供应套数": 数字（分组行填0）
}

重要：
- 保留居室列的完整文字，包括"-顶"、"-底"、"-底1"等后缀
- 供应套数必须是数字，无法识别时填0
- 请识别所有行，包括底部的"合计"行（合计的居室填"合计"）
- 只返回 JSON 数组，不要其他文字"""

TRANSACTION_PROMPT = """请识别这张房地产项目成交情况表格截图。

表格列名：居室、面积范围(m²)、成交套数、成交面积(m²)、成交均价(元/m²)。

请仔细区分两种行：
1. **分组行**（居室分类标题，如"三室"、"四室"）：这些行没有具体户型名，仅用于分类
2. **户型明细行**（如"A户型 3室2厅1卫"）：包含完整的居室名称和各列数据

返回 JSON 数组，每个元素包含：
{
  "type": "group" 或 "detail",
  "居室": "完整的居室列文字",
  "面积范围": "面积范围列文字",
  "成交套数": 数字,
  "成交面积": 数字,
  "成交均价": 数字
}

重要：
- 保留居室列的完整文字
- 所有数值必须是数字类型，无法识别时填0
- 请识别所有行，包括底部的"合计"行
- 只返回 JSON 数组，不要其他文字"""


class ClaudeVisionOCR(BaseOCREngine):
    """使用 Claude Vision API 识别表格截图"""

    def __init__(self, api_key: str = None, model: str = "claude-opus-4-8"):
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def extract_table(self, image_path: str, table_type: str = "supply") -> list[dict]:
        """识别图片中的表格"""
        # 读取并编码图片
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        # 确定 media_type
        ext = os.path.splitext(image_path)[1].lower()
        media_type_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
        media_type = media_type_map.get(ext, "image/png")

        # 选择 Prompt
        prompt = SUPPLY_PROMPT if table_type == "supply" else TRANSACTION_PROMPT

        # 调用 Vision API（同步）
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )

        # 提取 JSON
        text = response.content[0].text
        return self._parse_json(text)

    def _parse_json(self, text: str) -> list[dict]:
        """从响应文本中提取 JSON 数组"""
        text = text.strip()
        # 去掉可能的 markdown 代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "rows" in data:
                return data["rows"]
            return []
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组部分
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return []
