"""FastAPI 主应用 — 房地产户型盘点工具"""
import os
import traceback
import uuid
import shutil
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from ocr.qwen_vision import QwenVisionOCR
from processor.parser import parse_to_dataframe, get_total_price
from processor.merger import merge_supply, merge_transaction
from processor.template import map_room_type, classify_area
from processor.calculator import calculate_all
from exporter.excel_writer import generate_excel

app = FastAPI(title="房地产户型盘点工具")

# 目录
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# OCR 引擎（通义千问 Qwen-VL — 同步调用）
ocr_engine = QwenVisionOCR()


@app.post("/api/process")
def process_images(
    project_name: str = Form(...),
    plate: str = Form(""),
    open_date: str = Form(""),
    plot_ratio: str = Form(""),
    supply_image: UploadFile = File(...),
    transaction_image: UploadFile = File(...),
    month_image_1: UploadFile = File(None),
    month_image_2: UploadFile = File(None),
    month_image_3: UploadFile = File(None),
    month_label_1: str = Form(""),
    month_label_2: str = Form(""),
    month_label_3: str = Form(""),
):
    """处理上传的截图，生成户型盘点结果（同步端点，FastAPI 自动放入线程池）"""
    task_id = uuid.uuid4().hex[:8]
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    try:
        # === 1. 保存上传图片（同步读写）===
        supply_path = task_dir / f"supply{Path(supply_image.filename).suffix}"
        trans_path = task_dir / f"transaction{Path(transaction_image.filename).suffix}"

        with open(supply_path, "wb") as f:
            f.write(supply_image.file.read())
        with open(trans_path, "wb") as f:
            f.write(transaction_image.file.read())

        # 收集月度图片
        month_images = []
        month_labels = []
        for img, label in [
            (month_image_1, month_label_1),
            (month_image_2, month_label_2),
            (month_image_3, month_label_3),
        ]:
            if img and label:
                path = task_dir / f"month_{label}{Path(img.filename).suffix}"
                with open(path, "wb") as f:
                    f.write(img.file.read())
                month_images.append((label, str(path)))
                month_labels.append(label)

        if not month_labels:
            raise HTTPException(400, "至少需要 1 张月度成交截图")

        # === 2. OCR 识别（直接同步调用，不绕任何 async/to_thread）===
        errors = []

        try:
            supply_raw = ocr_engine.extract_table(str(supply_path), "supply")
        except Exception as e:
            errors.append(f"供应截图识别失败: {e}")
            supply_raw = []

        try:
            trans_raw = ocr_engine.extract_table(str(trans_path), "transaction")
            total_avg_price = get_total_price(trans_raw)  # 提取合计行成交均价
        except Exception as e:
            errors.append(f"成交截图识别失败: {e}")
            trans_raw = []
            total_avg_price = ''

        monthly_raw = {}
        monthly_total_prices = {}  # 各月合计行成交均价
        for label, path in month_images:
            try:
                m_raw = ocr_engine.extract_table(path, "transaction")
                monthly_raw[label] = m_raw
                monthly_total_prices[label] = get_total_price(m_raw)
            except Exception as e:
                errors.append(f"月度截图 {label} 识别失败: {e}")
                monthly_raw[label] = []
                monthly_total_prices[label] = ''

        # === 3. 解析结构化数据 ===
        supply_df = parse_to_dataframe(supply_raw, "supply")
        trans_df = parse_to_dataframe(trans_raw, "transaction")

        monthly_dfs = {}
        for label, raw in monthly_raw.items():
            monthly_dfs[label] = parse_to_dataframe(raw, "transaction")

        if supply_df.empty:
            raise HTTPException(400, "供应截图中未识别到户型数据")

        # === 4. 户型变体合并 ===
        supply_merged = merge_supply(supply_df)
        trans_merged = merge_transaction(trans_df)

        monthly_merged = {}
        for label, mdf in monthly_dfs.items():
            monthly_merged[label] = merge_transaction(mdf) if not mdf.empty else mdf

        # === 5. 模板映射 ===
        supply_merged["户型"] = supply_merged["室厅卫"].apply(map_room_type)
        supply_merged["建面分段"] = supply_merged["面积范围"].apply(classify_area)

        # === 6. 计算指标 ===
        result_df, total_supply, total_trans, project_total = calculate_all(
            supply_merged, trans_merged, monthly_merged, month_labels
        )

        # === 7. 生成 Excel ===
        excel_filename = f"{project_name}_{task_id}.xlsx"
        excel_path = OUTPUT_DIR / excel_filename
        generate_excel(
            df=result_df,
            total_supply=total_supply,
            total_trans=total_trans,
            project_total=project_total,
            month_labels=month_labels,
            project_name=project_name,
            output_path=str(excel_path),
            plate=plate,
            competitor=project_name,
            open_date=open_date,
            plot_ratio=plot_ratio,
            total_avg_price=total_avg_price,
            monthly_total_prices=monthly_total_prices,
        )

        # === 8. 构建预览 JSON ===
        preview_rows = []
        for _, row in result_df.iterrows():
            r = {
                '编码': row.get('编码', ''),
                '户型': row.get('户型', ''),
                '户型面积': row.get('面积范围', ''),
                '建面分段': row.get('建面分段', ''),
                '整盘套数': int(row.get('整盘套数', 0)),
                '户配': round(float(row.get('户配', 0)), 2),
                '供应套数': int(row.get('供应套数', 0)),
                '成交套数': int(row.get('成交套数', 0)),
                '成交均价': row.get('成交均价', ''),
                '整盘去化率': round(float(row.get('整盘去化率', 0)), 2),
                '已供去化率': round(float(row.get('已供去化率', 0)), 2),
                '已供去化占比': round(float(row.get('已供去化占比', 0)), 2),
                '已取证库存': int(row.get('已取证库存', 0)),
                '整盘库存': int(row.get('整盘库存', 0)),
            }
            for ml in month_labels:
                r[ml] = row.get(ml, '')
            r['近3月月均销量'] = round(float(row.get('近3月月均销量', 0)), 1)
            r['近3月月均销量占比'] = round(float(row.get('近3月月均销量占比', 0)), 4)
            preview_rows.append(r)

        return {
            'success': True,
            'task_id': task_id,
            'project_name': project_name,
            'plate': plate,
            'competitor': project_name,  # 项目名称 = 竞品
            'month_labels': month_labels,
            'summary': {
                'total_supply': int(total_supply),
                'total_transaction': int(total_trans),
            },
            'manual_fields': ['板块', '竞品', '业态'],
            'rows': preview_rows,
            'errors': errors if errors else None,
            'excel_url': f'/api/download/{excel_filename}',
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"处理失败: {str(e)}")
    finally:
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)


@app.get("/api/download/{filename}")
def download_excel(filename: str):
    """下载生成的 Excel 文件"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在或已过期")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# 静态文件
app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
