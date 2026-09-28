// Global Data References
window.TRACKS = APP_DATA.tracks;
window.POINTS = APP_DATA.points;
window.CONTOURS = APP_DATA.contours;
window.MARGINALS = APP_DATA.marginals;
window.STATS = APP_DATA.stats;
window.AXIS = APP_DATA.axis;

let currentTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
document.documentElement.setAttribute('data-theme', currentTheme);

// Default to color by song count
let colorMode = 'count';
let selectedPoint = null;
let activePointTrackIndex = 0;
let searchQuery = '';

const chartDom = document.getElementById('chart');
const myChart = echarts.init(chartDom, null, { renderer: 'svg' });

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Color calculations
function getCountColor(count) {
    const isDark = currentTheme === 'dark';
    if (count <= 1) return isDark ? '#38bdf8' : '#0284c7'; // 1 song: clean sky blue
    if (count === 2) return isDark ? '#34d399' : '#059669'; // 2 songs: emerald green
    if (count === 3) return isDark ? '#fbbf24' : '#d97706'; // 3 songs: amber gold
    if (count === 4) return isDark ? '#fb923c' : '#ea580c'; // 4 songs: vivid orange
    return isDark ? '#f87171' : '#dc2626';                  // 5+ songs: crimson red
}

function getEnergyColor(val) {
    const t = Math.max(0, Math.min(1, val));
    if (t < 0.35) return '#0284c7';
    if (t < 0.6) return '#2563eb';
    if (t < 0.78) return '#7c3aed';
    return '#e11d48';
}

function getYearColor(year) {
    if (!year) return '#94a3b8';
    const min = APP_DATA.stats.min_year;
    const max = APP_DATA.stats.max_year;
    const t = (year - min) / Math.max(1, (max - min));
    if (t < 0.25) return '#3b82f6';
    if (t < 0.5) return '#0d9488';
    if (t < 0.75) return '#16a34a';
    return '#d97706';
}

function getBpmColor(bpm) {
    const t = Math.max(0, Math.min(1, (bpm - 60) / 120));
    if (t < 0.3) return '#0284c7';
    if (t < 0.6) return '#4f46e5';
    if (t < 0.8) return '#9333ea';
    return '#e11d48';
}

function getOutlierColor(pt) {
    const isDark = currentTheme === 'dark';
    const rank = pt.outlier_rank;
    if (rank === 1) return isDark ? '#fb7185' : '#e11d48';
    if (rank === 2) return isDark ? '#fb923c' : '#ea580c';
    if (rank === 3) return isDark ? '#fbbf24' : '#d97706';
    if (rank && rank <= 6) return isDark ? '#c084fc' : '#9333ea';
    if (rank && rank <= 10) return isDark ? '#60a5fa' : '#2563eb';
    const s = pt.anomaly_score || 0;
    if (s > 0.85) return isDark ? 'rgba(96, 165, 250, 0.5)' : 'rgba(37, 99, 235, 0.45)';
    return isDark ? 'rgba(148, 163, 184, 0.22)' : 'rgba(100, 116, 139, 0.2)';
}

function getPointColor(pt) {
    if (colorMode === 'outlier') return getOutlierColor(pt);
    if (colorMode === 'count') return getCountColor(pt.count);
    if (colorMode === 'energy') return getEnergyColor(pt.y);
    if (colorMode === 'year') return getYearColor(pt.year);
    if (colorMode === 'bpm') return getBpmColor(pt.x);
    return currentTheme === 'dark' ? '#60a5fa' : '#2563eb';
}

