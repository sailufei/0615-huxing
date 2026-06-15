/**
 * 房地产户型盘点工具 — 前端逻辑
 */

// === 文件拖拽上传 ===
function setupDropZone(dropZone, fileInput, previewImg) {
  const dropContent = dropZone.querySelector('.drop-content');

  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      handleFile(file, dropContent, previewImg, fileInput);
    }
  });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) handleFile(file, dropContent, previewImg, fileInput);
  });
}

function handleFile(file, dropContent, previewImg, fileInput) {
  // 显示预览
  const reader = new FileReader();
  reader.onload = (e) => {
    previewImg.src = e.target.result;
    previewImg.classList.remove('hidden');
    dropContent.classList.add('hidden');
  };
  reader.readAsDataURL(file);
}

// === 月度行管理 ===
function createMonthlyRow(index) {
  const container = document.getElementById('monthlyContainer');
  const row = document.createElement('div');
  row.className = 'monthly-row';
  row.dataset.index = index;
  row.innerHTML = `
    <input type="text" class="month-label" placeholder="如：2024-05" value="">
    <div class="drop-zone month-drop">
      <input type="file" accept="image/*" hidden>
      <div class="drop-content"><span class="icon">📅</span><p>拖拽或<span class="link">点击上传</span></p></div>
      <img class="preview hidden">
    </div>
    <button class="btn-remove" title="移除">×</button>
  `;
  container.appendChild(row);

  const dropZone = row.querySelector('.month-drop');
  const fileInput = row.querySelector('input[type="file"]');
  const previewImg = row.querySelector('.preview');
  setupDropZone(dropZone, fileInput, previewImg);

  // 移除按钮
  row.querySelector('.btn-remove').addEventListener('click', () => {
    if (container.children.length > 1) {
      row.remove();
    }
  });

  return row;
}

// === 初始化 ===
function init() {
  // 供应截图
  setupDropZone(
    document.getElementById('supplyDrop'),
    document.getElementById('supplyFile'),
    document.getElementById('supplyPreview')
  );

  // 整盘成交截图
  setupDropZone(
    document.getElementById('transDrop'),
    document.getElementById('transFile'),
    document.getElementById('transPreview')
  );

  // 初始化月度行（默认3行）
  const container = document.getElementById('monthlyContainer');
  container.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    createMonthlyRow(i);
  }

  // 添加月份按钮
  document.getElementById('addMonth').addEventListener('click', () => {
    const count = document.querySelectorAll('.monthly-row').length;
    createMonthlyRow(count);
  });

  // 提交按钮
  document.getElementById('submitBtn').addEventListener('click', submitData);

  // 下载按钮
  document.getElementById('downloadBtn').addEventListener('click', downloadExcel);

  // 重置按钮
  document.getElementById('resetBtn').addEventListener('click', reset);
}

// === 提交数据 ===
async function submitData() {
  const projectName = document.getElementById('projectName').value.trim();
  if (!projectName) {
    alert('请输入项目名称');
    return;
  }

  const supplyFile = document.getElementById('supplyFile').files[0];
  const transFile = document.getElementById('transFile').files[0];
  if (!supplyFile || !transFile) {
    alert('请上传整盘供应截图和整盘成交截图');
    return;
  }

  // 收集月度数据
  const monthlyRows = document.querySelectorAll('.monthly-row');
  const monthData = [];
  monthlyRows.forEach((row) => {
    const label = row.querySelector('.month-label').value.trim();
    const file = row.querySelector('input[type="file"]').files[0];
    if (label && file) monthData.push({ label, file });
  });

  if (monthData.length === 0) {
    alert('请至少填写 1 个月份标签并上传对应截图');
    return;
  }

  // 构建 FormData
  const formData = new FormData();
  formData.append('project_name', projectName);
  formData.append('plate', document.getElementById('plate').value.trim());
  formData.append('open_date', document.getElementById('openDate').value.trim());
  formData.append('plot_ratio', document.getElementById('plotRatio').value.trim());
  formData.append('supply_image', supplyFile);
  formData.append('transaction_image', transFile);

  monthData.forEach((m, i) => {
    formData.append(`month_image_${i + 1}`, m.file);
    formData.append(`month_label_${i + 1}`, m.label);
  });

  // 禁用按钮，显示进度
  const btn = document.getElementById('submitBtn');
  const progress = document.getElementById('progress');
  btn.disabled = true;
  btn.textContent = '处理中...';
  progress.classList.remove('hidden');
  progress.textContent = 'OCR 识别中，请耐心等待（约 10-30 秒）...';

  try {
    const resp = await fetch('/api/process', { method: 'POST', body: formData });
    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.detail || '处理失败');
    }

    // 存储结果
    window._resultData = data;

    // 显示结果
    showResult(data);
    progress.textContent = '处理完成！';

  } catch (err) {
    alert('处理失败: ' + err.message);
    progress.classList.add('hidden');
  } finally {
    btn.disabled = false;
    btn.textContent = '开始处理';
    setTimeout(() => progress.classList.add('hidden'), 3000);
  }
}

