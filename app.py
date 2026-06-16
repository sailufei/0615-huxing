"""FastAPI 主应用 — 房地产户型盘点工具"""
import os
import json
import traceback
import uuid
import shutil
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from ocr.qwen_vision import QwenVisionOCR
from processor.parser import parse_to_dataframe, get_total_price
from processor.merger import merge_supply, merge_transaction
from processor.template import map_room_type, classify_area
from processor.calculator import calculate_all
from exporter.excel_writer import generate_excel, generate_multi_sheet_excel

app = FastAPI(title="房地产户型盘点工具")

# 目录
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
PROJECTS_DIR = BASE_DIR / "projects"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

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
        result_df = sort_by_area(result_df)

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


@app.post("/api/process-batch")
async def process_batch(request: Request):
    """批量处理多个项目，生成多 Sheet Excel"""
    task_id = uuid.uuid4().hex[:8]
    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(exist_ok=True)

    try:
        form = await request.form()
        project_count = int(form.get("project_count", 0))
        if project_count == 0:
            raise HTTPException(400, "项目数量不能为0")

        all_results = []
        all_errors = []

        for idx in range(project_count):
            proj_name = form.get(f"name_{idx}", "")
            is_saved = form.get(f"is_saved_{idx}", "0") == "1"

            if not proj_name:
                all_errors.append(f"项目{idx+1}: 缺少项目名称")
                continue

            # === 已保存项目：直接从 JSON 加载 ===
            if is_saved:
                saved_path = PROJECTS_DIR / f"{proj_name}.json"
                if not saved_path.exists():
                    all_errors.append(f"项目{idx+1}({proj_name}): 保存记录不存在")
                    continue
                try:
                    saved = json.loads(saved_path.read_text(encoding='utf-8'))
                    # 从保存数据重建结果
                    proj_result = _build_result_from_saved(saved)
                    all_results.append(proj_result)
                except Exception as e:
                    all_errors.append(f"项目{idx+1}({proj_name}): {str(e)}")
                continue

            # === 新项目：OCR + 处理 ===
            plate = form.get(f"plate_{idx}", "")
            open_date = form.get(f"open_date_{idx}", "")
            plot_ratio = form.get(f"plot_ratio_{idx}", "")
            supply_file = form.get(f"supply_{idx}")
            trans_file = form.get(f"transaction_{idx}")

            if not supply_file or not trans_file:
                all_errors.append(f"项目{idx+1}: 缺少必填截图")
                continue

            supply_path = task_dir / f"supply_{idx}{Path(supply_file.filename).suffix}"
            with open(supply_path, "wb") as f:
                f.write(await supply_file.read())

            trans_path = task_dir / f"trans_{idx}{Path(trans_file.filename).suffix}"
            with open(trans_path, "wb") as f:
                f.write(await trans_file.read())

            month_images = []
            month_labels = []
            mi = 0
            while True:
                m_label = form.get(f"month_label_{idx}_{mi}")
                m_file = form.get(f"month_file_{idx}_{mi}")
                if not m_label or not m_file:
                    break
                m_path = task_dir / f"month_{idx}_{mi}{Path(m_file.filename).suffix}"
                with open(m_path, "wb") as f:
                    f.write(await m_file.read())
                month_images.append((m_label, str(m_path)))
                month_labels.append(m_label)
                mi += 1

            if not month_labels:
                all_errors.append(f"项目{idx+1}({proj_name}): 缺少月度截图")
                continue

            try:
                proj_result = process_single_project(
                    proj_name, plate, open_date, plot_ratio,
                    str(supply_path), str(trans_path),
                    month_images, month_labels
                )
                all_results.append(proj_result)
                save_data = {
                    'project_name': proj_name,
                    'plate': plate,
                    'month_labels': month_labels,
                    'summary': proj_result['preview']['summary'],
                    'rows': proj_result['preview']['rows'],
                    'total_avg_price': proj_result.get('total_avg_price', ''),
                    'monthly_total_prices': proj_result.get('monthly_total_prices', {}),
                }
                save_project_result(proj_name, save_data)
            except Exception as e:
                tb = traceback.format_exc()
                all_errors.append(f"项目{idx+1}({proj_name}): {str(e)} | 详情: {tb[-200:]}")

        if not all_results:
            raise HTTPException(400, "所有项目处理失败: " + "; ".join(all_errors))

        # 生成多 Sheet Excel
        excel_filename = f"户型盘点_{task_id}.xlsx"
        excel_path = OUTPUT_DIR / excel_filename
        generate_multi_sheet_excel(all_results, str(excel_path))

        return {
            'success': True,
            'task_id': task_id,
            'results': [r['preview'] for r in all_results],
            'errors': all_errors if all_errors else None,
            'excel_url': f'/api/download/{excel_filename}',
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"批量处理失败: {str(e)}")
    finally:
        if task_dir.exists():
            shutil.rmtree(task_dir, ignore_errors=True)