function buildSeriesData() {
    const isDark = currentTheme === 'dark';
    const query = searchQuery.trim().toLowerCase();

    return APP_DATA.points.map((pt, i) => {
        const color = getPointColor(pt);
        const count = pt.count;
        let size = count === 1 ? 8 : (count === 2 ? 11 : (count === 3 ? 14 : (count === 4 ? 16 : 18)));
        const isOutlierPoint = colorMode === 'outlier' && pt.outlier_rank;
        if (colorMode === 'outlier') {
            const rank = pt.outlier_rank;
            if (rank === 1) size = 18;
            else if (rank === 2 || rank === 3) size = 16;
            else if (rank && rank <= 6) size = 14;
            else if (rank && rank <= 10) size = 12;
            else size = 6;
        }

        // Check search match
        let isMatch = true;
        if (query) {
            isMatch = pt.indices.some(idx => {
                const tr = window.TRACKS[idx];
                return tr.name.toLowerCase().includes(query) ||
                    tr.artists.toLowerCase().includes(query) ||
                    tr.album.toLowerCase().includes(query);
            });
        }

        const opacity = isMatch
            ? (colorMode === 'outlier'
                ? (pt.outlier_rank ? 1.0 : (pt.anomaly_score > 0.85 ? 0.7 : 0.25))
                : (count > 1 ? 0.95 : 0.75))
            : 0.08;

        const borderColor = isOutlierPoint
            ? (isDark ? '#ffffff' : '#0f172a')
            : (count > 1 ? (isDark ? '#ffffff' : '#0f172a') : (isDark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.15)'));

        const borderWidth = isOutlierPoint ? 2 : (count > 1 ? 1.5 : 0.6);

        return {
            name: `pt_${i}`,
            value: [pt.x, pt.y, count, pt.year, pt.indices, pt.x, pt.y],
            symbolSize: size,
            itemStyle: {
                color: isMatch ? color : (isDark ? '#374151' : '#d1d5db'),
                opacity: opacity,
                borderColor: borderColor,
                borderWidth: borderWidth
            }
        };
    });
}

function getChartOption() {
    const isDark = currentTheme === 'dark';
    const textColor = isDark ? '#9ca3af' : '#6b7280';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';
    const histColor = isDark ? 'rgba(96, 165, 250, 0.55)' : 'rgba(31, 119, 180, 0.65)';
    const kdeColor = isDark ? '#f87171' : '#d62728';
    const contourColor = isDark ? 'rgba(147, 197, 253, 0.5)' : 'rgba(11, 61, 102, 0.6)';

    const energyMaxCount = Math.max(1, Math.ceil(APP_DATA.marginals.energy_max * 1.1));

    return {
        backgroundColor: 'transparent',
        animation: false,
        grid: [
            // 0: Main scatter plot
            { left: 55, right: 80, top: 90, bottom: 45 },
            // 1: Top BPM distribution
            { left: 55, right: 80, top: 16, height: 55 },
            // 2: Right Energy distribution
            { top: 90, bottom: 45, right: 16, width: 50 }
        ],
        xAxis: [
            // 0: Main BPM
            {
                gridIndex: 0,
                type: 'value',
                min: APP_DATA.axis.bpm[0],
                max: APP_DATA.axis.bpm[1],
                name: 'BPM',
                nameLocation: 'middle',
                nameGap: 24,
                nameTextStyle: { color: textColor, fontSize: 11 },
                axisLabel: { color: textColor, fontSize: 10, fontFamily: 'monospace' },
                splitLine: { lineStyle: { color: gridColor } }
            },
            // 1: Top BPM
            {
                gridIndex: 1,
                type: 'value',
                min: APP_DATA.axis.bpm[0],
                max: APP_DATA.axis.bpm[1],
                show: false
            },
            // 2: Right count (horizontal bar width)
            {
                gridIndex: 2,
                type: 'value',
                min: 0,
                max: energyMaxCount,
                show: false
            }
        ],
        yAxis: [
            // 0: Main Energy
            {
                gridIndex: 0,
                type: 'value',
                min: APP_DATA.axis.energy[0],
                max: APP_DATA.axis.energy[1],
                name: 'Energy',
                nameLocation: 'middle',
                nameGap: 30,
                nameTextStyle: { color: textColor, fontSize: 11 },
                axisLabel: { color: textColor, fontSize: 10, fontFamily: 'monospace' },
                splitLine: { lineStyle: { color: gridColor } }
            },
            // 1: Top count
            {
                gridIndex: 1,
                type: 'value',
                show: false
            },
            // 2: Right Energy (aligned with main Y-axis)
            {
                gridIndex: 2,
                type: 'value',
                min: APP_DATA.axis.energy[0],
                max: APP_DATA.axis.energy[1],
                show: false
            }
        ],
        tooltip: {
            trigger: 'item',
            confine: true,
            backgroundColor: isDark ? '#161922' : '#ffffff',
            borderColor: isDark ? '#272c3a' : '#e5e7eb',
            borderWidth: 1,
            padding: [8, 12],
            textStyle: { color: isDark ? '#f3f4f6' : '#111827', fontSize: 12 },
            extraCssText: 'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); border-radius: 6px;',
            formatter: function (params) {
                if (params.seriesType !== 'scatter') return '';
                const val = params.value;
                const bpm = val[5].toFixed(1);
                const energy = val[6].toFixed(3);
                const count = val[2];
                const indices = val[4];

                let html = '<div class="simple-tooltip">';
                html += `<div class="stt-coords">BPM ${bpm} · Energy ${energy}</div>`;

                const outlierTrack = indices.map(idx => window.TRACKS[idx]).find(t => t && t.outlier_rank);
                if (outlierTrack) {
                    html += `<div style="font-size:11px;font-weight:600;color:#e11d48;margin:2px 0 6px;">⚡ 算法挖掘离群 Top ${outlierTrack.outlier_rank} · ${escapeHtml(outlierTrack.outlier_tags[0] || '反常特征')}</div>`;
                }

                if (count === 1) {
                    const t = window.TRACKS[indices[0]];
                    html += `<div class="stt-title">${escapeHtml(t.name)}</div>`;
                    html += `<div class="stt-artist">${escapeHtml(t.artists)} · ${t.year || '未知'}</div>`;
                } else {
                    html += `<div style="font-weight:600;margin-bottom:4px;color:var(--text-main);">共 ${count} 首歌在此点：</div>`;
                    const showN = Math.min(count, 4);
                    for (let i = 0; i < showN; i++) {
                        const t = window.TRACKS[indices[i]];
                        html += `<div class="stt-item">${i + 1}. ${escapeHtml(t.name)} <span style="color:#9ca3af;">- ${escapeHtml(t.artists)}</span></div>`;
                    }
                    if (count > 4) {
                        html += `<div style="color:#9ca3af;font-size:10px;">... 另有 ${count - 4} 首歌</div>`;
                    }
                }
                html += '<div class="stt-hint">点击在右侧查看详情与原始数据</div>';
                html += '</div>';
                return html;
            }
        },
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1],
                filterMode: 'none',
                zoomOnMouseWheel: true,
                moveOnMouseMove: true
            },
            {
                type: 'inside',
                yAxisIndex: [0, 2],
                filterMode: 'none',
                zoomOnMouseWheel: true,
                moveOnMouseMove: true
            }
        ],
        series: [
            // Top BPM Histogram
            {
                name: 'BPM Hist',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                barWidth: '85%',
                data: APP_DATA.marginals.bpm_hist,
                itemStyle: { color: histColor },
                silent: true
            },
            // Top BPM KDE Line
            {
                name: 'BPM KDE',
                type: 'line',
                xAxisIndex: 1,
                yAxisIndex: 1,
                smooth: true,
                showSymbol: false,
                data: APP_DATA.marginals.bpm_kde,
                lineStyle: { color: kdeColor, width: 1.8 },
                silent: true
            },
            // Right Energy Histogram (Proper horizontal bars via custom series)
            {
                name: 'Energy Hist',
                type: 'custom',
                xAxisIndex: 2,
                yAxisIndex: 2,
                renderItem: function (params, api) {
                    const count = api.value(0);
                    const energy = api.value(1);
                    if (count <= 0) return;
                    // Bin height is 0.02 across [0, 1] range; half-height ~0.0085 for spacing
                    const p0 = api.coord([0, energy - 0.0085]);
                    const p1 = api.coord([count, energy + 0.0085]);
                    return {
                        type: 'rect',
                        shape: {
                            x: p0[0],
                            y: p1[1],
                            width: Math.max(0, p1[0] - p0[0]),
                            height: Math.max(0, p0[1] - p1[1])
                        },
                        style: {
                            fill: histColor
                        }
                    };
                },
                data: APP_DATA.marginals.energy_hist,
                silent: true
            },
            // Right Energy KDE Line (Horizontal profile curve)
            {
                name: 'Energy KDE',
                type: 'line',
                xAxisIndex: 2,
                yAxisIndex: 2,
                smooth: true,
                showSymbol: false,
                data: APP_DATA.marginals.energy_kde,
                lineStyle: { color: kdeColor, width: 1.8 },
                silent: true
            },
            // Density Contour Lines
            ...(APP_DATA.contours && APP_DATA.contours.length > 0 ? [{
                name: 'Contours',
                type: 'lines',
                coordinateSystem: 'cartesian2d',
                xAxisIndex: 0,
                yAxisIndex: 0,
                polyline: true,
                data: APP_DATA.contours.map(c => ({ coords: c.coords })),
                lineStyle: { color: contourColor, width: 1.2 },
                silent: true,
                z: 1
            }] : []),
            // Main Scatter Series
            {
                name: 'Tracks',
                type: 'scatter',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: buildSeriesData(),
                markLine: {
                    silent: true,
                    symbol: 'none',
                    lineStyle: {
                        color: isDark ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.12)',
                        type: 'dashed',
                        width: 1
                    },
                    label: {
                        formatter: '{b}',
                        position: 'insideEndTop',
                        color: textColor,
                        fontSize: 9
                    },
                    data: [
                        { xAxis: 85, name: '85' },
                        { xAxis: 128, name: '128' },
                        { xAxis: 174, name: '174' }
                    ]
                },
                z: 5
            }
        ]
    };
}

