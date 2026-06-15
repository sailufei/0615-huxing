"""通义千问 Qwen-VL OCR 引擎 — 国内方案，精度高，费用低"""
import json
import os
import dashscope
from .base import BaseOCREngine

# 供应截图识别 Prompt
SUPPLY_PROMPT = """请识别这张房地产项目供应情况表格截图。

表格列名：居室、面积范围(m²)、供应套数。

请仔细区分两种行：
1. **分组行**（居室分类标题，如"两室"、"三室"、"四室"、"复式"）：仅用于分类，不包含具体户型名
2. **户型明细行**（如"A户型 3室2厅1卫"、"A户型-底 2室2厅1卫"）：包含完整居室名和各列数据

返回 JSON 数组，每个元素格式：
{
  "type": "group" 或 "detail",
  "居室": "完整的居室列文字",
  "面积范围": "面积范围列文字",
  "供应套数": 数字（分组行填0，识别不了也填0）
}

重要规则：
- 保留居室列的完整文字，包括"-顶"、"-底"、"-底1"等后缀
- 供应套数必须是数字类型，无法识别时填0
- 识别所有行，包括底部"合计"行（居室填"合计"）
- 只返回 JSON 数组，不要任何其他文字"""

# 成交截图识别 Prompt
TRANSACTION_PROMPT = """请识别这张房地产项目成交情况表格截图。

表格列名：居室、面积范围(m²)、成交套数、成交面积(m²)、成交均价(元/m²)。

同样区分两种行：
1. **分组行**（居室分类标题，如"两室"、"三室"）：仅用于分类
2. **户型明细行**（如"A户型 3室2厅1卫"）：含完整居室名和各列数据

返回 JSON 数组，每个元素格式：
{
  "type": "group" 或 "detail",
  "居室": "完整的居室列文字",
  "面积范围": "面积范围列文字",
  "成交套数": 数字,
  "成交面积": 数字,
  "成交均价": 数字
}

重要规则：
- 保留居室列的完整文字
- 所有数值必须是数字类型，无法识别时填0
- 识别所有行，包括底部"合计"行
- 只返回 JSON 数组，不要任何其他文字"""


class QwenVisionOCR(BaseOCREngine):
    """使用通义千问 Qwen-VL 识别表格截图"""

    def __init__(self, api_key: str = None, model: str = "qwen-vl-max"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model
        # 设置全局 API Key，确保 DashScope 内部 OSS 上传等操作能读取到
        if self.api_key:
            dashscope.api_key = self.api_key

    def extract_table(self, image_path: str, table_type: str = "supply") -> list[dict]:
        """识别图片中的表格数据"""
        # 选择 Prompt
        prompt = SUPPLY_PROMPT if table_type == "supply" else TRANSACTION_PROMPT

        # 构建消息
        messages = [{
            "role": "user",
            "content": [
                {"image": f"file://{os.path.abspath(image_path)}"},
                {"text": prompt}
            ]
        }]

        # 调用 Qwen-VL API（注意：DashScope 的 MultiModalConversation 是同步方法）
        response = dashscope.MultiModalConversation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
        )

        # 提取文本
        if response.status_code == 200:
            text = response.output.choices[0].message.content[0]["text"]
            return self._parse_json(text)
        else:
            raise Exception(f"Qwen-VL API 调用失败: code={response.status_code}, message={response.message}")

    def _parse_json(self, text: str) -> list[dict]:
        """从响应文本中提取 JSON 数组"""
        text = text.strip()
        # 去掉 markdown 代码块标记
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
            # 尝试提取 JSON 数组
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return []
