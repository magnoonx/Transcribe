const form = document.getElementById('uploadForm');
const status = document.getElementById('status');
const submitBtn = document.getElementById('submitBtn');
const offsetInput = document.getElementById('timeOffsetSeconds');

document.querySelectorAll('.offset-btn').forEach((button) => {
  button.addEventListener('click', () => {
    const step = Number(button.dataset.step || 0);
    const current = Number(offsetInput.value || 0);
    offsetInput.value = String(current + step);
  });
});

form.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const input = document.getElementById('fileInput');
  const source = document.getElementById('source').value || 'auto';
  const target = document.getElementById('target').value;

  if (!input.files.length) {
    status.textContent = 'Por favor selecciona un archivo .srt';
    return;
  }
  if (!target) {
    status.textContent = 'Por favor indica el idioma destino (ej: es)';
    return;
  }

  submitBtn.disabled = true;
  status.textContent = 'Subiendo...';
  const progressWrap = document.querySelector('.progress-wrap');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  progressWrap.style.display = 'none';

  const fd = new FormData();
  fd.append('file', input.files[0]);
  fd.append('source', source);
  fd.append('target', target);
  fd.append('time_offset_seconds', offsetInput.value || '0');
  const useLLM = document.getElementById('useLLM').checked;
  fd.append('use_llm', useLLM ? 'true' : 'false');

  try {
    const resp = await fetch('/translate', { method: 'POST', body: fd });
    if (!resp.ok) {
      const txt = await resp.text();
      status.textContent = 'Error: ' + txt;
      submitBtn.disabled = false;
      return;
    }

    const data = await resp.json();
    const cacheId = data.cache_id;
    status.textContent = 'Procesando en servidor...';
    progressWrap.style.display = '';

    // Poll progress
    let done = false;
    while (!done) {
      await new Promise(r => setTimeout(r, 1000));
      try {
        const p = await fetch(`/progress/${encodeURIComponent(cacheId)}`);
        if (!p.ok) continue;
        const j = await p.json();
        const last = j.last_index || 0;
        const total = j.total || 0;
        let pct = 0;
        if (total > 0) pct = Math.round((last / total) * 100);
        progressFill.style.width = pct + '%';
        progressText.textContent = `${pct}% (${last}/${total})`;
        if (j.done) {
          done = true;
          break;
        }
      } catch (err) {
        console.error(err);
      }
    }

    status.textContent = 'Listo. Descargando...';
    // Descargar resultado
    const dl = await fetch(`/download/${encodeURIComponent(cacheId)}`);
    if (!dl.ok) {
      status.textContent = 'No se pudo descargar el resultado.';
      submitBtn.disabled = false;
      return;
    }
    const blob = await dl.blob();
    const disposition = dl.headers.get('content-disposition') || '';
    let filename = 'translated.srt';
    const m = /filename=(.*)/.exec(disposition);
    if (m && m[1]) filename = m[1].replace(/\"/g,'');

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    status.textContent = 'Descarga completada.';
  } catch (err) {
    status.textContent = 'Error durante la petición: ' + err.message;
  } finally {
    submitBtn.disabled = false;
  }
});
