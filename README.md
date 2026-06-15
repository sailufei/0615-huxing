# 房地产户型盘点工具 V1.0

## 快速启动

```bash
# 1. 安装依赖（仅首次）
pip install -r requirements.txt

# 2. 配置 API Key
#    复制 .env.example 为 .env，填写你的 DASHSCOPE_API_KEY

# 3. 启动
python app.py

# 4. 浏览器打开 http://localhost:8080
```

---

## 文件说明

### 主程序（核心代码，不要删）

| 文件 | 作用 |
|------|------|
| `app.py` | FastAPI 主程序，启动入口 |
| `requirements.txt` | Python 依赖包列表 |
| `.env.example` | API Key 配置模板 |
| `.env` | 你的 API Key（已被 Git 忽略，不会上传） |
| `.gitignore` | Git 忽略规则 |

### OCR 识别层（`ocr/` 目录）

| 文件 | 作用 |
|------|------|
| `ocr/base.py` | OCR 抽象接口定义 |
| `ocr/qwen_vision.py` | **通义千问 Qwen-VL 引擎（正在使用）** |
| `ocr/claude_vision.py` | Claude Vision 引擎（备选方案） |
| `ocr/__init__.py` | 包初始化 |

### 数据处理层（`processor/` 目录）

| 文件 | 作用 |
|------|------|
| `processor/parser.py` | OCR 结果 → 结构化数据解析 |
| `processor/merger.py` | **户型顶/底变体合并（核心逻辑）** |
| `processor/template.py` | 编码提取 + 室厅卫→户型映射 + 建面分段 |
| `processor/calculator.py` | 户配/去化率/库存/月均等指标计算 |
| `processor/__init__.py` | 包初始化 |

### Excel 输出层（`exporter/` 目录）

| 文件 | 作用 |
|------|------|
| `exporter/excel_writer.py` | Excel 生成（格式/样式/合并单元格） |
| `exporter/__init__.py` | 包初始化 |

### 前端界面（`static/` 目录）

| 文件 | 作用 |
|------|------|
| `static/index.html` | 网页页面结构 |
| `static/style.css` | 网页样式 |
| `static/app.js` | 网页交互逻辑（上传/提交/预览/下载） |

### 截图和数据（可保留可删除）

| 文件 | 说明 |
|------|------|
| `供应.png` | 整盘供应情况截图（示例） |
| `成交.png` | 整盘成交情况截图（示例） |
| `月度成交1.png` | 特定月份成交截图 1（示例） |
| `月度成交2.png` | 特定月份成交截图 2（示例） |
| `月度成交3.png` | 特定月份成交截图 3（示例） |
| `输出模板.png` | 输出模板参考截图 |
| `*_ocr.json` | EasyOCR 识别结果缓存（可删除，已不用） |

### 临时文件（可删除）

| 文件/目录 | 说明 |
|-----------|------|
| `poc_verify.py` | 早期验证脚本，不再需要 |
| `POC_验证输出.xlsx` | 早期验证产物，不再需要 |
| `uploads/` | 上传缓存目录（Git 忽略） |
| `outputs/` | 生成 Excel 的目录（Git 忽略） |
| `__pycache__/` | Python 缓存（Git 忽略，自动生成） |

---

## 工作流程

```
上传 5 张截图 → 填写项目信息 → 点击「开始处理」
                    ↓
    Qwen-VL OCR 识别 → 数据解析 → 户型合并
                    ↓
        指标计算 → Excel 生成 → 预览 + 下载
```

## 关键业务规则速记

- **顶/底合并**：A户型-底/顶 归入 A户型，套数求和，其他取标准户型
- **编码提取**：从 "A户型 3室2厅1卫" 中提取 "A户型"
- **户型映射**：3室2厅1卫 → 三室一卫
- **手动列**：板块、业态（Excel 中黄色标记）
- **竞品列**：自动填入项目名称 + 开盘时间 + 容积率
- **整盘套数** = 供应套数
- **已取证库存** = 供应套数 - 成交套数
- **整盘库存** = 整盘套数 - 成交套数
