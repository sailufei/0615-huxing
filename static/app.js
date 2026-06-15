/**
 * 房地产户型盘点工具 — 多项目队列版
 */

// === 全局状态 ===
let projectQueue = [];        // [{name, plate, openDate, plotRatio, supplyFile, transFile, monthlyFiles: [{label, file}]}]
let editingIndex = -1;       // -1 = 新增模式, >=0 = 编辑模式
let downloadUrl = '';

// === 初始化 ===
function init() {
  // 供应截图
  setupDropZone('supplyDrop', 'supplyFile', 'supplyPreview');
  // 成交截图
  setupDropZone('transDrop', 'transFile', 'transPreview');
  // 月度行
  resetMonthlyRows();
  // 保存按钮
  document.getElementById('saveProjectBtn').addEventListener('click', saveProject);
  // 全部处理
  document.getElementById('processAllBtn').addEventListener('click', processAll);
  // 清空队列
  document.getElementById('clearQueueBtn').addEventListener('click', clearQueue);
  // 添加月份
  document.getElementById('addMonth').addEventListener('click', addMonthlyRow);
  // 下载
  document.getElementById('downloadBtn').addEventListener('click', () => { if (downloadUrl) window.open(downloadUrl, '_blank'); });
  // 重置
  document.getElementById('resetBtn').addEventListener('click', fullReset);
  // 加载队列
  renderQueue();
}

// === 文件上传 ===
function setupDropZone(dropId, fileId, previewId) {
  const drop = document.getElementById(dropId);
  const input = document.getElementById(fileId);
  const preview = document.getElementById(previewId);
  const content = drop.querySelector('.drop-content');

  drop.addEventListener('click', () => input.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('dragover'));
  drop.addEventListener('drop', e => {
    e.preventDefault(); drop.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) showPreview(f, content, preview);
  });
  input.addEventListener('change', () => {
    if (input.files[0]) showPreview(input.files[0], content, preview);
  });
}

function showPreview(file, content, preview) {
  const r = new FileReader();
  r.onload = e => { preview.src = e.target.result; preview.classList.remove('hidden'); content.classList.add('hidden'); };
  r.readAsDataURL(file);
}

// === 月度行 ===
function resetMonthlyRows() {
  const c = document.getElementById('monthlyContainer');
  c.innerHTML = '';
  for (let i = 0; i < 3; i++) addMonthlyRow();
}

function addMonthlyRow() {
  const c = document.getElementById('monthlyContainer');
  const row = document.createElement('div');
  row.className = 'monthly-row';
  row.innerHTML = `
    <input type="text" class="month-label" placeholder="如：2024-05">
    <div class="drop-zone month-drop">
      <input type="file" accept="image/*" hidden>
      <div class="drop-content"><span class="icon">📅</span><p>拖拽或<span class="link">点击上传</span></p></div>
      <img class="preview hidden">
    </div>
    <button class="btn-remove" title="移除">×</button>
  `;
  c.appendChild(row);

  const dz = row.querySelector('.month-drop');
  const inp = row.querySelector('input[type="file"]');
  const prev = row.querySelector('.preview');
  setupDropZoneDynamic(dz, inp, prev);

  row.querySelector('.btn-remove').addEventListener('click', () => {
    if (c.children.length > 1) row.remove();
  });
  return row;
}

function setupDropZoneDynamic(drop, input, preview) {
  const content = drop.querySelector('.drop-content');
  drop.addEventListener('click', () => input.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('dragover'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('dragover'));
  drop.addEventListener('drop', e => {
    e.preventDefault(); drop.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) showPreview(f, content, preview);
  });
  input.addEventListener('change', () => {
    if (input.files[0]) showPreview(input.files[0], content, preview);
  });
}