function renderChart() {
    myChart.setOption(getChartOption(), true);
}

// Selection & Inspector
function selectPoint(val) {
    selectedPoint = val;
    const origBpm = val[5].toFixed(2);
    const origEnergy = val[6].toFixed(4);
    const count = val[2];
    const indices = val[4];

    document.getElementById('inspector-empty').style.display = 'none';
    document.getElementById('inspector-content').style.display = 'block';

    document.getElementById('coord-info').textContent = `BPM ${origBpm} · Energy ${origEnergy} · 共 ${count} 首歌曲`;

    const selector = document.getElementById('track-selector');
    selector.innerHTML = '';

    if (count > 1) {
        selector.style.display = 'flex';
        indices.forEach((trackIdx, pIdx) => {
            const tr = window.TRACKS[trackIdx];
            const pill = document.createElement('div');
            pill.className = `track-pill ${pIdx === activePointTrackIndex ? 'active' : ''}`;
            pill.textContent = `${pIdx + 1}. ${tr.name}`;
            pill.title = `${tr.name} - ${tr.artists}`;
            pill.addEventListener('click', () => {
                activePointTrackIndex = pIdx;
                updateInspectorDetails(window.TRACKS[indices[pIdx]]);
                document.querySelectorAll('.track-pill').forEach((el, i) => {
                    el.className = `track-pill ${i === pIdx ? 'active' : ''}`;
                });
            });
            selector.appendChild(pill);
        });
    } else {
        selector.style.display = 'none';
        activePointTrackIndex = 0;
    }

    const currentTrack = window.TRACKS[indices[activePointTrackIndex] || indices[0]];
    updateInspectorDetails(currentTrack);
}

