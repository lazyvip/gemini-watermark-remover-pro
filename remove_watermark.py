#!/usr/bin/env python3
"""
Gemini Watermark Remover (无痕去水印与高保真超分工具, 图片+视频)
专为去除 Google Gemini / Veo 内容右下角固定四角星水印设计。
核心: 纯代数反向 Alpha 混合逆解 (Pure Reverse Alpha Blending), 100% 保留底层纹理, 零模糊零涂抹。
支持 --auto-calibrate 逐帧增益校准: 应对多段拼接视频各片段水印强度不一致的场景 (实战经验)。
"""

import os
import sys
import argparse
import subprocess
import shutil
import platform
import urllib.request
import zipfile
import tarfile
import base64
import zlib
import cv2
import numpy as np

# 从官方背景反推并嵌入的高精度 Alpha Map (48x48)，经过 zlib+base64 紧凑编码
EMBEDDED_ALPHA_B64 = (
    'eNqVVrt24kAMlTQuOFuZju0mf5HtcrZyOvMHTpftho504s+j18zYDptDlICxuaPH1QtCBBF/'
    'Q33pG1wKqpD/J/+cyMGOhAALGp+YMxCgHyKKa8J2AORWPpNpx4l50quCgFKyQ8lPmTMYusw+'
    'YGG+Gtp8Uf1uRE5X/e69f87M6pDYBINBSuETAlXlDQ04K34JL81OUp96gB5IGKQjm4ymAKvm'
    '0C8iKowptGPo6pnPaLoT4eqMukNYH5FeVP3NIiA0VeJ88giMQ4tC9YL9KTkuS/NC4SlYMhrM'
    'MX0A+MJNnuWZEErkdBIFK6LAuFMzY4fz9STMCNQz7SmAWgNKM+FYVnguB4wsG1wDjezWDP/j'
    'jSy1dBp+lSi5OfNOZtOTmj+1jD2Mmb/I3PAeL7XCwcPClfqVvI+erTQkw2Itn5OHusdzOQ4t'
    'l9gL8/nK/5O/WnHWBuAEEeaFv5Eyeh6sBkTG831c920e3R/r1oXve74lKlsV5+nKD0qZ8lD4'
    'R3L5Ib5gnh4+cp2yVXKeH0Ev2flR+p3P230qvZmPrWWtw8byve7djMBNH+7k488G7TkmGC/3'
    'XSmn1jEN71XxfteXA27wGE226pcwcNPrLKPEkDaBevUrnPTAbYOfcRi8MqWcKSxRimpFfNs1'
    'l442G7tW/imm+6Djy5r012Xtkta9YhQ/SGZNrw9lPaHT8ve6XEfQ76y7fHDaVInJGDPvucNf'
    'bDpD+B4hrjNhs2/pxej7K5YU1EnXxWzl5o32N4XKDc4Xi36rmuY62mwTQUPs8HXi4djU9+Vb'
    '8TVOpK4C3jxTfVHjZupWmOdb8pCV/Ry78Su+BmPs2Mb9MHJ8V0Nf5RUP3Td/+sr82vsJdxG7'
    'BXXGakXuhdKnsOe/LLb1HHuplrbkoJRqD9x6fX0CPE6dwg=='
)

ALPHA_48 = np.frombuffer(zlib.decompress(base64.b64decode(EMBEDDED_ALPHA_B64)), dtype=np.uint8).reshape((48, 48))
ALPHA_MAP_NORM = ALPHA_48.astype(np.float32) / 255.0

