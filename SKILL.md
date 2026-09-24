---
name: "gemini-watermark-remover-pro"
description: "Removes the Google Gemini/Veo bottom-right star watermark from videos AND images using Pure Reverse Alpha Blending. Image mode: lossless gain=1.0; Video mode: gain=1.0 + aspect-ratio-aware Lanczos4 upscaling + audio remux. Supports --auto-calibrate per-frame gain calibration for multi-segment stitched videos with inconsistent watermark strengths. Zero blurring, 100% texture preservation. Invoke when user wants to clean Gemini watermarks from any file."
---

# Gemini 无痕去水印与高保真超分技能 (gemini-watermark-remover-pro)

本技能用于自动化去除 Google Gemini / Veo 生成内容右下角的半透明四角星品牌水印，**同时支持图片与视频**，基于纯代数反向 Alpha 混合数学逆解体系（Pure Reverse Alpha Blending），无损还原底层纹理，零模糊、零涂抹。

## 适用场景 (When to Invoke)

- 用户提到“去除 Gemini 视频水印”、“把 Gemini 视频右下角星星去掉”、“清理视频水印”、“去除 Veo 水印”。
- 用户提到“去除 Gemini 图片水印”、“图片右下角星星去掉”、“清理图片水印”。
- 从 Gemini / Veo 下载了带水印的**图片（png/jpg/webp/bmp/tif）或视频（mp4）**，需要纯净素材用于后期。
- 用户要求去水印达到“纯图片级”高保真质感，杜绝任何毛玻璃模糊或漫水涂抹痕迹。
- 用户提到“视频是多段拼接的”、“去完还有残留”、“部分片段水印没去干净”、“水印忽深忽浅”——这类拼接视频需要 `--auto-calibrate` 逐帧校准。
- 视频模式可选 1080P 超分并保留音轨；图片模式按官方尺寸档位自动匹配 48/96px 水印。

## 核心算法原理

1. **纯代数反向 Alpha 无痕还原 (Pure Reverse Alpha Blending)**：
   - 内嵌 Google Gemini 官方标准 48×48 Alpha Map，直接采用逆代数混合公式单像素逐点逆解：
     $$I_{\text{original}} = \frac{I_{\text{watermarked}} - \alpha \times 255}{1 - \alpha}$$
   - **彻底剔除任何邻域漫水修补（Inpainting）**，100% 完整保留半透明遮罩下方的底层纹理、反光与颗粒噪点，**零毛玻璃糊斑、零涂抹痕迹**。
2. **增益适配（图片 vs 视频）**：
   - **图片（无色彩损耗，与官方 `blendModes.js` 图片引擎一致）**：`gain=1.0`，无损精确还原底层纹理。
   - **视频**：`gain=1.0`，完整的反向 Alpha 逆解，确保水印彻底消失；若遇 H.264 色度损耗导致的中心残白，可用 `--gain` 实测下调微调。
   - 均设 `ALPHA_NOISE_FLOOR=3/255` 过滤微小压缩噪声，`ALPHA_THRESHOLD=0.002` 门限激活。
3. **图片水印尺寸档位自动匹配**：
   - 依据官方 `geminiSizeCatalog.js`：最大边 ≥1600 → 96px 水印 + 64px 边距；其余 → 48px 水印 + 32px 边距。可用 `--logo-size`、`--margin` 覆盖。自动保留 PNG/WebP/TIFF 的 Alpha 通道。
4. **视频超分与音画重封装 (Video Only)**：
   - Lanczos4 按原视频宽高比智能超分至 1080P（短边=1080，保持原始比例：竖屏→1080×1920，横屏→1920×1080）；自动抽取原 AAC 音轨，H.264 CRF=18 保真压制，保留音画同步。
5. **跨平台环境自动静默补全**：
   - 智能优先调用系统 FFmpeg，缺失时全自动静默下载静态二进制，抹平 Windows / Mac 环境差异。

## 命令行快速调用

```bash
# 1. 图片去水印 (自动识别扩展名，默认无损 gain=1.0，输出 _clean.png)
python remove_watermark.py "gemini_image.png"

# 2. 视频去水印 (默认超分至 1080P，保留音轨)
python remove_watermark.py "gemini_video.mp4"

# 3. 视频保持原分辨率
python remove_watermark.py "gemini_video.mp4" --no-upscale

# 4. 指定图片水印尺寸/边距 (自动档位失效时手动指定)
python remove_watermark.py "img.png" --logo-size 96 --margin 64

# 5. 指定输出路径与增益
python remove_watermark.py "input.png" -o out.png --gain 1.0

# 6. 多段拼接视频逐帧自动校准 (各片段水印强度不一致时必用)
python remove_watermark.py "stitched_video.mp4" --no-upscale --auto-calibrate

# 7. 校准采样步长调整 (默认每 2 帧校准 1 帧; 越小越精确越慢)
python remove_watermark.py "stitched_video.mp4" --auto-calibrate --calibrate-step 1
```

脚本会自动根据输入文件扩展名分流：图片扩展名（png/jpg/jpeg/webp/bmp/tif/tiff/jfif/gif）走图片引擎，其余按视频引擎处理。

## 经验与常见问题 (Lessons Learned)

以下教训来自真实生产（横屏/竖屏视频实测去水印）总结，改动代码前必读：