// === 收集当前表单数据 ===
function collectForm() {
  const name = document.getElementById('projectName').value.trim();
  const plate = document.getElementById('plate').value.trim();
  const openDate = document.getElementById('openDate').value.trim();
  const plotRatio = document.getElementById('plotRatio').value.trim();

  const supplyFile = document.getElementById('supplyFile').files[0];
  const transFile = document.getElementById('transFile').files[0];

  const monthlyRows = document.querySelectorAll('.monthly-row');
  const monthlyFiles = [];
  monthlyRows.forEach(r => {
    const label = r.querySelector('.month-label').value.trim();
    const file = r.querySelector('input[type="file"]').files[0];
    if (label && file) monthlyFiles.push({ label, file });
  });

  return { name, plate, openDate, plotRatio, supplyFile, transFile, monthlyFiles };
}

// === 保存到队列 ===
function saveProject() {
  const data = collectForm();
  if (!data.name) { alert('请输入项目名称'); return; }
  if (!data.supplyFile) { alert('请上传整盘供应截图'); return; }
  if (!data.transFile) { alert('请上传整盘成交截图'); return; }
  if (data.monthlyFiles.length === 0) { alert('请至少填写1个月份标签并上传截图'); return; }

  if (editingIndex >= 0) {
    projectQueue[editingIndex] = data;
  } else {
    projectQueue.push(data);
  }

  editingIndex = -1;
  clearForm();
  renderQueue();
  document.getElementById('formTitle').textContent = '添加项目';
}

// === 渲染队列 ===
function renderQueue() {
  const list = document.getElementById('queueList');
  const count = document.getElementById('queueCount');
  const actions = document.getElementById('queueActions');

  count.textContent = projectQueue.length + ' 个项目';

  if (projectQueue.length === 0) {
    list.innerHTML = '<p class="empty-hint">还没有添加项目，请在下方添加</p>';
    actions.style.display = 'none';
  } else {
    list.innerHTML = projectQueue.map((p, i) => `
      <div class="queue-item">
        <div class="q-info">
          <div class="q-name">${p.name}</div>
          <div class="q-detail">板块: ${p.plate || '-'} | 开盘: ${p.openDate || '-'} | 容积率: ${p.plotRatio || '-'} | 月度截图: ${p.monthlyFiles.length}张</div>
        </div>
        <div class="q-actions">
          <button class="btn-sm" onclick="editProject(${i})">编辑</button>
          <button class="btn-sm danger" onclick="removeProject(${i})">删除</button>
        </div>
      </div>
    `).join('');
    actions.style.display = 'flex';
  }
}

// === 编辑项目 ===
function editProject(index) {
  const p = projectQueue[index];
  editingIndex = index;
  document.getElementById('formTitle').textContent = '编辑项目: ' + p.name;
  document.getElementById('projectName').value = p.name;
  document.getElementById('plate').value = p.plate;
  document.getElementById('openDate').value = p.openDate;
  document.getElementById('plotRatio').value = p.plotRatio;

  // 恢复文件预览
  restorePreview('supplyFile', 'supplyPreview', 'supplyDrop', p.supplyFile);
  restorePreview('transFile', 'transPreview', 'transDrop', p.transFile);

  // 恢复月度
  const container = document.getElementById('monthlyContainer');
  container.innerHTML = '';
  p.monthlyFiles.forEach(m => {
    const row = addMonthlyRow();
    row.querySelector('.month-label').value = m.label;
    restorePreviewDynamic(row.querySelector('input[type="file"]'), row.querySelector('.preview'), row.querySelector('.drop-zone'), m.file);
  });
  if (p.monthlyFiles.length < 3) addMonthlyRow();

  document.getElementById('formSection').scrollIntoView({ behavior: 'smooth' });
}

function restorePreview(fileInputId, previewId, dropId, file) {
  // Can't fully restore File objects from queue, show filename indicator
  const preview = document.getElementById(previewId);
  const content = document.getElementById(dropId).querySelector('.drop-content');
  const reader = new FileReader();
  reader.onload = e => { preview.src = e.target.result; preview.classList.remove('hidden'); content.classList.add('hidden'); };
  reader.readAsDataURL(file);
}