function updateInspectorDetails(track) {
    if (!track) return;

    document.getElementById('track-name').textContent = track.name;
    document.getElementById('track-artist-album').textContent = `${track.artists} · 《${track.album || '单曲'}》`;
    document.getElementById('track-link').href = `https://music.163.com/#/song?id=${track.id}`;

    // Outlier banner
    const outlierBanner = document.getElementById('outlier-alert');
    if (outlierBanner) {
        if (track.outlier_rank) {
            outlierBanner.style.display = 'block';
            document.getElementById('oab-tag').textContent = `⚡ 综合反常度 Top ${track.outlier_rank}`;
            const isoStr = track.iso_score !== undefined ? Number(track.iso_score).toFixed(3) : '-';
            const lofStr = track.lof_score !== undefined ? Number(track.lof_score).toFixed(3) : '-';
            document.getElementById('oab-scores').textContent = `孤立森林: ${isoStr} · LOF: ${lofStr}`;
            document.getElementById('oab-reason').textContent = track.outlier_reason || '声学与空间特征综合偏离';
        } else {
            outlierBanner.style.display = 'none';
        }
    }

    // Key values
    document.getElementById('val-bpm').textContent = `${track.bpm}`;
    document.getElementById('val-engine').textContent = `${track.bpm_method}`;
    const beatThisStr = track.bpm_beat_this !== null ? track.bpm_beat_this : '-';
    const essentiaStr = track.bpm_essentia !== null ? `${track.bpm_essentia}` : '-';
    document.getElementById('val-dual-bpm').textContent = `${beatThisStr} / ${essentiaStr}`;
    document.getElementById('val-energy').textContent = `${track.energy}`;
    document.getElementById('val-year-dur').textContent = `${track.year || '未知'} · ${track.duration_str}`;
    document.getElementById('val-audio').textContent = `${Math.round(track.source_br / 1000)}k · ${track.source_kind === 'trial' ? '试听片段' : '完整音频'}`;

    // Feature breakdown
    const f = track.features;
    document.getElementById('feat-onset').textContent = `${f.onset_rate} /s (${Math.round(f.norm_onset * 100)}%)`;
    document.getElementById('bar-onset').style.width = `${Math.min(100, Math.round(f.norm_onset * 100))}%`;

    document.getElementById('feat-flux').textContent = `${f.flux_rel} (${Math.round(f.norm_flux * 100)}%)`;
    document.getElementById('bar-flux').style.width = `${Math.min(100, Math.round(f.norm_flux * 100))}%`;

    document.getElementById('feat-centroid').textContent = `${f.centroid_hz} Hz (${Math.round(f.norm_centroid * 100)}%)`;
    document.getElementById('bar-centroid').style.width = `${Math.min(100, Math.round(f.norm_centroid * 100))}%`;

    document.getElementById('feat-zcr').textContent = `${f.zcr} (${Math.round(f.norm_zcr * 100)}%)`;
    document.getElementById('bar-zcr').style.width = `${Math.min(100, Math.round(f.norm_zcr * 100))}%`;

    document.getElementById('feat-loudness').textContent = `${f.loudness_lufs} LUFS`;

    // Raw JSON
    const rawJsonStr = JSON.stringify(track.raw_record, null, 2);
    document.getElementById('raw-json-code').textContent = rawJsonStr;
}