@app.get("/api/projects")
def list_projects():
    """列出所有已保存的项目"""
    projects = []
    for f in sorted(PROJECTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            projects.append({
                'name': f.stem,
                'updated': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'total_supply': data.get('summary', {}).get('total_supply', 0),
                'total_transaction': data.get('summary', {}).get('total_transaction', 0),
            })
        except Exception:
            pass
    return {'projects': projects}


@app.get("/api/projects/{name}")
def get_project(name: str):
    """加载已保存项目的完整结果 + 重新生成 Excel"""
    file_path = PROJECTS_DIR / f"{name}.json"
    if not file_path.exists():
        raise HTTPException(404, "项目不存在")

    data = json.loads(file_path.read_text(encoding='utf-8'))

    # 重新生成 Excel
    excel_filename = f"{name}_{uuid.uuid4().hex[:6]}.xlsx"
    excel_path = OUTPUT_DIR / excel_filename

    # 从保存的数据重建 DataFrame 并生成 Excel
    _regenerate_excel(data, str(excel_path))

    return {
        'success': True,
        'project_name': name,
        'data': data,
        'excel_url': f'/api/download/{excel_filename}',
    }


@app.delete("/api/projects/{name}")
def delete_project(name: str):
    """删除已保存的项目"""
    file_path = PROJECTS_DIR / f"{name}.json"
    if file_path.exists():
        file_path.unlink()
        return {'success': True}
    raise HTTPException(404, "项目不存在")


def save_project_result(project_name: str, result_data: dict):
    """保存项目结果（同名覆盖）"""
    file_path = PROJECTS_DIR / f"{project_name}.json"
    file_path.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding='utf-8')


def _build_result_from_saved(saved: dict) -> dict:
    """从保存的 JSON 重建结果（复用已计算的数据，无需重新 OCR）"""
    rows = saved.get('rows', [])
    df = pd.DataFrame(rows)
    # 字段名映射：保存的 JSON 用 "户型面积"，Excel 生成器期待 "面积范围"
    if '户型面积' in df.columns and '面积范围' not in df.columns:
        df['面积范围'] = df['户型面积']
    total_supply = saved['summary']['total_supply']
    total_trans = saved['summary']['total_transaction']
    project_total = sum(r.get('整盘套数', 0) for r in rows)
    month_labels = saved.get('month_labels', [])

    return {
        'df': df,
        'total_supply': total_supply,
        'total_trans': total_trans,
        'project_total': project_total,
        'project_name': saved.get('project_name', ''),
        'plate': saved.get('plate', ''),
        'competitor': saved.get('project_name', ''),
        'open_date': saved.get('open_date', ''),
        'plot_ratio': saved.get('plot_ratio', ''),
        'month_labels': month_labels,
        'total_avg_price': saved.get('total_avg_price', ''),
        'monthly_total_prices': saved.get('monthly_total_prices', {}),
        'preview': {
            'project_name': saved.get('project_name', ''),
            'summary': saved['summary'],
            'rows': rows,
        },
    }