// === 显示结果 ===
function showResult(data) {
  const section = document.getElementById('resultSection');
  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth' });

  // 汇总信息
  document.getElementById('resultSummary').innerHTML = `
    <div>项目: <span>${data.project_name}</span></div>
    <div>整盘供应: <span>${data.summary.total_supply}</span> 套</div>
    <div>整盘成交: <span>${data.summary.total_transaction}</span> 套</div>
    <div>月份: <span>${data.month_labels.join(' / ')}</span></div>
  `;

  // 错误提示
  const errorsDiv = document.getElementById('resultErrors');
  if (data.errors && data.errors.length > 0) {
    errorsDiv.classList.remove('hidden');
    errorsDiv.textContent = '⚠️ ' + data.errors.join('；');
  } else {
    errorsDiv.classList.add('hidden');
  }

  // 手动列
  const manualCols = new Set(data.manual_fields || []);

  // 构建表头
  const columns = ['板块','竞品','业态','编码','户型','户型面积','建面分段',
    '整盘套数','户配','供应套数','成交套数','成交均价',
    '整盘去化率','已供去化率','已供去化占比',
    ...data.month_labels,
    '近3月月均销量','近3月月均销量占比',
    '已取证库存','整盘库存'];

  const thead = document.querySelector('#resultTable thead');
  thead.innerHTML = '<tr>' + columns.map(c => {
    const cls = manualCols.has(c) ? ' class="manual-header"' : '';
    return `<th${cls}>${c}</th>`;
  }).join('') + '</tr>';

  // 构建数据行
  const tbody = document.querySelector('#resultTable tbody');
  tbody.innerHTML = data.rows.map((row, i) => {
    const isTotal = row['编码'] === '' && row['户型'] === '合计';
    const rowClass = isTotal ? ' class="total-row"' : '';
    return `<tr${rowClass}>` + columns.map(col => {
      let val = '';
      if (col in row) {
        val = row[col];
        // 格式化
        if (['户配','整盘去化率','已供去化率','已供去化占比','近3月月均销量占比'].includes(col)) {
          val = val !== '' ? (parseFloat(val) * 100).toFixed(1) + '%' : '';
        }
      }
      const cellClass = manualCols.has(col) ? ' class="manual-cell"' : '';
      return `<td${cellClass}>${val !== undefined && val !== null ? val : ''}</td>`;
    }).join('') + '</tr>';
  }).join('');

  // 存储下载 URL
  window._excelUrl = data.excel_url;
}

// === 下载 Excel ===
function downloadExcel() {
  if (window._excelUrl) {
    window.open(window._excelUrl, '_blank');
  }
}

// === 重置 ===
function reset() {
  document.getElementById('resultSection').classList.add('hidden');
  document.getElementById('projectName').value = '';
  document.getElementById('plate').value = '';
  document.getElementById('openDate').value = '';
  document.getElementById('plotRatio').value = '';

  // 重置所有上传区
  document.querySelectorAll('.drop-zone').forEach(zone => {
    const content = zone.querySelector('.drop-content');
    const preview = zone.querySelector('.preview');
    const input = zone.querySelector('input[type="file"]');
    if (content) content.classList.remove('hidden');
    if (preview) preview.classList.add('hidden');
    if (input) input.value = '';
  });

  // 重置月度行
  const container = document.getElementById('monthlyContainer');
  container.innerHTML = '';
  for (let i = 0; i < 3; i++) createMonthlyRow(i);

  window._resultData = null;
  window._excelUrl = null;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 启动
document.addEventListener('DOMContentLoaded', init);