// Outliers List in empty inspector
function renderOutliersList() {
    const list = document.getElementById('outliers-list');
    if (!list) return;
    if (!APP_DATA.outliers || APP_DATA.outliers.length === 0) {
        list.innerHTML = '<div style="color:var(--text-faint);font-size:12px;text-align:center;padding:12px;">未检测到显著离群曲目</div>';
        return;
    }
    list.innerHTML = '';
    APP_DATA.outliers.forEach(o => {
        const item = document.createElement('div');
        item.className = 'od-item';
        item.dataset.index = o.track_index;
        item.innerHTML = `
            <div class="od-item-top">
                <span class="od-item-title">${escapeHtml(o.name)}</span>
                <span class="od-item-rank">#${o.rank}</span>
            </div>
            <div class="od-item-meta">${escapeHtml(o.artists)}</div>
            <div class="od-item-metrics">BPM ${o.bpm.toFixed(1)} · Energy ${o.energy.toFixed(3)}</div>
            <div class="od-item-reason">${escapeHtml(o.reason || '反常特征')}</div>
        `;
        item.addEventListener('click', () => {
            selectTrackByIndex(o.track_index);
        });
        list.appendChild(item);
    });
}

function selectTrackByIndex(trackIndex) {
    const ptIdx = APP_DATA.points.findIndex(p => p.indices.includes(trackIndex));
    if (ptIdx === -1) return;
    const pt = APP_DATA.points[ptIdx];
    const subIdx = pt.indices.indexOf(trackIndex);
    activePointTrackIndex = subIdx >= 0 ? subIdx : 0;
    const val = [pt.x, pt.y, pt.count, pt.year, pt.indices, pt.x, pt.y];
    selectPoint(val);
    myChart.dispatchAction({
        type: 'highlight',
        seriesName: 'Tracks',
        dataIndex: ptIdx
    });
}

function showOutliersPanel() {
    selectedPoint = null;
    document.getElementById('inspector-content').style.display = 'none';
    document.getElementById('inspector-empty').style.display = 'flex';
    myChart.dispatchAction({
        type: 'downplay',
        seriesName: 'Tracks'
    });
}

// Copy JSON
document.getElementById('btn-copy-raw').addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const code = document.getElementById('raw-json-code').textContent;
    if (code) {
        navigator.clipboard.writeText(code).then(() => {
            const toast = document.getElementById('toast');
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 1800);
        });
    }
});

// Event Listeners
myChart.on('click', function (params) {
    if (params.seriesType === 'scatter') {
        selectPoint(params.value);
    }
});

document.getElementById('search-input').addEventListener('input', function (e) {
    searchQuery = e.target.value;
    renderChart();
});

document.getElementById('color-select').addEventListener('change', function (e) {
    colorMode = e.target.value;
    renderChart();
});

document.getElementById('btn-reset').addEventListener('click', () => {
    myChart.dispatchAction({
        type: 'dataZoom',
        startValue: APP_DATA.axis.bpm[0],
        endValue: APP_DATA.axis.bpm[1],
        xAxisIndex: [0, 1]
    });
    myChart.dispatchAction({
        type: 'dataZoom',
        startValue: APP_DATA.axis.energy[0],
        endValue: APP_DATA.axis.energy[1],
        yAxisIndex: [0, 2]
    });
});

document.getElementById('btn-theme').addEventListener('click', () => {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    renderChart();
});

const btnBack = document.getElementById('btn-back-outliers');
if (btnBack) {
    btnBack.addEventListener('click', showOutliersPanel);
}

const btnOutliers = document.getElementById('btn-outliers');
if (btnOutliers) {
    btnOutliers.addEventListener('click', () => {
        showOutliersPanel();
        if (colorMode !== 'outlier') {
            colorMode = 'outlier';
            document.getElementById('color-select').value = 'outlier';
            renderChart();
        }
    });
}

window.addEventListener('resize', () => {
    myChart.resize();
});

// Initial Setup
renderOutliersList();
renderChart();