def _regenerate_excel(data: dict, output_path: str):
    """从保存的 JSON 重建 Excel 文件"""
    # 重建简单 DataFrame 用于 generate_excel
    rows = data.get('rows', [])
    if not rows:
        return
    df = pd.DataFrame(rows)
    # 字段名映射
    if '户型面积' in df.columns and '面积范围' not in df.columns:
        df['面积范围'] = df['户型面积']
    month_labels = data.get('month_labels', [])
    total_supply = data['summary']['total_supply']
    total_trans = data['summary']['total_transaction']
    project_total = sum(r.get('整盘套数', 0) for r in rows)
    project_name = data.get('project_name', '')
    plate = data.get('plate', '')

    generate_excel(
        df=df,
        total_supply=total_supply,
        total_trans=total_trans,
        project_total=project_total,
        month_labels=month_labels,
        project_name=project_name,
        output_path=output_path,
        plate=plate,
        competitor=project_name,
        total_avg_price=data.get('total_avg_price', ''),
        monthly_total_prices=data.get('monthly_total_prices', {}),
    )


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


def _area_sort_key(area_str: str) -> float:
    """从面积范围字符串提取排序用的数值（取中位数）"""
    import re
    if not area_str:
        return 999999
    nums = re.findall(r'[\d.]+', str(area_str))
    if not nums:
        return 999999
    nums = [float(n) for n in nums]
    return sum(nums) / len(nums)


def sort_by_area(df):
    """按户型面积升序排列"""
    if '面积范围' in df.columns:
        df = df.copy()
        df['_sort_key'] = df['面积范围'].apply(_area_sort_key)
        df = df.sort_values('_sort_key').drop(columns=['_sort_key'])
    return df


def process_single_project(
    project_name: str, plate: str, open_date: str, plot_ratio: str,
    supply_path: str, trans_path: str,
    month_images: list, month_labels: list,
) -> dict:
    """处理单个项目，返回 {df, total_supply, total_trans, project_total, preview}"""
    # OCR
    supply_raw = ocr_engine.extract_table(supply_path, "supply")
    trans_raw = ocr_engine.extract_table(trans_path, "transaction")

    # 数据清洗：过滤掉空数据行
    supply_raw = [r for r in supply_raw if r.get("居室", "").strip()]
    trans_raw = [r for r in trans_raw if r.get("居室", "").strip()]
    total_avg_price = get_total_price(trans_raw)

    monthly_raw = {}
    monthly_total_prices = {}
    for label, path in month_images:
        m_raw = ocr_engine.extract_table(path, "transaction")
        monthly_raw[label] = m_raw
        monthly_total_prices[label] = get_total_price(m_raw)

    # 解析
    supply_df = parse_to_dataframe(supply_raw, "supply")
    trans_df = parse_to_dataframe(trans_raw, "transaction")
    monthly_dfs = {label: parse_to_dataframe(raw, "transaction") for label, raw in monthly_raw.items()}

    # 合并
    supply_merged = merge_supply(supply_df)
    trans_merged = merge_transaction(trans_df)
    monthly_merged = {label: merge_transaction(mdf) if not mdf.empty else mdf for label, mdf in monthly_dfs.items()}

    # 映射
    supply_merged["户型"] = supply_merged["室厅卫"].apply(map_room_type)
    supply_merged["建面分段"] = supply_merged["面积范围"].apply(classify_area)

    # 计算
    result_df, total_supply, total_trans, project_total = calculate_all(
        supply_merged, trans_merged, monthly_merged, month_labels
    )

    # 按户型面积升序排列
    result_df = sort_by_area(result_df)

    # 构建预览
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
        r['近3月月均销量占比'] = round(float(row.get('近3月月均销量占比', 0)), 2)
        preview_rows.append(r)

    return {
        'df': result_df,
        'total_supply': total_supply,
        'total_trans': total_trans,
        'project_total': project_total,
        'project_name': project_name,
        'plate': plate,
        'competitor': project_name,
        'open_date': open_date,
        'plot_ratio': plot_ratio,
        'month_labels': month_labels,
        'total_avg_price': total_avg_price,
        'monthly_total_prices': monthly_total_prices,
        'preview': {
            'project_name': project_name,
            'summary': {'total_supply': int(total_supply), 'total_transaction': int(total_trans)},
            'rows': preview_rows,
        },
    }


# 静态文件
app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
