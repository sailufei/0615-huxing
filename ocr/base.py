"""OCR 引擎抽象基类"""
from abc import ABC, abstractmethod


class BaseOCREngine(ABC):
    """OCR 引擎统一接口"""

    @abstractmethod
    def extract_table(self, image_path: str, table_type: str) -> list[dict]:
        """
        从截图中提取表格数据

        Args:
            image_path: 截图文件路径
            table_type: "supply" | "transaction"
        Returns:
            [{居室, 面积范围, 供应套数/成交套数/成交面积/成交均价}, ...]
        """
        pass