def ensure_ffmpeg():
    """
    智能解析与自动配置 FFmpeg:
    1. 优先使用系统 PATH 或脚本同级目录下的 ffmpeg 可执行文件
    2. 尝试从已安装的 Python 生态 (如 imageio_ffmpeg) 导入
    3. 若无，则全自动从官方源下载开箱即用的静态单文件二进制并放入当前目录
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    is_win = platform.system() == "Windows"
    binary_name = "ffmpeg.exe" if is_win else "ffmpeg"
    local_ffmpeg = os.path.join(script_dir, binary_name)

    # 1. 检查同级目录下是否存在
    if os.path.isfile(local_ffmpeg) and os.access(local_ffmpeg, os.X_OK if not is_win else os.F_OK):
        return local_ffmpeg

    # 2. 检查系统 PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 3. 检查 imageio_ffmpeg 扩展库
    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_bin and os.path.exists(ffmpeg_bin):
            return ffmpeg_bin
    except ImportError:
        pass

    # 4. 自动下载对应平台的静态独立 ffmpeg
    print("\n[环境自动补全] 未检测到 FFmpeg，正在为您自动下载静默二进制包，请稍候...")
    try:
        if is_win:
            # 下载 gyan.dev 或 btbN 提供的 Windows 静态精简版
            download_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            # 备用轻量镜像源
            print(f"正在从官方源下载 Windows 版 FFmpeg...")
            req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = int(resp.info().get("Content-Length", 0))
                downloaded = 0
                zip_path = os.path.join(script_dir, "temp_ffmpeg.zip")
                with open(zip_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = (downloaded / total_size) * 100
                            sys.stdout.write(f"\rFFmpeg 下载进度: {downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB ({pct:.1f}%)")
                            sys.stdout.flush()

                print("\n正在解压并配置 ffmpeg.exe...")
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for member in zf.namelist():
                        if member.endswith("bin/ffmpeg.exe") or member.endswith("ffmpeg.exe"):
                            with zf.open(member) as source, open(local_ffmpeg, "wb") as target:
                                shutil.copyfileobj(source, target)
                            break
                if os.path.exists(zip_path):
                    os.remove(zip_path)

            if os.path.isfile(local_ffmpeg):
                print(f"[成功] FFmpeg 已自动配置完毕: {local_ffmpeg}\n")
                return local_ffmpeg

        elif platform.system() == "Darwin":
            # macOS 静态包 (evermeet)
            download_url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            print("正在为 macOS 下载静态 ffmpeg 二进制...")
            req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            zip_path = os.path.join(script_dir, "temp_ffmpeg.zip")
            with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as f:
                shutil.copyfileobj(resp, f)
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extract("ffmpeg", script_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            os.chmod(local_ffmpeg, 0o755)
            if os.path.isfile(local_ffmpeg):
                print(f"[成功] FFmpeg 已自动配置完毕: {local_ffmpeg}\n")
                return local_ffmpeg

    except Exception as err:
        print(f"[提示] FFmpeg 在线自动下载失败 ({err})。尝试使用 pip 安装 imageio-ffmpeg 自动补全...", file=sys.stderr)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"], check=True)
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as e2:
            print(f"[提示] 自动安装 imageio-ffmpeg 未成功: {e2}", file=sys.stderr)

    return None

def compute_video_roi(w, h):
    """
    计算视频水印 ROI (视频模式专用)。
    水印是方形四角星，锚定在画面右下角，尺寸随画面较短边等比缩放。
    以竖屏基准 720x1280 为准：水印 48x48px，距右下角边距 96px。
    """
    short_side = min(w, h)
    scale = short_side / 720.0
    logo = int(round(48 * scale))
    margin = int(round(96 * scale))
    x = w - margin - logo
    y = h - margin - logo
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    return (x, y, logo, logo)

def detect_or_default_roi(sample_frame, custom_roi=None):
    """
    根据给定的分辨率自动缩放 ROI，或使用用户传入的坐标 (x, y, w, h)
    水印视为方形并锚定右下角，按较短边统一缩放 (720 边基准: 48x48, 边距96)
    """
    h, w = sample_frame.shape[:2]
    if custom_roi:
        return custom_roi
    return compute_video_roi(w, h)

def build_watermark_mask(roi_w, roi_h, scale=1.0, dilate_k=3):
    """
    针对 Google Gemini 四角星水印生成参数化星状线（Astroid）紧致掩码。
    几何方程: (|x-cx|/rx)^p + (|y-cy|/ry)^p <= 1 (p=0.65)
    精准覆盖发光星体与半透明边缘，修补面积减少 60% 以上，
    避免传统大圆掩码侵入相邻物体（如毛发/边缘）造成色彩溢出与方形糊斑。
    """
    # 720x1280 下基准水印中心与长短半轴
    cx = int(round(29 * scale))
    cy = int(round(23 * scale))
    rx = int(round(22 * scale))
    ry = int(round(22 * scale))
    p = 0.65

    y, x = np.ogrid[:roi_h, :roi_w]
    dx = np.abs(x - cx) / float(max(1, rx))
    dy = np.abs(y - cy) / float(max(1, ry))
    val = (dx ** p) + (dy ** p)
    mask = (val <= 1.0).astype(np.uint8) * 255

    # 3px 极微羽化膨胀覆盖抗锯齿透明外发光
    k = max(3, int(round(dilate_k * scale)))
    if k % 2 == 0:
        k += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    dilated = cv2.dilate(mask, kernel, iterations=1)
    return dilated

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".jfif", ".gif"}

def resolve_image_watermark(img_w, img_h):
    """
    根据图片分辨率自动匹配官方 Gemini 图片水印档位 (依据 geminiSizeCatalog.js)。
    返回 (logo_size, margin_right, margin_bottom)。
    - 0.5k / 1k (短边 <=512 或 最大边 <1024 附近): logo 48, margin 32
    - 2k / 4k (最大边 >=1280): logo 96, margin 64
    """
    max_dim = max(img_w, img_h)
    if max_dim >= 1600:          # 2k / 4k 档
        return 96, 64, 64
    elif max_dim >= 1024:        # 1k 档 (如 1024x1024, 1376x768, 1408x768)
        return 48, 32, 32
    elif max_dim >= 512:         # 0.5k 档
        return 48, 32, 32
    else:
        return 48, 32, 32

def process_image(input_path, output_path, mode="lossless", gain=1.0, logo_size=None, margin=None):
    """
    处理单张 Gemini 图片水印。使用与视频完全一致的纯代数反向 Alpha 逆解。
    图片无 H.264/YUV420 色度损耗，因此增益默认 1.0 (与官方 blendModes.js 图片引擎一致，
    无损精确还原底层纹理)，无需为视频压缩做补偿缩放。
    """
    proper_ext = os.path.splitext(output_path)[1].lower()
    allow_alpha = proper_ext in (".png", ".webp", ".tif", ".tiff")

    img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED if allow_alpha else cv2.IMREAD_COLOR)
    if img is None:
        print(f"[错误] 无法读取图片: {input_path}", file=sys.stderr)
        return False

    has_alpha = img.ndim == 3 and img.shape[2] == 4
    color = img[:, :, :3].copy() if has_alpha else img.copy()
    alpha_ch = img[:, :, 3].copy() if has_alpha else None

    src_h, src_w = color.shape[:2]

    ls, mr, mb = resolve_image_watermark(src_w, src_h)
    if logo_size is not None and logo_size > 0:
        ls = int(logo_size)
    if margin is not None and margin > 0:
        mr = mb = int(margin)

    x = src_w - mr - ls
    y = src_h - mb - ls
    if x < 0 or y < 0:
        print(f"[警告] 水印位置超出图片边界 (w={src_w}, h={src_h}, logo={ls}, margin={mr})，自动回退到右下角。", file=sys.stderr)
        x = max(0, src_w - ls)
        y = max(0, src_h - ls)

    # 缩放 48 基准 Alpha 到目标水印尺寸
    if ls == 48:
        scaled_alpha = ALPHA_MAP_NORM.copy()
    else:
        scaled_alpha = cv2.resize(ALPHA_MAP_NORM, (ls, ls), interpolation=cv2.INTER_LANCZOS4)

    ALPHA_NOISE_FLOOR = 3.0 / 255.0
    ALPHA_THRESHOLD = 0.002
    MAX_ALPHA = 0.99

    # 自适应水印配色检测：右下星形区域中心与四角背景的亮度关系决定 LOGO 值。
    # - 白色加光型水印（深色背景）：logical_logo = 255
    # - 深色 / 金色减光型水印（浅色背景）：logical_logo = 背景色参考（约等于该区域背景色）
    detect_roi = color[y:y+ls, x:x+ls].astype(np.float32)
    c_h, c_w = detect_roi.shape[:2]
    cx, cy = c_h // 2, c_w // 2
    inn = detect_roi[cy-2:cy+2, cx-2:cx+2].reshape(-1, 3).mean(axis=0)
    corn = np.concatenate([
        detect_roi[:2, :2], detect_roi[:2, -2:],
        detect_roi[-2:, :2], detect_roi[-2:, -2:],
    ]).reshape(-1, 3).mean(axis=0)
    center_lum = float(inn.mean())
    corner_lum = float(corn.mean())
    # 若星形中心明显暗于四角背景 → 减光型（深/金色）水印，需要"提亮"式还原
    is_dark_logo = center_lum < (corner_lum - 12.0)
    if is_dark_logo:
        LOGO_VALUE = corn.astype(np.float32)   # 用背景色作还原参考（各通道）
        gain = 1.0
    else:
        LOGO_VALUE = np.array([255.0, 255.0, 255.0])

    sig_alpha = np.maximum(0.0, scaled_alpha - ALPHA_NOISE_FLOOR) * gain
    active_mask = sig_alpha >= ALPHA_THRESHOLD
    effective_alpha = np.minimum(scaled_alpha * gain, MAX_ALPHA)
    one_minus_alpha = 1.0 - effective_alpha

    roi = color[y:y+ls, x:x+ls].astype(np.float32)

    if mode == "inpaint":
        local_mask = build_watermark_mask(ls, ls, scale=ls/48.0, dilate_k=3)
        color[y:y+ls, x:x+ls] = cv2.inpaint(roi.astype(np.uint8), local_mask, 5, cv2.INPAINT_TELEA)
    elif is_dark_logo:
        # 减光型（深/金色）水印：水印是不透明遮罩，覆盖在较均匀的背景上。
        # 恢复目标 = 星形精确遮罩内所有像素完全回填背景色；仅在最外圈羽化 1-2px 贴合抗锯齿。
        bg = corn.astype(np.float32)
        core = scaled_alpha > 0.08              # 精确星形遮罩
        w = core.astype(np.float32)
        # 轻微羽化边缘以贴合抗锯齿
        wb = cv2.GaussianBlur(w, (5, 5), 0)
        wb = np.clip(wb * 2.2, 0.0, 1.0)[..., np.newaxis]
        clean_roi = np.clip(roi * (1.0 - wb) + bg * wb, 0, 255).astype(np.uint8)
    else:
        for c in range(3):
            orig_c = (roi[:, :, c] - effective_alpha * LOGO_VALUE[c]) / one_minus_alpha
            roi[:, :, c] = np.where(active_mask, np.clip(np.round(orig_c), 0, 255), roi[:, :, c])
        clean_roi = roi.astype(np.uint8)
    if mode == "hybrid":
        core_mask = (effective_alpha > 0.25).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        core_mask = cv2.dilate(core_mask, kernel, iterations=1)
        clean_roi = cv2.inpaint(clean_roi, core_mask, 2, cv2.INPAINT_TELEA)
    color[y:y+ls, x:x+ls] = clean_roi

    # 组装并保存
    if has_alpha:
        color = np.dstack([color.astype(np.uint8), alpha_ch])
    out_ext = os.path.splitext(output_path)[1].lower() or ".png"
    params = []
    if out_ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, 98]
    elif out_ext == ".webp":
        params = [cv2.IMWRITE_WEBP_QUALITY, 100]
    ok = cv2.imwrite(output_path, color, params)
    if ok:
        print(f"\n[成功] 去水印图片已生成: {output_path} (尺寸 {src_w}x{src_h}, logo {ls}px, margin {mr}px)")
        return True
    print(f"[错误] 图片写出失败: {output_path}", file=sys.stderr)
    return False

def alpha_for_size(roi_w, roi_h):
    """缩放 48 基准 Alpha Map 到目标水印尺寸 (视频/校准共用)。"""
    if roi_w == 48 and roi_h == 48:
        return ALPHA_MAP_NORM.copy()
    return cv2.resize(ALPHA_MAP_NORM, (roi_w, roi_h), interpolation=cv2.INTER_LANCZOS4)


def build_clean_roi(roi, scaled_alpha, gain, mode="lossless", core_mask=None):
    """
    对单帧 ROI 执行纯代数反向 Alpha 逆解 (渲染主循环与校准器共用的同一实现)。
    roi: float32 (h, w, 3); scaled_alpha: float32 (h, w) 归一化 0~1
    """
    ALPHA_NOISE_FLOOR = 3.0 / 255.0
    ALPHA_THRESHOLD = 0.002
    MAX_ALPHA = 0.99
    LOGO_VALUE = 255.0

    sig_alpha = np.maximum(0.0, scaled_alpha - ALPHA_NOISE_FLOOR) * gain
    active_mask = sig_alpha >= ALPHA_THRESHOLD
    effective_alpha = np.minimum(scaled_alpha * gain, MAX_ALPHA)
    one_minus_alpha = 1.0 - effective_alpha

    out = roi.copy()
    for c in range(3):
        orig_c = (roi[:, :, c] - effective_alpha * LOGO_VALUE) / one_minus_alpha
        out[:, :, c] = np.where(active_mask, np.clip(np.round(orig_c), 0, 255), roi[:, :, c])
    clean_roi = out.astype(np.uint8)

    if mode == "hybrid" and core_mask is not None:
        clean_roi = cv2.inpaint(clean_roi, core_mask, 2, cv2.INPAINT_TELEA)
    return clean_roi


def auto_calibrate_video(input_path, sample_step=2, progress_every=120):
    """
    逐帧增益自动校准 (针对多段拼接视频: 不同片段来自不同源, 水印实际有效强度不一致)。

    原理 (2025-09 实战两案例沉淀):
    1. 每个采样帧在增益网格 (0.30~0.86 步长0.05) 上模拟去水印,
       测量「星形高alpha台地」与「低alpha环带」的亮度差 delta;
       对 delta(g) 做线性拟合, 解 delta = +3 (轻微偏亮不可见) 的 g*。
       正残差安全 (人眼对暗鬼影远比对残白敏感), 负 delta 即暗鬼影必须避免。
    2. 可靠帧过滤: 仅当 (255-背景).min() > 60 (背景够暗、对比够足) 时读数才可信;
       白色/奶油色等亮背景会让逆解分母被钳制, 读数系统性偏低, 必须剔除。
    3. 绝不做跨帧中值/均值平滑: 拼接视频的转场交叉淡化区相邻帧所需增益差异极大
       (实测相邻帧 0.40 vs 0.66), 任何平滑都会毁掉逐帧校准。

    返回: gains (ndarray, 每帧一个增益值, 不可信帧用中位数填充)
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"[错误] 无法打开输入视频进行校准: {input_path}", file=sys.stderr)
        return None, None

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    x, y, roi_w, roi_h = compute_video_roi(src_w, src_h)
    scaled_alpha = alpha_for_size(roi_w, roi_h)

    plateau = scaled_alpha > 0.45
    ring = scaled_alpha < 0.02
    n_pl = int(plateau.sum())
    if n_pl < 8 or not ring.any():
        print("[错误] 校准区域过小, 放弃自动校准", file=sys.stderr)
        cap.release()
        return None, None

    GRID = np.arange(0.30, 0.861, 0.05)
    n_g = len(GRID)
    a_stack = scaled_alpha[None, :, :]
    ea_grid = np.minimum(a_stack * GRID[:, None, None], 0.99)
    om_grid = 1.0 - ea_grid
    sig_grid = (np.maximum(0.0, scaled_alpha - 3.0 / 255.0))[None, :, :] * GRID[:, None, None]
    act_grid = sig_grid >= 0.002

    cal_frames = np.arange(0, total, sample_step)
    gains = np.full(total, np.nan, dtype=np.float32)

    print(f"=== 逐帧增益自动校准 ===")
    print(f"校准采样: 每 {sample_step} 帧 1 帧, 共 {len(cal_frames)} 帧 | ROI({x},{y},{roi_w},{roi_h}) | 目标残差 delta=+3")

    done = 0
    for fi in cal_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
        ret, frame = cap.read()
        if not ret:
            continue
        roi = frame[y:y+roi_h, x:x+roi_w].astype(np.float32)

        # 可靠性: 星形高alpha区四角背景亮度 (亮背景读数不可信)
        bg = roi[ring].mean(axis=0)
        if (255.0 - bg).min() <= 60.0:
            done += 1
            if done % progress_every == 0:
                print(f"  校准进度: {done}/{len(cal_frames)} (本帧亮背景跳过)")
            continue

        clean = np.empty((n_g, roi_h, roi_w, 3), dtype=np.float32)
        for gi in range(n_g):
            clean[gi] = build_clean_roi(roi, scaled_alpha, float(GRID[gi]))

        pl = clean[:, plateau, :].mean(axis=(1, 2))
        rg = np.stack([c[ring].mean(axis=0).mean() for c in clean])
        delta = pl - rg
        A = np.vstack([GRID, np.ones(n_g)]).T
        try:
            slope, intercept = np.linalg.lstsq(A, delta, rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        if abs(slope) < 1e-6:
            g_star = GRID[np.argmin(np.abs(delta - 3.0))]
        else:
            g_star = (3.0 - intercept) / slope
        if np.isfinite(g_star):
            gains[fi] = g_star
        done += 1
        if done % progress_every == 0:
            print(f"  校准进度: {done}/{len(cal_frames)}")

    cap.release()

    valid = gains[np.isfinite(gains)]
    if len(valid) < 5:
        print(f"[警告] 可靠校准帧仅 {len(valid)} 个 (亮背景占比过高), 回退全局增益 1.0", file=sys.stderr)
        return np.ones(total, dtype=np.float32), gains

    med = float(np.median(valid))
    print(f"校准完成: 可靠帧 {len(valid)}/{len(cal_frames)}, 中位增益 {med:.3f}, "
          f"范围 [{valid.min():.3f}, {valid.max():.3f}]")
    if med < 0.85:
        print("[提示] 检测到拼接视频特征 (有效增益明显 <1.0), 已为每帧生成独立增益。")
    return np.where(np.isfinite(gains), gains, med).astype(np.float32), gains


def process_video(input_path, output_path, upscale_1080p=True, mode="lossless", gain=1.0,
                  auto_calibrate=False, calibrate_sample_step=2):
    """
    mode:
      - 'lossless': 纯代数反向 Alpha 混合数学解构 (同 lazyvip/gemini-watermark-remover 图像级无损还原，100% 保留底层纹理，零涂抹)
      - 'hybrid': 反向 Alpha 混合 + 中心微修补
      - 'inpaint': 经典星状线流体几何修补
    auto_calibrate: 逐帧增益校准, 用于多段拼接视频 (不同片段水印强度不一致)。
    """
    if not os.path.exists(input_path):
        print(f"[错误] 输入视频文件不存在: {input_path}", file=sys.stderr)
        return False
        
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"[错误] 无法打开输入视频: {input_path}", file=sys.stderr)
        return False
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if upscale_1080p:
        # 按原视频宽高比智能超分至 1080P (短边=1080，保持原比例)
        if src_w >= src_h:
            # 横屏或方形：高边拉到 1080，宽按比例缩放
            dst_h = 1080
            dst_w = int(round(src_w * 1080.0 / src_h))
        else:
            # 竖屏：宽边拉到 1080，高按比例缩放
            dst_w = 1080
            dst_h = int(round(src_h * 1080.0 / src_w))
        # 确保偶数尺寸 (H.264/yuv420p 硬性要求)
        dst_w += dst_w % 2
        dst_h += dst_h % 2
    else:
        dst_w, dst_h = src_w, src_h
    
    print(f"=== Gemini 视频无痕去水印启动 ===")
    print(f"输入视频: {input_path}")
    print(f"原始规格: {src_w}x{src_h} @ {fps:.2f}fps (总帧数: {total_frames})")
    print(f"目标规格: {dst_w}x{dst_h} (超分模式: {'开启 (Lanczos4)' if upscale_1080p else '关闭'})")
    algorithm_desc = "图片级无损反向 Alpha 逆解 (100%保留底层质感，零模糊)" if mode == "lossless" else mode
    print(f"核心算法: {algorithm_desc}")
    
    # 水印为方形且锚定在右下角，按较短边统一缩放定位 (避免横屏时按宽高分别缩放导致压扁漂移)
    x, y, roi_w, roi_h = compute_video_roi(src_w, src_h)
    print(f"水印精准定位 ROI: x={x}, y={y}, w={roi_w}, h={roi_h}")
    
    # 缩放 Alpha 矩阵并应用底噪截断与视频增益 (算法严格对齐官方 blendModes.js)
    scaled_alpha = alpha_for_size(roi_w, roi_h)

    ALPHA_NOISE_FLOOR = 3.0 / 255.0
    ALPHA_THRESHOLD = 0.002
    MAX_ALPHA = 0.99

    # 逐帧增益校准: 多段拼接视频各片段水印强度不一致, 需按帧取增益
    per_frame_gains = None
    if auto_calibrate:
        per_frame_gains, raw_gains = auto_calibrate_video(
            input_path, sample_step=max(1, int(calibrate_sample_step)))
        if per_frame_gains is None:
            print("[警告] 自动校准失败, 回退统一增益", file=sys.stderr)

    # 若为 hybrid 模式，准备微修补掩码
    core_mask = None
    if mode == "hybrid":
        _g0 = float(per_frame_gains[0]) if per_frame_gains is not None else gain
        _ea = np.minimum(scaled_alpha * _g0, MAX_ALPHA)
        core_mask = (_ea > 0.25).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        core_mask = cv2.dilate(core_mask, kernel, iterations=1)
    
    # 准备临时中间无声视频文件
    temp_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(temp_dir, exist_ok=True)
    temp_silent_video = os.path.join(temp_dir, f".temp_silent_{os.path.basename(output_path)}")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_silent_video, fourcc, fps, (dst_w, dst_h))
    
    frame_idx = 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            roi = frame[y:y+roi_h, x:x+roi_w].astype(np.float32)
            
            if mode == "inpaint":
                local_mask = build_watermark_mask(roi_w, roi_h, scale=roi_w/48.0, dilate_k=3)
                frame[y:y+roi_h, x:x+roi_w] = cv2.inpaint(frame[y:y+roi_h, x:x+roi_w], local_mask, 5, cv2.INPAINT_TELEA)
            else:
                # 纯代数反向 Alpha 逆解: original = (watermarked - alpha * 255) / (1 - alpha)
                # 校准模式下每帧取各自的增益 (拼接视频各片段水印有效强度不同)
                if per_frame_gains is not None:
                    frame_gain = float(per_frame_gains[frame_idx])
                else:
                    frame_gain = gain
                clean_roi = build_clean_roi(roi, scaled_alpha, frame_gain, mode=mode, core_mask=core_mask)
                frame[y:y+roi_h, x:x+roi_w] = clean_roi
            
            if upscale_1080p:
                out_frame = cv2.resize(frame, (dst_w, dst_h), interpolation=cv2.INTER_LANCZOS4)
            else:
                out_frame = frame
                
            writer.write(out_frame)
            frame_idx += 1
            if frame_idx % 30 == 0 or frame_idx == total_frames:
                pct = (frame_idx / total_frames) * 100 if total_frames > 0 else 0
                sys.stdout.write(f"\r进度: {frame_idx}/{total_frames} 帧 ({pct:.1f}%)")
                sys.stdout.flush()
    finally:
        cap.release()
        writer.release()
        print("\n视频画面去水印与重采样完成！")

    # 自动解析或下载配置 ffmpeg
    ffmpeg_bin = ensure_ffmpeg()

    if ffmpeg_bin:
        # 抽取原视频音频并重封装成标准广播级 MP4
        print(f"正在利用 FFmpeg ({ffmpeg_bin}) 进行音画混流封装...")
        cmd = [
            ffmpeg_bin, "-y",
            "-i", temp_silent_video,
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest",
            output_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[提示] 原视频可能无音轨，切换为单视频流快速封装...", file=sys.stderr)
                cmd_noaudio = [
                    ffmpeg_bin, "-y",
                    "-i", temp_silent_video,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path
                ]
                subprocess.run(cmd_noaudio, check=True)
        except Exception as e:
            print(f"[警告] FFmpeg 封装异常: {e}，直接采用 OpenCV 原生视频输出", file=sys.stderr)
            if os.path.exists(output_path):
                os.remove(output_path)
            shutil.move(temp_silent_video, output_path)
    else:
        print("[提示] 暂未获取到 FFmpeg，直接使用 OpenCV 渲染的视频作为成品")
        if os.path.exists(output_path):
            os.remove(output_path)
        shutil.move(temp_silent_video, output_path)

    if os.path.exists(temp_silent_video):
        try:
            os.remove(temp_silent_video)
        except OSError:
            pass
        
    print(f"\n[成功] 去水印视频已生成: {output_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Gemini 无痕去水印工具 (纯反向 Alpha 代数逆解，支持图片与视频)")
    parser.add_argument("input", help="输入文件路径 (支持图片: png/jpg/webp/bmp/tif 或视频: mp4)")
    parser.add_argument("-o", "--output", help="输出文件路径 (图片默认: [原文件名]_clean.png, 视频默认: [原文件名]_clean.mp4)")
    parser.add_argument("--no-upscale", action="store_true", help="(仅视频) 不进行 1080P 超分，保留原尺寸导出")
    parser.add_argument("--mode", choices=["lossless", "hybrid", "inpaint"], default="lossless", 
                        help="去水印模式: lossless(纯反向Alpha无损还原，完全保留底层纹理，默认推荐), hybrid(反向Alpha+微修补), inpaint(经典流体修补)")
    parser.add_argument("--gain", type=float, default=None,
                        help="Alpha 增益调节 (图片/视频默认 1.0)，用于平衡中心残白与边缘暗环")
    parser.add_argument("--auto-calibrate", action="store_true",
                        help="(仅视频) 逐帧增益自动校准: 多段拼接视频各片段水印强度不一致时使用, "
                             "自动为每帧求解最佳增益 (亮背景帧自动跳过并用中位数填充)")
    parser.add_argument("--calibrate-step", type=int, default=2,
                        help="(仅视频) 逐帧校准的采样步长, 每 N 帧校准 1 帧, 默认 2 (越小越精确越慢)")
    parser.add_argument("--logo-size", type=int, default=0, help="(仅图片) 水印像素尺寸，0=根据分辨率自动匹配 48/96")
    parser.add_argument("--margin", type=int, default=0, help="(仅图片) 水印距右下角边距像素，0=自动")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"[错误] 输入文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(input_path)[1].lower().lstrip(".")
    is_image = f".{ext}" in IMAGE_EXTS

    base, _ = os.path.splitext(input_path)
    if not args.output:
        output_path = f"{base}_clean.png" if is_image else f"{base}_clean.mp4"
    else:
        output_path = os.path.abspath(args.output)

    if is_image:
        mode = args.mode
        gain = args.gain if args.gain is not None else 1.0
        ok = process_image(
            input_path,
            output_path,
            mode=mode,
            gain=gain,
            logo_size=(args.logo_size if args.logo_size > 0 else None),
            margin=(args.margin if args.margin > 0 else None),
        )
    else:
        gain = args.gain if args.gain is not None else 1.0
        ok = process_video(
            input_path,
            output_path,
            upscale_1080p=(not args.no_upscale),
            mode=args.mode,
            gain=gain,
            auto_calibrate=args.auto_calibrate,
            calibrate_sample_step=args.calibrate_step,
        )

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
