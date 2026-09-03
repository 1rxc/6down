document.addEventListener('DOMContentLoaded', () => {
  window.addEventListener('mousemove', (e) => {
    document.documentElement.style.setProperty('--mouse-x', `${e.clientX}px`);
    document.documentElement.style.setProperty('--mouse-y', `${e.clientY}px`);
  });

  const videoUrlInput = document.getElementById('videoUrlInput');
  const pasteBtn = document.getElementById('pasteBtn');
  const clearBtn = document.getElementById('clearBtn');
  const fetchBtn = document.getElementById('fetchBtn');
  const statusToast = document.getElementById('statusToast');
  const toastMessage = document.getElementById('toastMessage');

  const previewCard = document.getElementById('previewCard');
  const videoThumb = document.getElementById('videoThumb');
  const videoDuration = document.getElementById('videoDuration');
  const videoTitle = document.getElementById('videoTitle');
  const videoAuthor = document.getElementById('videoAuthor');
  const videoViews = document.getElementById('videoViews');
  const videoLiveBadge = document.getElementById('videoLiveBadge');
  
  const modeTabs = document.querySelectorAll('.mode-tab');
  const modeIndicator = document.getElementById('modeIndicator');
  const qualitySelect = document.getElementById('qualitySelect');
  const startDownloadBtn = document.getElementById('startDownloadBtn');

  const progressCard = document.getElementById('progressCard');
  const statStatusText = document.getElementById('statStatusText');
  const progressMediaTitle = document.getElementById('progressMediaTitle');
  const progressPercentNum = document.getElementById('progressPercentNum');
  const progressBarFill = document.getElementById('progressBarFill');
  const statSpeed = document.getElementById('statSpeed');
  const statSize = document.getElementById('statSize');
  const statEta = document.getElementById('statEta');
  const completedRow = document.getElementById('completedRow');
  const manualDownloadLink = document.getElementById('manualDownloadLink');
  const resetBtn = document.getElementById('resetBtn');

  const historyBtn = document.getElementById('historyBtn');
  const historyModal = document.getElementById('historyModal');
  const closeHistoryBtn = document.getElementById('closeHistoryBtn');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');
  const historyList = document.getElementById('historyList');

  let currentVideo = null;
  let currentMode = 'video';
  let activeEventSource = null;

  function getTargetDownloadLabel() {
    const selectedOpt = qualitySelect.options[qualitySelect.selectedIndex];
    if (!selectedOpt) return 'Download Media';
    if (currentMode === 'video') {
      return `Download MP4 (${selectedOpt.value}p)`;
    } else {
      const bit = selectedOpt.value === '0' ? (selectedOpt.dataset.format || 'AUDIO').toUpperCase() : `${selectedOpt.value}kbps`;
      return `Download ${(selectedOpt.dataset.format || 'MP3').toUpperCase()} (${bit})`;
    }
  }

  function setButtonState(state = 'idle', customText = null) {
    if (state === 'loading') {
      startDownloadBtn.disabled = true;
      startDownloadBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>${customText || 'Converting...'}</span>`;
    } else if (state === 'success') {
      startDownloadBtn.disabled = false;
      startDownloadBtn.innerHTML = `<i class="fa-solid fa-check"></i> <span>${customText || 'Conversion Ready!'}</span>`;
    } else {
      startDownloadBtn.disabled = false;
      const label = customText || getTargetDownloadLabel();
      startDownloadBtn.innerHTML = `<i class="fa-solid fa-arrow-down-to-line"></i> <span>${label}</span>`;
    }
  }

  function showToast(msg, isError = false) {
    toastMessage.textContent = msg;
    statusToast.style.display = 'inline-flex';
    statusToast.style.borderColor = isError ? 'rgba(244, 63, 94, 0.4)' : 'rgba(16, 185, 129, 0.3)';
    statusToast.style.color = isError ? '#fda4af' : '#6ee7b7';
    statusToast.style.backgroundColor = isError ? 'rgba(244, 63, 94, 0.12)' : 'rgba(16, 185, 129, 0.12)';
    statusToast.querySelector('.toast-icon').className = isError 
      ? 'fa-solid fa-circle-exclamation toast-icon' 
      : 'fa-solid fa-circle-check toast-icon';

    setTimeout(() => {
      statusToast.style.display = 'none';
    }, 4500);
  }

  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        videoUrlInput.value = text.trim();
        clearBtn.style.display = 'block';
        fetchVideo();
      }
    } catch {
      showToast('Paste link manually into input.', true);
    }
  });

  videoUrlInput.addEventListener('input', () => {
    clearBtn.style.display = videoUrlInput.value.trim() ? 'block' : 'none';
  });

  clearBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    clearBtn.style.display = 'none';
    previewCard.style.display = 'none';
    progressCard.style.display = 'none';
    videoUrlInput.focus();
  });

  fetchBtn.addEventListener('click', fetchVideo);
  videoUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') fetchVideo();
  });

  async function fetchVideo() {
    const url = videoUrlInput.value.trim();
    if (!url) return showToast('Please enter a valid YouTube URL.', true);

    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
      return showToast('Please provide a valid YouTube video link.', true);
    }

    statusToast.style.display = 'none';
    fetchBtn.disabled = true;
    fetchBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
    previewCard.style.display = 'none';
    progressCard.style.display = 'none';

    try {
      const res = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.detail || 'Could not fetch video info.');

      currentVideo = data.data;
      renderPreview(currentVideo);
    } catch (err) {
      showToast(err.message || 'Failed to fetch video.', true);
    } finally {
      fetchBtn.disabled = false;
      fetchBtn.innerHTML = '<span class="btn-text">Fetch</span> <i class="fa-solid fa-arrow-right arrow-icon"></i>';
    }
  }

  function renderPreview(data) {
    videoThumb.src = data.thumbnail || '';
    videoDuration.textContent = data.duration_formatted || '00:00';
    videoTitle.textContent = data.title;
    videoAuthor.innerHTML = `<i class="fa-solid fa-circle-user"></i> ${data.uploader}`;
    videoViews.innerHTML = `<i class="fa-solid fa-eye"></i> ${data.view_count} views`;
    videoLiveBadge.style.display = data.is_live ? 'flex' : 'none';

    updateQualityDropdown();
    previewCard.style.display = 'block';
    previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  modeTabs.forEach((tab, index) => {
    tab.addEventListener('click', () => {
      modeTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentMode = tab.dataset.mode;
      
      modeIndicator.style.transform = `translateX(${index * 100}%)`;
      updateQualityDropdown();
    });
  });

  function updateQualityDropdown() {
    qualitySelect.innerHTML = '';
    if (currentMode === 'video') {
      const vFormats = currentVideo.video_formats || [];
      vFormats.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.height;
        opt.textContent = `${f.label} • MP4`;
        qualitySelect.appendChild(opt);
      });
    } else {
      const aFormats = currentVideo.audio_formats || [];
      aFormats.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.bitrate;
        opt.dataset.format = f.format;
        opt.textContent = f.label;
        qualitySelect.appendChild(opt);
      });
    }
    setButtonState('idle');
  }

  qualitySelect.addEventListener('change', () => {
    setButtonState('idle');
  });

  startDownloadBtn.addEventListener('click', async () => {
    if (!currentVideo) return;

    const selectedOpt = qualitySelect.options[qualitySelect.selectedIndex];
    const qualityVal = selectedOpt ? selectedOpt.value : (currentMode === 'video' ? '1080' : '320');
    const targetFormat = currentMode === 'video' ? 'mp4' : (selectedOpt.dataset.format || 'mp3');

    setButtonState('loading', 'Starting...');

    try {
      const res = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentVideo.url,
          media_type: currentMode,
          quality: qualityVal,
          format: targetFormat
        })
      });

      const data = await res.json();
      if (!data.success) throw new Error(data.detail);

      trackProgress(data.task_id, currentVideo, currentMode, qualityVal, targetFormat);
    } catch (err) {
      showToast(err.message || 'Download initialization error.', true);
      setButtonState('idle');
    }
  });

  function trackProgress(taskId, videoInfo, mode, qualityVal, formatVal) {
    if (activeEventSource) activeEventSource.close();

    progressCard.style.display = 'block';
    completedRow.style.display = 'none';
    progressMediaTitle.textContent = videoInfo.title;
    progressPercentNum.textContent = '0';
    progressBarFill.style.width = '0%';
    statStatusText.textContent = 'DOWNLOADING';
    statSpeed.textContent = 'Starting...';
    statSize.textContent = '0 / 0 MB';
    statEta.textContent = '--:--';
    
    progressCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    activeEventSource = new EventSource(`/api/progress/stream/${taskId}`);

    activeEventSource.onmessage = (e) => {
      try {
        const task = JSON.parse(e.data);
        const p = Math.max(0, Math.min(100, Math.round(task.progress || 0)));
        
        progressPercentNum.textContent = p;
        progressBarFill.style.width = `${p}%`;
        statStatusText.textContent = (task.status || 'CONVERTING').toUpperCase();
        statSpeed.textContent = task.speed || '-- MB/s';
        statEta.textContent = task.eta || '--:--';

        if (task.downloaded_bytes) {
          const dl = (task.downloaded_bytes / (1024 * 1024)).toFixed(1);
          const tot = task.total_bytes ? (task.total_bytes / (1024 * 1024)).toFixed(1) : dl;
          statSize.textContent = `${dl} / ${tot} MB`;
        }

        if (task.status === 'downloading') {
          setButtonState('loading', `Downloading ${p}%`);
        } else if (task.status === 'processing') {
          setButtonState('loading', 'Merging & Finishing...');
        } else if (task.status === 'completed') {
          activeEventSource.close();
          progressPercentNum.textContent = '100';
          progressBarFill.style.width = '100%';
          statStatusText.textContent = 'COMPLETED';
          statSpeed.textContent = 'Ready';
          statEta.textContent = '0s';

          const finalName = task.filename || `download.${mode === 'video' ? 'mp4' : formatVal}`;
          const fileUrl = `/api/file/${taskId}/${encodeURIComponent(finalName)}`;
          
          manualDownloadLink.href = fileUrl;
          manualDownloadLink.setAttribute('download', finalName);
          completedRow.style.display = 'flex';

          triggerDirectDownload(fileUrl, finalName);

          setButtonState('success', 'Download Complete!');
          setTimeout(() => {
            setButtonState('idle');
          }, 3500);

          saveHistory({
            title: videoInfo.title,
            format: mode === 'video' ? `MP4 ${qualityVal}p` : `${formatVal.toUpperCase()} ${qualityVal}k`,
            url: videoInfo.url,
            taskId: taskId,
            filename: finalName,
            date: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          });

        } else if (task.status === 'error') {
          activeEventSource.close();
          showToast(`Error: ${task.error}`, true);
          statStatusText.textContent = 'FAILED';
          setButtonState('idle');
        }
      } catch (err) {
        console.error('SSE parsing error:', err);
      }
    };

    activeEventSource.onerror = () => {
      activeEventSource.close();
    };
  }

  function triggerDirectDownload(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', filename);
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      try { document.body.removeChild(a); } catch {}
    }, 2000);
  }

  resetBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    clearBtn.style.display = 'none';
    previewCard.style.display = 'none';
    progressCard.style.display = 'none';
    videoUrlInput.focus();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  function getHistory() {
    try { return JSON.parse(localStorage.getItem('6down_studio_hist') || '[]'); } catch { return []; }
  }

  function saveHistory(item) {
    const list = getHistory();
    list.unshift(item);
    localStorage.setItem('6down_studio_hist', JSON.stringify(list.slice(0, 25)));
  }

  function renderHistory() {
    const list = getHistory();
    historyList.innerHTML = list.length ? '' : '<p style="color:#8492a6;text-align:center;padding:24px;">No downloads yet.</p>';
    list.forEach(item => {
      const div = document.createElement('div');
      div.className = 'history-entry';
      const dlUrl = item.taskId ? `/api/file/${item.taskId}/${encodeURIComponent(item.filename || 'download')}` : null;
      
      div.innerHTML = `
        <div style="flex:1;min-width:0;">
          <div class="h-title">${item.title}</div>
          <div class="h-meta">${item.format} • ${item.date}</div>
        </div>
        <div style="display:flex;gap:6px;">
          ${dlUrl ? `<a href="${dlUrl}" download="${item.filename || ''}" class="btn-chip" title="Download Again"><i class="fa-solid fa-download"></i></a>` : ''}
          <button class="btn-chip load-hist-btn" title="Reload"><i class="fa-solid fa-arrow-up-right-from-square"></i></button>
        </div>
      `;
      div.querySelector('.load-hist-btn').addEventListener('click', () => {
        videoUrlInput.value = item.url;
        clearBtn.style.display = 'block';
        historyModal.style.display = 'none';
        fetchVideo();
      });
      historyList.appendChild(div);
    });
  }

  historyBtn.addEventListener('click', () => {
    renderHistory();
    historyModal.style.display = 'flex';
  });

  closeHistoryBtn.addEventListener('click', () => historyModal.style.display = 'none');
  historyModal.addEventListener('click', (e) => {
    if (e.target === historyModal) historyModal.style.display = 'none';
  });

  clearHistoryBtn.addEventListener('click', () => {
    localStorage.removeItem('6down_studio_hist');
    renderHistory();
  });
});
