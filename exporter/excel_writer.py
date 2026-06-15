"""Excel 生成器：按模板格式输出"""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


HEADER_FILL = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
HEADER_FONT = Font(name='微软雅黑', bold=True, size=10, color='FFFFFF')
MANUAL_FILL = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
TOTAL_FONT = Font(name='微软雅黑', bold=True, size=10)
NORMAL_FONT = Font(name='微软雅黑', size=10)
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
CENTER_WRAP = Alignment(horizontal='center', vertical='center', wrap_text=True)

MANUAL_COLS = {'板块', '竞品', '业态'}


def generate_excel(
    df: pd.DataFrame,
    total_supply: int,
    total_trans: int,
    project_total: int,
    month_labels: list[str],
    project_name: str,
    output_path: str,
    plate: str = '',
    competitor: str = '',
    open_date: str = '',
    plot_ratio: str = '',
    total_avg_price: str = '',
    monthly_total_prices: dict = None,
) -> str:
    """生成户型盘点 Excel 文件"""
    wb = Workbook()
    ws = wb.active
    ws.title = project_name[:31]

    # 列定义（按模板顺序）
    base_cols = ['板块', '竞品', '业态', '编码', '户型', '户型面积', '建面分段',
                 '整盘套数', '户配', '供应套数', '成交套数', '成交均价',
                 '整盘去化率', '已供去化率', '已供去化占比']
    month_cols = list(month_labels)
    trailing_cols = ['近3月月均销量', '近3月月均销量占比', '已取证库存', '整盘库存']
    all_cols = base_cols + month_cols + trailing_cols

    # === 表头 ===
    for col_idx, col_name in enumerate(all_cols, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_WRAP
        cell.border = THIN_BORDER

    # === 数据行 ===
    df_col_map = {
        '板块': '板块', '竞品': '竞品', '业态': '业态',
        '编码': '编码', '户型': '户型', '户型面积': '面积范围',
        '建面分段': '建面分段', '整盘套数': '整盘套数', '户配': '户配',
        '供应套数': '供应套数', '成交套数': '成交套数', '成交均价': '成交均价',
        '整盘去化率': '整盘去化率', '已供去化率': '已供去化率',
        '已供去化占比': '已供去化占比', '已取证库存': '已取证库存',
        '整盘库存': '整盘库存',
        '近3月月均销量': '近3月月均销量', '近3月月均销量占比': '近3月月均销量占比',
    }

    pct_cols = {'户配', '整盘去化率', '已供去化率', '已供去化占比', '近3月月均销量占比'}

    for row_idx, (_, row) in enumerate(df.iterrows()):
        excel_row = row_idx + 2

        for col_idx, col_name in enumerate(all_cols, 1):
            cell = ws.cell(row=excel_row, column=col_idx)
            cell.border = THIN_BORDER
            cell.alignment = CENTER_WRAP
            cell.font = NORMAL_FONT

            if col_name in df_col_map:
                value = row.get(df_col_map[col_name], '')
            elif col_name in month_labels:
                value = row.get(col_name, '')
            else:
                value = ''

            cell.value = value

            if col_name in MANUAL_COLS:
                cell.fill = MANUAL_FILL

            if col_name in pct_cols and isinstance(value, (int, float)) and value != '':
                cell.number_format = '0%'  # 整数百分比

            if '均价' in col_name and isinstance(value, (int, float)):
                cell.number_format = '#,##0'

            if col_name == '近3月月均销量' and isinstance(value, (int, float)):
                cell.number_format = '0'

    # === 合计行 ===
    total_row = len(df) + 2

    # 月度合计：上方=各户型成交套数之和，下方=该月截图合计行成交均价
    if monthly_total_prices is None:
        monthly_total_prices = {}
    monthly_totals = {}
    for ml in month_labels:
        month_units = 0
        for _, row in df.iterrows():
            val = row.get(ml, '')
            if val and '\n' in str(val):
                try:
                    month_units += int(str(val).split('\n')[0])
                except (ValueError, IndexError):
                    pass
        month_price = monthly_total_prices.get(ml, '')
        monthly_totals[ml] = f"{month_units}\n{month_price}" if month_units else ''

    total_values = {
        '板块': '', '竞品': '', '业态': '',
        '编码': '合计', '户型': '', '户型面积': '',
        '建面分段': '-',
        '整盘套数': project_total,
        '户配': 1.0,
        '供应套数': total_supply,
        '成交套数': total_trans,
        '成交均价': total_avg_price,
        '整盘去化率': total_trans / project_total if project_total > 0 else 0,
        '已供去化率': total_trans / total_supply if total_supply > 0 else 0,
        '已供去化占比': '-',
        '已取证库存': total_supply - total_trans,
        '整盘库存': project_total - total_trans,
        '近3月月均销量': round(df['近3月月均销量'].sum()) if '近3月月均销量' in df.columns else 0,
        '近3月月均销量占比': '-',
    }

    for col_idx, col_name in enumerate(all_cols, 1):
        cell = ws.cell(row=total_row, column=col_idx)
        cell.border = THIN_BORDER
        cell.alignment = CENTER_WRAP
        cell.font = TOTAL_FONT

        if col_name in total_values:
            value = total_values[col_name]
        elif col_name in month_labels:
            value = monthly_totals.get(col_name, '')
        else:
            value = ''

        cell.value = value

        if col_name in MANUAL_COLS:
            cell.fill = MANUAL_FILL

        if col_name in pct_cols and isinstance(value, (int, float)):
            cell.number_format = '0%'

    # 合计行：编码、户型、户型面积 三列合并，显示"合计"
    # 编码=第4列, 户型=第5列, 户型面积=第6列
    code_col = all_cols.index('编码') + 1
    area_col = all_cols.index('户型面积') + 1
    ws.merge_cells(start_row=total_row, start_column=code_col, end_row=total_row, end_column=area_col)
    merged_cell = ws.cell(row=total_row, column=code_col)
    merged_cell.value = '合计'
    merged_cell.font = TOTAL_FONT
    merged_cell.alignment = CENTER_WRAP

    # === 合并板块列（所有数据行 + 合计行 → 一个单元格）===
    plate_col = all_cols.index('板块') + 1
    if plate:
        ws.merge_cells(start_row=2, start_column=plate_col, end_row=total_row, end_column=plate_col)
        ws.cell(row=2, column=plate_col).value = plate

    # === 合并竞品列（项目名称 + 开盘时间 + 容积率，换行分隔）===
    competitor_col = all_cols.index('竞品') + 1
    competitor_content = project_name
    if open_date:
        competitor_content += f"\n{open_date}"
    if plot_ratio:
        competitor_content += f"\n{plot_ratio}"
    ws.merge_cells(start_row=2, start_column=competitor_col, end_row=total_row, end_column=competitor_col)
    ws.cell(row=2, column=competitor_col).value = competitor_content

    # === 列宽 ===
    col_widths = {
        '板块': 8, '竞品': 10, '业态': 12, '编码': 10, '户型': 10,
        '户型面积': 10, '建面分段': 12, '整盘套数': 10, '户配': 8,
        '供应套数': 10, '成交套数': 10, '成交均价': 10,
        '整盘去化率': 10, '已供去化率': 10, '已供去化占比': 10,
        '已取证库存': 10, '整盘库存': 10,
        '近3月月均销量': 12, '近3月月均销量占比': 12,
    }
    for col_idx, col_name in enumerate(all_cols, 1):
        width = col_widths.get(col_name, 14)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = 'A2'
    wb.save(output_path)
    return output_path


def generate_multi_sheet_excel(all_results: list[dict], output_path: str) -> str:
    """
    生成单 Sheet Excel（所有项目共用表头，顺序堆叠）

    每个项目的数据块：数据行 + 合计行 + 空行分隔
    """
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "户型盘点"

    if not all_results:
        wb.save(output_path)
        return output_path

    # 取第一个项目的月份标签作为列定义
    first = all_results[0]
    month_labels = first['month_labels']
    base_cols = ['板块', '竞品', '业态', '编码', '户型', '户型面积', '建面分段',
                 '整盘套数', '户配', '供应套数', '成交套数', '成交均价',
                 '整盘去化率', '已供去化率', '已供去化占比']
    trailing_cols = ['近3月月均销量', '近3月月均销量占比', '已取证库存', '整盘库存']
    all_cols = base_cols + list(month_labels) + trailing_cols
    pct_cols = {'户配', '整盘去化率', '已供去化率', '已供去化占比', '近3月月均销量占比'}

    # === 写表头（仅一次）===
    for col_idx, col_name in enumerate(all_cols, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_WRAP
        cell.border = THIN_BORDER

    current_row = 2  # 当前写入行

    for proj_idx, result in enumerate(all_results):
        df = result['df']
        total_supply = result['total_supply']
        total_trans = result['total_trans']
        project_total = result['project_total']
        project_name = result['project_name']
        plate = result.get('plate', '')
        open_date = result.get('open_date', '')
        plot_ratio = result.get('plot_ratio', '')
        total_avg_price = result.get('total_avg_price', '')
        monthly_total_prices = result.get('monthly_total_prices', {})

        df_col_map = {
            '板块': '板块', '竞品': '竞品', '业态': '业态',
            '编码': '编码', '户型': '户型', '户型面积': '面积范围',
            '建面分段': '建面分段', '整盘套数': '整盘套数', '户配': '户配',
            '供应套数': '供应套数', '成交套数': '成交套数', '成交均价': '成交均价',
            '整盘去化率': '整盘去化率', '已供去化率': '已供去化率',
            '已供去化占比': '已供去化占比', '已取证库存': '已取证库存',
            '整盘库存': '整盘库存',
            '近3月月均销量': '近3月月均销量', '近3月月均销量占比': '近3月月均销量占比',
        }

        # 数据行
        data_start = current_row
        for _, row in df.iterrows():
            for col_idx, col_name in enumerate(all_cols, 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = THIN_BORDER
                cell.alignment = CENTER_WRAP
                cell.font = NORMAL_FONT

                if col_name in df_col_map:
                    value = row.get(df_col_map[col_name], '')
                elif col_name in month_labels:
                    value = row.get(col_name, '')
                else:
                    value = ''

                cell.value = value
                if col_name in MANUAL_COLS:
                    cell.fill = MANUAL_FILL
                if col_name in pct_cols and isinstance(value, (int, float)) and value != '':
                    cell.number_format = '0%'
                if '均价' in col_name and isinstance(value, (int, float)):
                    cell.number_format = '#,##0'
                if col_name == '近3月月均销量' and isinstance(value, (int, float)):
                    cell.number_format = '0'
            current_row += 1

        # 合计行
        total_row = current_row
        monthly_totals = {}
        for ml in month_labels:
            month_units = 0
            for _, row in df.iterrows():
                val = row.get(ml, '')
                if val and '\n' in str(val):
                    try:
                        month_units += int(str(val).split('\n')[0])
                    except (ValueError, IndexError):
                        pass
            month_price = monthly_total_prices.get(ml, '')
            monthly_totals[ml] = f"{month_units}\n{month_price}" if month_units else ''

        total_values = {
            '板块': '', '竞品': '', '业态': '',
            '编码': '合计', '户型': '', '户型面积': '',
            '建面分段': '-',
            '整盘套数': project_total,
            '户配': 1.0,
            '供应套数': total_supply,
            '成交套数': total_trans,
            '成交均价': total_avg_price,
            '整盘去化率': total_trans / project_total if project_total > 0 else 0,
            '已供去化率': total_trans / total_supply if total_supply > 0 else 0,
            '已供去化占比': '-',
            '已取证库存': total_supply - total_trans,
            '整盘库存': project_total - total_trans,
            '近3月月均销量': round(df['近3月月均销量'].sum()) if '近3月月均销量' in df.columns else 0,
            '近3月月均销量占比': '-',
        }

        for col_idx, col_name in enumerate(all_cols, 1):
            cell = ws.cell(row=total_row, column=col_idx)
            cell.border = THIN_BORDER
            cell.alignment = CENTER_WRAP
            cell.font = TOTAL_FONT

            if col_name in total_values:
                value = total_values[col_name]
            elif col_name in month_labels:
                value = monthly_totals.get(col_name, '')
            else:
                value = ''

            cell.value = value
            if col_name in MANUAL_COLS:
                cell.fill = MANUAL_FILL
            if col_name in pct_cols and isinstance(value, (int, float)):
                cell.number_format = '0%'

        # 合计行：编码+户型+户型面积合并
        code_col = all_cols.index('编码') + 1
        area_col = all_cols.index('户型面积') + 1
        ws.merge_cells(start_row=total_row, start_column=code_col, end_row=total_row, end_column=area_col)
        mc = ws.cell(row=total_row, column=code_col)
        mc.value = '合计'
        mc.font = TOTAL_FONT
        mc.alignment = CENTER_WRAP

        # 板块列合并（本项目的数据行 + 合计行）
        plate_col = all_cols.index('板块') + 1
        if plate:
            ws.merge_cells(start_row=data_start, start_column=plate_col, end_row=total_row, end_column=plate_col)
            ws.cell(row=data_start, column=plate_col).value = plate

        # 竞品列合并
        competitor_col = all_cols.index('竞品') + 1
        competitor_content = project_name
        if open_date:
            competitor_content += f"\n{open_date}"
        if plot_ratio:
            competitor_content += f"\n{plot_ratio}"
        ws.merge_cells(start_row=data_start, start_column=competitor_col, end_row=total_row, end_column=competitor_col)
        ws.cell(row=data_start, column=competitor_col).value = competitor_content

        current_row += 1  # 合计行之后

        # 项目之间空一行分隔（最后一个项目不加）
        if proj_idx < len(all_results) - 1:
            current_row += 1

    # 列宽
    col_widths = {
        '板块': 8, '竞品': 10, '业态': 12, '编码': 10, '户型': 10,
        '户型面积': 10, '建面分段': 12, '整盘套数': 10, '户配': 8,
        '供应套数': 10, '成交套数': 10, '成交均价': 10,
        '整盘去化率': 10, '已供去化率': 10, '已供去化占比': 10,
        '已取证库存': 10, '整盘库存': 10,
        '近3月月均销量': 12, '近3月月均销量占比': 12,
    }
    for col_idx, col_name in enumerate(all_cols, 1):
        width = col_widths.get(col_name, 14)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = 'A2'
    wb.save(output_path)
    return output_path