function restorePreviewDynamic(input, preview, drop, file) {
  const content = drop.querySelector('.drop-content');
  const reader = new FileReader();
  reader.onload = e => { preview.src = e.target.result; preview.classList.remove('hidden'); content.classList.add('hidden'); };
  reader.readAsDataURL(file);
}

// === 删除项目 ===
function removeProject(index) {
  if (confirm('确定删除项目 "' + projectQueue[index].name + '"？')) {
    projectQueue.splice(index, 1);
    if (editingIndex === index) { editingIndex = -1; clearForm(); }
    else if (editingIndex > index) editingIndex--;
    renderQueue();
  }
}

// === 清空队列 ===
function clearQueue() {
  if (confirm('确定清空全部 ' + projectQueue.length + ' 个项目？')) {
    projectQueue = [];
    editingIndex = -1;
    clearForm();
    renderQueue();
  }
}

// === 清空表单 ===
function clearForm() {
  document.getElementById('projectName').value = '';
  document.getElementById('plate').value = '';
  document.getElementById('openDate').value = '';
  document.getElementById('plotRatio').value = '';
  // 重置上传区
  ['supplyDrop', 'transDrop'].forEach(id => {
    const drop = document.getElementById(id);
    drop.querySelector('.drop-content').classList.remove('hidden');
    drop.querySelector('.preview').classList.add('hidden');
  });
  document.getElementById('supplyFile').value = '';
  document.getElementById('transFile').value = '';
  resetMonthlyRows();
}

// === 全部处理 ===
async function processAll() {
  if (projectQueue.length === 0) { alert('队列为空，请先添加项目'); return; }

  const btn = document.getElementById('processAllBtn');
  const progress = document.getElementById('batchProgress');
  btn.disabled = true;
  btn.textContent = '处理中...';
  progress.classList.remove('hidden');

  const formData = new FormData();
  formData.append('project_count', projectQueue.length);

  for (let i = 0; i < projectQueue.length; i++) {
    const p = projectQueue[i];
    formData.append(`name_${i}`, p.name);
    formData.append(`plate_${i}`, p.plate);
    formData.append(`open_date_${i}`, p.openDate);
    formData.append(`plot_ratio_${i}`, p.plotRatio);
    formData.append(`supply_${i}`, p.supplyFile);
    formData.append(`transaction_${i}`, p.transFile);
    p.monthlyFiles.forEach((m, mi) => {
      formData.append(`month_file_${i}_${mi}`, m.file);
      formData.append(`month_label_${i}_${mi}`, m.label);
    });
    progress.textContent = `处理中... (${i + 1}/${projectQueue.length})`;
  }

  try {
    const resp = await fetch('/api/process-batch', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || '处理失败');

    downloadUrl = data.excel_url;
    document.getElementById('resultSection').classList.remove('hidden');

    const errorsDiv = document.getElementById('resultErrors');
    if (data.errors && data.errors.length > 0) {
      errorsDiv.classList.remove('hidden');
      errorsDiv.textContent = '部分项目处理异常: ' + data.errors.join('; ');
    } else {
      errorsDiv.classList.add('hidden');
    }

    progress.textContent = '处理完成！共 ' + data.results.length + ' 个项目';
    document.getElementById('resultSection').scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    alert('处理失败: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '全部处理并导出';
    setTimeout(() => progress.classList.add('hidden'), 5000);
  }
}

// === 完全重置 ===
function fullReset() {
  projectQueue = [];
  editingIndex = -1;
  downloadUrl = '';
  clearForm();
  renderQueue();
  document.getElementById('resultSection').classList.add('hidden');
  document.getElementById('formTitle').textContent = '添加项目';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.addEventListener('DOMContentLoaded', init);
