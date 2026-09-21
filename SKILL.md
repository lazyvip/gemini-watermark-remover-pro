---
name: "gemini-watermark-remover-pro"
description: "Removes the Google Gemini/Veo bottom-right star watermark from videos AND images using Pure Reverse Alpha Blending. Image mode: lossless gain=1.0; Video mode: gain=1.0 + aspect-ratio-aware Lanczos4 upscaling + audio remux. Zero blurring, 100% texture preservation. Invoke when user wants to clean Gemini watermarks from any file."
---

# Gemini 无痕去水印与高保真超分技能 (gemini-watermark-remover-pro)

本技能用于自动化去除 Google Gemini / Veo 生成内容右下角的半透明四角星品牌水印，**同时支持图片与视频**，基于纯代数反向 Alpha 混合数学逆解体系（Pure Reverse Alpha Blending），无损还原底层纹理，零模糊、零涂抹。

## 适用场景 (When to Invoke)

- 用户提到“去除 Gemini 视频水印”、“把 Gemini 视频右下角星星去掉”、“清理视频水印”、“去除 Veo 水印”。
- 用户提到“去除 Gemini 图片水印”、“图片右下角星星去掉”、“清理图片水印”。
- 从 Gemini / Veo 下载了带水印的**图片（png/jpg/webp/bmp/tif）或视频（mp4）**，需要纯净素材用于后期。
- 用户要求去水印达到“纯图片级”高保真质感，杜绝任何毛玻璃模糊或漫水涂抹痕迹。
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
```

脚本会自动根据输入文件扩展名分流：图片扩展名（png/jpg/jpeg/webp/bmp/tif/tiff/jfif/gif）走图片引擎，其余按视频引擎处理。

## 读者公众号技术分享建议

1. **痛点切入**：Gemini 生成的内容动作自然逼真，但右下角星星水印影响商用质感；剪映等常规涂抹工具会导致画面边缘模糊变形。
2. **技术亮点**：图片去水印不靠“猜测填补”，而是用数学上精确的反向 Alpha 混合逆解（$original = \frac{watermarked - \alpha \times 255}{1 - \alpha}$），把透明星形底下的真实纹理逐像素“提”回来，图片/视频全程零模糊。
3. **开箱即用**：同一套脚本既可处理图片又可处理视频，Windows 下把文件拖到 `run_windows.bat` 上即可一键完成。