### 1. 横屏视频超分必须保持宽高比
- 早期把目标尺寸**写死** `1080×1920`（竖屏），横屏 1920×1080 会被压扁/拉伸成竖屏，比例全歪。
- ✅ 正确：按**短边=1080**、保持原始宽高比计算目标尺寸，并确保结果为偶数像素（H.264/yuv420p 硬性要求）。
- 验证：`1920×1080→1920×1080`，`720×1280→1080×1920`，`1440×1080→1440×1080`。

### 2. 水印 ROI 定位要用「短边统一缩放 + 右下角锚定」
- 早期按竖屏基准 `720×1280` 的**绝对坐标 (576,1136)** 对宽高做**两套缩放系数**，横屏时宽(h)比例与高比例不同，方形水印被压成 `85×27` 的扁条且位置漂移，完全对不上。
- ✅ 正确：水印是**方形**、锚定**右下角**，用一个 `scale = min(w,h)/720` 统一缩放（720 边基准 logo=48px、边距=96px）。
- 验证：横屏 1280×720 → ROI(1136,576,48,48)，竖屏 720×1280 → ROI(576,1136,48,48)，均正确。

### 3. 视频增益默认 1.0，过低只减淡不消失
- 早期视频 `gain=0.58`（为平衡中心残白/边缘暗环），但实测水印只被**减淡**、肉眼仍清晰（模板匹配去偏相关 0.94→0.84，几乎没动）。
- ✅ 正确：视频与图片一致用 `gain=1.0` 完整反向 Alpha 逆解，水印彻底消失（相关降到 0.61，残留仅为暗背景散在纹理）。若个别片段出现"中心残白"，再用 `--gain` 下调微调。

### 4. 验证去水印效果用「模板匹配去偏相关」
- 不要只肉眼/只看单帧亮度对比（半透明+暗背景场景下会产生误判）。
- ✅ 方法：把内嵌的 48×48 Alpha 星形模板 resize 到**与成片水印相同尺寸**（720p→48px，1080p→72px），在右下半区滑窗计算去偏相关系数，分数越低越干净。

### 5. 模板尺寸必须匹配目标分辨率
- 用 48px 模板去匹配已超分到 1080p（水印 72px）的帧会得到错误结果，务必先把模板按比例 resize 到水印实际像素尺寸再匹配。

### 6. 多段拼接视频：不同片段水印有效强度不一致，必须逐帧（分段）校准增益
- **现象**（2025-09 两案例实战）：Gemini 多段拼接的视频里，不同片段来自不同生成批次，H.264 有损编码程度不同，同一颗星星的实际不透明度每段都不同；用统一 `gain=1.0` 处理，部分片段会出现明显残留，另一部分却偏暗。
- **根因**：水印叠加发生在各段生成时，拼接后无法用一个增益适配全部片段。
- ✅ 正确：用 `--auto-calibrate` 逐帧自动校准。原理：对每个采样帧在增益网格 0.30~0.86（步长0.05）上模拟去水印，计算「星形高alpha台地」与「低alpha环带」的亮度差 delta，对 delta(g) 线性拟合解 `delta=+3`（轻微偏亮、肉眼不可见，宁可偏亮不可偏暗成鬼影）。
- **可靠帧过滤**：仅当 `(255-背景).min() > 60`（环带有足够暗度）时读数才可信；亮背景帧自动跳过并沿用附近可靠帧增益。
- **绝不做跨帧中值/均值平滑**：转场/拼接缝的相邻帧增益差异极大，平滑会把对的改错。

### 7. 亮背景帧的 delta 验证假阳性：改用高通结构残差判别
- **现象**：逐帧校准后用 `delta = mean(台地) - mean(环带) > 8` 扫残留，亮背景段 130/480 帧被标白"残留"，但肉眼与对比图均干净。
- **根因**：亮背景接近 255 时，源视频编码阶段就发生高光截断（信息永久丢失），反解后天台区天然偏亮——这是**平滑的亮度抬升**，不是星形锐利残留。
- ✅ 正确：用**高通结构残差**判别真伪残留：`hp = gray - GaussianBlur(gray, 31)`，比较台地与环带的 `mean(|hp|)` 差。真水印残留是锐利星形结构（差值 > 2.0），平滑亮度梯度差值 ≈ 0。实测同一视频：人工验收版 16 帧结构残留，逐帧校准版仅 4 帧。
- **通用原则**：验证指标必须区分背景亮度选用；delta 类指标只适合暗背景帧。

### 8. 实测效果：逐帧校准优于人工调参
- 对同一拼接视频：恒定增益 0.604 版（人工验收）在可靠帧上 delta 均值 -7.34（轻微暗鬼影），逐帧校准版 +3.44（正中目标）；高通结构残差 0.327 vs 0.070。
- 结论：`--auto-calibrate` 应作为拼接视频的默认推荐；单段短视频无需开启（gain=1.0 即可）。

## 读者公众号技术分享建议

1. **痛点切入**：Gemini 生成的内容动作自然逼真，但右下角星星水印影响商用质感；剪映等常规涂抹工具会导致画面边缘模糊变形。
2. **技术亮点**：图片去水印不靠“猜测填补”，而是用数学上精确的反向 Alpha 混合逆解（$original = \frac{watermarked - \alpha \times 255}{1 - \alpha}$），把透明星形底下的真实纹理逐像素“提”回来，图片/视频全程零模糊。
3. **开箱即用**：同一套脚本既可处理图片又可处理视频，Windows 下把文件拖到 `run_windows.bat` 上即可一键完成。